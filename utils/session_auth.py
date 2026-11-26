from uuid import UUID

import streamlit as st
from sqlalchemy.orm import Session

from database.models import UserORM
from models.access import UserRole
from services.auth_service import ACCESS_DENIED_MESSAGE, AuthService


def get_session_user(session: Session) -> UserORM:
    raw_user_id = st.session_state.get("authenticated_user_id")
    try:
        user_id = UUID(str(raw_user_id))
    except (TypeError, ValueError) as exc:
        raise PermissionError(ACCESS_DENIED_MESSAGE) from exc
    return AuthService().get_active_user(session, user_id)


def format_user_role(role: UserRole) -> str:
    return role.value.replace("_", " ").title()
