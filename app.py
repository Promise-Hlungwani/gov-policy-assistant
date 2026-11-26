import logging

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from database.session import get_session, initialize_database
from models.access import UserRole
from services.auth_service import (
    AccountPendingError,
    AuthService,
    ROLE_CLASSIFICATIONS,
)
from components.status_badge import status_badge
from components.theme import apply_theme, render_page_header
from utils.logging_config import configure_logging
from utils.session_auth import format_user_role, get_session_user
from utils.ui_messages import error_card, info_card

configure_logging()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Government Knowledge & Policy Assistant",
    page_icon="📚",
    layout="wide",
)
apply_theme()

_ROLE_DESCRIPTIONS = {
    UserRole.CITIZEN: "Find public-facing policies and government information.",
    UserRole.GOVERNMENT_OFFICER: "Work with public and internal departmental guidance.",
    UserRole.DEPARTMENT_MANAGER: "Access public, internal, and restricted material.",
    UserRole.ADMINISTRATOR: "Manage the platform and access all classifications.",
}


def _show_login() -> None:
    render_page_header(
        "Trusted answers from approved government documents",
        "Sign in with an approved account. New accounts require administrator approval.",
    )

    login_column, roles_column = st.columns([1, 1.15], gap="large")
    with login_column:
        with st.container(border=True):
            st.subheader("Sign in")
            with st.form("login-form", clear_on_submit=True):
                email = st.text_input("Email", autocomplete="username")
                password = st.text_input(
                    "Password",
                    type="password",
                    autocomplete="current-password",
                )
                submitted = st.form_submit_button("Sign in", type="primary")
            st.page_link("pages/0_Register.py", label="Create an account")

    with roles_column:
        st.subheader("Access by role")
        st.caption("Role access is assigned by an administrator—not selected at sign-in.")
        role_columns = st.columns(2, gap="small")
        for index, role in enumerate(UserRole):
            with role_columns[index % 2]:
                with st.container(border=True):
                    st.markdown(f"**{format_user_role(role)}**")
                    st.caption(_ROLE_DESCRIPTIONS[role])
                    for classification in sorted(
                        ROLE_CLASSIFICATIONS[role], key=lambda item: item.value
                    ):
                        status_badge(classification.value, classification.value)

    if not submitted:
        return
    if not email.strip() or not password:
        error_card("Sign-in details required", "Enter your email and password.")
        return

    try:
        initialize_database()
        with get_session() as session:
            user = AuthService().authenticate(session, email, password)
    except AccountPendingError as exc:
        info_card("Account awaiting approval", str(exc))
        return
    except SQLAlchemyError as exc:
        logger.exception("Could not authenticate user against PostgreSQL: %s", exc)
        error_card(
            "Sign-in temporarily unavailable",
            "We could not verify your account right now. Please try again later or contact a system administrator.",
        )
        return

    if user is None:
        error_card("Sign-in failed", "The email or password is not correct.")
        return

    user_id = user.id
    st.session_state.clear()
    st.session_state["authenticated_user_id"] = str(user_id)
    st.rerun()


current_user = None
raw_user_id = st.session_state.get("authenticated_user_id")
if raw_user_id is not None:
    try:
        with get_session() as session:
            current_user = get_session_user(session)
    except PermissionError:
        st.session_state.clear()
        info_card(
            "Access Restricted",
            "Your account is inactive or is not authorized to sign in. Contact a system administrator.",
        )
    except SQLAlchemyError as exc:
        logger.exception("Could not validate the signed-in user: %s", exc)
        error_card(
            "Service temporarily unavailable",
            "Your session cannot be verified right now. Please try again later.",
        )
        st.stop()

if current_user is None:
    public_pages = [
        st.Page(_show_login, title="Sign in", icon="🔐", default=True),
        st.Page("pages/0_Register.py", title="Create an account", icon="📝"),
    ]
    st.navigation(public_pages).run()
    st.stop()

with st.sidebar:
    st.markdown(
        '<div class="gov-brand"><div class="gov-brand-title">'
        "Government Knowledge &amp; Policy Assistant</div>"
        '<div class="gov-brand-tagline">Trusted answers from approved government documents</div></div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Signed in as {current_user.display_name}")
    status_badge(format_user_role(current_user.role), "neutral")
    if st.button("Sign out"):
        st.session_state.clear()
        st.rerun()

pages = [
    st.Page("pages/0_Home.py", title="Home", icon="🏛️"),
    st.Page("pages/1_Upload_Documents.py", title="Upload Documents", icon="📤"),
    st.Page(
        "pages/2_Chat_Assistant.py",
        title="Chat Assistant",
        icon="💬",
        default=True,
    ),
    st.Page("pages/3_Document_Library.py", title="Document Library", icon="📚"),
]
if current_user.role == UserRole.ADMINISTRATOR:
    pages.append(
        st.Page("pages/4_Admin_Logs.py", title="Admin & Audit Logs", icon="🔐")
    )

st.navigation(pages).run()
