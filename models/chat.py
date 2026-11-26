from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: UUID | None = None


class SourceCitation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    citation_id: int
    document_id: UUID
    document_version_id: UUID
    document_title: str
    document_filename: str
    version_number: int | None
    section_title: str
    page_number: int | None = None
    chunk_id: UUID
    excerpt: str
    similarity: float


class ChatResponse(BaseModel):
    conversation_id: UUID | None = None
    answer: str
    citations: list[SourceCitation] = Field(default_factory=list)
