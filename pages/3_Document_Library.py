import logging
import math

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.status_badge import status_badge
from components.theme import render_page_header
from database.session import get_session
from models.access import DocumentClassification
from models.document import DocumentLifecycleStatus
from services.auth_service import AuthService
from services.document_library_service import DocumentLibraryService
from utils.session_auth import get_session_user
from utils.ui_messages import error_card, info_card

logger = logging.getLogger(__name__)
PAGE_SIZE = 12

render_page_header(
    "Document Library",
    "Search and review the policy documents your assigned role is authorized to access.",
)

try:
    with get_session() as session:
        current_user = get_session_user(session)
        allowed_classifications = AuthService().allowed_classifications(current_user)
        library = DocumentLibraryService(session)
        available_versions = library.available_versions(user_id=current_user.id)
except PermissionError:
    error_card(
        "Access Restricted",
        "You do not have permission to access this document library.",
        ["Required Role: An active, approved account"],
    )
    st.stop()
except SQLAlchemyError as exc:
    logger.exception("Could not initialize the document library: %s", exc)
    error_card(
        "Document library unavailable",
        "We could not load the document library. Please try again later.",
    )
    st.stop()

if "library_page" not in st.session_state:
    st.session_state["library_page"] = 1

with st.container(border=True):
    with st.form("library-filters"):
        search_value = st.text_input(
            "Search documents",
            placeholder="Search by document title or filename",
            key="library_search",
        )
        filters = st.columns(3)
        with filters[0]:
            classification_options = [None, *allowed_classifications]
            selected_classification = st.selectbox(
                "Classification",
                options=classification_options,
                format_func=lambda value: (
                    "All classifications" if value is None else value.value.title()
                ),
                key="library_classification",
            )
        with filters[1]:
            status_options = [None, *list(DocumentLifecycleStatus)]
            selected_status = st.selectbox(
                "Status",
                options=status_options,
                format_func=lambda value: (
                    "All statuses" if value is None else value.value.title()
                ),
                key="library_status",
            )
        with filters[2]:
            version_options = [None, *available_versions]
            selected_version = st.selectbox(
                "Version",
                options=version_options,
                format_func=lambda value: "All versions" if value is None else str(value),
                key="library_version",
            )
        filters_submitted = st.form_submit_button("Apply filters", type="primary")

if filters_submitted:
    st.session_state["library_page"] = 1

page_number = st.session_state["library_page"]
try:
    with get_session() as session:
        items, total = DocumentLibraryService(session).list_items(
            user_id=current_user.id,
            search=search_value,
            classification=selected_classification,
            lifecycle_status=selected_status,
            version_number=selected_version,
            page=page_number,
            page_size=PAGE_SIZE,
        )
except PermissionError:
    error_card(
        "Access Restricted",
        "You do not have permission to view documents with the selected classification.",
        ["Required Role: An authorized role for this classification"],
    )
    st.stop()
except SQLAlchemyError as exc:
    logger.exception("Could not search the document library: %s", exc)
    error_card(
        "Search temporarily unavailable",
        "We could not retrieve document results. Please try again later.",
    )
    st.stop()

total_pages = max(1, math.ceil(total / PAGE_SIZE))
if page_number > total_pages:
    st.session_state["library_page"] = total_pages
    st.rerun()

st.caption(f"{total} document version{'s' if total != 1 else ''} found")
if not items:
    info_card(
        "No documents found",
        "No authorized documents match these filters.",
        ["Try a different search term", "Clear one or more filters"],
    )
else:
    for item in items:
        with st.container(border=True):
            title_column, badges_column = st.columns([3, 2], vertical_alignment="center")
            with title_column:
                st.markdown(f"### {item.title}")
                st.caption(
                    f"{item.filename} · Version {item.version_number}"
                )
            with badges_column:
                status_badge(item.classification.value, item.classification.value)
                status_badge(
                    item.lifecycle_status.value,
                    item.lifecycle_status.value,
                )
                status_badge(
                    item.index_status,
                    "success" if item.index_status == "indexed" else "warning",
                )
            st.caption(
                f"Added {item.created_at.strftime('%d %b %Y, %H:%M UTC')}"
            )

if total_pages > 1:
    left, center, right = st.columns([1, 2, 1])
    with left:
        if st.button("← Previous", disabled=page_number <= 1):
            st.session_state["library_page"] = page_number - 1
            st.rerun()
    with center:
        st.markdown(
            f"<div style='text-align:center;padding:.5rem'>"
            f"Page {page_number} of {total_pages}</div>",
            unsafe_allow_html=True,
        )
    with right:
        if st.button("Next →", disabled=page_number >= total_pages):
            st.session_state["library_page"] = page_number + 1
            st.rerun()
