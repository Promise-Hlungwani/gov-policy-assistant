from uuid import UUID, uuid4

from models.document import DocumentChunk


def chunk_pages(
    document_id: UUID,
    document_version_id: UUID,
    pages: list[tuple[int | None, str | None, str]],
    *,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[DocumentChunk]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Chunk size must be positive and overlap smaller than chunk size.")

    chunks: list[DocumentChunk] = []
    for page_number, section_title, page_text in pages:
        text = " ".join(page_text.split())
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start, end)
                if boundary > start:
                    end = boundary
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    DocumentChunk(
                        id=uuid4(),
                        document_id=document_id,
                        document_version_id=document_version_id,
                        chunk_index=len(chunks),
                        text=chunk_text,
                        page_number=page_number,
                        section_title=section_title,
                    )
                )
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
    return chunks
