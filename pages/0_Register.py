import logging

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from database.session import get_session, initialize_database
from components.theme import apply_theme, render_page_header
from services.registration_service import RegistrationService
from utils.ui_messages import error_card, info_card, success_card

logger = logging.getLogger(__name__)

apply_theme()

render_page_header(
    "Create an account",
    "Request access to the Government Knowledge & Policy Assistant.",
)
with st.container(border=True):
    info_card(
        "Approval required",
        "New accounts remain inactive until an administrator approves them and "
        "assigns a role. You cannot select your own role or access documents while pending."
    )

with st.container(border=True):
    with st.form("registration-form", clear_on_submit=True):
        display_name = st.text_input("Full name", max_chars=200)
        email = st.text_input("Email", max_chars=320, autocomplete="email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Request account", type="primary")

if submitted:
    if password != confirm_password:
        error_card("Passwords do not match", "Enter the same password in both fields.")
    else:
        try:
            initialize_database()
            with get_session() as session:
                RegistrationService().register(
                    session,
                    email=email,
                    display_name=display_name,
                    password=password,
                )
            success_card(
                "Registration received",
                "An administrator must approve your account and assign a role before you can sign in or access documents.",
            )
        except ValueError as exc:
            error_card("Registration not completed", str(exc))
        except SQLAlchemyError as exc:
            logger.exception("Could not save an account registration: %s", exc)
            error_card(
                "Registration temporarily unavailable",
                "We could not save your request right now. Please try again later or contact a system administrator.",
            )

st.markdown("[Back to sign in](/)")
