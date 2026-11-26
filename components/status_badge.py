from html import escape

import streamlit as st

_BADGE_CLASSES = {
    "current": "badge-current",
    "draft": "badge-draft",
    "superseded": "badge-superseded",
    "public": "badge-public",
    "internal": "badge-internal",
    "restricted": "badge-restricted",
    "confidential": "badge-confidential",
    "success": "badge-success",
    "warning": "badge-warning",
    "danger": "badge-danger",
    "neutral": "badge-neutral",
    "high": "badge-high",
    "medium": "badge-medium",
    "low": "badge-low",
}


def status_badge(label: str, variant: str | None = None) -> None:
    text = getattr(label, "value", label)
    key = (variant or str(text)).lower().replace(" ", "_")
    css_class = _BADGE_CLASSES.get(key, "badge-neutral")
    safe_text = escape(str(text).replace("_", " ").title())
    st.markdown(
        f'<span class="status-badge {css_class}" role="status">{safe_text}</span>',
        unsafe_allow_html=True,
    )
