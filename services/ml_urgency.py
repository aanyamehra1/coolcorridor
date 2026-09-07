"""
Machine Learning service for forecasting neighborhood-level heat vulnerability
and compound climate-equity urgency.

Analyzes multi-year historical panel data (Census Tracts) across thermal,
ecological, and socioeconomic indicators. Evaluates trajectories (slopes,
accelerations, and compound interactions) and fits an interpretable regularized
model to forecast forward urgency scores (0-1) and explainable risk drivers.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature Engineering Helpers
# ---------------------------------------------------------------------------

def compute_linear_slope(years: np.ndarray, values: np.ndarray) -> float:
    """Compute OLS linear slope beta = Cov(years, values) / Var(years)."""
    if len(years) < 2:
        return 0.0
    var_t = np.var(years)
    if var_t < 1e-9:
        return 0.0
    cov_ty = np.mean((years - np.mean(years)) * (values - np.mean(values)))
    return float(cov_ty / var_t)


def extract_trajectory_features(
    history_df: pd.DataFrame,
    current_year: int = 2023,
    lookback_years: int = 5,
) -> pd.DataFrame:
    """
    Extract longitudinal trend and interaction features per census tract
    over the lookback window [current_year - lookback_years, current_year].
    """
    min_year = current_year - lookback_years
    window_df = history_df[
        (history_df["year"] >= min_year) & (history_df["year"] <= current_year)
    ].copy()

    if len(window_df) == 0:
        raise ValueError(
            f"No historical observations found in year range [{min_year}, {current_year}]."
        )

    records = []
    grouped = window_df.groupby("tract_id")

    for tract_id, group in grouped:
        group_sorted = group.sort_values("year")
        yrs = group_sorted["year"].to_numpy()
        
        # Pull current observation
        curr_mask = group_sorted["year"] == current_year
        if not curr_mask.any():
            curr_row = group_sorted.iloc[-1]
            c_yr = int(curr_row["year"])
        else:
            curr_row = group_sorted[curr_mask].iloc[0]
            c_yr = current_year

        first_row = group_sorted.iloc[0]
        n_obs = len(group_sorted)

        # Thermal trajectory
        lst_vals = group_sorted["lst_median_c"].to_numpy()
        lst_slope = compute_linear_slope(yrs, lst_vals)
        anom_vals = group_sorted["lst_anomaly_c"].to_numpy()
        anom_drift = float(curr_row["lst_anomaly_c"] - first_row["lst_anomaly_c"])

        # Vegetation / canopy depletion
        ndvi_first = max(0.01, float(first_row.get("ndvi_mean", 0.15)))
        ndvi_curr = float(curr_row.get("ndvi_mean", 0.15))
        ndvi_delta_pct = float((ndvi_curr - ndvi_first) / ndvi_first)

        # Socioeconomic trajectory
        svi_first = float(first_row.get("svi_score", 0.5))
        svi_curr = float(curr_row.get("svi_score", 0.5))
        svi_delta = float(svi_curr - svi_first)

        poverty_curr = float(curr_row.get("poverty_rate", 0.20))
        poverty_first = float(first_row.get("poverty_rate", 0.20))
        poverty_trend = float(poverty_curr - poverty_first)

        elderly_curr = float(curr_row.get("elderly_pct", 0.12))

        # Extreme heat days
        if "extreme_heat_days" in group_sorted.columns:
            heat_days_slope = compute_linear_slope(yrs, group_sorted["extreme_heat_days"].to_numpy())
        else:
            heat_days_slope = 0.0

        # Compound and interaction features
        heat_poverty_interaction = max(0.0, lst_slope) * poverty_curr
        canopy_deprivation_ratio = max(0.0, float(curr_row["lst_anomaly_c"])) / (ndvi_curr + 0.01)
        elderly_heat_risk = elderly_curr * max(0.0, float(curr_row["lst_anomaly_c"]))

        tract_name = curr_row.get("tract_name", f"Tract {tract_id}")
        geometry = curr_row.get("geometry", None)

        record = {
            "tract_id": str(tract_id),
            "tract_name": tract_name,
            "year": c_yr,
            "n_obs": n_obs,
            "current_lst_c": float(curr_row["lst_median_c"]),
            "current_lst_anomaly_c": float(curr_row["lst_anomaly_c"]),
            "current_ndvi": ndvi_curr,
            "current_svi": svi_curr,
            "current_poverty_rate": poverty_curr,
            "current_elderly_pct": elderly_curr,
            "lst_slope_5yr": lst_slope,
            "lst_anomaly_drift": anom_drift,
            "ndvi_delta_pct": ndvi_delta_pct,
            "svi_delta": svi_delta,
            "poverty_trend": poverty_trend,
            "extreme_heat_days_slope": heat_days_slope,
            "heat_poverty_interaction": heat_poverty_interaction,
            "canopy_deprivation_ratio": canopy_deprivation_ratio,
            "elderly_heat_risk": elderly_heat_risk,
        }
        if geometry is not None:
            record["geometry"] = geometry
        records.append(record)

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Interpretable Model Implementation
# ---------------------------------------------------------------------------

FEATURE_COLUMNS = [
    "lst_slope_5yr",
    "lst_anomaly_drift",
    "ndvi_delta_pct",
    "svi_delta",
    "poverty_trend",
    "heat_poverty_interaction",
    "canopy_deprivation_ratio",
    "elderly_heat_risk",
]

FEATURE_LABELS = {
    "lst_slope_5yr": "Accelerating surface temperature",
    "lst_anomaly_drift": "Expanding thermal anomaly",
    "ndvi_delta_pct": "Loss of cooling canopy & vegetation",
    "svi_delta": "Rising social vulnerability",
    "poverty_trend": "Increasing poverty rate",
    "heat_poverty_interaction": "Compounding heat & economic disadvantage",
    "canopy_deprivation_ratio": "Treeless urban heat island exposure",
    "elderly_heat_risk": "Elevated senior population heat risk",
}


@dataclass
class ModelAttribution:
    tract_id: str
    urgency_score: float
    urgency_level: str
    primary_driver: str
    secondary_driver: str
    raw_score: float


class NeighborhoodUrgencyEngine:
    """
    Fits and runs an interpretable regression model for neighborhood heat urgency.
    Uses scikit-learn Ridge regression if available, with an analytical OLS/Ridge
    linear algebra fallback for zero-dependency portability.
    """

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.weights_: np.ndarray | None = None
        self.intercept_: float = 0.0
        self.mean_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None

    def _default_weights(self) -> np.ndarray:
        # Domain-informed prior weights (aligned with physical & climate equity principles)
        # 1. lst_slope_5yr: positive
        # 2. lst_anomaly_drift: positive
        # 3. ndvi_delta_pct: negative (loss of vegetation increases risk)
        # 4. svi_delta: positive
        # 5. poverty_trend: positive
        # 6. heat_poverty_interaction: positive
        # 7. canopy_deprivation_ratio: positive
        # 8. elderly_heat_risk: positive
        return np.array([0.25, 0.20, -0.20, 0.15, 0.15, 0.25, 0.20, 0.15], dtype=float)

    def fit(self, X: pd.DataFrame, y: np.ndarray | None = None) -> "NeighborhoodUrgencyEngine":
        X_mat = X[FEATURE_COLUMNS].to_numpy(dtype=float)
        self.mean_ = np.nanmean(X_mat, axis=0)
        self.scale_ = np.nanstd(X_mat, axis=0)
        self.scale_[self.scale_ < 1e-6] = 1.0

        if y is not None and len(y) == len(X_mat) and len(y) >= len(FEATURE_COLUMNS):
            try:
                from sklearn.linear_model import Ridge
                clf = Ridge(alpha=self.alpha)
                X_norm = (X_mat - self.mean_) / self.scale_
                clf.fit(X_norm, y)
                self.weights_ = clf.coef_
                self.intercept_ = float(clf.intercept_)
                return self
            except ImportError:
                # Analytical Ridge: beta = (X^T X + alpha * I)^(-1) X^T y
                X_norm = (X_mat - self.mean_) / self.scale_
                n_feats = X_norm.shape[1]
                reg_mat = np.dot(X_norm.T, X_norm) + self.alpha * np.eye(n_feats)
                rhs = np.dot(X_norm.T, (y - np.mean(y)))
                self.weights_ = np.linalg.solve(reg_mat, rhs)
                self.intercept_ = float(np.mean(y))
                return self

        # If no explicit training target labels passed, use domain-calibrated priors
        self.weights_ = self._default_weights()
        self.intercept_ = 0.5
        return self

    def predict_urgency(self, feat_df: pd.DataFrame) -> Tuple[pd.DataFrame, list[ModelAttribution]]:
        if self.weights_ is None:
            self.fit(feat_df)

        X_mat = feat_df[FEATURE_COLUMNS].to_numpy(dtype=float)
        mean = self.mean_ if self.mean_ is not None else np.nanmean(X_mat, axis=0)
        scale = self.scale_ if self.scale_ is not None else np.nanstd(X_mat, axis=0)
        scale[scale < 1e-6] = 1.0

        X_norm = (X_mat - mean) / scale
        raw_scores = np.dot(X_norm, self.weights_) + self.intercept_

        # Min-max normalize to [0, 1] range across neighborhoods
        lo, hi = float(np.min(raw_scores)), float(np.max(raw_scores))
        if hi - lo < 1e-6:
            normalized_scores = np.full_like(raw_scores, 0.5)
        else:
            normalized_scores = (raw_scores - lo) / (hi - lo)

        # Compute feature-level attributions: contribution = X_norm * weights
        contributions = X_norm * self.weights_

        attributions: list[ModelAttribution] = []
        out_df = feat_df.copy()
        out_df["neighborhood_urgency_score"] = np.round(normalized_scores, 3)

        urgency_levels = []
        primary_drivers = []
        secondary_drivers = []

        for i, row in out_df.iterrows():
            score = float(row["neighborhood_urgency_score"])
            if score >= 0.70:
                lvl = "High"
            elif score >= 0.40:
                lvl = "Moderate"
            else:
                lvl = "Low"
            urgency_levels.append(lvl)

            # Sort positive contributors (factors pushing urgency higher)
            c_row = contributions[i]
            sorted_idx = np.argsort(-c_row)
            top1_feat = FEATURE_COLUMNS[sorted_idx[0]]
            top2_feat = FEATURE_COLUMNS[sorted_idx[1]]

            p_driver = FEATURE_LABELS.get(top1_feat, top1_feat)
            s_driver = FEATURE_LABELS.get(top2_feat, top2_feat)

            primary_drivers.append(p_driver)
            secondary_drivers.append(s_driver)

            attributions.append(
                ModelAttribution(
                    tract_id=str(row["tract_id"]),
                    urgency_score=score,
                    urgency_level=lvl,
                    primary_driver=p_driver,
                    secondary_driver=s_driver,
                    raw_score=float(raw_scores[i]),
                )
            )

        out_df["urgency_level"] = urgency_levels
        out_df["primary_driver"] = primary_drivers
        out_df["secondary_driver"] = secondary_drivers

        return out_df, attributions


# ---------------------------------------------------------------------------
# High-Level Service API
# ---------------------------------------------------------------------------

def load_historical_panel(filepath: str) -> pd.DataFrame:
    """Load historical tract dataset from GeoJSON or Parquet."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Historical panel dataset not found at: {filepath}")

    try:
        import geopandas as gpd
        gdf = gpd.read_file(filepath)
        return gdf
    except Exception as exc:
        logger.warning("GeoPandas load failed (%s); reading as JSON.", exc)
        with open(filepath, "r") as f:
            data = json.load(f)
        features = data.get("features", [])
        rows = [feat.get("properties", {}) for feat in features]
        return pd.DataFrame(rows)


def run_neighborhood_urgency_pipeline(
    history_filepath: str,
    current_year: int = 2023,
    lookback_years: int = 5,
) -> Tuple[pd.DataFrame, list[dict]]:
    """
    Executes the end-to-end historical ML urgency pipeline:
    1. Loads historical neighborhood panel.
    2. Computes multi-year trend and interaction features.
    3. Fits interpretable urgency engine and computes normalized urgency scores.
    4. Returns enriched tract DataFrame and human-readable summary.
    """
    logger.info("Running ML neighborhood urgency pipeline on %s...", history_filepath)
    raw_df = load_historical_panel(history_filepath)
    feat_df = extract_trajectory_features(raw_df, current_year=current_year, lookback_years=lookback_years)

    engine = NeighborhoodUrgencyEngine()
    scored_df, attributions = engine.predict_urgency(feat_df)

    # Sort descending by urgency score
    scored_df = scored_df.sort_values("neighborhood_urgency_score", ascending=False).reset_index(drop=True)

    summary = [
        {
            "tract_id": a.tract_id,
            "tract_name": scored_df.loc[scored_df["tract_id"] == a.tract_id, "tract_name"].iloc[0]
            if "tract_name" in scored_df.columns else a.tract_id,
            "urgency_score": a.urgency_score,
            "urgency_level": a.urgency_level,
            "primary_driver": a.primary_driver,
            "secondary_driver": a.secondary_driver,
        }
        for a in sorted(attributions, key=lambda x: x.urgency_score, reverse=True)
    ]

    return scored_df, summary
