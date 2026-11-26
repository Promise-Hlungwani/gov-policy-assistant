from html import escape

import streamlit as st

_CALL_OUTS = {
    "error": ("Access Restricted", "callout-error"),
    "info": ("Information", ""),
    "success": ("Success", "callout-success"),
    "warning": ("Please note", "callout-warning"),
}


def callout_card(
    kind: str,
    title: str,
    message: str,
    suggestions: list[str] | None = None,
) -> None:
    callout_class = _CALL_OUTS.get(kind, _CALL_OUTS["info"])[1]
    suggestion_html = ""
    if suggestions:
        suggestion_html = "<ul>" + "".join(
            f"<li>{escape(item)}</li>" for item in suggestions
        ) + "</ul>"
    st.markdown(
        (
            f'<section class="callout {callout_class}" role="status" aria-live="polite">'
            f'<div class="callout-title">{escape(title)}</div>'
            f'<div class="callout-body">{escape(message)}</div>'
            f"{suggestion_html}"
            "</section>"
        ),
        unsafe_allow_html=True,
    )


def error_card(
    title: str,
    message: str,
    suggestions: list[str] | None = None,
) -> None:
    callout_card("error", title, message, suggestions)


def info_card(
    title: str,
    message: str,
    suggestions: list[str] | None = None,
) -> None:
    callout_card("info", title, message, suggestions)


def success_card(title: str, message: str) -> None:
    callout_card("success", title, message)


def warning_card(title: str, message: str) -> None:
    callout_card("warning", title, message)
