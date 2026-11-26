from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from models.access import DocumentClassification


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    filename: str
    mime_type: str
    classification: DocumentClassification
    owner_id: UUID
    created_at: datetime


class DocumentVersion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    version_number: int
    filename: str
    checksum: str
    created_by: UUID
    created_at: datetime
    index_status: str


class DocumentChunk(BaseModel):
    id: UUID
    document_id: UUID
    document_version_id: UUID
    chunk_index: int
    text: str
    page_number: int | None = None
    vector_point_id: str | None = None
