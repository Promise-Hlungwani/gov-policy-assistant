from html import escape

import streamlit as st


def metric_card(label: str, value: str | int, icon: str) -> None:
    st.markdown(
        (
            '<div class="metric-card">'
            f'<span class="metric-card-icon" aria-hidden="true">{escape(icon)}</span>'
            f'<div class="metric-card-value">{escape(str(value))}</div>'
            f'<div class="metric-card-label">{escape(label)}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )
