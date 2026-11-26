from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: UUID | None = None


class SourceCitation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    document_version_id: UUID
    document_title: str
    version_number: int
    page_number: int | None = None
    chunk_id: UUID
    excerpt: str


class ChatResponse(BaseModel):
    conversation_id: UUID | None = None
    answer: str
    citations: list[SourceCitation] = Field(default_factory=list)
