from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from models.access import DocumentClassification


class DocumentLifecycleStatus(str, Enum):
    DRAFT = "draft"
    CURRENT = "current"
    SUPERSEDED = "superseded"


class KnowledgeSourceType(str, Enum):
    UPLOADED_DOCUMENT = "uploaded_document"
    GOVERNMENT_REPOSITORY = "government_repository"
    GOVERNMENT_WEBSITE = "government_website"

    @property
    def label(self) -> str:
        return {
            KnowledgeSourceType.UPLOADED_DOCUMENT: "Uploaded Document",
            KnowledgeSourceType.GOVERNMENT_REPOSITORY: "Government Repository",
            KnowledgeSourceType.GOVERNMENT_WEBSITE: "Government Website",
        }[self]


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
    lifecycle_status: DocumentLifecycleStatus


class DocumentLibraryItem(BaseModel):
    document_id: UUID
    title: str
    filename: str
    classification: DocumentClassification
    version_id: UUID
    version_number: int
    lifecycle_status: DocumentLifecycleStatus
    index_status: str
    created_at: datetime


class DocumentChunk(BaseModel):
    id: UUID
    document_id: UUID
    document_version_id: UUID
    chunk_index: int
    text: str
    page_number: int | None = None
    section_title: str | None = None
    vector_point_id: str | None = None
    document_title: str | None = None
    document_filename: str | None = None
    version_number: int | None = None
    classification: DocumentClassification = DocumentClassification.PUBLIC
    lifecycle_status: DocumentLifecycleStatus = DocumentLifecycleStatus.CURRENT
    source_type: KnowledgeSourceType = KnowledgeSourceType.UPLOADED_DOCUMENT
    source_url: str | None = None
    similarity: float | None = None
