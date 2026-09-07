"""
PyDeck map construction.

Color is mapped accurately to the new teal-to-terracotta visual identity.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pydeck as pdk

from ui.theme import (
    MAP_CANDIDATE_RGBA,
    MAP_NON_CANDIDATE_RGBA,
    selected_building_color,
    C_DEEP_TEAL,
    C_OFF_WHITE,
    C_TAUPE,
)


def _extrusion_height(gdf: gpd.GeoDataFrame) -> np.ndarray:
    if "height" in gdf.columns:
        parsed = pd_to_numeric_safe(gdf["height"])
        proxy = np.sqrt(gdf["roof_area_m2"].clip(lower=1)) * 1.2
        return parsed.fillna(proxy).to_numpy()
    return (np.sqrt(gdf["roof_area_m2"].clip(lower=1)) * 1.2).to_numpy()


def pd_to_numeric_safe(series):
    import pandas as pd
    return pd.to_numeric(series, errors="coerce")


def _fill_colors(gdf: gpd.GeoDataFrame) -> list:
    has_benefit = "benefit_score" in gdf.columns
    selected_mask = gdf["selected"] == 1

    if has_benefit and selected_mask.any():
        selected_scores = gdf.loc[selected_mask, "benefit_score"]
        min_score = float(selected_scores.min())
        max_score = float(selected_scores.max())
    else:
        min_score = max_score = 0.0

    colors = []
    for is_selected, score in zip(
        selected_mask, gdf["benefit_score"] if has_benefit else [None] * len(gdf)
    ):
        if is_selected:
            colors.append(selected_building_color(score, min_score, max_score))
        else:
            colors.append(MAP_CANDIDATE_RGBA)
    return colors


def build_deck(candidates_wgs84: gpd.GeoDataFrame) -> pdk.Deck:
    gdf = candidates_wgs84.copy()
    gdf["viz_height_m"] = _extrusion_height(gdf)
    gdf["status_label"] = np.where(
        gdf["selected"] == 1, "Selected for treatment", "Candidate (not selected)"
    )
    gdf["fill_color"] = _fill_colors(gdf)

    layer = pdk.Layer(
        "GeoJsonLayer",
        gdf,
        opacity=0.9,
        stroked=True,
        filled=True,
        extruded=True,
        wireframe=True,
        get_elevation="viz_height_m",
        get_fill_color="fill_color",
        get_line_color=[255, 255, 255, 40],
        pickable=True,
        auto_highlight=True,
    )

    centroid = gdf.geometry.union_all().centroid
    view_state = pdk.ViewState(
        latitude=centroid.y, longitude=centroid.x, zoom=14.5, pitch=50, bearing=15
    )

    tooltip = {
        "html": (
            "<div style='font-family: Montserrat, sans-serif;'>"
            "<b style='color: #AB907A; font-size: 0.8rem; text-transform: uppercase;'>Building Info</b><br/>"
            "<span style='font-size: 0.9rem;'>"
            "<b>ID:</b> {osm_building_id}<br/>"
            "<b>Area:</b> {roof_area_m2} m²<br/>"
            "<b>LST (Median):</b> {lst_median_c}°C<br/>"
            "<b>Anomaly:</b> +{lst_anomaly_c}°C<br/>"
            "<b>Score:</b> {benefit_score}<br/>"
            "<b>Status:</b> {status_label}<br/>"
            "<b>Est. Cost:</b> ${intervention_cost_usd}"
            "</span></div>"
        ),
        "style": {
            "color": C_OFF_WHITE,
            "backgroundColor": C_DEEP_TEAL,
            "border": f"1px solid {C_TAUPE}",
            "borderRadius": "4px",
            "padding": "12px",
            "boxShadow": "0 4px 12px rgba(0,0,0,0.15)",
        },
    }

    return pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style="mapbox://styles/mapbox/dark-v11",
        tooltip=tooltip,
    )