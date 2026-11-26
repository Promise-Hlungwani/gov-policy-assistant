import logging

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.metric_card import metric_card
from components.theme import render_page_header
from components.status_badge import status_badge
from database.session import get_session
from services.document_library_service import DashboardService
from utils.session_auth import format_user_role, get_session_user
from utils.ui_messages import error_card, info_card

logger = logging.getLogger(__name__)

render_page_header(
    "Home",
    "A role-aware overview of your approved policy knowledge workspace.",
)

try:
    with get_session() as session:
        current_user = get_session_user(session)
        metrics = DashboardService(session).metrics(user_id=current_user.id)
except PermissionError:
    error_card(
        "Access Restricted",
        "You do not have permission to access this information.",
        ["Required Role: An active, approved account"],
    )
    st.stop()
except SQLAlchemyError as exc:
    logger.exception("Could not load dashboard metrics: %s", exc)
    error_card(
        "Dashboard temporarily unavailable",
        "We could not load workspace metrics. Please try again later.",
    )
    st.stop()

with st.container(border=True):
    st.markdown(f"### Welcome, {current_user.display_name}")
    st.write("Your assigned access:")
    status_badge(format_user_role(current_user.role), "neutral")

cards = st.columns(4, gap="medium")
with cards[0]:
    metric_card("Authorized documents", metrics["total_documents"], "📚")
with cards[1]:
    metric_card("Current versions", metrics["current_versions"], "✓")
with cards[2]:
    metric_card("Questions asked", metrics["questions_asked"], "💬")
with cards[3]:
    metric_card("Audit logs", metrics["audit_logs"], "🔎")

st.subheader("Get started")
action_columns = st.columns(3, gap="medium")
with action_columns[0]:
    with st.container(border=True):
        st.markdown("#### Ask a policy question")
        st.caption("Get grounded answers with document, version, and section citations.")
        st.page_link("pages/2_Chat_Assistant.py", label="Open Chat Assistant")
with action_columns[1]:
    with st.container(border=True):
        st.markdown("#### Browse documents")
        st.caption("Search authorized policy documents and review their lifecycle status.")
        st.page_link("pages/3_Document_Library.py", label="Open Document Library")
with action_columns[2]:
    with st.container(border=True):
        st.markdown("#### Add approved knowledge")
        st.caption("Upload a PDF or DOCX policy document for processing and indexing.")
        st.page_link("pages/1_Upload_Documents.py", label="Upload a document")

if metrics["total_documents"] == 0:
    info_card(
        "Your repository is getting started",
        "No documents are available to your role yet. Ask a document owner or administrator to add approved sources.",
        ["Upload a policy document", "Contact your administrator"],
    )
