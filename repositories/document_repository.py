from typing import Protocol
from uuid import UUID

from models.access import UserRole
from models.document import DocumentMetadata, DocumentVersion


class DocumentRepository(Protocol):
    def add(self, document: DocumentMetadata) -> DocumentMetadata: ...

    def get_by_id(self, document_id: UUID) -> DocumentMetadata | None: ...

    def list_authorized(
        self,
        user_id: UUID,
        role: UserRole,
        limit: int,
        offset: int,
    ) -> list[DocumentMetadata]: ...

    def add_version(self, version: DocumentVersion) -> DocumentVersion: ...

    def list_versions(self, document_id: UUID) -> list[DocumentVersion]: ...
