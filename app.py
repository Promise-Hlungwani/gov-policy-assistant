import streamlit as st

from utils.logging_config import configure_logging

configure_logging()

st.set_page_config(
    page_title="Government Knowledge & Policy Assistant",
    page_icon="📚",
    layout="wide",
)

pages = [
    st.Page("pages/1_Upload_Documents.py", title="Upload Documents", icon="📤"),
    st.Page("pages/2_Chat_Assistant.py", title="Chat Assistant", icon="💬", default=True),
    st.Page("pages/3_Document_Library.py", title="Document Library", icon="📚"),
    st.Page("pages/4_Admin_Logs.py", title="Admin & Audit Logs", icon="🔐"),
]

st.navigation(pages).run()
