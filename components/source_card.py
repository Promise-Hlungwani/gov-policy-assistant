import streamlit as st

from components.status_badge import status_badge
from models.chat import SourceCitation


def source_card(citation: SourceCitation) -> None:
    with st.expander(
        f"[{citation.citation_id}] {citation.document_title}",
        icon="📄",
    ):
        st.markdown(f"**Document:** {citation.document_title}")
        st.markdown(f"**Source Type:** {citation.source_type.label}")
        if (
            citation.source_type.value == "government_website"
            and citation.source_url
        ):
            st.link_button(
                "Open original source",
                citation.source_url,
                use_container_width=False,
            )
        elif citation.source_url:
            st.text(f"Repository reference: {citation.source_url}")
        st.markdown(
            f"**Version:** {citation.version_number or 'Not specified'}"
        )
        st.markdown(f"**Section:** {citation.section_title}")
        if citation.page_number is not None:
            st.markdown(f"**Page:** {citation.page_number}")
        st.markdown("**Document classification**")
        status_badge(citation.classification, citation.classification.value)
        st.markdown("**Version status**")
        status_badge(citation.lifecycle_status, citation.lifecycle_status.value)
        st.markdown("**Excerpt**")
        st.text(citation.excerpt)
