import logging

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from database.session import get_session, initialize_database
from models.chat import ChatRequest
from services.rag_service import FALLBACK_ANSWER, RAGService, RAGServiceError

logger = logging.getLogger(__name__)

st.title("Chat Assistant")
st.caption(
    "Answers are limited to documents authorized for your role and include source citations."
)

if not st.user.is_logged_in:
    st.info("Sign in with your organization account to ask policy questions.")
    if st.button("Sign in"):
        st.login()
    st.stop()

auth_subject = st.user.get("sub")
if not auth_subject:
    st.error("Access denied: the identity provider did not return a user subject.")
    st.stop()

try:
    initialize_database()
except SQLAlchemyError as exc:
    logger.exception("Could not initialize the chat page: %s", exc)
    st.error("The PostgreSQL database is unavailable. Check the server logs.")
    st.stop()

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


def _show_sources(citations: list[dict]) -> None:
    if not citations:
        return
    with st.expander("Sources used"):
        for citation in citations:
            page = (
                f", page {citation['page_number']}"
                if citation.get("page_number") is not None
                else ""
            )
            version = citation.get("version_number") or "unknown"
            lifecycle_status = citation["lifecycle_status"].replace("_", " ").title()
            st.markdown(
                f"**[{citation['citation_id']}] {citation['document_title']}**  \n"
                f"{citation['document_filename']} · "
                f"Version {version} · {lifecycle_status} · "
                f"Section: {citation['section_title']}{page}"
            )
            st.caption(citation["excerpt"])


for message in st.session_state.chat_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            for warning in message.get("warnings", []):
                st.warning(warning)
            _show_sources(message.get("citations", []))

question = st.chat_input("Ask a question about approved policy documents")
if question:
    st.session_state.chat_messages.append(
        {"role": "user", "content": question}
    )
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching authorized documents and preparing an answer..."):
            try:
                with get_session() as session:
                    response = RAGService(session).answer(
                        ChatRequest(question=question),
                        auth_subject=auth_subject,
                    )
                st.markdown(response.answer)
                for warning in response.warnings:
                    st.warning(warning)
                citations = [
                    citation.model_dump(mode="json")
                    for citation in response.citations
                ]
                _show_sources(citations)
                st.session_state.chat_messages.append(
                    {
                        "role": "assistant",
                        "content": response.answer or FALLBACK_ANSWER,
                        "citations": citations,
                        "warnings": response.warnings,
                    }
                )
            except PermissionError as exc:
                st.error(f"Access denied: {exc}")
            except ValueError as exc:
                st.error(str(exc))
            except RAGServiceError:
                st.error(
                    "Could not answer from the approved document repository. "
                    "Check server logs."
                )
            except (SQLAlchemyError, RuntimeError, OSError) as exc:
                logger.exception("Policy RAG request failed: %s", exc)
                st.error(
                    "Could not answer from the approved document repository. "
                    "Check server logs."
                )
