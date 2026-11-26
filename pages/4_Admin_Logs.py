import logging
from datetime import datetime, time, timedelta, timezone

import pandas as pd
import streamlit as st
from sqlalchemy import String, cast, desc, or_, select
from sqlalchemy.exc import SQLAlchemyError

from components.theme import render_page_header
from database.models import AuditEventORM, UserORM
from database.session import get_session
from models.access import UserRole
from services.registration_service import RegistrationService
from utils.session_auth import format_user_role, get_session_user
from utils.ui_messages import error_card, info_card, success_card

logger = logging.getLogger(__name__)

render_page_header(
    "Administration & Audit Logs",
    "Review access activity and manage pending account requests.",
)

try:
    with get_session() as session:
        current_user = get_session_user(session)
except PermissionError:
    error_card(
        "Access Restricted",
        "You do not have permission to access administration tools.",
        ["Required Role: Administrator"],
    )
    st.stop()
except SQLAlchemyError as exc:
    logger.exception("Could not validate administrator session: %s", exc)
    error_card(
        "Administration temporarily unavailable",
        "We could not verify your account. Please try again later.",
    )
    st.stop()

if current_user.role != UserRole.ADMINISTRATOR:
    error_card(
        "Access Restricted",
        "You do not have permission to access administration tools.",
        ["Required Role: Administrator"],
    )
    st.stop()

st.subheader("Audit activity")
with st.container(border=True):
    with st.form("audit-filters"):
        audit_search = st.text_input(
            "Search audit logs",
            placeholder="Search users, questions, answers, or documents",
        )
        filter_columns = st.columns(3)
        with filter_columns[0]:
            role_filter = st.selectbox(
                "Role",
                options=[None, *list(UserRole)],
                format_func=lambda value: (
                    "All roles" if value is None else format_user_role(value)
                ),
            )
        with filter_columns[1]:
            date_range = st.date_input(
                "Date range",
                value=(
                    datetime.now(timezone.utc).date() - timedelta(days=30),
                    datetime.now(timezone.utc).date(),
                ),
            )
        st.form_submit_button("Apply filters", type="primary")

try:
    conditions = []
    if role_filter is not None:
        conditions.append(UserORM.role == role_filter)
    if isinstance(date_range, (tuple, list)):
        selected_dates = [value for value in date_range if value is not None]
    elif date_range is not None:
        selected_dates = [date_range]
    else:
        selected_dates = []
    if selected_dates:
        start_date, end_date = selected_dates[0], selected_dates[-1]
        if start_date > end_date:
            error_card("Invalid date range", "The start date must be before the end date.")
            st.stop()
        conditions.extend(
            [
                AuditEventORM.created_at
                >= datetime.combine(start_date, time.min, tzinfo=timezone.utc),
                AuditEventORM.created_at
                < datetime.combine(
                    end_date + timedelta(days=1),
                    time.min,
                    tzinfo=timezone.utc,
                ),
            ]
        )
    if audit_search.strip():
        pattern = f"%{audit_search.strip()}%"
        conditions.append(
            or_(
                UserORM.email.ilike(pattern),
                UserORM.display_name.ilike(pattern),
                cast(AuditEventORM.details, String).ilike(pattern),
            )
        )

    with get_session() as session:
        audit_rows = session.execute(
            select(AuditEventORM, UserORM)
            .outerjoin(UserORM, AuditEventORM.actor_id == UserORM.id)
            .where(*conditions)
            .order_by(desc(AuditEventORM.created_at))
            .limit(500)
        ).all()
except SQLAlchemyError as exc:
    logger.exception("Could not load audit log records: %s", exc)
    error_card(
        "Audit logs temporarily unavailable",
        "We could not load audit activity. Please try again later.",
    )
    audit_rows = []

if audit_rows:
    records = []
    for event, actor in audit_rows:
        details = event.details or {}
        role_name = details.get("role") or (
            format_user_role(actor.role) if actor is not None else "System"
        )
        question = details.get("question", "")
        accessed_docs = details.get("documents_accessed", [])
        if accessed_docs:
            documents_used = "; ".join(
                "{} (v{}){}".format(
                    item.get("title") or item.get("name") or "Policy document",
                    item.get("version_number") or "unknown",
                    f", {item['lifecycle_status']}" if item.get("lifecycle_status") else "",
                )
                for item in accessed_docs
            )
        else:
            documents_used = details.get("title", event.resource_type.replace("_", " "))
        created_at = event.created_at
        if created_at is not None and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        records.append(
            {
                "Timestamp": (
                    created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                    if created_at
                    else ""
                ),
                "User": actor.email if actor is not None else "System",
                "Role": role_name.replace("_", " ").title(),
                "Question": question or event.action.replace(".", " ").title(),
                "Documents Used": documents_used,
            }
        )
    st.dataframe(
        pd.DataFrame(records),
        use_container_width=True,
        hide_index=True,
        height=420,
    )
    if len(audit_rows) == 500:
        st.caption("Showing the 500 most recent matching audit events.")
else:
    info_card(
        "No audit activity found",
        "No audit records match the selected date range and filters.",
        ["Adjust the search term", "Expand the date range"],
    )

st.divider()
st.subheader("Pending account requests")
try:
    with get_session() as session:
        pending_users = RegistrationService().list_pending(session)
except SQLAlchemyError as exc:
    logger.exception("Could not load pending account requests: %s", exc)
    error_card(
        "Account requests unavailable",
        "We could not load pending account requests. Please try again later.",
    )
    pending_users = []

if not pending_users:
    info_card("All caught up", "There are no accounts waiting for approval.")

for pending_user in pending_users:
    with st.container(border=True):
        st.markdown(f"**{pending_user.display_name}** · {pending_user.email}")
        with st.form(f"approve-account-{pending_user.id}"):
            role = st.selectbox(
                "Assign role",
                options=list(UserRole),
                format_func=format_user_role,
                key=f"pending-role-{pending_user.id}",
            )
            approve_submitted = st.form_submit_button("Approve account")

        if approve_submitted:
            try:
                with get_session() as session:
                    RegistrationService().approve(
                        session,
                        user_id=pending_user.id,
                        role=role,
                        approver_id=current_user.id,
                    )
                st.session_state["account_approval_notice"] = (
                    f"Approved {pending_user.email}."
                )
                st.rerun()
            except PermissionError:
                error_card(
                    "Access Restricted",
                    "You are not authorized to approve this account.",
                    ["Required Role: Administrator"],
                )
            except ValueError as exc:
                info_card("Approval not completed", str(exc))
            except SQLAlchemyError as exc:
                logger.exception(
                    "Could not approve account %s: %s",
                    pending_user.id,
                    exc,
                )
                error_card(
                    "Approval temporarily unavailable",
                    "The account could not be approved. Please try again later.",
                )

approval_notice = st.session_state.pop("account_approval_notice", None)
if approval_notice:
    success_card("Account approved", approval_notice)
