import streamlit as st


def loading_indicator(label: str, *, expanded: bool = False):
    return st.status(label, expanded=expanded, state="running")
