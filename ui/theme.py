"""
Visual theme for CoolCorridor — frontend presentation only.

Palette: Extracted exactly from the reference image.
Deep Teal, Turquoise, Taupe, Tan, Burnt Orange, and Deep Brown.
Both light and dark modes are built exclusively from these tones to create 
a premium, warm, climate-tech aesthetic without generic dashboard colours.
"""
from __future__ import annotations

import streamlit as st

THEME_STATE_KEY = "cc_dark_mode"

# ---------------------------------------------------------------------------
# Exact Palette from Reference Image
# ---------------------------------------------------------------------------
C_DEEP_TEAL = "#064E52"
C_TURQUOISE = "#0C7C81"
C_TAUPE     = "#AB907A"
C_TAN       = "#996D47"
C_ORANGE    = "#B35C1E"
C_BROWN     = "#7D3D1A"

# Tints for backgrounds and soft accents
C_OFF_WHITE = "#F8F6F4"
C_DARK_BG   = "#03282A"

DARK = {
    "bg": C_DARK_BG,
    "bg_elevated": C_DEEP_TEAL,
    "bg_card": C_DEEP_TEAL,
    "border": C_TAN,
    "text_primary": C_OFF_WHITE,
    "text_secondary": C_TAUPE,
    "accent": C_TURQUOISE,
    "accent_soft": "rgba(12, 124, 129, 0.15)",
    "heat": C_ORANGE,
    "heat_soft": "rgba(179, 92, 30, 0.15)",
    "danger": C_ORANGE,
    "success": C_TURQUOISE,
    "info": C_TAN,
}

LIGHT = {
    "bg": C_OFF_WHITE,
    "bg_elevated": "#FFFFFF",
    "bg_card": "#FFFFFF",
    "border": C_TAUPE,
    "text_primary": C_TAUPE,
    "text_secondary": C_BROWN,
    "accent": C_TURQUOISE,
    "accent_soft": "rgba(12, 124, 129, 0.10)",
    "heat": C_ORANGE,
    "heat_soft": "rgba(179, 92, 30, 0.10)",
    "danger": C_ORANGE,
    "success": C_TURQUOISE,
    "info": C_TAN,
}

# ---------------------------------------------------------------------------
# Map layer colors 
# ---------------------------------------------------------------------------
# Muted turquoise for eligible candidates
MAP_CANDIDATE_RGBA = [12, 124, 129, 140]       
MAP_NON_CANDIDATE_RGBA = [171, 144, 122, 60]    

# Gradient runs from warm tan to deep burnt orange/brown
MAP_SELECTED_LOW_RGBA = [153, 109, 71, 235]     
MAP_SELECTED_HIGH_RGBA = [179, 92, 30, 235]     


def selected_building_color(benefit_score: float, min_score: float, max_score: float) -> list:
    if benefit_score is None or max_score <= min_score:
        t = 1.0
    else:
        t = (benefit_score - min_score) / (max_score - min_score)
    t = max(0.0, min(1.0, t))
    low, high = MAP_SELECTED_LOW_RGBA, MAP_SELECTED_HIGH_RGBA
    return [int(low[i] + (high[i] - low[i]) * t) for i in range(4)]


def is_dark_mode() -> bool:
    return bool(st.session_state.get(THEME_STATE_KEY, True))


def palette() -> dict:
    return DARK if is_dark_mode() else LIGHT


def render_theme_toggle() -> bool:
    st.session_state.setdefault(THEME_STATE_KEY, True)
    
    st.markdown(
        """
        <style>
        .theme-toggle-container {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            padding: 1rem 0;
            width: 100%;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    col1, col2 = st.columns([10, 2])
    with col2:
        st.toggle("Dark Mode", key=THEME_STATE_KEY)
    
    return is_dark_mode()


def inject_css() -> None:
    p = palette()
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500;600&family=Montserrat:wght@300;400;500;600&display=swap');

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
            --cc-heat-soft: {p['heat_soft']};
            --cc-serif: 'Cinzel', serif;
            --cc-sans: 'Montserrat', sans-serif;
        }}

        html, body, [class*="css"] {{
            font-family: var(--cc-sans) !important;
            background-color: var(--cc-bg) !important;
            color: var(--cc-text);
        }}

        .stApp {{
            background: var(--cc-bg);
            color: var(--cc-text);
        }}

        .block-container {{
            max-width: 1200px;
            padding-top: 2rem;
            padding-bottom: 5rem;
        }}

        h1, h2, h3, .cc-hero-title {{
            font-family: var(--cc-serif) !important;
            color: var(--cc-text) !important;
            font-weight: 500 !important;
        }}

        p, span, label, .stMarkdown {{
            color: var(--cc-text);
            font-weight: 400;
        }}

        .stCaption, [data-testid="stCaptionContainer"] {{
            color: var(--cc-text-secondary) !important;
        }}

        /* Hide the sidebar completely as we moved to a scroll layout */
        [data-testid="collapsedControl"] {{
            display: none !important;
        }}

        /* Containers & Cards */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--cc-bg-card);
            border: 1px solid var(--cc-border) !important;
            border-radius: 4px !important;
            padding: 1.5rem;
        }}

        /* Metrics */
        [data-testid="stMetric"] {{
            background: var(--cc-bg-card);
            border: 1px solid var(--cc-border);
            border-radius: 4px;
            padding: 1.5rem;
            text-align: center;
        }}
        [data-testid="stMetricLabel"] {{
            color: var(--cc-text-secondary) !important;
            font-weight: 500 !important;
            font-size: 0.85rem !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            justify-content: center;
        }}
        [data-testid="stMetricValue"] {{
            color: var(--cc-text) !important;
            font-family: var(--cc-serif) !important;
            font-size: 2rem !important;
            justify-content: center;
        }}

        /* Progress Bar */
        [data-testid="stProgress"] div[role="progressbar"] > div {{
            background: linear-gradient(90deg, var(--cc-accent), var(--cc-heat)) !important;
        }}

        /* Expanders */
        [data-testid="stExpander"] {{
            border: 1px solid var(--cc-border) !important;
            border-radius: 4px !important;
            background: var(--cc-bg-card);
        }}

        /* Dataframes - Enforce Wrapping */
        [data-testid="stDataFrame"] {{
            border: 1px solid var(--cc-border);
            border-radius: 4px;
        }}
        [data-testid="stDataFrame"] td, 
        [data-testid="stDataFrame"] th,
        [data-testid="stDataFrame"] div[data-testid="StyledDataFrameDataCell"] {{
            white-space: normal !important;
            word-wrap: break-word !important;
            line-height: 1.5;
        }}

        /* Hero */
        .cc-hero {{
            text-align: center;
            padding: 5rem 0 4rem 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .cc-hero-title {{
            font-size: clamp(3rem, 6vw, 5rem);
            letter-spacing: 0.15em;
            margin: 0 0 1rem 0;
            color: var(--cc-text);
        }}
        .cc-hero-decor {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-top: 1rem;
        }}
        .cc-hero-line {{
            height: 1px;
            width: 60px;
            background-color: var(--cc-border);
        }}
        .cc-hero-dot {{
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: var(--cc-accent);
        }}
        .cc-hero-dot.heat {{
            background-color: var(--cc-heat);
        }}

        /* Legend */
        .cc-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 2rem;
            align-items: center;
            justify-content: center;
            background: var(--cc-bg-card);
            border: 1px solid var(--cc-border);
            border-radius: 4px;
            padding: 1rem 2rem;
            margin-top: 1rem;
            font-size: 0.85rem;
            color: var(--cc-text-secondary);
            font-family: var(--cc-sans);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .cc-legend-item {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        .cc-legend-swatch {{
            width: 12px;
            height: 12px;
            border-radius: 2px;
        }}
        .cc-legend-gradient {{
            width: 60px;
            height: 12px;
            border-radius: 2px;
        }}
        
        /* Sliders & Inputs */
        [data-baseweb="slider"] div[role="slider"] {{
            background-color: var(--cc-accent) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <div class="cc-hero">
            <h1 class="cc-hero-title">COOLCORRIDOR</h1>
            <div class="cc-hero-decor">
                <div class="cc-hero-line"></div>
                <div class="cc-hero-dot"></div>
                <div class="cc-hero-dot heat"></div>
                <div class="cc-hero-line"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_map_legend() -> None:
    def _rgba(c: list) -> str:
        r, g, b, a = c
        return f"rgba({r},{g},{b},{a / 255:.2f})"

    st.markdown(
        f"""
        <div class="cc-legend">
            <div class="cc-legend-item">
                <span class="cc-legend-gradient" style="background:linear-gradient(90deg, {_rgba(MAP_SELECTED_LOW_RGBA)}, {_rgba(MAP_SELECTED_HIGH_RGBA)});"></span>
                Selected (Low to High Benefit)
            </div>
            <div class="cc-legend-item">
                <span class="cc-legend-swatch" style="background:{_rgba(MAP_CANDIDATE_RGBA)}"></span>
                Eligible Candidate
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )