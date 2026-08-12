from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import requests
import streamlit as st

st.set_page_config(page_title="dockernts — cluster dashboard", page_icon="🐳", layout="wide")


def html(s: str) -> str:
    """Strip leading whitespace from every line so Streamlit's Markdown
    parser never mistakes the block for a code fence (4+ leading spaces
    = code block in Markdown)."""
    return re.sub(r"(?m)^[ \t]+", "", s).strip()


DARK_VARS = {
    "ink": "#0F1319", "panel": "#161C25", "panel-raised": "#1B222C",
    "line": "#262E3A", "line-soft": "#1E2530",
    "text": "#E7EBF0", "muted": "#8791A0", "dim": "#5B6472",
    "amber": "#F0A93A", "amber-soft": "rgba(240,169,58,0.14)", "amber-ink": "#1A1206",
    "moss": "#5FBE8A", "moss-soft": "rgba(95,190,138,0.14)",
    "red": "#E1555B", "red-soft": "rgba(225,85,91,0.14)",
    "blue": "#6FA8DC", "blue-soft": "rgba(111,168,220,0.14)",
    "radius": "10px",
}
LIGHT_VARS = {
    "ink": "#F2F4F8", "panel": "#FFFFFF", "panel-raised": "#F7F8FB",
    "line": "#E1E5EC", "line-soft": "#ECEEF3",
    "text": "#171B22", "muted": "#5B6270", "dim": "#8791A0",
    "amber": "#B9720C", "amber-soft": "rgba(185,114,12,0.12)", "amber-ink": "#FFFFFF",
    "moss": "#1F8A5C", "moss-soft": "rgba(31,138,92,0.12)",
    "red": "#C13A40", "red-soft": "rgba(193,58,64,0.10)",
    "blue": "#2E62B0", "blue-soft": "rgba(46,98,176,0.10)",
    "radius": "10px",
}


def _vars_block(d: dict) -> str:
    return "\n".join(f"--{k}:{v};" for k, v in d.items())



if "theme_choice" not in st.session_state:
    st.session_state.theme_choice = "Dark"

with st.sidebar:
    st.markdown(
        html("""
        <style>
        div[data-testid="stSidebarUserContent"] div[role="radiogroup"]{
            display:flex; gap:4px; background:#1B222C; border:1px solid #262E3A;
            border-radius:10px; padding:3px; margin-bottom:14px;
        }
        div[data-testid="stSidebarUserContent"] div[role="radiogroup"] label{
            flex:1; justify-content:center; margin:0 !important; padding:6px 0 !important;
            border-radius:7px !important; font-family:'IBM Plex Mono', monospace !important; font-size:11.5px !important;
            border:none !important; background:transparent !important; color:#8791A0 !important;
        }
        div[data-testid="stSidebarUserContent"] div[role="radiogroup"] label:has(input:checked){
            background:#262E3A !important; color:#E7EBF0 !important;
        }
        div[data-testid="stSidebarUserContent"] div[role="radiogroup"] label div:first-child{ display:none; }
        </style>
        """),
        unsafe_allow_html=True,
    )
    st.markdown('<div style="font-family:\'IBM Plex Mono\',monospace;font-size:10.5px;color:#5B6472;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;">Appearance</div>', unsafe_allow_html=True)
    st.session_state.theme_choice = st.radio(
        "Theme", ["Dark", "Light"], horizontal=True, label_visibility="collapsed",
        index=["Dark", "Light"].index(st.session_state.theme_choice),
    )

_THEME = st.session_state.theme_choice
VARS = DARK_VARS if _THEME == "Dark" else LIGHT_VARS
_root_css = f":root{{{_vars_block(VARS)}}}"


st.markdown(
    html(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap');

    {_root_css}

    html, body, [class*="css"], .stMarkdown, p, span, div {{ font-family:'Inter', -apple-system, sans-serif; }}
    .stApp{{
        background:
          radial-gradient(circle at 12% 8%, rgba(111,168,220,0.06), transparent 40%),
          radial-gradient(circle at 90% 85%, rgba(240,169,58,0.05), transparent 45%),
          linear-gradient(rgba(111,168,220,0.045) 1px, transparent 1px) 0 0/36px 36px,
          linear-gradient(90deg, rgba(111,168,220,0.045) 1px, transparent 1px) 0 0/36px 36px,
          var(--ink);
        color:var(--text);
        transition: background .15s ease, color .15s ease;
    }}
    #MainMenu, footer, header[data-testid="stHeader"]{{ background:transparent; }}
    .block-container{{ padding-top:1.4rem; padding-bottom:3rem; max-width:1180px; }}

    h1,h2,h3,h4 {{ font-family:'Space Grotesk', sans-serif !important; color:var(--text) !important; }}
    code, .mono {{ font-family:'IBM Plex Mono', monospace !important; }}
    hr{{ border-color:var(--line) !important; margin:8px 0 !important; }}
    p, span, label, .stMarkdown {{ color:var(--text); }}
    a{{ color:var(--blue); }}

    /* ---------- sidebar ---------- */
    section[data-testid="stSidebar"]{{ background:var(--panel); border-right:1px solid var(--line); }}
    /* keep the whole sidebar body from needing its own inner scrollbar
       whenever the collapsed Settings/Debug expanders push it slightly
       taller than the viewport */
    section[data-testid="stSidebar"] > div:first-child{{ overflow-y:visible !important; }}
    section[data-testid="stSidebar"] .block-container{{ padding-top:1rem !important; padding-bottom:1rem !important; }}
    /* brand header stays pinned at the top of the sidebar instead of
       scrolling out of view */
    .sidebar-brand{{
        position:sticky; top:0; z-index:5; background:var(--panel);
        padding-bottom:12px; margin-bottom:6px; border-bottom:1px solid var(--line-soft);
    }}
    section[data-testid="stSidebar"] input{{
        background:var(--panel-raised) !important; color:var(--text) !important; border:1px solid var(--line) !important;
        font-family:'IBM Plex Mono', monospace !important; border-radius:7px !important;
    }}
    section[data-testid="stSidebar"] label p{{ color:var(--muted) !important; font-size:11.5px !important;
        font-family:'IBM Plex Mono',monospace !important; text-transform:uppercase; letter-spacing:.05em; }}
    div[data-testid="stExpander"]{{ background:var(--panel-raised); border:1px solid var(--line); border-radius:8px; }}
    div[data-testid="stExpander"] summary{{ font-family:'Space Grotesk',sans-serif; font-weight:600; color:var(--text); }}
    div[data-testid="stCodeBlock"] pre{{ background:#0B0E12 !important; }}
    div[data-testid="stCodeBlock"] code{{ color:#B9C3CE !important; font-family:'IBM Plex Mono',monospace !important; }}

    /* ---------- buttons ---------- */
    .stButton>button, .stFormSubmitButton>button, .stDownloadButton>button{{
        border-radius:7px !important; border:1px solid var(--line) !important;
        background:var(--panel) !important; color:var(--text) !important;
        font-family:'Inter',sans-serif !important; font-weight:600 !important; font-size:13px !important;
        padding:8px 14px !important; transition:.12s ease;
    }}
    .stButton>button:hover{{ border-color:var(--dim) !important; }}
    .stButton>button:active{{ transform:scale(0.97); }}
    .stButton>button[kind="primary"], .stFormSubmitButton>button[kind="primary"]{{
        background:var(--amber) !important; color:var(--amber-ink) !important; border:none !important;
    }}
    button[kind="primary"] p{{ color:var(--amber-ink) !important; font-weight:700 !important; }}

    /* ---------- inputs ---------- */
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div{{
        background:var(--panel-raised) !important; color:var(--text) !important; border:1px solid var(--line) !important;
        font-family:'IBM Plex Mono', monospace !important; border-radius:7px !important; font-size:12.5px !important;
    }}
    .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus{{
        border-color:var(--blue) !important; box-shadow:0 0 0 2px rgba(111,168,220,.15) !important;
    }}
    label p{{ color:var(--muted) !important; font-size:11.5px !important; font-family:'IBM Plex Mono',monospace !important; letter-spacing:.03em; }}

    /* ---------- containers ---------- */
    div[data-testid="stVerticalBlockBorderWrapper"]{{
        background:var(--panel); border:1px solid var(--line) !important; border-radius:var(--radius) !important;
    }}

    /* ---------- chips (machine filter row) ---------- */
    div.main div[role="radiogroup"]{{ display:flex; flex-wrap:wrap; gap:8px; }}
    div.main div[role="radiogroup"] label{{
        margin:0 !important; padding:5px 13px !important; border-radius:20px !important;
        border:1px solid var(--line) !important; background:var(--panel) !important;
        font-family:'IBM Plex Mono',monospace !important; font-size:11.5px !important; color:var(--muted) !important;
        transition:.15s ease;
    }}
    div.main div[role="radiogroup"] label:has(input:checked){{
        background:var(--amber-soft) !important; border-color:var(--amber) !important; color:var(--amber) !important;
    }}
    div.main div[role="radiogroup"] label div:first-child{{ display:none; }}
    div.main div[role="radiogroup"] label p{{ color:inherit !important; text-transform:none !important; font-size:11.5px !important; }}

    /* ---------- top bar ---------- */
    .topbar{{
        display:flex; align-items:center; justify-content:space-between;
        padding:14px 20px; margin-bottom:26px;
        background:var(--panel); border:1px solid var(--line); border-radius:var(--radius);
        flex-wrap:wrap; gap:12px;
    }}
    .brand{{ display:flex; align-items:center; gap:12px; }}
    .brand-mark{{
        width:30px; height:30px; border-radius:7px; flex-shrink:0;
        background:linear-gradient(135deg, var(--amber), #C97B1A);
        display:flex; align-items:center; justify-content:center;
        font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:14px; color:#1A1206;
    }}
    .brand-name{{ font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:17px; letter-spacing:.2px; }}
    .brand-sub{{ font-family:'IBM Plex Mono',monospace; font-size:12px; color:var(--muted); padding-left:12px; border-left:1px solid var(--line); }}
    .cluster-pulse{{ display:flex; align-items:center; gap:8px; font-size:13px; color:var(--muted); }}
    .pulse-dot{{ width:8px; height:8px; border-radius:50%; background:var(--moss); animation:beat 5s ease-out infinite; }}
    @keyframes beat{{
        0%{{ box-shadow:0 0 0 0 rgba(95,190,138,.55); }}
        6%{{ box-shadow:0 0 0 6px rgba(95,190,138,0); }}
        100%{{ box-shadow:0 0 0 6px rgba(95,190,138,0); }}
    }}

    /* ---------- section headers ---------- */
    .section-title{{
        font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:14px; letter-spacing:1.4px;
        text-transform:uppercase; color:var(--text); display:flex; align-items:center; gap:10px;
    }}
    .section-title .count{{
        font-family:'IBM Plex Mono',monospace; font-size:11.5px; color:var(--dim);
        background:var(--panel-raised); border:1px solid var(--line); padding:2px 7px; border-radius:20px; letter-spacing:0;
    }}
    .section-note{{ font-size:12.5px; color:var(--dim); }}

    /* ---------- machine cards ---------- */
    .machine-card{{
        background:var(--panel); border:1px solid var(--line); border-radius:var(--radius);
        padding:16px 17px 14px; position:relative; height:100%;
    }}
    .machine-card.offline{{ opacity:.55; }}
    .m-head{{ display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:12px; }}
    .m-name{{ font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:15px; }}
    .m-host{{ font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--dim); margin-top:2px; }}
    .m-status{{ display:flex; align-items:center; gap:6px; font-size:11.5px; font-family:'IBM Plex Mono',monospace; flex-shrink:0; }}
    .m-status.online{{ color:var(--moss); }}
    .m-status.offline{{ color:var(--red); }}
    .beat-dot{{ width:7px; height:7px; border-radius:50%; flex-shrink:0; }}
    .beat-dot.online{{ background:var(--moss); animation:beat 5s ease-out infinite; }}
    .beat-dot.offline{{ background:var(--red); }}
    .trace{{ width:100%; height:26px; margin:10px 0 12px; opacity:.9; display:block; }}
    .trace path{{ fill:none; stroke:var(--moss); stroke-width:1.4; stroke-dasharray:400; stroke-dashoffset:400; animation:sweep 5s linear infinite; }}
    .machine-card.offline .trace path{{ stroke:var(--dim); animation:none; stroke-dashoffset:0; opacity:.35; }}
    @keyframes sweep{{ 0%{{ stroke-dashoffset:400; }} 100%{{ stroke-dashoffset:0; }} }}
    .bar-row{{ display:flex; align-items:center; gap:8px; margin-bottom:6px; }}
    .bar-label{{ font-size:10.5px; font-family:'IBM Plex Mono',monospace; color:var(--dim); width:30px; flex-shrink:0; }}
    .bar-track{{ flex:1; height:5px; border-radius:4px; background:var(--line-soft); overflow:hidden; }}
    .bar-fill{{ height:100%; border-radius:4px; }}
    .bar-fill.cpu{{ background:var(--blue); }}
    .bar-fill.mem{{ background:var(--amber); }}
    .bar-val{{ font-size:10.5px; font-family:'IBM Plex Mono',monospace; color:var(--muted); width:32px; text-align:right; flex-shrink:0; }}
    .m-foot{{
        display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap;
        padding-top:11px; border-top:1px solid var(--line-soft); margin-top:2px;
        font-size:11px; color:var(--dim); font-family:'IBM Plex Mono',monospace;
    }}

    /* ---------- containers table ---------- */
    .table-card{{ background:var(--panel); border:1px solid var(--line); border-radius:var(--radius); overflow:hidden; }}
    table.ctable{{ width:100%; border-collapse:collapse; font-size:13px; }}
    table.ctable thead th{{
        text-align:left; padding:11px 16px; font-family:'IBM Plex Mono',monospace; font-size:10.5px;
        letter-spacing:.8px; text-transform:uppercase; color:var(--dim); border-bottom:1px solid var(--line); font-weight:500;
    }}
    table.ctable tbody td{{ padding:12px 16px; border-bottom:1px solid var(--line-soft); vertical-align:middle; background:var(--panel-raised); }}
    table.ctable tbody tr:last-child td{{ border-bottom:none; }}
    .c-name{{ font-family:'IBM Plex Mono',monospace; font-size:12.5px; font-weight:500; }}
    .c-id{{ font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--dim); margin-top:2px; }}
    .c-image{{ font-family:'IBM Plex Mono',monospace; font-size:12px; color:var(--muted); }}
    .c-machine{{ display:flex; align-items:center; gap:6px; font-size:12.5px; color:var(--muted); }}
    .c-machine .dot{{ width:5px; height:5px; border-radius:50%; background:var(--moss); flex-shrink:0; }}
    .c-machine.is-offline .dot{{ background:var(--red); }}
    .status-pill{{
        display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:20px;
        font-size:11.5px; font-family:'IBM Plex Mono',monospace; font-weight:500;
    }}
    .status-pill .d{{ width:6px; height:6px; border-radius:50%; }}
    .status-pill.running{{ background:var(--moss-soft); color:var(--moss); }}
    .status-pill.running .d{{ background:var(--moss); animation:beat 5s ease-out infinite; }}
    .status-pill.exited{{ background:var(--red-soft); color:var(--red); }}
    .status-pill.exited .d{{ background:var(--red); }}
    .status-pill.restarting{{ background:var(--amber-soft); color:var(--amber); }}
    .status-pill.restarting .d{{ background:var(--amber); }}
    .status-pill.unknown{{ background:var(--blue-soft); color:var(--blue); }}
    .status-pill.unknown .d{{ background:var(--blue); }}
    .empty-cell{{ text-align:center; padding:34px 20px; color:var(--dim); font-size:13px; }}

    /* ---------- manage panel ---------- */
    .manage-card{{ background:var(--panel); border:1px solid var(--line); border-radius:var(--radius); padding:16px 18px; margin-top:14px; }}
    .manage-title{{ font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:13px; color:var(--text); margin-bottom:10px; }}
    .term{{
        background:#0B0E12; border:1px solid var(--line); border-radius:8px; padding:14px 16px;
        font-family:'IBM Plex Mono',monospace; font-size:12px; line-height:1.65; color:#B9C3CE;
        max-height:420px; overflow-y:auto; white-space:pre-wrap;
    }}
    .issue-row{{
        display:flex; align-items:center; gap:10px; flex-wrap:wrap;
        background:var(--red-soft); border:1px solid var(--red); border-radius:10px;
        padding:9px 14px; margin-bottom:10px;
    }}
    .issue-note{{ font-family:'IBM Plex Mono',monospace; font-size:11.5px; color:var(--muted); }}

    /* ---------- dialogs (deploy / logs) — styled like the mockup's
       slide-over drawer: clear header block, subtitle, spaced fields ---------- */
    div[data-testid="stDialog"] > div{{
        background:var(--panel) !important; border:1px solid var(--line) !important;
        border-radius:16px !important; max-width:480px !important; width:92vw !important; margin:0 auto !important;
        box-shadow:0 20px 50px rgba(0,0,0,.45) !important;
    }}
    div[role="dialog"] *:not(button):not(svg):not(path){{ color:var(--text); }}
    div[role="dialog"] h1, div[role="dialog"] h2, div[role="dialog"] h3{{
        color:var(--text) !important; font-family:'Space Grotesk',sans-serif !important; font-size:18px !important;
        font-weight:600 !important;
    }}
    div[role="dialog"] [data-testid="stMarkdownContainer"] p{{ color:var(--muted); font-size:12.5px; }}
    div[role="dialog"] .stTextInput input, div[role="dialog"] .stNumberInput input, div[role="dialog"] .stTextArea textarea{{
        background:var(--panel-raised) !important; color:var(--text) !important; border:1px solid var(--line) !important;
        font-family:'IBM Plex Mono',monospace !important; font-size:12.5px !important;
    }}
    div[role="dialog"] div[data-baseweb="select"] > div{{ background:var(--panel-raised) !important; border:1px solid var(--line) !important; color:var(--text) !important; }}
    div[data-baseweb="popover"] ul, div[data-baseweb="popover"] li{{ background:var(--panel-raised) !important; color:var(--text) !important; }}
    div[data-baseweb="popover"] li:hover{{ background:var(--panel) !important; }}
    div[role="dialog"] .stFormSubmitButton>button[kind="primary"]{{
        background:var(--amber) !important; color:var(--amber-ink) !important; border:none !important; width:100% !important;
    }}
    .drawer-head{{ display:flex; align-items:center; gap:10px; margin-bottom:4px; }}
    .drawer-title{{ font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:16px; color:var(--text); }}
    .drawer-sub{{ font-size:12px; color:var(--dim); margin-top:2px; }}

    @media (prefers-reduced-motion: reduce){{
        .pulse-dot, .beat-dot, .trace path, .status-pill .d{{ animation:none !important; }}
    }}
    </style>
    """),
    unsafe_allow_html=True,
)


if "session_deploys" not in st.session_state:
    st.session_state.session_deploys = []
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
if "container_filter" not in st.session_state:
    st.session_state.container_filter = "All machines"


with st.sidebar:
    st.markdown(
        html(f"""
        <div class="brand sidebar-brand">
            <div class="brand-mark">D</div>
            <div><div class="brand-name">dockernts</div>
            <div class="brand-sub" style="border-left:none; padding-left:0;">cluster control</div></div>
        </div>
        """),
        unsafe_allow_html=True,
    )
    with st.expander("⚙  Settings", expanded=False):
        api_base = st.text_input("Server address", value="http://127.0.0.1:8000/api")
        timeout_s = st.slider("Request timeout (s)", 3, 30, 10)
        st.session_state.auto_refresh = st.checkbox("Auto-refresh", value=st.session_state.auto_refresh)
        refresh_every = st.slider("Every (s)", 3, 30, 5, disabled=not st.session_state.auto_refresh)
    if st.button("↻ Refresh now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    try:
        r = requests.get(f"{api_base}/health", timeout=timeout_s)
        healthy = r.ok and r.json().get("status") == "ok"
    except Exception:
        healthy = False
    st.markdown(
        html(f"""
        <span class="status-pill {'running' if healthy else 'exited'}"><span class="d"></span>
        {'manager reachable' if healthy else 'manager unreachable'}</span>
        """),
        unsafe_allow_html=True,
    )
    if not healthy:
        st.caption("Can't reach the manager — check the server address above.")


def api_get(path, params=None):
    try:
        r = requests.get(f"{api_base}{path}", params=params, timeout=timeout_s)
        return (r.json(), None) if r.ok else (None, f"{r.status_code}: {_detail(r)}")
    except Exception as exc:
        return None, str(exc)


def api_post(path, body=None):
    try:
        r = requests.post(f"{api_base}{path}", json=body or {}, timeout=timeout_s)
        return (r.json(), None) if r.ok else (None, f"{r.status_code}: {_detail(r)}")
    except Exception as exc:
        return None, str(exc)


def api_delete(path, params=None):
    try:
        r = requests.delete(f"{api_base}{path}", params=params, timeout=timeout_s)
        return (r.json(), None) if r.ok else (None, f"{r.status_code}: {_detail(r)}")
    except Exception as exc:
        return None, str(exc)


def _detail(r):
    try:
        return r.json().get("detail", r.text)
    except Exception:
        return r.text


with st.sidebar:
    with st.expander("🐞 Debug: raw /machines response", expanded=False):
        _dbg_data, _dbg_err = api_get("/machines")
        if _dbg_err:
            st.caption(f"Request failed: {_dbg_err}")
        else:
            st.caption("If cpu_percent / memory_percent aren't in here, the manager isn't returning them — the fix belongs in the manager's /machines handler, not the agent or this UI.")
            st.json(_dbg_data)


@st.cache_data(ttl=4, show_spinner=False)
