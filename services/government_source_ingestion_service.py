import logging
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx

from config.settings import settings
from models.access import DocumentClassification
from models.document import KnowledgeSourceType
from services.embedding_service import EmbeddingService
from services.parser_service import DocumentParser
from services.qdrant_service import (
    GOVERNMENT_REPOSITORY_COLLECTION_NAME,
    GOVERNMENT_WEB_COLLECTION_NAME,
    QdrantService,
)
from utils.chunking import chunk_pages

logger = logging.getLogger(__name__)
_SUPPORTED_LOCAL_EXTENSIONS = {".pdf", ".docx"}
_MAX_SOURCE_BYTES = 8 * 1024 * 1024
_MAX_PAGES_PER_SITE = 20
_MAX_REDIRECTS = 3


class _PageTextParser(HTMLParser):
    _SKIPPED_TAGS = {"script", "style", "noscript", "svg", "nav", "footer"}
    _BLOCK_TAGS = {
        "article",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "li",
        "p",
        "section",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self._SKIPPED_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in self._BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in self._BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if not value:
            return
        if self._in_title:
            self.title_parts.append(value)
        if not self._skip_depth:
            self.text_parts.append(value)

    def result(self) -> tuple[str, str]:
        title = " ".join(self.title_parts).strip()
        text = " ".join(self.text_parts).strip()
        return title, text


class GovernmentSourceIngestionService:
    def __init__(
        self,
        *,
        parser: DocumentParser | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: QdrantService | None = None,
        approved_urls: tuple[str, ...] | None = None,
        max_pages_per_site: int = _MAX_PAGES_PER_SITE,
    ) -> None:
        self.parser = parser or DocumentParser()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or QdrantService()
        self.approved_urls = (
            settings.government_website_urls
            if approved_urls is None
            else approved_urls
        )
        self.max_pages_per_site = max_pages_per_site
        self._client = httpx.Client(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=False,
            headers={"User-Agent": "GovPolicyAssistantKnowledgeIndexer/1.0"},
        )

    def close(self) -> None:
        self._client.close()

    def ingest_repository_directory(self, directory: Path) -> int:
        root = directory.resolve()
        if not root.exists():
            return 0
        if not root.is_dir():
            raise ValueError("Government repository path must be a directory.")
        indexed = 0
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _SUPPORTED_LOCAL_EXTENSIONS:
                continue
            resolved_path = path.resolve()
            if root not in resolved_path.parents:
                logger.warning("Skipped repository file outside its configured root.")
                continue
            try:
                content = resolved_path.read_bytes()
            except OSError:
                logger.exception("Could not read repository file %s", resolved_path.name)
                continue
            if len(content) > 50 * 1024 * 1024:
                logger.warning("Skipped oversized repository file %s", resolved_path.name)
                continue
            try:
                parsed_pages = self.parser.parse_file(resolved_path.name, content)
            except (OSError, RuntimeError, ValueError):
                logger.exception("Could not parse repository file %s", resolved_path.name)
                continue
            source_uri = "repo://" + resolved_path.relative_to(root).as_posix()
            title = resolved_path.stem.replace("_", " ").replace("-", " ")
            pages = [
                (page.page_number, page.section_title, page.text)
                for page in parsed_pages
                if page.text.strip()
            ]
            if self._index_pages(
                source_uri=source_uri,
                title=title,
                filename=resolved_path.name,
                pages=pages,
                source_type=KnowledgeSourceType.GOVERNMENT_REPOSITORY,
                collection_name=GOVERNMENT_REPOSITORY_COLLECTION_NAME,
            ):
                indexed += 1
        return indexed

    def sync_approved_websites(self) -> int:
        indexed = 0
        seen_hosts: dict[str, set[str]] = {}
        for configured_url in self.approved_urls:
            try:
                self._validate_approved_url(configured_url)
            except ValueError:
                logger.warning("Skipped an invalid approved government website URL.")
                continue
            parsed = urlparse(configured_url)
            host_key = parsed.hostname or ""
            if host_key not in seen_hosts:
                seen_hosts[host_key] = set()
                site_urls = self._site_urls(configured_url)
            else:
                site_urls = [configured_url]
            for source_url in site_urls:
                if len(seen_hosts[host_key]) >= self.max_pages_per_site:
                    break
                if source_url in seen_hosts[host_key]:
                    continue
                seen_hosts[host_key].add(source_url)
                source = self._fetch_source(source_url)
                if source is None:
                    continue
                title, filename, pages = source
                if self._index_pages(
                    source_uri=source_url,
                    title=title,
                    filename=filename,
                    pages=pages,
                    source_type=KnowledgeSourceType.GOVERNMENT_WEBSITE,
                    collection_name=GOVERNMENT_WEB_COLLECTION_NAME,
                ):
                    indexed += 1
        return indexed

    def _site_urls(self, base_url: str) -> list[str]:
        parsed = urlparse(base_url)
        root_url = f"{parsed.scheme}://{parsed.netloc}/"
        sitemap_url = urljoin(root_url, "sitemap.xml")
        sitemap_response = self._fetch_bytes(sitemap_url)
        discovered: list[str] = [base_url]
        if sitemap_response is not None:
            content_type, payload = sitemap_response
            if "xml" in content_type or payload.lstrip().startswith(b"<?xml"):
                sitemap_urls = self._parse_sitemap(payload)
                for nested_sitemap in sitemap_urls:
                    if (
                        "sitemap" not in nested_sitemap.lower()
                        and not nested_sitemap.lower().endswith(
                            (".xml", ".xml.gz")
                        )
                    ):
                        discovered.append(nested_sitemap)
                        continue
                    nested_response = self._fetch_bytes(nested_sitemap)
                    if nested_response is not None:
                        discovered.extend(
                            self._parse_sitemap(nested_response[1])
                        )
        allowed = []
        seen = set()
        for candidate in discovered:
            try:
                self._validate_approved_url(candidate)
            except ValueError:
                continue
            normalized = candidate.split("#", 1)[0]
            if normalized not in seen:
                seen.add(normalized)
                allowed.append(normalized)
            if len(allowed) >= self.max_pages_per_site:
                break
        return allowed

    @staticmethod
    def _parse_sitemap(payload: bytes) -> list[str]:
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return []
        urls = []
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] == "loc" and element.text:
                urls.append(element.text.strip())
        return urls

    def _validate_approved_url(self, url: str) -> None:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme.lower() != "https"
            or not host
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise ValueError("Government source URLs must use approved HTTPS hosts.")
        allowed_hosts = set()
        for approved in self.approved_urls:
            approved_parsed = urlparse(approved)
            approved_host = (approved_parsed.hostname or "").lower()
            if approved_host:
                allowed_hosts.add(approved_host)
                if approved_host.startswith("www."):
                    allowed_hosts.add(approved_host[4:])
        if host not in allowed_hosts:
            raise ValueError("Government source host is not approved.")

    def _fetch_bytes(self, url: str) -> tuple[str, bytes] | None:
        current_url = url
        for _ in range(_MAX_REDIRECTS + 1):
            try:
                self._validate_approved_url(current_url)
                with self._client.stream("GET", current_url) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            return None
                        current_url = urljoin(current_url, location)
                        continue
                    if response.status_code >= 400:
                        logger.info(
                            "Government source returned HTTP %s: %s",
                            response.status_code,
                            current_url,
                        )
                        return None
                    content_type = response.headers.get("content-type", "").lower()
                    body = bytearray()
                    for part in response.iter_bytes():
                        body.extend(part)
                        if len(body) > _MAX_SOURCE_BYTES:
                            logger.warning(
                                "Skipped oversized government source %s",
                                current_url,
                            )
                            return None
                    return content_type, bytes(body)
            except (httpx.HTTPError, ValueError) as exc:
                logger.info("Could not fetch approved source %s: %s", current_url, exc)
                return None
        logger.warning("Stopped a government source redirect loop at %s", url)
        return None

    def _fetch_source(
        self,
        url: str,
    ) -> tuple[str, str, list[tuple[int | None, str | None, str]]] | None:
        fetched = self._fetch_bytes(url)
        if fetched is None:
            return None
        content_type, payload = fetched
        if not payload:
            return None
        filename = Path(urlparse(url).path).name or "government-web-page"
        if "pdf" in content_type or urlparse(url).path.lower().endswith(".pdf"):
            try:
                parsed_pages = self.parser.parse_pdf(payload)
            except (OSError, RuntimeError, ValueError):
                logger.exception("Could not parse official PDF source %s", url)
                return None
            pages = [
                (page.page_number, page.section_title, page.text)
                for page in parsed_pages
                if page.text.strip()
            ]
            return Path(filename).stem, filename, pages
        if "html" not in content_type and b"<html" not in payload[:2048].lower():
            return None
        page_parser = _PageTextParser()
        page_parser.feed(payload.decode("utf-8", errors="replace"))
        title, text = page_parser.result()
        if not text:
            return None
        return title or url, filename, [(None, title or "Web page", text)]

    def _index_pages(
        self,
        *,
        source_uri: str,
        title: str,
        filename: str,
        pages: list[tuple[int | None, str | None, str]],
        source_type: KnowledgeSourceType,
        collection_name: str,
    ) -> bool:
        pages = [page for page in pages if page[2].strip()]
        if not pages:
            return False
        document_id = uuid5(NAMESPACE_URL, source_uri)
        version_id = uuid5(document_id, "approved-public-source")
        chunks = chunk_pages(document_id, version_id, pages)
        if not chunks:
            return False
        chunks = [
            chunk.model_copy(
                update={
                    "id": uuid5(version_id, f"{chunk.chunk_index}:{chunk.text}"),
                    "source_type": source_type,
                    "source_url": source_uri,
                }
            )
            for chunk in chunks
        ]
        try:
            vectors = self.embedding_service.embed_documents(chunks)
            self.vector_store.delete_public_source(collection_name, source_uri)
            self.vector_store.upsert_chunks(
                chunks,
                vectors,
                classification=DocumentClassification.PUBLIC,
                document_title=title,
                document_filename=filename,
                version_number=None,
                collection_name=collection_name,
                source_type=source_type,
                source_url=source_uri,
            )
        except (RuntimeError, OSError, ValueError):
            logger.exception("Could not index approved source %s", source_uri)
            return False
        logger.info(
            "Indexed %d chunks from approved source %s",
            len(chunks),
            source_uri,
        )
        return True
