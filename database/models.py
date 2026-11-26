from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.access import DocumentClassification, UserRole
from models.document import DocumentLifecycleStatus


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    auth_subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_type: [item.value for item in enum_type],
        )
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DocumentORM(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("owner_id", "title", name="uq_documents_owner_title"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(500))
    filename: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(200))
    classification: Mapped[DocumentClassification] = mapped_column(
        SqlEnum(
            DocumentClassification,
            name="document_classification",
            values_callable=lambda enum_type: [item.value for item in enum_type],
        ),
        index=True,
    )
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    versions: Mapped[list["DocumentVersionORM"]] = relationship(
        back_populates="document"
    )


class DocumentVersionORM(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "version_number", name="uq_document_versions_number"
        ),
        CheckConstraint(
            "lifecycle_status IN ('draft', 'current', 'superseded')",
            name="ck_document_versions_lifecycle_status",
        ),
        Index(
            "uq_document_versions_one_current",
            "document_id",
            unique=True,
            postgresql_where=text("lifecycle_status = 'current'"),
            sqlite_where=text("lifecycle_status = 'current'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(128))
    source_file_key: Mapped[str] = mapped_column(String(1000))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    index_status: Mapped[str] = mapped_column(String(20), default="pending")
    lifecycle_status: Mapped[str] = mapped_column(
        String(20),
        default=DocumentLifecycleStatus.CURRENT.value,
        server_default=text("'current'"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    document: Mapped["DocumentORM"] = relationship(back_populates="versions")
    chunks: Mapped[list["DocumentChunkORM"]] = relationship(
        back_populates="document_version"
    )


class DocumentChunkORM(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id", "chunk_index", name="uq_document_chunks_index"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    document_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_versions.id"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    vector_point_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_version: Mapped["DocumentVersionORM"] = relationship(
        back_populates="chunks"
    )


class AuditEventORM(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(120), index=True)
    resource_type: Mapped[str] = mapped_column(String(120))
    resource_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
