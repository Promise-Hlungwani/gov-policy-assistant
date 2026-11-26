import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from models.access import UserRole
from models.document import KnowledgeSourceType
from services.qdrant_service import (
    GOVERNMENT_WEB_COLLECTION_NAME,
    UPLOADED_COLLECTION_NAME,
    QdrantService,
)


class FakeQdrantClient:
    def __init__(self, points=None) -> None:
        self.points = points or []
        self.searches = []

    def collection_exists(self, collection_name):
        return True

    def query_points(self, **kwargs):
        self.searches.append(kwargs)
        return SimpleNamespace(points=self.points)


class QdrantMultiCollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user = SimpleNamespace(role=UserRole.CITIZEN, is_active=True)

    def test_uploaded_collection_search_is_role_classification_filtered(self) -> None:
        client = FakeQdrantClient()

        with patch("services.qdrant_service._client", return_value=client):
            QdrantService().search([0.1, 0.2], user=self.user, limit=3)

        self.assertEqual(client.searches[0]["collection_name"], UPLOADED_COLLECTION_NAME)
        classification_filter = client.searches[0]["query_filter"]
        allowed_values = classification_filter.must[0].match.any
        self.assertEqual(allowed_values, ["public"])

    def test_government_web_search_is_separate_and_unfiltered_by_classification(
        self,
    ) -> None:
        client = FakeQdrantClient()

        with patch("services.qdrant_service._client", return_value=client):
            QdrantService().search_government_web_sources(
                [0.1, 0.2],
                user=self.user,
                limit=3,
            )

        self.assertEqual(
            client.searches[0]["collection_name"],
            GOVERNMENT_WEB_COLLECTION_NAME,
        )
        self.assertIsNone(client.searches[0]["query_filter"])

    def test_web_collection_citations_keep_source_type_and_url(self) -> None:
        chunk_id = uuid4()
        document_id = uuid4()
        version_id = uuid4()
        point = SimpleNamespace(
            id=str(chunk_id),
            score=0.87,
            payload={
                "chunk_id": str(chunk_id),
                "document_id": str(document_id),
                "document_version_id": str(version_id),
                "chunk_index": 0,
                "text": "Public sector policy excerpt",
                "classification": "public",
                "source_type": KnowledgeSourceType.GOVERNMENT_WEBSITE.value,
                "source_url": "https://www.gov.za/documents/policy",
                "document_title": "Policy",
                "document_filename": "policy",
            },
        )
        client = FakeQdrantClient([point])

        with patch("services.qdrant_service._client", return_value=client):
            results = QdrantService().search_government_web_sources(
                [0.1, 0.2],
                user=self.user,
                limit=3,
            )

        self.assertEqual(results[0].source_type, KnowledgeSourceType.GOVERNMENT_WEBSITE)
        self.assertEqual(results[0].source_url, "https://www.gov.za/documents/policy")

    def test_public_sources_require_an_active_user(self) -> None:
        inactive_user = SimpleNamespace(is_active=False)

        with self.assertRaises(PermissionError):
            QdrantService().search_government_repository(
                [0.1, 0.2],
                user=inactive_user,
            )


if __name__ == "__main__":
    unittest.main()
