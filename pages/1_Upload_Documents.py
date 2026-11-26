import logging

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from database.session import get_session, initialize_database
from models.document import DocumentLifecycleStatus
from services.auth_service import AuthService
from services.document_service import DocumentService
from services.qdrant_service import VectorStoreError

logger = logging.getLogger(__name__)

st.title("Upload Documents")
st.caption("Upload and index a policy document. Access is controlled by your assigned role.")

if not st.user.is_logged_in:
    st.info("Sign in with your organization account to upload a document.")
    if st.button("Sign in"):
        st.login()
    st.stop()

auth_subject = st.user.get("sub")
if not auth_subject:
    st.error("Access denied: the identity provider did not return a user subject.")
    st.stop()

try:
    initialize_database()
    with get_session() as session:
        auth = AuthService()
        current_user = auth.get_user_for_subject(session, auth_subject)
        allowed_classifications = auth.allowed_classifications(current_user)
except PermissionError as exc:
    st.error(f"Access denied: {exc}")
    st.stop()
except SQLAlchemyError as exc:
    logger.exception("Could not initialize the document upload page: %s", exc)
    st.error("The PostgreSQL database is unavailable. Check the server logs.")
    st.stop()

st.caption(
    f"Signed in as {current_user.display_name} · "
    f"{current_user.role.value.replace('_', ' ').title()}"
)

with st.form("upload-document-form"):
    uploaded_file = st.file_uploader(
        "Select a PDF or DOCX file",
        type=["pdf", "docx"],
        accept_multiple_files=False,
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
        st.error("Choose a PDF or DOCX file to upload.")
        st.stop()
    if not document_title.strip():
        st.error("Enter a document title.")
        st.stop()

    try:
        with st.spinner("Extracting text, saving metadata, and indexing passages..."):
            with get_session() as session:
                version = DocumentService(session).upload(
                    content=uploaded_file.getvalue(),
                    filename=uploaded_file.name,
                    title=document_title,
                    version_number=int(version_number),
                    classification=classification,
                    auth_subject=auth_subject,
                    lifecycle_status=lifecycle_status,
                )
        st.success(
            f"Uploaded **{document_title.strip()}**, version "
            f"**{version.version_number}** ({version.index_status}, "
            f"{version.lifecycle_status.value})."
        )
    except PermissionError as exc:
        st.error(f"Access denied: {exc}")
    except ValueError as exc:
        st.error(str(exc))
    except VectorStoreError:
        st.error(
            "Document metadata was saved, but Qdrant indexing failed. "
            "Check the Qdrant configuration and server logs."
        )
    except (SQLAlchemyError, RuntimeError, OSError) as exc:
        logger.exception("Document upload failed: %s", exc)
        st.error("Upload processing failed. Check the application server logs.")
