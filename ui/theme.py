"""
Visual theme for CoolCorridor — frontend presentation only.

This module owns every color, font, and CSS rule in the app. It has no
knowledge of buildings, LST, PuLP, or any pipeline data — it only decides
how things *look*. That separation is deliberate: nothing here should ever
need to change when the scoring model, satellite acquisition, or
optimization logic changes, and nothing in services/ or utils/ should ever
need to import this module.

Theme state (light vs. dark) is stored in `st.session_state` under
THEME_STATE_KEY, so it persists for the lifetime of the browser session
(Streamlit's normal session-state behavior) without touching any pipeline
caching or config.
"""
from __future__ import annotations

import streamlit as st

THEME_STATE_KEY = "cc_dark_mode"

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
# Chosen for: a "climate-tech" feel (deep teal/cyan = cool/mitigation,
# amber = heat/priority) and AA-level contrast in both modes.
DARK = {
    "bg": "#0B1220",
    "bg_elevated": "#121A2B",
    "bg_card": "#141D30",
    "border": "#223049",
    "text_primary": "#E7ECF3",
    "text_secondary": "#93A4BD",
    "accent": "#2DD4BF",       # teal — primary brand accent
    "accent_soft": "rgba(45, 212, 191, 0.14)",
    "heat": "#FBBF24",         # amber — heat / selected-for-treatment
    "danger": "#F87171",
    "success": "#34D399",
    "info": "#38BDF8",
}

LIGHT = {
    "bg": "#F6F8FB",
    "bg_elevated": "#FFFFFF",
    "bg_card": "#FFFFFF",
    "border": "#E2E8F0",
    "text_primary": "#0F172A",
    "text_secondary": "#51617A",
    "accent": "#0D9488",
    "accent_soft": "rgba(13, 148, 136, 0.10)",
    "heat": "#D97706",
    "danger": "#DC2626",
    "success": "#059669",
    "info": "#0284C7",
}

# Shared with ui/map.py so the legend and the actual map layer can never
# drift out of sync — one source of truth for "what color means what".
MAP_SELECTED_RGBA = [251, 191, 36, 235]     # amber — targeted for treatment
MAP_CANDIDATE_RGBA = [45, 212, 191, 130]    # teal — eligible, not selected
MAP_NON_CANDIDATE_RGBA = [120, 130, 145, 70]  # unused today (kept for parity)


def is_dark_mode() -> bool:
    return bool(st.session_state.get(THEME_STATE_KEY, True))


def palette() -> dict:
    return DARK if is_dark_mode() else LIGHT


def render_theme_toggle() -> bool:
    """Sidebar light/dark switch. Call once, before any other UI renders,
    so the CSS injected afterward reflects the current choice. Persists via
    `st.session_state` for the rest of the browser session.
    """
    st.session_state.setdefault(THEME_STATE_KEY, True)
    with st.sidebar:
        col_label, col_toggle = st.columns([3, 1], vertical_alignment="center")
        col_label.markdown(
            "<span style='font-size:0.85rem;font-weight:600;"
            "color:var(--cc-text-secondary);'>🌓 Dark mode</span>",
            unsafe_allow_html=True,
        )
        col_toggle.toggle(
            "Dark mode", key=THEME_STATE_KEY, label_visibility="collapsed"
        )
        st.markdown("<div style='height:0.35rem'></div>", unsafe_allow_html=True)
    return is_dark_mode()


def inject_css() -> None:
    """Inject CSS variables + component restyling for the current theme.

    Every rule targets Streamlit's existing DOM (via stable `data-testid`
    hooks) or general HTML elements — this never changes what a widget
    *does*, only how it's painted. Re-run on every rerun so switching the
    toggle takes effect immediately.
    """
    p = palette()
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {{
            --cc-bg: {p['bg']};
            --cc-bg-elevated: {p['bg_elevated']};
            --cc-bg-card: {p['bg_card']};
            --cc-border: {p['border']};
            --cc-text: {p['text_primary']};
            --cc-text-secondary: {p['text_secondary']};
            --cc-accent: {p['accent']};
            --cc-accent-soft: {p['accent_soft']};
            --cc-heat: {p['heat']};
            --cc-danger: {p['danger']};
            --cc-success: {p['success']};
            --cc-info: {p['info']};
        }}

        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI',
                         Roboto, Helvetica, Arial, sans-serif !important;
        }}

        .stApp {{
            background: var(--cc-bg);
            color: var(--cc-text);
        }}

        /* Slightly narrower, more readable max width on very wide desktop
           monitors, without breaking the "wide" layout on normal screens. */
        .block-container {{
            max-width: 1400px;
            padding-top: 1.5rem;
        }}

        h1, h2, h3 {{
            color: var(--cc-text) !important;
            font-weight: 700 !important;
            letter-spacing: -0.01em;
        }}
        p, span, label, .stMarkdown {{
            color: var(--cc-text);
        }}
        .stCaption, [data-testid="stCaptionContainer"] {{
            color: var(--cc-text-secondary) !important;
        }}

        /* Sidebar */
        [data-testid="stSidebar"] {{
            background: var(--cc-bg-elevated);
            border-right: 1px solid var(--cc-border);
        }}
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {{
            font-size: 1rem !important;
        }}

        /* Bordered containers used to group sidebar sections into cards */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--cc-bg-card);
            border: 1px solid var(--cc-border) !important;
            border-radius: 12px !important;
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }}
        [data-testid="stVerticalBlockBorderWrapper"]:hover {{
            border-color: var(--cc-accent) !important;
            box-shadow: 0 0 0 1px var(--cc-accent-soft);
        }}

        /* Metric cards */
        [data-testid="stMetric"] {{
            background: var(--cc-bg-card);
            border: 1px solid var(--cc-border);
            border-radius: 12px;
            padding: 0.9rem 1rem 0.7rem 1rem;
            transition: transform 0.15s ease, box-shadow 0.15s ease,
                        border-color 0.15s ease;
        }}
        [data-testid="stMetric"]:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 18px rgba(0,0,0,0.18);
            border-color: var(--cc-accent);
        }}
        [data-testid="stMetricLabel"] {{
            color: var(--cc-text-secondary) !important;
            font-weight: 600 !important;
            font-size: 0.78rem !important;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }}
        [data-testid="stMetricValue"] {{
            color: var(--cc-text) !important;
            font-weight: 700 !important;
        }}

        /* Alerts */
        .stAlert {{
            border-radius: 10px !important;
            border: 1px solid var(--cc-border) !important;
        }}

        /* Expanders */
        [data-testid="stExpander"] {{
            border: 1px solid var(--cc-border) !important;
            border-radius: 10px !important;
            background: var(--cc-bg-card);
            overflow: hidden;
        }}
        [data-testid="stExpander"] summary {{
            transition: background 0.15s ease;
        }}
        [data-testid="stExpander"] summary:hover {{
            background: var(--cc-accent-soft);
        }}

        /* Status widget (pipeline loading stages) */
        [data-testid="stStatusWidget"] {{
            border: 1px solid var(--cc-border) !important;
            border-radius: 10px !important;
            background: var(--cc-bg-card);
        }}

        /* Dataframes */
        [data-testid="stDataFrame"] {{
            border: 1px solid var(--cc-border);
            border-radius: 10px;
            overflow: hidden;
        }}

        /* Sliders / number inputs: accent color */
        [data-baseweb="slider"] div[role="slider"] {{
            background-color: var(--cc-accent) !important;
        }}
        .stSlider [data-testid="stTickBarMin"],
        .stSlider [data-testid="stTickBarMax"] {{
            color: var(--cc-text-secondary) !important;
        }}

        hr {{
            border-color: var(--cc-border) !important;
        }}

        /* Hero header */
        .cc-hero {{
            display: flex;
            align-items: center;
            gap: 0.9rem;
            padding: 0.25rem 0 1.1rem 0;
            border-bottom: 1px solid var(--cc-border);
            margin-bottom: 1.4rem;
        }}
        .cc-hero-icon {{
            font-size: 2.1rem;
            line-height: 1;
        }}
        .cc-hero-title {{
            font-size: 1.6rem;
            font-weight: 700;
            color: var(--cc-text);
            margin: 0;
            letter-spacing: -0.01em;
        }}
        .cc-hero-sub {{
            font-size: 0.92rem;
            color: var(--cc-text-secondary);
            margin-top: 0.15rem;
        }}
        .cc-badge {{
            display: inline-block;
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--cc-accent);
            background: var(--cc-accent-soft);
            border: 1px solid var(--cc-accent);
            border-radius: 999px;
            padding: 0.15rem 0.55rem;
            margin-left: 0.6rem;
            vertical-align: middle;
        }}

        /* Map legend */
        .cc-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.2rem;
            align-items: center;
            background: var(--cc-bg-card);
            border: 1px solid var(--cc-border);
            border-radius: 10px;
            padding: 0.6rem 1rem;
            margin-top: 0.6rem;
            font-size: 0.85rem;
            color: var(--cc-text-secondary);
        }}
        .cc-legend-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .cc-legend-swatch {{
            width: 14px;
            height: 14px;
            border-radius: 4px;
            display: inline-block;
            border: 1px solid rgba(0,0,0,0.15);
        }}

        /* Section card wrapper (main content) */
        .cc-section-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--cc-text);
            margin: 1.6rem 0 0.5rem 0;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    """Styled hero header, replacing a plain st.title/st.caption pair."""
    st.markdown(
        """
        <div class="cc-hero">
            <div class="cc-hero-icon">🏙️</div>
            <div>
                <div class="cc-hero-title">CoolCorridor
                    <span class="cc-badge">Prototype</span>
                </div>
                <div class="cc-hero-sub">
                    Decision support for prioritizing reflective cool-roof
                    interventions under a limited municipal budget.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_map_legend() -> None:
    """Legend for ui.map.build_deck's fill colors. Kept in sync via the
    shared MAP_*_RGBA constants imported by both modules.
    """
    def _rgba(c: list[int]) -> str:
        r, g, b, a = c
        return f"rgba({r},{g},{b},{a / 255:.2f})"

    st.markdown(
        f"""
        <div class="cc-legend">
            <div class="cc-legend-item">
                <span class="cc-legend-swatch" style="background:{_rgba(MAP_SELECTED_RGBA)}"></span>
                Selected for treatment
            </div>
            <div class="cc-legend-item">
                <span class="cc-legend-swatch" style="background:{_rgba(MAP_CANDIDATE_RGBA)}"></span>
                Eligible candidate (not selected)
            </div>
            <div class="cc-legend-item" style="margin-left:auto;color:var(--cc-text-secondary);">
                Drag to rotate · scroll to zoom · click a building for details
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
