from models.chat import ChatRequest, ChatResponse


class RAGService:
    def answer(self, request: ChatRequest) -> ChatResponse:
        """Return a source-grounded response; implementation is pending."""
        raise NotImplementedError
