import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

from database.models import AuditEventORM
from models.access import UserRole
from models.chat import ChatRequest
from models.document import DocumentChunk, DocumentLifecycleStatus
from services.audit_service import AuditService
from services.rag_service import FALLBACK_ANSWER, RAGService


class FakeSession:
    def __init__(self) -> None:
        self.added = []

    def begin(self):
        return nullcontext()

    def add(self, event) -> None:
        self.added.append(event)


class FakeAuthService:
    def __init__(self, user) -> None:
        self.user = user

    def get_user_for_subject(self, session, auth_subject):
        return self.user


class FakeAuditService:
    def __init__(self) -> None:
        self.events = []

    def record_chat(self, **event) -> None:
        self.events.append(event)


class FakeDocumentRepository:
    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self.statuses = {
            chunk.document_version_id: chunk.lifecycle_status for chunk in chunks
        }

    def get_version_statuses(self, version_ids):
        return {
            version_id: self.statuses[version_id]
            for version_id in version_ids
            if version_id in self.statuses
        }


class FakeEmbeddingService:
    def embed_query(self, query: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class FakeVectorStore:
    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self.chunks = chunks
        self.searched_as = None

    def search(self, query_vector, *, user, limit):
        self.searched_as = user
        return self.chunks


class FakeLLMService:
    def __init__(self, answer: str) -> None:
        self.answer_text = answer
        self.calls = []

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.answer_text


def make_chunk(
    similarity: float = 0.9,
    lifecycle_status: DocumentLifecycleStatus = DocumentLifecycleStatus.CURRENT,
) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        document_id=uuid4(),
        document_version_id=uuid4(),
        chunk_index=0,
        text="Policy benefits begin on the effective date.",
        page_number=4,
        section_title="Eligibility",
        document_title="Benefits Policy",
        document_filename="benefits-policy.pdf",
        version_number=3,
        lifecycle_status=lifecycle_status,
        similarity=similarity,
    )


class RAGServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user = SimpleNamespace(
            id=uuid4(),
            role=UserRole.GOVERNMENT_OFFICER,
            is_active=True,
        )

    def build_service(self, chunks, answer="Supported answer [1]"):
        self.vector_store = FakeVectorStore(chunks)
        self.llm = FakeLLMService(answer)
        self.audit = FakeAuditService()
        return RAGService(
            FakeSession(),
            auth_service=FakeAuthService(self.user),
            audit_service=self.audit,
            document_repository=FakeDocumentRepository(chunks),
            embedding_service=FakeEmbeddingService(),
            vector_store=self.vector_store,
            llm_service=self.llm,
            minimum_similarity=0.35,
            top_k=5,
        )

    def test_returns_exact_fallback_without_sources(self) -> None:
        service = self.build_service([])

        response = service.answer(
            ChatRequest(question="When does eligibility begin?"),
            auth_subject="trusted-subject",
        )

        self.assertEqual(
            response.answer,
            "I could not find this information in the approved document repository.",
        )
        self.assertEqual(response.citations, [])
        self.assertEqual(self.llm.calls, [])
        self.assertIs(self.vector_store.searched_as, self.user)
        self.assertEqual(len(self.audit.events), 1)
        event = self.audit.events[0]
        self.assertEqual(event["actor_id"], self.user.id)
        self.assertEqual(event["role"], self.user.role)
        self.assertEqual(event["question"], "When does eligibility begin?")
        self.assertEqual(
            event["answer"],
            "I could not find this information in the approved document repository.",
        )
        self.assertEqual(event["documents_accessed"], [])

    def test_returns_fallback_when_source_confidence_is_low(self) -> None:
        service = self.build_service([make_chunk(similarity=0.2)])

        response = service.answer(
            ChatRequest(question="When does eligibility begin?"),
            auth_subject="trusted-subject",
        )

        self.assertEqual(
            response.answer,
            "I could not find this information in the approved document repository.",
        )
        self.assertEqual(self.llm.calls, [])
        self.assertEqual(self.audit.events[0]["documents_accessed"], [])

    def test_returns_document_version_section_and_valid_citation(self) -> None:
        service = self.build_service([make_chunk()])

        response = service.answer(
            ChatRequest(question="When does eligibility begin?"),
            auth_subject="trusted-subject",
        )

        self.assertEqual(response.answer, "Supported answer [1]")
        self.assertEqual(response.citations[0].document_filename, "benefits-policy.pdf")
        self.assertEqual(response.citations[0].version_number, 3)
        self.assertEqual(
            response.citations[0].lifecycle_status,
            DocumentLifecycleStatus.CURRENT,
        )
        self.assertEqual(response.citations[0].section_title, "Eligibility")
        self.assertIn("benefits-policy.pdf", self.llm.calls[0][1])
        self.assertIn("Section: Eligibility", self.llm.calls[0][1])
        self.assertEqual(len(self.audit.events), 1)
        self.assertEqual(
            self.audit.events[0]["documents_accessed"],
            [
                {
                    "document_id": str(response.citations[0].document_id),
                    "document_version_id": str(
                        response.citations[0].document_version_id
                    ),
                    "name": "benefits-policy.pdf",
                    "title": "Benefits Policy",
                    "version_number": 3,
                    "lifecycle_status": "current",
                    "sections": [{"section": "Eligibility", "page": 4}],
                }
            ],
        )
        self.assertEqual(response.warnings, [])

    def test_rejects_answer_with_unknown_citation(self) -> None:
        service = self.build_service([make_chunk()], answer="Unsupported claim [99]")

        response = service.answer(
            ChatRequest(question="When does eligibility begin?"),
            auth_subject="trusted-subject",
        )

        self.assertEqual(response.answer, FALLBACK_ANSWER)
        self.assertEqual(response.citations, [])
        self.assertEqual(len(self.audit.events), 1)
        self.assertEqual(len(self.audit.events[0]["documents_accessed"]), 1)

    def test_prioritizes_current_sources_over_higher_scoring_drafts(self) -> None:
        current = make_chunk(
            similarity=0.5,
            lifecycle_status=DocumentLifecycleStatus.CURRENT,
        )
        draft = make_chunk(
            similarity=0.95,
            lifecycle_status=DocumentLifecycleStatus.DRAFT,
        )
        service = self.build_service([draft, current])

        response = service.answer(
            ChatRequest(question="When does eligibility begin?"),
            auth_subject="trusted-subject",
        )

        self.assertEqual(
            response.citations[0].lifecycle_status,
            DocumentLifecycleStatus.CURRENT,
        )
        self.assertEqual(response.warnings, [])

    def test_warns_when_answer_uses_draft_and_superseded_versions(self) -> None:
        draft = make_chunk(lifecycle_status=DocumentLifecycleStatus.DRAFT)
        superseded = make_chunk(
            lifecycle_status=DocumentLifecycleStatus.SUPERSEDED
        )
        service = self.build_service(
            [draft, superseded],
            answer="Draft claim [1]. Older policy claim [2].",
        )

        response = service.answer(
            ChatRequest(question="Summarize the available rules."),
            auth_subject="trusted-subject",
        )

        self.assertEqual(len(response.warnings), 2)
        self.assertIn("draft document", response.warnings[0])
        self.assertIn("superseded document", response.warnings[1])
        self.assertEqual(
            [citation.lifecycle_status for citation in response.citations],
            [
                DocumentLifecycleStatus.DRAFT,
                DocumentLifecycleStatus.SUPERSEDED,
            ],
        )


class ChatAuditTests(unittest.TestCase):
    def test_records_chat_fields_in_postgres_audit_event(self) -> None:
        session = FakeSession()
        service = AuditService(session)
        actor_id = uuid4()
        conversation_id = uuid4()
        documents_accessed = [
            {
                "document_id": str(uuid4()),
                "document_version_id": str(uuid4()),
                "name": "benefits-policy.pdf",
                "version_number": 3,
                "sections": [{"section": "Eligibility", "page": 4}],
            }
        ]

        service.record_chat(
            actor_id=actor_id,
            role=UserRole.GOVERNMENT_OFFICER,
            question="When does eligibility begin?",
            answer="It begins on the effective date [1].",
            documents_accessed=documents_accessed,
            conversation_id=conversation_id,
            warnings=["Draft source warning"],
        )

        event = session.added[0]
        self.assertIsInstance(event, AuditEventORM)
        self.assertEqual(event.actor_id, actor_id)
        self.assertEqual(event.action, "chat.answered")
        self.assertEqual(event.resource_id, conversation_id)
        self.assertEqual(
            event.details,
            {
                "role": "government_officer",
                "question": "When does eligibility begin?",
                "answer": "It begins on the effective date [1].",
                "documents_accessed": documents_accessed,
                "warnings": ["Draft source warning"],
            },
        )
        self.assertIsNotNone(AuditEventORM.__table__.c.created_at.server_default)


if __name__ == "__main__":
    unittest.main()
