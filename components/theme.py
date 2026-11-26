import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            color-scheme: light;
            --gov-navy: #102a43;
            --gov-blue: #1463a5;
            --gov-blue-dark: #0f4c81;
            --gov-ink: #172b4d;
            --gov-muted: #526579;
            --gov-canvas: #f4f7fb;
            --gov-border: #d9e2ec;
            --gov-green: #177245;
            --gov-amber: #805b00;
        }
        html, body, [class*="st-"] {
            font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
        }
        [data-testid="stAppViewContainer"] {
            background: var(--gov-canvas);
            color: var(--gov-ink);
        }
        [data-testid="stHeader"] {
            background: rgba(244, 247, 251, .94);
        }
        [data-testid="stSidebar"] {
            background: #102a43;
            border-right: 1px solid #28465f;
        }
        [data-testid="stSidebar"] * {
            color: #f5f8fb;
        }
        [data-testid="stSidebar"] button {
            border-color: #49637a;
        }
        [data-testid="stMain"] {
            max-width: 1440px;
            margin: 0 auto;
        }
        h1, h2, h3 {
            color: var(--gov-navy);
            letter-spacing: -.02em;
        }
        p, label, [data-testid="stCaptionContainer"] {
            line-height: 1.55;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--gov-border);
            border-radius: 14px;
            box-shadow: 0 2px 8px rgba(16, 42, 67, .045);
            background: #fff;
        }
        div.stButton > button, div.stFormSubmitButton > button {
            border-radius: 9px;
            font-weight: 600;
            min-height: 2.65rem;
            transition: background-color .15s ease, box-shadow .15s ease;
        }
        div.stButton > button[kind="primary"],
        div.stFormSubmitButton > button[kind="primary"] {
            background: var(--gov-blue);
            border-color: var(--gov-blue);
        }
        div.stButton > button:focus-visible,
        div.stFormSubmitButton > button:focus-visible,
        input:focus-visible {
            outline: 3px solid #f0b429 !important;
            outline-offset: 2px;
        }
        .gov-brand {
            padding: 1.15rem 1rem .6rem;
            margin-bottom: .7rem;
            border-bottom: 1px solid #35536b;
        }
        .gov-brand-title {
            font-size: 1rem;
            line-height: 1.35;
            font-weight: 700;
            color: #fff;
        }
        .gov-brand-tagline {
            margin-top: .35rem;
            color: #c9d8e6;
            font-size: .79rem;
            line-height: 1.45;
        }
        .page-kicker {
            color: var(--gov-blue);
            font-size: .82rem;
            font-weight: 700;
            letter-spacing: .08em;
            text-transform: uppercase;
            margin-bottom: .25rem;
        }
        .metric-card {
            background: #fff;
            border: 1px solid var(--gov-border);
            border-radius: 14px;
            box-shadow: 0 2px 8px rgba(16, 42, 67, .05);
            min-height: 122px;
            padding: 1rem 1.1rem;
        }
        .metric-card-icon { font-size: 1.25rem; }
        .metric-card-value {
            color: var(--gov-navy);
            font-size: 1.85rem;
            font-weight: 700;
            line-height: 1.25;
            margin-top: .4rem;
        }
        .metric-card-label {
            color: var(--gov-muted);
            font-size: .88rem;
            margin-top: .15rem;
        }
        .status-badge {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            border: 1px solid transparent;
            font-size: .76rem;
            font-weight: 700;
            line-height: 1.3;
            padding: .24rem .62rem;
            margin: .12rem .22rem .12rem 0;
            white-space: nowrap;
        }
        .badge-current, .badge-public, .badge-success, .badge-high {
            color: #145c37; background: #e7f5ec; border-color: #b7dfc4;
        }
        .badge-draft, .badge-internal, .badge-warning, .badge-medium {
            color: #765400; background: #fff5d6; border-color: #f0dc91;
        }
        .badge-superseded, .badge-neutral {
            color: #526579; background: #edf1f5; border-color: #d4dde6;
        }
        .badge-low {
            color: #8b2635; background: #fdecef; border-color: #efbdc5;
        }
        .badge-restricted {
            color: #8a4b08; background: #fff0df; border-color: #f1c99b;
        }
        .badge-confidential, .badge-danger {
            color: #8b2635; background: #fdecef; border-color: #efbdc5;
        }
        .callout {
            border: 1px solid var(--gov-border);
            border-left: 5px solid var(--gov-blue);
            border-radius: 12px;
            background: #fff;
            padding: 1rem 1.15rem;
            margin: .55rem 0 1rem;
        }
        .callout-title { color: var(--gov-navy); font-weight: 700; }
        .callout-body { color: var(--gov-muted); margin-top: .25rem; }
        .callout-success { border-left-color: var(--gov-green); }
        .callout-warning { border-left-color: #d19a00; }
        .callout-error { border-left-color: #b42332; }
        .chat-row { display: flex; width: 100%; margin: .4rem 0 .9rem; }
        .chat-row-user { justify-content: flex-end; }
        .chat-row-assistant { justify-content: flex-start; }
        .chat-bubble {
            border: 1px solid var(--gov-border);
            border-radius: 16px;
            box-shadow: 0 2px 7px rgba(16, 42, 67, .045);
            max-width: min(82%, 850px);
            padding: .85rem 1rem;
            overflow-wrap: anywhere;
        }
        .chat-bubble-user {
            background: #e8f2fb;
            border-color: #c7dced;
            border-bottom-right-radius: 5px;
        }
        .chat-bubble-assistant {
            background: #fff;
            border-bottom-left-radius: 5px;
        }
        .chat-meta {
            color: var(--gov-muted);
            display: flex;
            justify-content: space-between;
            gap: 1.2rem;
            font-size: .75rem;
            font-weight: 600;
            margin-bottom: .45rem;
        }
        .chat-content { color: var(--gov-ink); line-height: 1.6; white-space: pre-wrap; }
        @media (max-width: 700px) {
            .chat-bubble { max-width: 96%; }
            .metric-card { min-height: 105px; }
        }
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str) -> None:
    st.markdown(
        '<div class="page-kicker">Government Knowledge &amp; Policy Assistant</div>',
        unsafe_allow_html=True,
    )
    st.title(title)
    st.caption(subtitle)
