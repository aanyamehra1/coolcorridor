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

The original uploaded project shipped a single-feature
`phoenix_buildings.geojson` with fabricated, article-style building
attributes (a named real building, an invented surface temperature,
solar potential, etc.) under a schema (`footprint_area_sqm`,
`surface_temp_c`, `heat_vulnerability_index`, ...) that didn't match what
`optimization.py` actually read (`roof_area`, `lst_median`, `svi_score`).
That file has been removed rather than "fixed" — presenting fabricated
per-building data as if it were real is exactly the kind of scientific
misrepresentation this project's own spec warns against. Real data should
come from `services.osm.fetch_building_footprints` (live OSM) or, for
thermal data, a real Landsat scene; short of that, use the explicitly
labelled mock paths in `services.raster` / `services.vulnerability`.
