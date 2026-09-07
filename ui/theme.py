"""
Visual theme for CoolCorridor — frontend presentation only.

Palette: Extracted exactly from the reference image.
Deep Teal, Turquoise, Taupe, Tan, Burnt Orange, and Deep Brown.
Both light and dark modes are built exclusively from these tones to create 
a premium, warm, climate-tech aesthetic without generic dashboard colours.
"""
from __future__ import annotations

from urllib.parse import quote as _urlquote

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


# ---------------------------------------------------------------------------
# Decorative motifs — airflow, foliage, corridor hero
# ---------------------------------------------------------------------------
# Kept intentionally spare: a handful of hand-tuned SVG fragments, reused as
# tiled backgrounds / pseudo-elements rather than new widgets, so the visual
# language stays a background texture and never competes with the data.

def _svg_data_uri(svg: str) -> str:
    return "data:image/svg+xml," + _urlquote(" ".join(svg.split()))


# Seamless tile of faint, wind-like contour lines. Repeated + slowly panned
# to suggest air moving through the page without ever reading as "busy".
_WIND_TILE_SVG = """
<svg xmlns='http://www.w3.org/2000/svg' width='260' height='130'>
  <path d='M-10 28 Q 22 10 55 28 T 120 28 T 185 28 T 250 28 T 315 28'
        fill='none' stroke='#0C7C81' stroke-width='1' stroke-opacity='0.09'/>
  <path d='M-10 66 Q 22 84 55 66 T 120 66 T 185 66 T 250 66 T 315 66'
        fill='none' stroke='#AB907A' stroke-width='1' stroke-opacity='0.08'/>
  <path d='M-10 104 Q 22 90 55 104 T 120 104 T 185 104 T 250 104 T 315 104'
        fill='none' stroke='#0C7C81' stroke-width='0.75' stroke-opacity='0.06'/>
</svg>
"""

# A small cluster of overlapping leaf silhouettes, tucked into two opposing
# corners of the viewport via ::before / ::after — "a few", not a border.
_LEAF_CLUSTER_SVG = """
<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150'>
  <path d='M18 132 C 6 92 24 46 68 22 C 56 66 46 100 18 132 Z'
        fill='#0C7C81' fill-opacity='0.16'/>
  <path d='M40 140 C 34 106 56 74 94 58 C 82 92 70 118 40 140 Z'
        fill='#AB907A' fill-opacity='0.13'/>
  <path d='M64 24 C 58 14 46 10 36 14' fill='none' stroke='#996D47'
        stroke-width='1.4' stroke-opacity='0.22' stroke-linecap='round'/>
  <path d='M86 62 C 80 50 66 44 54 47' fill='none' stroke='#996D47'
        stroke-width='1.2' stroke-opacity='0.18' stroke-linecap='round'/>
</svg>
"""

# Tiny wind-swirl ornament used as a between-section marker on dividers.
_DIVIDER_SWIRL_SVG = """
<svg xmlns='http://www.w3.org/2000/svg' width='34' height='34' viewBox='0 0 34 34'>
  <path d='M4 13 Q 11 4 17 13 T 30 13' fill='none' stroke='#0C7C81'
        stroke-width='1.4' stroke-linecap='round' stroke-opacity='0.55'/>
  <path d='M4 21 Q 11 30 17 21 T 30 21' fill='none' stroke='#AB907A'
        stroke-width='1.2' stroke-linecap='round' stroke-opacity='0.5'/>
</svg>
"""

WIND_TILE_URI = _svg_data_uri(_WIND_TILE_SVG)
LEAF_CLUSTER_URI = _svg_data_uri(_LEAF_CLUSTER_SVG)
DIVIDER_SWIRL_URI = _svg_data_uri(_DIVIDER_SWIRL_SVG)


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

        /* ---- Airflow / foliage motifs -------------------------------- */
        @keyframes cc-air-drift {{
            from {{ background-position: 0 0; }}
            to   {{ background-position: 260px 0; }}
        }}
        @keyframes cc-leaf-sway {{
            0%, 100% {{ transform: rotate(0deg) translateY(0); }}
            50%      {{ transform: rotate(2.5deg) translateY(-4px); }}
        }}
        @keyframes cc-flow {{
            to {{ stroke-dashoffset: -220; }}
        }}
        @keyframes cc-fleck-drift {{
            0%   {{ transform: translate(0, 0) rotate(0deg); opacity: 0.45; }}
            50%  {{ transform: translate(16px, -9px) rotate(10deg); opacity: 0.85; }}
            100% {{ transform: translate(0, 0) rotate(0deg); opacity: 0.45; }}
        }}

        .stApp {{
            background-image: url("{WIND_TILE_URI}");
            background-repeat: repeat;
            background-size: 260px 130px;
            animation: cc-air-drift 60s linear infinite;
        }}
        .stApp::before, .stApp::after {{
            content: "";
            position: fixed;
            width: 130px;
            height: 130px;
            background-image: url("{LEAF_CLUSTER_URI}");
            background-repeat: no-repeat;
            background-size: contain;
            pointer-events: none;
            z-index: 0;
            animation: cc-leaf-sway 11s ease-in-out infinite;
        }}
        .stApp::before {{ top: -16px; left: -16px; }}
        .stApp::after   {{ bottom: -16px; right: -16px; transform: rotate(180deg); animation-delay: 2.2s; }}

        [data-testid="stAppViewContainer"] {{ position: relative; z-index: 1; }}

        /* Organic divider ornament between sections */
        hr {{
            border: none !important;
            height: 1px;
            margin: 3rem 0 !important;
            background: linear-gradient(90deg, transparent, var(--cc-border) 50%, transparent) !important;
            position: relative;
        }}
        hr::after {{
            content: "";
            position: absolute;
            top: 50%; left: 50%;
            width: 30px; height: 30px;
            transform: translate(-50%, -50%);
            background-image: url("{DIVIDER_SWIRL_URI}");
            background-repeat: no-repeat;
            background-size: contain;
            background-color: var(--cc-bg);
            padding: 0 0.5rem;
        }}

        @media (max-width: 640px) {{
            .stApp::before, .stApp::after {{ width: 70px; height: 70px; opacity: 0.7; }}
            .cc-hero {{ padding: 2.5rem 0 2rem 0 !important; }}
            .cc-hero-visual svg {{ max-height: 110px; }}
        }}

        @media (prefers-reduced-motion: reduce) {{
            .stApp, .cc-wind-line, .cc-leaf-fleck, .stApp::before, .stApp::after {{
                animation: none !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
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
            background-color: var(--cc-bg);
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
            padding: 3rem 0 4rem 0;
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

        /* Hero corridor visual */
        .cc-hero-visual {{
            width: 100%;
            max-width: 560px;
            margin: 0 auto;
        }}
        .cc-hero-visual svg {{
            width: 100%;
            height: auto;
            max-height: 170px;
            display: block;
        }}
        .cc-wind-line {{
            stroke-dasharray: 5 9;
            animation: cc-flow 16s linear infinite;
        }}
        .cc-wind-line.slow {{ animation-duration: 24s; }}
        .cc-wind-line.slower {{ animation-duration: 34s; }}
        .cc-leaf-fleck {{
            animation: cc-fleck-drift 8s ease-in-out infinite;
            transform-origin: center;
        }}
        .cc-leaf-fleck:nth-of-type(2) {{ animation-delay: 1.4s; }}
        .cc-leaf-fleck:nth-of-type(3) {{ animation-delay: 2.8s; }}
        .cc-leaf-fleck:nth-of-type(4) {{ animation-delay: 0.6s; }}

        /* Section transition ornament — sits above cards for organic continuity */
        .cc-flow-divider {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.75rem;
            margin: 0.5rem 0 1.5rem 0;
            opacity: 0.7;
        }}
        .cc-flow-divider svg {{ width: 120px; height: 14px; }}

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


_HERO_VISUAL_SVG = """
<div class="cc-hero-visual">
<svg viewBox="0 0 900 210" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Illustration of a tree-lined corridor with cooling airflow">
  <defs>
    <linearGradient id="ccCanopy" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0C7C81"/>
      <stop offset="100%" stop-color="#064E52"/>
    </linearGradient>
  </defs>

  <!-- ground -->
  <path d="M0 178 Q 225 158 450 176 T 900 178" fill="none" stroke="#AB907A" stroke-width="1.5" stroke-opacity="0.35"/>

  <!-- left trees -->
  <g opacity="0.92">
    <line x1="120" y1="176" x2="128" y2="108" stroke="#996D47" stroke-width="4" stroke-linecap="round"/>
    <ellipse cx="122" cy="86" rx="46" ry="40" fill="url(#ccCanopy)"/>
    <line x1="205" y1="178" x2="211" y2="128" stroke="#7D3D1A" stroke-width="3" stroke-linecap="round"/>
    <ellipse cx="208" cy="112" rx="32" ry="28" fill="#0C7C81" opacity="0.85"/>
  </g>

  <!-- right trees (mirrored) -->
  <g opacity="0.92">
    <line x1="780" y1="176" x2="772" y2="108" stroke="#996D47" stroke-width="4" stroke-linecap="round"/>
    <ellipse cx="778" cy="86" rx="46" ry="40" fill="url(#ccCanopy)"/>
    <line x1="695" y1="178" x2="689" y2="128" stroke="#7D3D1A" stroke-width="3" stroke-linecap="round"/>
    <ellipse cx="692" cy="112" rx="32" ry="28" fill="#0C7C81" opacity="0.85"/>
  </g>

  <!-- flowing air through the corridor -->
  <path class="cc-wind-line" d="M40 96 Q 160 76 280 96 T 520 96 T 760 96 T 900 96" fill="none" stroke="#F8F6F4" stroke-width="1.6" stroke-opacity="0.55" stroke-linecap="round"/>
  <path class="cc-wind-line slow" d="M20 122 Q 150 140 270 122 T 510 122 T 750 122 T 900 122" fill="none" stroke="#AB907A" stroke-width="1.4" stroke-opacity="0.4" stroke-linecap="round"/>
  <path class="cc-wind-line slower" d="M60 68 Q 180 52 300 68 T 540 68 T 780 68 T 900 68" fill="none" stroke="#0C7C81" stroke-width="1.2" stroke-opacity="0.4" stroke-linecap="round"/>

  <!-- drifting leaf flecks -->
  <path class="cc-leaf-fleck" d="M300 100 q 8 -10 16 0 q -8 10 -16 0 Z" fill="#996D47" opacity="0.5"/>
  <path class="cc-leaf-fleck" d="M430 118 q 7 -9 14 0 q -7 9 -14 0 Z" fill="#0C7C81" opacity="0.55"/>
  <path class="cc-leaf-fleck" d="M560 88 q 7 -9 14 0 q -7 9 -14 0 Z" fill="#AB907A" opacity="0.5"/>
  <path class="cc-leaf-fleck" d="M660 112 q 6 -8 12 0 q -6 8 -12 0 Z" fill="#996D47" opacity="0.45"/>
</svg>
</div>
"""


def render_header() -> None:
    st.markdown(
f"""
<div class="cc-hero">
{_HERO_VISUAL_SVG}
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


def render_flow_divider() -> None:
    """Small airflow ornament for visual continuity between sections.

    Optional — purely decorative. Existing ``st.markdown("---")`` dividers
    already pick up the organic swirl via CSS, so this is only for spots
    that want a lighter-weight transition than a full rule.
    """
    st.markdown(
        """
<div class="cc-flow-divider" aria-hidden="true">
    <svg viewBox="0 0 120 14" xmlns="http://www.w3.org/2000/svg">
        <path d="M2 7 Q 20 1 38 7 T 74 7 T 110 7"
                fill="none" stroke="#0C7C81" stroke-width="1.2"
                stroke-opacity="0.45" class="cc-wind-line"/>
    </svg>
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