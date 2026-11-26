from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
from statistics import median
from zipfile import BadZipFile

import fitz
from docx import Document
from docx.opc.exceptions import PackageNotFoundError


@dataclass(frozen=True)
class ParsedPage:
    page_number: int | None
    text: str
    section_title: str | None = None


class DocumentParser:
    @staticmethod
    def _pdf_heading(page: fitz.Page) -> str | None:
        page_data = page.get_text("dict")
        lines: list[tuple[float, str]] = []
        font_sizes = []
        for block in page_data.get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = " ".join(span.get("text", "").strip() for span in spans).strip()
                if not text:
                    continue
                size = max((span.get("size", 0.0) for span in spans), default=0.0)
                lines.append((size, text))
                font_sizes.extend(
                    span.get("size", 0.0)
                    for span in spans
                    if span.get("text", "").strip()
                )

        if font_sizes:
            body_size = median(font_sizes)
            for size, text in lines:
                if size >= body_size * 1.2 and 3 <= len(text) <= 160:
                    return text

        for _, text in lines:
            if re.match(r"^\d+(?:\.\d+)*\.?\s+\S", text) or (
                len(text) <= 120 and text.isupper() and len(text.split()) >= 2
            ):
                return text
        return None

    def parse_pdf(self, content: bytes) -> list[ParsedPage]:
        try:
            document = fitz.open(stream=content, filetype="pdf")
        except fitz.FileDataError as exc:
            raise ValueError("The uploaded PDF file is invalid or corrupted.") from exc
        try:
            if document.needs_pass:
                raise ValueError("Password-protected PDF files are not supported.")
            pages = []
            active_section = None
            for index, page in enumerate(document):
                heading = self._pdf_heading(page)
                if heading:
                    active_section = heading
                page_number = index + 1
                pages.append(
                    ParsedPage(
                        page_number=page_number,
                        text=page.get_text("text"),
                        section_title=active_section or f"Page {page_number}",
                    )
                )
            return pages
        finally:
            document.close()

    def parse_docx(self, content: bytes) -> list[ParsedPage]:
        try:
            document = Document(BytesIO(content))
        except (PackageNotFoundError, BadZipFile) as exc:
            raise ValueError("The uploaded DOCX file is invalid or corrupted.") from exc
        sections: list[ParsedPage] = []
        current_title = "Document body"
        current_parts: list[str] = []

        def finish_section() -> None:
            text = "\n".join(part for part in current_parts if part.strip()).strip()
            if text:
                sections.append(
                    ParsedPage(
                        page_number=None,
                        text=text,
                        section_title=current_title,
                    )
                )

        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            style_name = paragraph.style.name if paragraph.style else ""
            if text and style_name.lower().startswith("heading"):
                finish_section()
                current_parts.clear()
                current_title = text[:500]
            elif text:
                current_parts.append(text)

        for table in document.tables:
            current_parts.extend(
                " ".join(cell.text.strip() for cell in row.cells).strip()
                for row in table.rows
            )
        finish_section()
        return sections

    def parse_file(self, filename: str, content: bytes) -> list[ParsedPage]:
        extension = Path(filename).suffix.lower()
        if extension == ".pdf":
            return self.parse_pdf(content)
        if extension == ".docx":
            return self.parse_docx(content)
        raise ValueError("Upload a PDF or DOCX document.")
