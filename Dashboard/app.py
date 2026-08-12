"""
dockernts — Streamlit cluster dashboard (pixel-matched to mockup)
===================================================================
Real API integration (no mock data), reskinned to match the ink/amber
HTML mockup: Space Grotesk + IBM Plex Mono + Inter, machine cards with
an animated heartbeat trace, and a containers table with filter chips.

v2 fixes:
  - Containers table was rendering as a literal code block because the
    generated HTML had leading indentation (Markdown treats 4+ leading
    spaces as a code fence). All HTML-producing helpers now strip
    leading whitespace before being handed to st.markdown.
  - Ports column was dumping the raw Docker ports dict, e.g.
    "{'80/tcp': None}" — now formatted as "80" / "8080:80" etc.
  - Dark / Light toggle restored at the top of the sidebar.
  - CPU/MEM bars now check several common field-name variants
    (cpu_percent, cpu, cpu_usage, mem_percent, memory_percent, mem)
    so real numbers show up if your API reports them under a
    different key. Still shows "—" rather than a fabricated number
    if nothing matches.
  - Deploy dialog reworked with a proper header/subtitle block instead
    of the bare default Streamlit dialog look.

Run:
    pip install streamlit requests
    streamlit run app.py
"""

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


# ═══════════════════════════════════════════════════════════════════════
#  DESIGN TOKENS — lifted 1:1 from the mockup's :root variables, with a
#  light counterpart for the theme toggle.
# ═══════════════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════════════
#  THEME TOGGLE — rendered first so the CSS below can bake in the right
#  palette before anything else on the page.
# ═══════════════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════════════
#  GLOBAL CSS
# ═══════════════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ═══════════════════════════════════════════════════════════════════════
if "session_deploys" not in st.session_state:
    st.session_state.session_deploys = []
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
if "container_filter" not in st.session_state:
    st.session_state.container_filter = "All machines"

# ═══════════════════════════════════════════════════════════════════════
#  SIDEBAR — connection settings
# ═══════════════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════════════
#  API HELPERS
# ═══════════════════════════════════════════════════════════════════════
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
def fetch_machines(_base):
    data, err = api_get("/machines")
    return (data or {}).get("machines", []), err


@st.cache_data(ttl=4, show_spinner=False)
def fetch_containers(_base, machine=None):
    data, err = api_get("/containers", params={"machine": machine} if machine else None)
    return (data or {}).get("containers", []), err


def relative_time(iso_str):
    if not iso_str:
        return "never"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = (datetime.now(timezone.utc) - dt).total_seconds()
        if secs < 60: return f"{int(secs)}s ago"
        if secs < 3600: return f"{int(secs // 60)}m ago"
        if secs < 86400: return f"{int(secs // 3600)}h ago"
        return f"{int(secs // 86400)}d ago"
    except Exception:
        return iso_str


def refresh():
    st.cache_data.clear()
    st.rerun()


def connection_issue(label: str, err: str | None):
    if not err:
        return
    st.markdown(
        html(f"""
        <div class="issue-row">
        <span class="status-pill exited"><span class="d"></span>{label} unavailable</span>
        <span class="issue-note">manager may be unreachable, starting up, or slow to respond</span>
        </div>
        """),
        unsafe_allow_html=True,
    )
    with st.expander("Technical details", expanded=False):
        st.code(err, language="text")


def quiet_loading(label: str, err: str | None):
    """Low-key placeholder for the initial page fetch — no alarming red
    box, no expander. Used where a brief hiccup while the manager warms
    up shouldn't look like a hard failure."""
    if not err:
        return
    st.markdown(
        f'<div style="font-family:\'IBM Plex Mono\',monospace; font-size:12px; color:var(--dim); '
        f'padding:8px 2px; margin-bottom:6px;">Loading {label.lower()}…</div>',
        unsafe_allow_html=True,
    )


def first_present(d: dict, keys: list[str]):
    """Return the first non-None value found under any of these keys —
    lets the UI pick up cpu/mem stats regardless of naming convention."""
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


def format_ports(ports) -> str:
    """Docker-style ports dict -> readable string.
    {'80/tcp': None} -> '80'
    {'80/tcp': [{'HostPort': '8080'}]} -> '8080:80'
    """
    if not ports:
        return "—"
    if isinstance(ports, str):
        return ports if ports.strip() else "—"
    if isinstance(ports, dict):
        parts = []
        for container_port, bindings in ports.items():
            cport = container_port.split("/")[0] if isinstance(container_port, str) else container_port
            if not bindings:
                parts.append(str(cport))
            elif isinstance(bindings, list):
                for b in bindings:
                    host_port = b.get("HostPort") if isinstance(b, dict) else b
                    parts.append(f"{host_port}:{cport}" if host_port else str(cport))
            else:
                parts.append(f"{bindings}:{cport}")
        return ", ".join(parts) if parts else "—"
    if isinstance(ports, list):
        return ", ".join(str(p) for p in ports) if ports else "—"
    return str(ports)


# the exact heartbeat waveform used in the mockup
TRACE_PATH = "M0,13 L40,13 L48,13 L54,3 L60,23 L66,13 L74,13 L120,13 L128,13 L134,3 L140,23 L146,13 L154,13 L200,13"


def machine_card_html(m: dict) -> str:
    status = (m.get("status") or "unknown").lower()
    is_online = status in ("healthy", "online")
    state_cls = "online" if is_online else "offline"
    cpu = first_present(m, ["cpu_percent", "cpu_usage", "cpu_pct", "cpu"])
    mem = first_present(m, ["mem_percent", "memory_percent", "mem_usage", "mem_pct", "memory_usage"])
    try:
        cpu_val = round(float(cpu), 1) if cpu is not None else None
    except (TypeError, ValueError):
        cpu_val = None
    try:
        mem_val = round(float(mem), 1) if mem is not None else None
    except (TypeError, ValueError):
        mem_val = None
    cpu_disp = f"{cpu_val}%" if cpu_val is not None else "—"
    mem_disp = f"{mem_val}%" if mem_val is not None else "—"
    cpu_w = cpu_val if cpu_val is not None else 0
    mem_w = mem_val if mem_val is not None else 0
    ip = m.get("ip") or m.get("address") or ""
    ip_part = f"{ip} · " if ip else ""
    return html(f"""
    <div class="machine-card {'' if is_online else 'offline'}">
    <div class="m-head">
    <div>
    <div class="m-name">{m.get('name','?')}</div>
    <div class="m-host">{m.get('hostname','')}</div>
    </div>
    <div class="m-status {state_cls}">
    <span class="beat-dot {state_cls}"></span>{'online' if is_online else 'offline'}
    </div>
    </div>
    <svg class="trace" viewBox="0 0 200 26" preserveAspectRatio="none">
    <path d="{TRACE_PATH}"/>
    </svg>
    <div class="bar-row">
    <span class="bar-label">CPU</span>
    <span class="bar-track"><span class="bar-fill cpu" style="width:{cpu_w}%"></span></span>
    <span class="bar-val">{cpu_disp}</span>
    </div>
    <div class="bar-row">
    <span class="bar-label">MEM</span>
    <span class="bar-track"><span class="bar-fill mem" style="width:{mem_w}%"></span></span>
    <span class="bar-val">{mem_disp}</span>
    </div>
    <div class="m-foot">
    <span>{ip_part}{m.get('cpu_count','?')} cores · docker {m.get('docker_version','?')}</span>
    <span>{relative_time(m.get('last_heartbeat'))}</span>
    </div>
    </div>
    """)


def status_pill_html(status: str) -> str:
    s = (status or "unknown").lower()
    cls = {"running": "running", "exited": "exited", "error": "exited", "restarting": "restarting"}.get(s, "unknown")
    return f'<span class="status-pill {cls}"><span class="d"></span>{s}</span>'


def containers_table_html(rows: list[dict]) -> str:
    if not rows:
        return html('<table class="ctable"><tbody><tr><td class="empty-cell">No containers to show.</td></tr></tbody></table>')
    body_parts = []
    for c in rows:
        ref = c.get("id") or c.get("short_id") or c.get("name") or ""
        offline = (c.get("machine_status") or "").lower() in ("offline",)
        row = html(f"""
        <tr>
        <td><div class="c-name">{c.get('name','?')}</div><div class="c-id">{str(ref)[:12]}</div></td>
        <td><span class="c-image">{c.get('image','?')}</span></td>
        <td><div class="c-machine {'is-offline' if offline else ''}"><span class="dot"></span>{c.get('machine','?')}</div></td>
        <td><span class="c-image">{format_ports(c.get('ports'))}</span></td>
        <td>{status_pill_html(c.get('status'))}</td>
        </tr>
        """)
        body_parts.append(row)
    body = "".join(body_parts)
    return html(f"""
    <table class="ctable">
    <thead><tr><th>Name</th><th>Image</th><th>Machine</th><th>Ports</th><th>Status</th></tr></thead>
    <tbody>{body}</tbody>
    </table>
    """)


# ═══════════════════════════════════════════════════════════════════════
#  DIALOGS
# ═══════════════════════════════════════════════════════════════════════
@st.dialog("Deploy containers", width="small")
def deploy_dialog(machines):
    st.markdown(
        html("""
        <div class="drawer-head">
        <div class="brand-mark" style="width:26px;height:26px;font-size:12px;">+</div>
        <div>
        <div class="drawer-title">Deploy a container</div>
        <div class="drawer-sub">Runs on a single machine · one replica per port you publish</div>
        </div>
        </div>
        """),
        unsafe_allow_html=True,
    )
    st.write("")
    image = st.text_input("Image", value="nginx:latest")
    names = [m.get("name") for m in machines] or ["(no machines registered)"]
    col1, col2 = st.columns(2)
    machine_choice = col1.selectbox("Machine", names)
    replicas = col2.number_input("Replicas", min_value=1, max_value=100, value=1)
    name_prefix = st.text_input("Name prefix (optional)", value="", placeholder="web")
    ports_raw = st.text_input("Publish ports — host:container", value="", placeholder="8080:80")
    st.caption("Leave empty for multiple replicas on one machine — Docker rejects duplicate host ports.")
    env_raw = st.text_area("Environment variables — one per line", value="", placeholder="APP_ENV=dev\nLOG_LEVEL=info", height=68)
    volumes_raw = st.text_area("Volumes — one per line", value="", placeholder="mydata:/data", height=68)
    network = st.text_input("Network (optional)", value="", placeholder="bridge")

    # Plain widgets (not st.form) on purpose: st.form submits on Enter
    # inside any text field, which fires the deploy before every field
    # is filled in. This only deploys when the button is actually clicked.
    submitted = st.button(f"Deploy {int(replicas)} replicas to {machine_choice}", type="primary", use_container_width=True)
    if submitted:
        ports = {}
        for line in ports_raw.splitlines():
            line = line.strip()
            if line and ":" in line:
                h, c = line.split(":", 1)
                ports[h.strip()] = c.strip()
        env = [l.strip() for l in env_raw.splitlines() if l.strip()]
        volumes = [l.strip() for l in volumes_raw.splitlines() if l.strip()]
        body = {
            "machine": machine_choice, "replicas": int(replicas), "image": image,
            "name_prefix": name_prefix or None, "env": env, "ports": ports,
            "volumes": volumes, "network": network or None,
        }
        data, err = api_post("/deployments", body)
        if err:
            st.error(f"Deploy failed: {err}")
        else:
            st.success(f"Deployed `{image}` ({replicas}x) to {machine_choice}")
            st.session_state.session_deploys.insert(0, {
                "time": datetime.now().strftime("%H:%M:%S"), "image": image,
                "machine": machine_choice, "replicas": replicas,
                "deployment_id": (data or {}).get("deployment_id"),
            })
            st.cache_data.clear()
            time.sleep(0.6)
            st.rerun()


@st.dialog("Logs", width="small")
def logs_dialog(ref, name):
    st.markdown(
        html(f"""
        <div class="drawer-head">
        <div>
        <div class="drawer-title">{name or ref}</div>
        <div class="drawer-sub">container logs</div>
        </div>
        </div>
        """),
        unsafe_allow_html=True,
    )
    tail = st.slider("Tail lines", 20, 500, 200)
    data, err = api_get(f"/containers/{ref}/logs", params={"tail": tail})
    if err:
        connection_issue("Logs", err)
    else:
        text = data.get("logs") if isinstance(data, dict) else str(data)
        st.markdown(html(f'<div class="term">{text or "(empty)"}</div>'), unsafe_allow_html=True)
    if st.button("↻ Refresh", key="logs_refresh"):
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════
#  DATA
# ═══════════════════════════════════════════════════════════════════════
machines, m_err = fetch_machines(api_base)
containers, c_err = fetch_containers(api_base)
connection_issue("Machines", m_err)
quiet_loading("Containers", c_err)

online_ct = sum(1 for m in machines if (m.get("status") or "").lower() in ("healthy", "online"))

# ═══════════════════════════════════════════════════════════════════════
#  TOP BAR
# ═══════════════════════════════════════════════════════════════════════
tb_left, tb_right = st.columns([3, 1])
with tb_left:
    st.markdown(
        html(f"""
        <div class="topbar">
        <div class="brand">
        <div class="brand-mark">D</div>
        <div><div class="brand-name">dockernts</div></div>
        <div class="brand-sub">home-lab · {api_base.replace('http://', '').replace('https://', '').replace('/api','')}</div>
        </div>
        <div class="cluster-pulse">
        <span class="pulse-dot"></span>
        {online_ct} / {len(machines)} machines online
        </div>
        </div>
        """),
        unsafe_allow_html=True,
    )
with tb_right:
    st.write("")
    if st.button("+ Deploy", type="primary", use_container_width=True):
        deploy_dialog(machines)

# ═══════════════════════════════════════════════════════════════════════
#  MACHINES
# ═══════════════════════════════════════════════════════════════════════
st.markdown(
    html(f"""
    <div class="section-head" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
    <div class="section-title">Machines <span class="count">{len(machines)}</span></div>
    <div class="section-note">heartbeat every 5s</div>
    </div>
    """),
    unsafe_allow_html=True,
)

if not machines:
    st.info("No machines registered yet.")
else:
    cols = st.columns(3)
    for i, m in enumerate(machines):
        with cols[i % 3]:
            st.markdown(machine_card_html(m), unsafe_allow_html=True)
            st.write("")

st.write("")

# ═══════════════════════════════════════════════════════════════════════
#  CONTAINERS
# ═══════════════════════════════════════════════════════════════════════
machine_names = [m.get("name") for m in machines if m.get("name")]
filter_options = ["All machines"] + machine_names

head_l, head_r = st.columns([2, 3])
with head_l:
    st.markdown(f'<div class="section-title">Containers <span class="count">{len(containers)}</span></div>', unsafe_allow_html=True)
with head_r:
    st.session_state.container_filter = st.radio(
        "Filter", filter_options,
        index=filter_options.index(st.session_state.container_filter) if st.session_state.container_filter in filter_options else 0,
        horizontal=True, label_visibility="collapsed",
    )

chosen = st.session_state.container_filter
filtered = containers if chosen == "All machines" else [c for c in containers if c.get("machine") == chosen]

st.markdown(f'<div class="table-card">{containers_table_html(filtered)}</div>', unsafe_allow_html=True)

# ---- manage panel: interactive controls kept beneath the display table ----
if filtered:
    st.markdown('<div class="manage-card">', unsafe_allow_html=True)
    st.markdown('<div class="manage-title">Manage a container</div>', unsafe_allow_html=True)
    labels = [f"{c.get('name','?')} · {c.get('machine','?')}" for c in filtered]
    pick = st.selectbox("Container", labels, label_visibility="collapsed")
    target = filtered[labels.index(pick)]
    ref = target.get("id") or target.get("short_id") or target.get("name")
    status_l = (target.get("status") or "").lower()

    b1, b2, b3, b4, b5 = st.columns(5)
    if b1.button("▶ Start", key=f"start_{ref}", disabled="running" in status_l, use_container_width=True):
        _, err = api_post(f"/containers/{ref}/start"); connection_issue("Start", err) if err else refresh()
    if b2.button("■ Stop", key=f"stop_{ref}", disabled="running" not in status_l, use_container_width=True):
        _, err = api_post(f"/containers/{ref}/stop"); connection_issue("Stop", err) if err else refresh()
    if b3.button("↻ Restart", key=f"restart_{ref}", use_container_width=True):
        _, err = api_post(f"/containers/{ref}/restart"); connection_issue("Restart", err) if err else refresh()
    if b4.button("🗑 Remove", key=f"rm_{ref}", use_container_width=True):
        _, err = api_delete(f"/containers/{ref}", params={"force": True}); connection_issue("Remove", err) if err else refresh()
    if b5.button("View logs", key=f"logs_{ref}", use_container_width=True):
        logs_dialog(ref, target.get("name"))
    st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
#  SESSION DEPLOYS
# ═══════════════════════════════════════════════════════════════════════
if st.session_state.session_deploys:
    with st.expander(f"Deployments this session ({len(st.session_state.session_deploys)})", expanded=False):
        st.table(st.session_state.session_deploys)

if st.session_state.auto_refresh:
    time.sleep(refresh_every)
    st.cache_data.clear()
    st.rerun()