from models.chat import SourceCitation
from models.document import DocumentChunk


def build_citations(chunks: list[DocumentChunk]) -> list[SourceCitation]:
    raise NotImplementedError
