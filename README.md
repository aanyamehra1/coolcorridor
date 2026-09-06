# CoolCorridor

Decision-support prototype: given a limited municipal budget, identify which
buildings would benefit most from reflective cool-roof treatment, combining
heat mitigation, energy savings, and social-equity priority.

## Quick start

```bash
python -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt
streamlit run app.py
```

By default, thermal data comes from **live Landsat 8/9 acquisition**
(`services/satellite.py`), which searches Microsoft Planetary Computer's
public STAC API for the most recent suitable, cloud-filtered Collection 2
Level-2 Surface Temperature scene covering the study area, QA-masks it, and
caches the result. No account or API key is required. If that fails or is
disabled, the app falls back through two more tiers, and always tells you
which one actually ran:

1. **Live satellite acquisition** — real, current Landsat data (default).
   Set `USE_REMOTE_SATELLITE_DATA=false` in a `.env` file (see
   `.env.example`) to skip this and go straight to tier 2 — useful offline
   or in CI.
2. **Local static raster file** — if you'd rather pin a specific scene,
   download a Landsat 8/9 Collection 2 Level-2 scene's `ST_B10.TIF` for your
   study area/date and place it at the path configured in
   `config/settings.py::StudyAreaConfig.raster_path`.
3. **Mock thermal data** — a clearly-flagged synthetic fallback ("MOCK" in
   the UI) so the rest of the pipeline can still be exercised end-to-end.

Other things to know:
- Social vulnerability is always synthetic until a real dataset is wired
  into `services/vulnerability.py::attach_vulnerability`.
- Building footprints are always real, live OSM data (via OSMnx) — the
  first run will make a network call to OpenStreetMap. By default this
  queries a bounding box over downtown Phoenix
  (`config/settings.py::StudyAreaConfig.bbox`), not a geocoded place name —
  see `services/osm.py` for why: many descriptive names (e.g. "Downtown, X")
  have no matching polygon boundary in OSM for Nominatim to resolve, even
  though the area and its buildings are mapped. Set `bbox=None` to fall back
  to geocoding `place_name` instead.
- "Live" satellite data is still the most recent *suitable* overpass, not
  real-time or continuous imagery — see `services/satellite.py` for why.

## Run tests

```bash
pip install pytest
pytest
```

## Architecture

```
app.py                    Streamlit entry point / wiring
config/settings.py        All tunable parameters in one place
services/
  satellite.py            Live Landsat 8/9 C2 L2 acquisition (Planetary Computer STAC)
  osm.py                  OSM building footprints (OSMnx)
  raster.py               Landsat LST loading, DN->Celsius, zonal stats, mock fallback
  spatial.py              Vector/raster CRS alignment
  metrics.py              Thermal anomaly, candidate filtering
  vulnerability.py        Social equity input (real-data hook + mock fallback)
  economics.py            Cost / energy savings / payback model
  optimization.py         Benefit score + 0/1 ILP (PuLP)
  pipeline.py             Orchestrates the above, Streamlit-independent
ui/
  dashboard.py            Sidebar controls, KPIs, selection table
  map.py                  PyDeck 3D map layer
utils/
  geo.py                  CRS-safe area/perimeter/compactness, UTM zone inference
  validation.py           Typed errors, quality-report accumulator
  logging.py              Logging setup
tests/                    pytest unit + formula tests (no network/raster needed)
```

## Optimization formulation

Binary decision variable per candidate building `x_i ∈ {0,1}`.

```
maximize   Σ benefit_i · x_i
subject to Σ cost_i · x_i ≤ budget
           x_i ∈ {0, 1}
```

`benefit_i = w_heat·norm(anomaly_i) + w_energy·norm(savings_i) + w_equity·norm(svi_i)`,
weights configurable in the sidebar and re-normalized to sum to 1. Each
component is min-max normalized across the candidate set before combining
(they live on very different scales — degrees C, dollars, a 0–1 index).

Solved as an integer linear program with PuLP/CBC — not a greedy heuristic,
and not silently downgraded to one if the solver fails; solver status
(`Optimal` / infeasible / etc.) is always surfaced to the user.

## Key assumptions (all editable in the sidebar or config/settings.py)

| Assumption | Default |
|---|---|
| Coating cost | $15/m² |
| Electricity rate | $0.16/kWh |
| Annual cooling factor | 18 kWh/m²/yr |
| Solar reflectance change (Δα) | 0.50 |

These are **model estimates**, not measured facts about any real building —
actual savings depend on HVAC system, insulation, occupancy, and climate,
none of which this prototype models.

## Scientific limitations (see docstrings in `services/satellite.py` and `services/raster.py` for detail)

- Live acquisition returns the most recent *suitable* Landsat overpass, not
  real-time or continuous imagery — Landsat 8/9's combined revisit interval
  is roughly 8 days, plus a processing delay before Collection 2 L2 is
  published. Never described as "real-time" in the UI.
- Landsat LST is **surface** temperature, not air temperature.
- The USGS Level-2 product's 30 m grid is a *resampling*, not 30 m native
  thermal resolution (native TIRS footprint is closer to 100 m). A
  building's "median LST" is a neighborhood-scale thermal signal, not a
  roof-specific measurement — this is stated in the UI, not just the code.
- Social vulnerability is synthetic until a real dataset (e.g. CDC/ATSDR
  SVI tracts) is spatially joined in; see `services/vulnerability.py`.
- 3D building heights use OSM's `height` tag when present, otherwise a
  visual-only proxy — never presented as a real height measurement.
