import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

from models.access import UserRole
from models.chat import ChatRequest
from models.document import DocumentChunk
from services.rag_service import FALLBACK_ANSWER, RAGService


class FakeSession:
    def begin(self):
        return nullcontext()


class FakeAuthService:
    def __init__(self, user) -> None:
        self.user = user

    def get_user_for_subject(self, session, auth_subject):
        return self.user


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


def make_chunk(similarity: float = 0.9) -> DocumentChunk:
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
        return RAGService(
            FakeSession(),
            auth_service=FakeAuthService(self.user),
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

    def test_returns_document_version_section_and_valid_citation(self) -> None:
        service = self.build_service([make_chunk()])

        response = service.answer(
            ChatRequest(question="When does eligibility begin?"),
            auth_subject="trusted-subject",
        )

        self.assertEqual(response.answer, "Supported answer [1]")
        self.assertEqual(response.citations[0].document_filename, "benefits-policy.pdf")
        self.assertEqual(response.citations[0].version_number, 3)
        self.assertEqual(response.citations[0].section_title, "Eligibility")
        self.assertIn("benefits-policy.pdf", self.llm.calls[0][1])
        self.assertIn("Section: Eligibility", self.llm.calls[0][1])

    def test_rejects_answer_with_unknown_citation(self) -> None:
        service = self.build_service([make_chunk()], answer="Unsupported claim [99]")

        response = service.answer(
            ChatRequest(question="When does eligibility begin?"),
            auth_subject="trusted-subject",
        )

        self.assertEqual(response.answer, FALLBACK_ANSWER)
        self.assertEqual(response.citations, [])


if __name__ == "__main__":
    unittest.main()
