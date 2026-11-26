from models.chat import SourceCitation
from models.document import DocumentChunk


def build_citations(chunks: list[DocumentChunk]) -> list[SourceCitation]:
    citations = []
    for citation_id, chunk in enumerate(chunks, start=1):
        title = chunk.document_title or chunk.document_filename or "Policy document"
        filename = chunk.document_filename or title
        version_number = chunk.version_number
        section_title = chunk.section_title or (
            f"Page {chunk.page_number}" if chunk.page_number else "Document body"
        )
        citations.append(
            SourceCitation(
                citation_id=citation_id,
                document_id=chunk.document_id,
                document_version_id=chunk.document_version_id,
                document_title=title,
                document_filename=filename,
                version_number=version_number,
                section_title=section_title,
                page_number=chunk.page_number,
                chunk_id=chunk.id,
                excerpt=chunk.text,
                similarity=chunk.similarity or 0.0,
            )
        )
    return citations
