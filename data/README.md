# data/

Thermal data now has three tiers, tried in order by `services.pipeline`:

1. **Live satellite acquisition** (`services/satellite.py`) — by default the
   app searches Microsoft Planetary Computer's STAC API for the most recent
   suitable Landsat 8/9 Collection 2 Level-2 Surface Temperature scene
   covering the study area, QA/cloud-masks it, converts to Celsius, and
   caches the clipped result under `processed/satellite_cache/`. Set
   `USE_REMOTE_SATELLITE_DATA=false` (see `.env.example`) to skip this and
   fall through to tier 2.
2. **Local static raster file** — `raw/` — place a Landsat 8/9 Collection 2
   Level-2 surface-temperature GeoTIFF here (e.g. `..._ST_B10.TIF`) and point
   `config.settings.StudyAreaConfig.raster_path` at it. Used automatically if
   tier 1 is disabled or fails (no scenes found, network error, etc.).
3. **Mock thermal data** — if neither of the above is available, the app
   runs in **mock thermal mode** and clearly flags every number derived from
   it as synthetic.

Whichever tier actually ran is recorded on the pipeline result and surfaced
in the UI (never silently swapped in) -- see `services/pipeline.py`.

- `processed/` — cached intermediate outputs written by the pipeline
  (gitignored). Safe to delete; the app regenerates them.
- `processed/satellite_cache/` — day-bucketed cache of live satellite reads
  (GeoTIFF + JSON metadata), written by `services/satellite.py` (gitignored).
  Safe to delete; it will be refetched on demand.

The active pipeline uses `roof_area_m2`, `lst_median_c`, and `svi_score`.
No fabricated per-building dataset is committed. Real building data comes
from `services.osm.fetch_building_footprints` (live OSM), while thermal data
comes from a real Landsat scene when available or from the explicitly
labelled mock path in `services.raster`.
