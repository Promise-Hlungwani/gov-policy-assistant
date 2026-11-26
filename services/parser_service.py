from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile

import fitz
from docx import Document
from docx.opc.exceptions import PackageNotFoundError


@dataclass(frozen=True)
class ParsedPage:
    page_number: int | None
    text: str


class DocumentParser:
    def parse_pdf(self, content: bytes) -> list[ParsedPage]:
        try:
            document = fitz.open(stream=content, filetype="pdf")
        except fitz.FileDataError as exc:
            raise ValueError("The uploaded PDF file is invalid or corrupted.") from exc
        try:
            if document.needs_pass:
                raise ValueError("Password-protected PDF files are not supported.")
            return [
                ParsedPage(page_number=index + 1, text=page.get_text("text"))
                for index, page in enumerate(document)
            ]
        finally:
            document.close()

    def parse_docx(self, content: bytes) -> list[ParsedPage]:
        try:
            document = Document(BytesIO(content))
        except (PackageNotFoundError, BadZipFile) as exc:
            raise ValueError("The uploaded DOCX file is invalid or corrupted.") from exc
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            parts.extend(
                " ".join(cell.text for cell in row.cells) for row in table.rows
            )
        return [ParsedPage(page_number=None, text="\n".join(parts))]

    def parse_file(self, filename: str, content: bytes) -> list[ParsedPage]:
        extension = Path(filename).suffix.lower()
        if extension == ".pdf":
            return self.parse_pdf(content)
        if extension == ".docx":
            return self.parse_docx(content)
        raise ValueError("Upload a PDF or DOCX document.")
