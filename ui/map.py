"""
PyDeck map construction.

Building "height" for the 3D extrusion uses OSM's `height` tag when present
(a real, surveyed-ish value, though still OSM-community-sourced and not
authoritative) and falls back to a visual proxy derived from footprint area
otherwise. The fallback is for visual legibility only -- it is not a height
measurement, and is not presented as one in the tooltip.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pydeck as pdk

from ui.theme import MAP_CANDIDATE_RGBA, MAP_NON_CANDIDATE_RGBA, MAP_SELECTED_RGBA

# Colors are defined once in ui.theme (shared with the on-screen legend) so
# the map and its legend can never drift out of sync. Values unchanged in
# meaning from the original palette — only centralized.
SELECTED_COLOR = MAP_SELECTED_RGBA      # targeted for cool-roof coating
CANDIDATE_COLOR = MAP_CANDIDATE_RGBA    # eligible, not selected
NON_CANDIDATE_COLOR = MAP_NON_CANDIDATE_RGBA  # unused today (kept for parity)


def _extrusion_height(gdf: gpd.GeoDataFrame) -> np.ndarray:
    if "height" in gdf.columns:
        parsed = pd_to_numeric_safe(gdf["height"])
        proxy = np.sqrt(gdf["roof_area_m2"].clip(lower=1)) * 1.2
        return parsed.fillna(proxy).to_numpy()
    return (np.sqrt(gdf["roof_area_m2"].clip(lower=1)) * 1.2).to_numpy()


def pd_to_numeric_safe(series):
    import pandas as pd
    return pd.to_numeric(series, errors="coerce")


def build_deck(candidates_wgs84: gpd.GeoDataFrame, dark_mode: bool = True) -> pdk.Deck:
    """Build the 3D building map.

    `dark_mode` only selects the Mapbox basemap style tile (dark vs. light)
    to match the app's theme toggle — it has no effect on the underlying
    data, geometry, or `selected` values.
    """
    gdf = candidates_wgs84.copy()
    gdf["viz_height_m"] = _extrusion_height(gdf)
    gdf["status_label"] = np.where(
        gdf["selected"] == 1, "Selected for treatment", "Candidate (not selected)"
    )
    gdf["fill_color"] = gdf["selected"].apply(
        lambda s: SELECTED_COLOR if s == 1 else CANDIDATE_COLOR
    )

    layer = pdk.Layer(
        "GeoJsonLayer",
        gdf,
        opacity=0.85,
        stroked=True,
        filled=True,
        extruded=True,
        wireframe=True,
        get_elevation="viz_height_m",
        get_fill_color="fill_color",
        get_line_color=[20, 20, 20, 120],
        pickable=True,
        auto_highlight=True,
        highlight_color=[255, 255, 255, 90],
    )

    centroid = gdf.geometry.union_all().centroid
    view_state = pdk.ViewState(
        latitude=centroid.y, longitude=centroid.x, zoom=14.5, pitch=50, bearing=15
    )

    tooltip = {
        "html": (
            "<div style='font-family:Inter,sans-serif;line-height:1.5;'>"
            "<b>Building:</b> {osm_building_id}<br/>"
            "<b>Roof area:</b> {roof_area_m2} m²<br/>"
            "<b>LST (median, neighborhood-scale):</b> {lst_median_c}°C<br/>"
            "<b>Thermal anomaly:</b> +{lst_anomaly_c}°C<br/>"
            "<b>Status:</b> {status_label}<br/>"
            "<b>Est. cost:</b> ${intervention_cost_usd}"
            "</div>"
        ),
        "style": {
            "color": "white",
            "backgroundColor": "#111827",
            "borderRadius": "8px",
            "padding": "8px 10px",
            "fontSize": "0.82rem",
            "boxShadow": "0 4px 14px rgba(0,0,0,0.35)",
        },
    }

    basemap = (
        "mapbox://styles/mapbox/dark-v11" if dark_mode
        else "mapbox://styles/mapbox/light-v11"
    )

    return pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style=basemap,
        tooltip=tooltip,
    )
