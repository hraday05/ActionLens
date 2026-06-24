import streamlit as st
import tempfile
import os
from datetime import datetime
from agent import run_agent
from chat_db import (
    create_session,
    save_message,
    get_session_list,
    load_session,
    delete_session,
    get_session_title,
)

# ─── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Multi-Agent Knowledge System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Google Font ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ── Global ── */
    .stApp {
        background: #f0f2f6 !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* ── Hide Streamlit defaults ── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {
        background: transparent !important;
        height: auto !important;
    }
    header [data-testid="stToolbar"] {display: none !important;}
    .stDeployButton {display: none !important;}

    /* ── Sidebar — Dark Navy (always visible) ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f2344 0%, #1a365d 100%) !important;
        border-right: none !important;
        padding-top: 0 !important;
        min-width: 250px !important;
        max-width: 270px !important;
        transform: none !important;
        width: 270px !important;
        transition: none !important;
    }
    /* Prevent sidebar from collapsing */
    section[data-testid="stSidebar"][aria-expanded="false"] {
        display: block !important;
        min-width: 250px !important;
        width: 270px !important;
        transform: none !important;
        margin-left: 0 !important;
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 0 !important;
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown li,
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3,
    section[data-testid="stSidebar"] .stMarkdown h4,
    section[data-testid="stSidebar"] label {
        color: #c7d2e0 !important;
    }

    /* ── Sidebar Logo Area ── */
    .sidebar-logo {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding: 1.2rem 1rem 1rem 1rem;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 0.5rem;
    }
    .sidebar-logo-icon { font-size: 1.6rem; }
    .sidebar-logo-text {
        font-size: 1.15rem;
        font-weight: 700;
        color: #ffffff !important;
        letter-spacing: -0.01em;
    }

    /* ── Sidebar Section Labels ── */
    .sidebar-section-label {
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #7b8fa8 !important;
        padding: 0.8rem 1rem 0.4rem 1rem;
        margin-top: 0.2rem;
    }

    /* ── Sidebar Divider ── */
    .sidebar-divider {
        height: 1px;
        background: rgba(255,255,255,0.08);
        margin: 0.5rem 1rem;
    }

    /* ── History Items ── */
    .history-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 0.8rem;
        margin: 0.15rem 0.5rem;
        border-radius: 8px;
        font-size: 0.82rem;
        color: #a0b3c8;
        cursor: pointer;
        transition: all 0.2s ease;
        border-left: 2px solid transparent;
        overflow: hidden;
    }
    .history-item:hover {
        background: rgba(255,255,255,0.06);
        color: #ffffff;
        border-left-color: #4299e1;
    }
    .history-item.active {
        background: rgba(43, 108, 176, 0.3);
        color: #ffffff;
        border-left-color: #63b3ed;
        font-weight: 600;
    }
    .history-title {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 1;
    }
    .history-time {
        font-size: 0.65rem;
        color: #5a7a99;
        white-space: nowrap;
        flex-shrink: 0;
    }
    .history-item.active .history-time {
        color: #90cdf4;
    }

    /* ── Empty history ── */
    .history-empty {
        padding: 0.5rem 1rem;
        font-size: 0.78rem;
        color: #5a7a99;
        font-style: italic;
    }

    /* ── File Uploader in sidebar ── */
    section[data-testid="stFileUploader"] > div {
        background: rgba(255,255,255,0.06) !important;
        border: 1px dashed rgba(255,255,255,0.15) !important;
        border-radius: 8px !important;
    }
    section[data-testid="stFileUploader"] label {
        color: #a0b3c8 !important;
        font-size: 0.8rem !important;
    }
    section[data-testid="stFileUploader"] button {
        background: #2b6cb0 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 0.78rem !important;
    }

    /* ── Text Area (URLs) in sidebar ── */
    section[data-testid="stSidebar"] .stTextArea textarea {
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
        font-size: 0.8rem !important;
    }
    section[data-testid="stSidebar"] .stTextArea textarea:focus {
        border-color: #4299e1 !important;
        box-shadow: 0 0 0 2px rgba(66, 153, 225, 0.2) !important;
    }

    /* ── Success alerts in sidebar ── */
    section[data-testid="stSidebar"] div[data-testid="stAlert"] {
        background: rgba(72, 187, 120, 0.15) !important;
        border: 1px solid rgba(72, 187, 120, 0.3) !important;
        border-radius: 8px !important;
        font-size: 0.78rem !important;
    }

    /* ── Top Header Bar ── */
    .top-bar {
        background: #ffffff;
        border-bottom: 1px solid #e2e8f0;
        padding: 0.7rem 1.5rem;
        margin: -1rem -1rem 1rem -1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-radius: 0;
    }
    .top-bar-title {
        font-size: 0.88rem;
        font-weight: 500;
        color: #2d3748;
    }
    .top-bar-title strong {
        color: #1a365d;
        font-weight: 700;
    }

    /* ── Main content area ── */
    .main .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 5rem !important;
        max-width: 960px !important;
    }

    /* ── Chat messages ── */
    .stChatMessage {
        background: transparent !important;
        border: none !important;
        padding: 0.5rem 0 !important;
    }

    /* ── Custom chat bubbles ── */
    .user-bubble {
        background: #ebf2fa;
        border: 1px solid #d4e1f0;
        border-radius: 16px 16px 4px 16px;
        padding: 0.9rem 1.2rem;
        max-width: 75%;
        margin-left: auto;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
        color: #2d3748;
        line-height: 1.6;
    }
    .bot-bubble {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px 16px 16px 4px;
        padding: 0.9rem 1.2rem;
        max-width: 80%;
        margin-right: auto;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
        color: #2d3748;
        line-height: 1.6;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .bot-bubble strong { color: #1a365d; }
    .bot-avatar, .user-avatar {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.85rem;
        flex-shrink: 0;
    }
    .bot-avatar { background: #e2e8f0; }
    .user-avatar { background: #d4e1f0; margin-left: auto; }

   /* ── Chat input bar FIXED ── */

/* Force consistent light behavior */
html, body {
    color-scheme: light !important;
}

/* Main chat input container */
[data-testid="stChatInput"] {
    background: #ffffff !important;
    border-top: 1px solid #e2e8f0 !important;
}

/* Inner box */
[data-testid="stChatInput"] > div {
    background: #ffffff !important;
    border: 1px solid #d4dbe5 !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
}

/* Focus effect */
[data-testid="stChatInput"] > div:focus-within {
    border-color: #4299e1 !important;
    box-shadow: 0 2px 12px rgba(66, 153, 225, 0.15) !important;
}

/* TEXTAREA — MOST IMPORTANT FIX */
[data-testid="stChatInput"] textarea {
    background-color: #ffffff !important;
    color: #000000 !important;
    caret-color: #000000 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
}

/* Placeholder */
[data-testid="stChatInput"] textarea::placeholder {
    color: #6b7280 !important;
}

/* Send button */
[data-testid="stChatInput"] button {
    background: #2b6cb0 !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    border: none !important;
}

    /* ── Spinner ── */
    .stSpinner > div { border-top-color: #2b6cb0 !important; }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #cbd5e0; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #a0aec0; }

    /* ── Sidebar buttons ── */
    section[data-testid="stSidebar"] .stButton button {
        background: rgba(255,255,255,0.08) !important;
        color: #c7d2e0 !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 8px !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background: rgba(255,255,255,0.15) !important;
        color: #ffffff !important;
        border-color: rgba(255,255,255,0.2) !important;
    }
</style>
""", unsafe_allow_html=True)


# ─── API Key Check ─────────────────────────────────────────────
if not os.getenv("GROQ_API_KEY"):
    try:
        if "GROQ_API_KEY" in st.secrets:
            os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
    except Exception:
        pass

if not os.getenv("GROQ_API_KEY"):
    st.markdown("""
    <div style="text-align:center; padding: 4rem 2rem;">
        <div style="font-size: 3rem; margin-bottom: 1rem;">🔐</div>
        <h2 style="color: #c53030;">API Key Required</h2>
        <p style="color: #718096;">Add <code>GROQ_API_KEY</code> to your <code>.env</code> file to continue.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ─── Helper: relative time ─────────────────────────────────────
def _relative_time(iso_str: str) -> str:
    """Converts an ISO timestamp to a human-readable relative time."""
    try:
        dt = datetime.fromisoformat(iso_str)
        diff = datetime.now() - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            m = seconds // 60
            return f"{m}m ago"
        elif seconds < 86400:
            h = seconds // 3600
            return f"{h}h ago"
        elif seconds < 604800:
            d = seconds // 86400
            return f"{d}d ago"
        else:
            return dt.strftime("%b %d")
    except Exception:
        return ""


# ─── Initialize Session State ──────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None


# ─── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    # Logo
    st.markdown("""
    <div class="sidebar-logo">
        <span class="sidebar-logo-icon">📈</span>
        <span class="sidebar-logo-text">Multi-Agent Knowledge System</span>
    </div>
    """, unsafe_allow_html=True)

    # ── + New Chat button
    if st.button("✨  New Chat", use_container_width=True, key="new_chat_btn"):
        st.session_state.messages = []
        st.session_state.active_session_id = None
        st.rerun()

    # ── Chat History
    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-label">💬 Chat History</div>', unsafe_allow_html=True)

    try:
        sessions = get_session_list(limit=30)
    except Exception:
        sessions = []

    if sessions:
        for session in sessions:
            is_active = session["id"] == st.session_state.active_session_id
            active_class = "active" if is_active else ""
            rel_time = _relative_time(session["updated_at"])

            # Render as HTML for styling
            st.markdown(f"""
            <div class="history-item {active_class}" id="hist-{session['id'][:8]}">
                <span class="history-title">{'💬 ' if is_active else ''}{session['title']}</span>
                <span class="history-time">{rel_time}</span>
            </div>
            """, unsafe_allow_html=True)

            # Use a Streamlit button (small, functional) to actually load the session
            if st.button(
                f"↳ {session['title'][:30]}",
                key=f"load_{session['id']}",
                use_container_width=True,
            ):
                try:
                    loaded_msgs = load_session(session["id"])
                    st.session_state.messages = [
                        {"role": m["role"], "content": m["content"]}
                        for m in loaded_msgs
                    ]
                    st.session_state.active_session_id = session["id"]
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load: {e}")
    else:
        st.markdown('<div class="history-empty">No conversations yet</div>', unsafe_allow_html=True)

    # ── Data Sources
    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-label">📄 Documents</div>', unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "Upload financial PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    processed_pdf_paths = []

    if uploaded_files:
        temp_dir = tempfile.mkdtemp()
        for uploaded_file in uploaded_files:
            file_path = os.path.join(temp_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            processed_pdf_paths.append(file_path)
        st.success(f"✓ {len(uploaded_files)} PDF(s) loaded")

    st.markdown('<div class="sidebar-section-label">🔗 Web Sources</div>', unsafe_allow_html=True)

    urls_input = st.text_area(
        "Enter URLs (one per line)",
        placeholder="https://sec.gov/...\nhttps://finance.yahoo.com/...",
        label_visibility="collapsed",
        height=80,
    )
    processed_urls = [url.strip() for url in urls_input.split("\n") if url.strip()]

    if processed_urls:
        st.success(f"✓ {len(processed_urls)} URL(s) linked")


# ─── Main Content ──────────────────────────────────────────────

# Top bar
if st.session_state.active_session_id:
    try:
        current_title = get_session_title(st.session_state.active_session_id)
    except Exception:
        current_title = "Conversation"
    bar_text = f'Chatting with <strong>Multi-Agent Knowledge System</strong> | {current_title}'
else:
    bar_text = 'Chatting with <strong>Multi-Agent Knowledge System</strong> | Start a conversation'

st.markdown(f"""
<div class="top-bar">
    <div class="top-bar-title">{bar_text}</div>
</div>
""", unsafe_allow_html=True)

# Display chat messages
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f"""
        <div style="display: flex; align-items: flex-start; justify-content: flex-end; gap: 0.5rem; margin-bottom: 0.8rem;">
            <div class="user-bubble">{message["content"]}</div>
            <div class="user-avatar">👤</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="display: flex; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.8rem;">
            <div class="bot-avatar">⚙️</div>
            <div class="bot-bubble">{message["content"]}</div>
        </div>
        """, unsafe_allow_html=True)

# Empty state
if not st.session_state.messages:
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem;">
        <div style="font-size: 3.5rem; margin-bottom: 1rem; opacity: 0.3;">📊</div>
        <h3 style="color: #4a5568; font-weight: 600; margin-bottom: 0.5rem;">Welcome to Multi-Agent Knowledge System</h3>
        <p style="color: #a0aec0; font-size: 0.95rem; max-width: 450px; margin: 0 auto; line-height: 1.6;">
            Upload financial documents, link market sources, and ask questions about
            your portfolio, market trends, or investment strategies.
        </p>
    </div>
    """, unsafe_allow_html=True)

# ─── Chat Input ────────────────────────────────────────────────
if prompt := st.chat_input("Ask a financial question..."):
    # Auto-create session on first message
    if st.session_state.active_session_id is None:
        try:
            st.session_state.active_session_id = create_session(prompt)
        except Exception as e:
            st.error(f"Failed to create session: {e}")

    # Add user message to state
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Save user message to disk
    if st.session_state.active_session_id:
        try:
            save_message(st.session_state.active_session_id, "user", prompt)
        except Exception:
            pass  # Don't block chat if save fails

    # Display user message
    st.markdown(f"""
    <div style="display: flex; align-items: flex-start; justify-content: flex-end; gap: 0.5rem; margin-bottom: 0.8rem;">
        <div class="user-bubble">{prompt}</div>
        <div class="user-avatar">👤</div>
    </div>
    """, unsafe_allow_html=True)

    # Get response from agent
    with st.spinner("Analyzing..."):
        try:
            # Pass conversation history so the LLM remembers past messages
            past_messages = st.session_state.messages[:-1]  # Exclude the just-added user message
            response = run_agent(prompt, files=processed_pdf_paths, urls=processed_urls, history=past_messages)

            st.session_state.messages.append({"role": "assistant", "content": response})

            # Save assistant message to disk
            if st.session_state.active_session_id:
                try:
                    save_message(st.session_state.active_session_id, "assistant", response)
                except Exception:
                    pass

            # Display bot response
            st.markdown(f"""
            <div style="display: flex; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.8rem;">
                <div class="bot-avatar">⚙️</div>
                <div class="bot-bubble">{response}</div>
            </div>
            """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"⚠️ Error: {e}")
