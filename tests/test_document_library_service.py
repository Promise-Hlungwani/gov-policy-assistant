import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.base import Base
from database.models import DocumentORM, DocumentVersionORM, UserORM
from models.access import DocumentClassification, UserRole
from models.document import DocumentLifecycleStatus
from services.document_library_service import (
    DashboardService,
    DocumentLibraryService,
)


class DocumentLibraryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)

        citizen = UserORM(
            id=uuid4(),
            auth_subject="local:citizen@example.gov",
            email="citizen@example.gov",
            display_name="Citizen",
            password_hash=None,
            role=UserRole.CITIZEN,
            is_active=True,
        )
        officer = UserORM(
            id=uuid4(),
            auth_subject="local:officer@example.gov",
            email="officer@example.gov",
            display_name="Officer",
            password_hash=None,
            role=UserRole.GOVERNMENT_OFFICER,
            is_active=True,
        )
        self.session.add_all([citizen, officer])
        self.session.flush()
        self.citizen_id = citizen.id
        self.officer_id = officer.id

        self._add_document(
            owner_id=officer.id,
            title="Public Benefits",
            classification=DocumentClassification.PUBLIC,
            version_number=2,
            status=DocumentLifecycleStatus.CURRENT,
        )
        self._add_document(
            owner_id=officer.id,
            title="Internal Procedure",
            classification=DocumentClassification.INTERNAL,
            version_number=1,
            status=DocumentLifecycleStatus.DRAFT,
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def _add_document(
        self,
        *,
        owner_id,
        title,
        classification,
        version_number,
        status,
    ) -> None:
        document_id = uuid4()
        document = DocumentORM(
            id=document_id,
            title=title,
            filename=f"{title.lower().replace(' ', '-')}.pdf",
            mime_type="application/pdf",
            classification=classification,
            owner_id=owner_id,
        )
        self.session.add(document)
        self.session.flush()
        self.session.add(
            DocumentVersionORM(
                id=uuid4(),
                document_id=document_id,
                version_number=version_number,
                filename=document.filename,
                checksum=f"checksum-{version_number}-{title}",
                source_file_key=document.filename,
                created_by=owner_id,
                index_status="indexed",
                lifecycle_status=status.value,
            )
        )

    def test_library_scopes_documents_to_authorized_classifications(self) -> None:
        service = DocumentLibraryService(self.session)

        citizen_items, citizen_total = service.list_items(user_id=self.citizen_id)
        officer_items, officer_total = service.list_items(user_id=self.officer_id)

        self.assertEqual(citizen_total, 1)
        self.assertEqual([item.title for item in citizen_items], ["Public Benefits"])
        self.assertEqual(officer_total, 2)

    def test_library_filters_status_and_search(self) -> None:
        service = DocumentLibraryService(self.session)

        items, total = service.list_items(
            user_id=self.officer_id,
            search="procedure",
            lifecycle_status=DocumentLifecycleStatus.DRAFT,
        )

        self.assertEqual(total, 1)
        self.assertEqual(items[0].title, "Internal Procedure")

    def test_dashboard_metrics_respect_user_role_scope(self) -> None:
        metrics = DashboardService(self.session).metrics(user_id=self.citizen_id)

        self.assertEqual(metrics["total_documents"], 1)
        self.assertEqual(metrics["current_versions"], 1)
        self.assertEqual(metrics["questions_asked"], 0)
        self.assertEqual(metrics["audit_logs"], 0)

    def test_citizen_cannot_filter_to_internal_classification(self) -> None:
        with self.assertRaises(PermissionError):
            DocumentLibraryService(self.session).list_items(
                user_id=self.citizen_id,
                classification=DocumentClassification.INTERNAL,
            )


if __name__ == "__main__":
    unittest.main()
