import logging

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.loading_indicator import loading_indicator
from components.theme import render_page_header
from database.session import get_session
from models.document import DocumentLifecycleStatus
from services.auth_service import AuthService
from services.document_service import DocumentService
from services.qdrant_service import VectorStoreError
from utils.session_auth import get_session_user
from utils.ui_messages import error_card, success_card

logger = logging.getLogger(__name__)

render_page_header(
    "Upload Document",
    "Add an approved PDF or DOCX policy document to the knowledge repository.",
)

try:
    with get_session() as session:
        auth = AuthService()
        current_user = get_session_user(session)
        allowed_classifications = auth.allowed_classifications(current_user)
except PermissionError:
    error_card(
        "Access Restricted",
        "You do not have permission to upload documents.",
        ["Required Role: An active, approved account"],
    )
    st.stop()
except SQLAlchemyError as exc:
    logger.exception("Could not initialize the document upload page: %s", exc)
    error_card(
        "Upload temporarily unavailable",
        "We could not connect to the document service. Please try again later.",
    )
    st.stop()

with st.container(border=True):
    st.markdown("### Supported formats")
    st.write("PDF and DOCX · Maximum file size: **20 MB**")

with st.container(border=True):
    with st.form("upload-document-form"):
        uploaded_file = st.file_uploader(
            "Select a PDF or DOCX file",
            type=["pdf", "docx"],
            accept_multiple_files=False,
            max_upload_size=20,
            help="Maximum file size is 20 MB.",
        )
        document_title = st.text_input("Document title", max_chars=500)
        version_number = st.number_input(
            "Version number",
            min_value=1,
            step=1,
            value=1,
        )
        classification = st.selectbox(
            "Classification",
            options=allowed_classifications,
            format_func=lambda value: value.value.title(),
        )
        lifecycle_status = st.selectbox(
            "Version status",
            options=[
                DocumentLifecycleStatus.DRAFT,
                DocumentLifecycleStatus.CURRENT,
            ],
            format_func=lambda value: value.value.title(),
            help="Uploading a version as Current supersedes the existing Current version.",
        )
        submitted = st.form_submit_button("Upload and index", type="primary")

if submitted:
    if uploaded_file is None:
        error_card("Select a document", "Choose a PDF or DOCX file to continue.")
        st.stop()
    if not document_title.strip():
        error_card("Document title required", "Enter a title for this document.")
        st.stop()

    try:
        with loading_indicator("Processing and indexing your document...") as status:
            with get_session() as session:
                version = DocumentService(session).upload(
                    content=uploaded_file.getvalue(),
                    filename=uploaded_file.name,
                    title=document_title,
                    version_number=int(version_number),
                    classification=classification,
                    user_id=current_user.id,
                    lifecycle_status=lifecycle_status,
                )
            status.update(
                label="Document processed and indexed",
                state="complete",
                expanded=False,
            )
        success_card("Document uploaded successfully", document_title.strip())
        success_card("Document processed successfully", "Text was extracted from the file.")
        success_card("Embeddings generated successfully", "Search vectors were created.")
        success_card(
            "Indexed into knowledge base",
            f"Version {version.version_number} is {version.lifecycle_status.value}.",
        )
    except PermissionError:
        required_role = {
            "public": "Citizen",
            "internal": "Government Officer",
            "restricted": "Department Manager",
            "confidential": "Administrator",
        }[classification.value]
        error_card(
            "Access Restricted",
            "You do not have permission to upload documents with this classification.",
            [f"Required Role: {required_role}"],
        )
    except ValueError as exc:
        error_card("Upload needs attention", str(exc))
    except VectorStoreError:
        error_card(
            "Document saved but not indexed",
            "The document could not be added to search right now. Please try again later or contact a system administrator.",
        )
    except (SQLAlchemyError, RuntimeError, OSError) as exc:
        logger.exception("Document upload failed: %s", exc)
        error_card(
            "Upload could not be completed",
            "We could not process this document right now. Please verify the file and try again.",
        )
