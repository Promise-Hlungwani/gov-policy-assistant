from html import escape

import streamlit as st


def chat_message(role: str, content: str, timestamp: str) -> None:
    is_user = role == "user"
    label = "You" if is_user else "Assistant"
    role_class = "user" if is_user else "assistant"
    st.markdown(
        (
            f'<div class="chat-row chat-row-{role_class}" role="article" '
            f'aria-label="{label} message">'
            f'<div class="chat-bubble chat-bubble-{role_class}">'
            f'<div class="chat-meta"><span>{label}</span>'
            f"<time>{escape(timestamp)}</time></div>"
            f'<div class="chat-content">{escape(content)}</div>'
            "</div></div>"
        ),
        unsafe_allow_html=True,
    )
