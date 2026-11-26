import logging
from datetime import datetime

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.chat_message import chat_message
from components.error_card import info_card, warning_card
from components.loading_indicator import loading_indicator
from components.source_card import source_card
from components.status_badge import status_badge
from components.theme import render_page_header
from database.session import get_session
from models.chat import ChatRequest, SourceCitation
from models.document import KnowledgeSourceType
from services.rag_service import FALLBACK_ANSWER, RAGService, RAGServiceError
from utils.session_auth import get_session_user
from utils.ui_messages import error_card

logger = logging.getLogger(__name__)
NO_ANSWER = FALLBACK_ANSWER
RETRIEVAL_SUGGESTIONS = [
    "Rephrase your question",
    "Check document permissions",
    "Upload additional documents",
    "Contact the document owner",
]

render_page_header(
    "Chat Assistant",
    "Ask a policy question and receive a grounded answer with approved source citations.",
)

try:
    with get_session() as session:
        current_user = get_session_user(session)
except SQLAlchemyError as exc:
    logger.exception("Could not initialize the chat page: %s", exc)
    error_card(
        "Chat temporarily unavailable",
        "We could not connect to the policy assistant. Please try again later.",
    )
    st.stop()
except PermissionError:
    error_card(
        "Access Restricted",
        "You do not have permission to access the chat assistant.",
        ["Required Role: An active, approved account"],
    )
    st.stop()

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


def _confidence(citations: list[dict]) -> str:
    if not citations:
        return "Low"
    score = sum(float(item.get("similarity", 0.0)) for item in citations) / len(
        citations
    )
    if score >= 0.7:
        return "High"
    return "Medium"


def _render_sources(citations: list[dict]) -> None:
    st.markdown("#### Sources Used")
    parsed_citations = [
        SourceCitation.model_validate(citation) for citation in citations
    ]
    if not parsed_citations:
        st.caption("No approved source was found for this response.")
        return
    for citation in parsed_citations:
        source_card(citation)


def _render_sources_searched(message: dict) -> None:
    sources = message.get("sources_searched", [])
    if not sources:
        return
    unavailable = set(message.get("unavailable_sources", []))
    st.markdown("#### Sources Searched")
    for source_value in sources:
        source_type = KnowledgeSourceType(source_value)
        if source_value in unavailable:
            status_badge(f"{source_type.label} · Unavailable", "warning")
        else:
            status_badge(f"{source_type.label} · Searched", "success")


def _render_assistant_details(message: dict) -> None:
    answer = message["content"]
    if answer == FALLBACK_ANSWER:
        info_card(
            "Information Not Found",
            NO_ANSWER,
            RETRIEVAL_SUGGESTIONS,
        )

    _render_sources(message.get("citations", []))
    _render_sources_searched(message)
    confidence = message.get(
        "confidence",
        _confidence(message.get("citations", [])),
    )
    st.markdown("#### Confidence")
    status_badge(confidence, confidence.lower())
    st.caption(
        "Confidence reflects source retrieval similarity, not a guarantee of factual completeness."
    )
    warnings = message.get("warnings", [])
    if warnings:
        st.markdown("#### Version Warning")
        for warning in warnings:
            warning_card("Version notice", warning)


with st.container(height=600, autoscroll=True):
    if not st.session_state.chat_messages:
        info_card(
            "Ask about government policy",
            "Questions search documents your role can access, then the public government repository and approved government websites.",
            ["Try legislation, public-service rules, or policy procedures"],
        )
    for message in st.session_state.chat_messages:
        timestamp = message.get("timestamp", "")
        bubble_content = message["content"]
        if message["role"] == "assistant":
            bubble_content = f"Answer\n{bubble_content}"
        chat_message(message["role"], bubble_content, timestamp)
        if message["role"] == "assistant":
            _render_assistant_details(message)

question = st.chat_input(
    "Ask a question about approved policy documents",
    max_chars=4000,
)
if question:
    timestamp = datetime.now().astimezone().strftime("%d %b %Y, %H:%M")
    st.session_state.chat_messages.append(
        {"role": "user", "content": question, "timestamp": timestamp}
    )
    status = loading_indicator(
        "Searching uploaded documents...",
        expanded=True,
    )
    try:
        with get_session() as session:
            response = RAGService(session).answer(
                ChatRequest(question=question),
                user_id=current_user.id,
                progress_callback=lambda stage: status.update(label=stage),
            )
        citations = [
            citation.model_dump(mode="json") for citation in response.citations
        ]
        status.update(
            label="Trusted response ready",
            state="complete",
            expanded=False,
        )
        st.session_state.chat_messages.append(
            {
                "role": "assistant",
                "content": response.answer or FALLBACK_ANSWER,
                "citations": citations,
                "warnings": response.warnings,
                "confidence": _confidence(citations),
                "sources_searched": [
                    source.value for source in response.sources_searched
                ],
                "unavailable_sources": [
                    source.value for source in response.unavailable_sources
                ],
                "timestamp": datetime.now().astimezone().strftime(
                    "%d %b %Y, %H:%M"
                ),
            }
        )
        st.rerun()
    except PermissionError:
        status.update(label="Access could not be verified", state="error")
        error_card(
            "Access Restricted",
            "You do not have permission to access this information.",
            ["Required Role: An authorized role for the document classification"],
        )
    except ValueError as exc:
        status.update(label="Question needs attention", state="error")
        error_card("Question not submitted", str(exc))
    except RAGServiceError:
        status.update(label="Response unavailable", state="error")
        error_card(
            "Unable to retrieve an answer",
            "If relevant information exists in the available government knowledge sources, I was unable to retrieve it at this time. Please try again or contact a system administrator.",
        )
    except (SQLAlchemyError, RuntimeError, OSError) as exc:
        logger.exception("Policy RAG request failed: %s", exc)
        status.update(label="Response unavailable", state="error")
        error_card(
            "Unable to retrieve an answer",
            "If relevant information exists in the available government knowledge sources, I was unable to retrieve it at this time. Please try again or contact a system administrator.",
        )
