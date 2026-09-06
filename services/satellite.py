"""
Programmatic Landsat 8/9 Collection 2 Level-2 Surface Temperature acquisition.

This module owns everything the app spec calls "satellite acquisition":
searching scenes, filtering by date/cloud cover/platform, retrieving the
Surface Temperature asset, applying QA/cloud masking, converting to Celsius,
clipping to the study area, and caching the result to disk. It does NOT
touch building geometries, zonal statistics, or the optimizer -- see
services.spatial / services.raster / services.pipeline for that boundary.

Data source: the Microsoft Planetary Computer STAC API
(https://planetarycomputer.microsoft.com/api/stac/v1), collection
"landsat-c2-l2". This was chosen over Google Earth Engine because:
  - no account/allowlisting/OAuth flow is required for read access --
    assets are anonymously readable Cloud-Optimized GeoTIFFs on Azure Blob
    Storage, signed on the fly with a short-lived SAS token via the
    `planetary-computer` package (`pc.sign`), which needs no credentials
    for the request volume a hackathon/prototype demo generates;
  - it's a small, stable, well-documented HTTP API (`requests` + JSON),
    which is easier to reason about, mock in tests, and keep working
    across environments than a heavier SDK;
  - Landsat Collection 2 Level-2 is indexed there with the exact
    "eo:cloud_cover" / "platform" fields this module filters on.

An optional `PC_SDK_SUBSCRIPTION_KEY` environment variable raises Planetary
Computer's anonymous rate limit if you hit it during heavy use -- it is
never required for normal operation and is never hard-coded (see
config.settings.SatelliteConfig / .env.example).

IMPORTANT — accuracy notes baked into this module (do not "simplify" away):
  - "Latest suitable scene" means the most recent Landsat 8/9 overpass that
    meets the quality filters, not live/continuous imagery. Landsat's
    revisit interval is ~16 days per satellite (~8 days combined for two
    satellites), plus a processing delay before Collection 2 L2 is
    published. Never describe this as "real-time" in the UI.
  - TIRS' native thermal ground sample distance is ~100 m; the Level-2 ST
    product is delivered on a 30 m grid to align with the optical bands.
    That resampling does not manufacture new 30 m thermal detail. Anything
    surfaced from this module should be described as a neighborhood-scale
    surface-temperature estimate, not a precise 30 m measurement.
  - A composite (Mode B) is a per-pixel median across *cloud-masked*
    scenes, not a plain mean of everything returned by the search --
    masked/nodata pixels are excluded per-scene before combining.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

import numpy as np
import rasterio
import requests
from pyproj import Transformer
from rasterio.transform import Affine
from rasterio.windows import Window, from_bounds

from services.raster import LANDSAT_C2_L2_ST_OFFSET, LANDSAT_C2_L2_ST_SCALE, digital_number_to_celsius

logger = logging.getLogger(__name__)

ST_ASSET_CANDIDATES = ["lwir11", "st", "surface_temperature", "ST_B10"]
QA_ASSET_CANDIDATES = ["qa_pixel", "QA_PIXEL"]

# USGS Landsat Collection 2 QA_PIXEL bit positions (see the Landsat Collection
# 2 Level-2 Science Product Guide). A pixel is treated as unusable for a
# thermal analysis if ANY of these are set.
_QA_BIT_FILL = 0
_QA_BIT_DILATED_CLOUD = 1
_QA_BIT_CIRRUS = 2
_QA_BIT_CLOUD = 3
_QA_BIT_CLOUD_SHADOW = 4


class SatelliteServiceError(Exception):
    """Base class for all satellite-acquisition failures. Messages are
    written to be shown directly to a non-technical user."""


class NoScenesFoundError(SatelliteServiceError):
    pass


class SceneRetrievalError(SatelliteServiceError):
    pass


class AllPixelsMaskedError(SatelliteServiceError):
    pass


class RemoteDataDisabled(SatelliteServiceError):
    """Raised when use_remote_satellite_data=False -- the caller (pipeline)
    should catch this and use the local dev raster / mock path instead,
    not treat it as an unexpected failure."""


@dataclass(frozen=True)
class SceneMetadata:
    scene_id: str
    platform: str                  # "landsat-8" | "landsat-9"
    collection: str                # "landsat-c2-l2"
    product: str                   # "L2SP Surface Temperature"
    acquisition_datetime: str      # ISO 8601, from STAC `properties.datetime`
    processing_datetime: str | None  # ISO 8601, from STAC `properties.created`, if present
    cloud_cover_pct: float
    bbox: tuple


@dataclass
class SatelliteFetchResult:
    raster_path: str               # local, already Celsius, QA-masked, clipped GeoTIFF
    scenes: list                   # list[SceneMetadata] -- 1 for a single scene, >1 for a composite
    mode: str                      # "latest" | "date_range" | "composite" | "local_dev" | "mock"
    source: str                    # human-readable data source label for the UI
    is_cached: bool
    is_mock: bool
    study_area_bbox: tuple
    limitations: list              # short, user-facing caveat strings for the UI


def _stac_headers(subscription_key: str | None) -> dict:
    headers = {"Content-Type": "application/json"}
    if subscription_key:
        headers["Ocp-Apim-Subscription-Key"] = subscription_key
    return headers


def _search_scenes(bbox: tuple, config) -> list[dict]:
    """POST a STAC search against the configured API and return raw item dicts.

    Raises NoScenesFoundError / SatelliteServiceError with a message that's
    safe to show a non-technical user -- never lets a bare requests
    exception or a stack trace reach the UI.
    """
    if config.mode == "latest":
        end = date.today()
        start = end - timedelta(days=config.lookback_days)
        datetime_str = f"{start.isoformat()}/{end.isoformat()}"
    elif config.mode == "date_range":
        if not config.date_range:
            raise SatelliteServiceError(
                "Date-range mode is selected but no start/end date was provided."
            )
        datetime_str = f"{config.date_range[0]}/{config.date_range[1]}"
    else:
        raise SatelliteServiceError(f"Unknown satellite acquisition mode: {config.mode!r}")

    payload = {
        "collections": [config.collection],
        "bbox": list(bbox),
        "datetime": datetime_str,
        "query": {
            "eo:cloud_cover": {"lt": config.max_cloud_cover_pct},
            "platform": {"in": list(config.platforms)},
        },
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        "limit": 50,
    }

    try:
        resp = requests.post(
            f"{config.stac_api_url.rstrip('/')}/search",
            json=payload,
            headers=_stac_headers(config.subscription_key),
            timeout=config.request_timeout_s,
        )
    except requests.Timeout as exc:
        raise SatelliteServiceError(
            "The Landsat scene search timed out. Check your network connection and try again."
        ) from exc
    except requests.ConnectionError as exc:
        raise SatelliteServiceError(
            "Could not reach the satellite data service (network error). "
            "Check your internet connection, or disable remote satellite data "
            "to use local/mock mode instead."
        ) from exc
    except requests.RequestException as exc:
        raise SatelliteServiceError(f"Landsat scene search failed: {exc}") from exc

    if resp.status_code in (401, 403):
        raise SatelliteServiceError(
            "The satellite data service rejected the request (authentication "
            "error). If you set PC_SDK_SUBSCRIPTION_KEY, verify it's correct; "
            "otherwise this endpoint should not require one."
        )
    if resp.status_code >= 400:
        raise SatelliteServiceError(
            f"Landsat scene search failed (HTTP {resp.status_code}): {resp.text[:300]}"
        )

    items = resp.json().get("features", [])
    if not items:
        raise NoScenesFoundError(
            "No Landsat 8/9 scenes were found for this study area with the "
            f"current filters (window: {datetime_str}, max cloud cover: "
            f"{config.max_cloud_cover_pct:.0f}%). Try a wider date range, a "
            "higher cloud-cover limit, or confirm the study area has Landsat "
            "coverage."
        )
    return items


def _item_to_metadata(item: dict) -> SceneMetadata:
    props = item.get("properties", {})
    return SceneMetadata(
        scene_id=item.get("id", "unknown"),
        platform=props.get("platform", "unknown"),
        collection=item.get("collection", "landsat-c2-l2"),
        product="L2SP Surface Temperature (ST_B10)",
        acquisition_datetime=props.get("datetime", ""),
        processing_datetime=props.get("created"),
        cloud_cover_pct=float(props.get("eo:cloud_cover", float("nan"))),
        bbox=tuple(item.get("bbox", ())),
    )


def _asset_href(item: dict, candidates: list[str]) -> str:
    assets = item.get("assets", {})
    for key in candidates:
        if key in assets and "href" in assets[key]:
            return assets[key]["href"]
    for asset in assets.values():
        title = (asset.get("title") or "").lower()
        if any(c.lower() in title for c in candidates) and "href" in asset:
            return asset["href"]
    raise SceneRetrievalError(
        f"Scene '{item.get('id')}' is missing an expected asset "
        f"(looked for {candidates}). This scene may use a different asset "
        "naming scheme than expected -- try a different scene/date."
    )


def _sign_href(href: str, config) -> str:
    try:
        import planetary_computer as pc
    except ImportError as exc:
        raise SatelliteServiceError(
            "The 'planetary-computer' package is required to access Landsat "
            "assets. Install it with `pip install planetary-computer`."
        ) from exc
    try:
        return pc.sign(href)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as an auth/network problem
        raise SceneRetrievalError(
            f"Failed to authorize access to a Landsat asset (signing error): {exc}"
        ) from exc


def _windowed_read(href: str, bbox_wgs84: tuple, timeout_s: int):
    """Open a (signed) remote COG URL and read only the window covering
    bbox_wgs84, instead of downloading the whole ~1 GB scene. Returns
    (array, transform, crs, nodata)."""
    env_opts = {
        "GDAL_HTTP_TIMEOUT": str(timeout_s),
        "GDAL_HTTP_CONNECTTIMEOUT": str(timeout_s),
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF",
    }
    try:
        with rasterio.Env(**env_opts):
            with rasterio.open(href) as src:
                transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                minx, miny = transformer.transform(bbox_wgs84[0], bbox_wgs84[1])
                maxx, maxy = transformer.transform(bbox_wgs84[2], bbox_wgs84[3])
                window = from_bounds(minx, miny, maxx, maxy, transform=src.transform)
                full = Window(0, 0, src.width, src.height)
                window = window.intersection(full) if _windows_overlap(window, full) else None
                if window is None or window.width <= 0 or window.height <= 0:
                    raise SceneRetrievalError(
                        "The study area falls outside this scene's coverage."
                    )
                window = window.round_offsets().round_lengths()
                array = src.read(1, window=window)
                transform = src.window_transform(window)
                return array, transform, src.crs, src.nodata
    except rasterio.errors.RasterioIOError as exc:
        raise SceneRetrievalError(
            f"Could not read the Landsat asset (corrupt or unreachable file): {exc}"
        ) from exc


def _windows_overlap(a: Window, b: Window) -> bool:
    return not (
        a.col_off + a.width <= b.col_off
        or b.col_off + b.width <= a.col_off
        or a.row_off + a.height <= b.row_off
        or b.row_off + b.height <= a.row_off
    )


def _qa_bad_mask(qa: np.ndarray) -> np.ndarray:
    """True where a pixel is fill, cloud, cirrus, dilated cloud, or cloud shadow."""
    qa = qa.astype("uint32")
    bad = np.zeros(qa.shape, dtype=bool)
    for bit in (_QA_BIT_FILL, _QA_BIT_DILATED_CLOUD, _QA_BIT_CIRRUS, _QA_BIT_CLOUD, _QA_BIT_CLOUD_SHADOW):
        bad |= (qa & (1 << bit)) != 0
    return bad


def _process_one_scene(item: dict, bbox_wgs84: tuple, config) -> tuple[np.ndarray, Affine, object]:
    """Fetch ST + QA_PIXEL for one scene, clip to bbox, QA-mask, convert to Celsius.

    Returns (celsius_array_with_nan_for_masked, transform, crs).
    """
    st_href = _sign_href(_asset_href(item, ST_ASSET_CANDIDATES), config)
    qa_href = _sign_href(_asset_href(item, QA_ASSET_CANDIDATES), config)

    st_dn, transform, crs, st_nodata = _windowed_read(st_href, bbox_wgs84, config.request_timeout_s)
    qa, _, _, _ = _windowed_read(qa_href, bbox_wgs84, config.request_timeout_s)

    celsius = digital_number_to_celsius(st_dn.astype("float64"))
    bad = _qa_bad_mask(qa)
    if st_nodata is not None:
        bad |= st_dn == st_nodata
    # match shapes defensively in case ST/QA windows rounded to slightly
    # different sizes (can happen at scene edges) -- crop to the common overlap
    h = min(celsius.shape[0], bad.shape[0])
    w = min(celsius.shape[1], bad.shape[1])
    celsius = celsius[:h, :w].copy()
    bad = bad[:h, :w]
    celsius[bad] = np.nan

    if np.all(np.isnan(celsius)):
        raise AllPixelsMaskedError(
            "Every pixel over the study area was cloud/shadow/fill-masked in "
            "this scene. Try a different date, a wider date range, or a "
            "higher cloud-cover limit."
        )
    return celsius, transform, crs


def _build_cache_key(bbox: tuple, config) -> str:
    bbox_rounded = tuple(round(v, 4) for v in bbox)
    if config.mode == "latest":
        # bucket by day: Landsat isn't updated more often than that, and this
        # keeps "latest suitable scene" from silently going stale for weeks.
        temporal_key = f"latest:{date.today().isoformat()}:{config.lookback_days}"
    else:
        temporal_key = f"range:{config.date_range}"
    payload = {
        "bbox": bbox_rounded,
        "temporal": temporal_key,
        "cloud": config.max_cloud_cover_pct,
        "composite": bool(config.composite),
        "collection": config.collection,
        "platforms": tuple(sorted(config.platforms)),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return digest[:20]


def _cache_paths(cache_key: str, cache_dir: str) -> tuple[str, str]:
    os.makedirs(cache_dir, exist_ok=True)
    return (
        os.path.join(cache_dir, f"lst_{cache_key}.tif"),
        os.path.join(cache_dir, f"lst_{cache_key}.json"),
    )


def _write_cache_raster(path: str, array: np.ndarray, transform: Affine, crs) -> None:
    """
    Persist the already-Celsius, QA-masked array to disk.

    We store masked/invalid pixels as a finite sentinel (-9999.0) rather
    than NaN: rasterstats' nodata handling (and services.raster.compute_zonal_lst,
    which reads this file back with raster_is_raw_dn=False) masks by value
    equality, and `nan == nan` is always False -- a NaN nodata tag would
    silently fail to exclude masked pixels from the zonal median.
    """
    sentinel = -9999.0
    out = np.where(np.isnan(array), sentinel, array).astype("float32")
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "height": out.shape[0],
        "width": out.shape[1],
        "crs": crs,
        "transform": transform,
        "nodata": sentinel,
        "compress": "deflate",
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(out, 1)


def _load_from_cache(cache_key: str, cache_dir: str, bbox: tuple) -> "SatelliteFetchResult | None":
    raster_path, meta_path = _cache_paths(cache_key, cache_dir)
    if not (os.path.exists(raster_path) and os.path.exists(meta_path)):
        return None
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        scenes = [SceneMetadata(**s) for s in meta["scenes"]]
        return SatelliteFetchResult(
            raster_path=raster_path,
            scenes=scenes,
            mode=meta["mode"],
            source=meta["source"],
            is_cached=True,
            is_mock=False,
            study_area_bbox=bbox,
            limitations=meta["limitations"],
        )
    except (json.JSONDecodeError, KeyError, TypeError, OSError) as exc:
        logger.warning("Ignoring corrupt satellite cache entry %s: %s", cache_key, exc)
        return None


def _save_to_cache(cache_key: str, cache_dir: str, result: "SatelliteFetchResult") -> None:
    _, meta_path = _cache_paths(cache_key, cache_dir)
    meta = {
        "scenes": [asdict(s) for s in result.scenes],
        "mode": result.mode,
        "source": result.source,
        "limitations": result.limitations,
        "cached_at": time.time(),
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)


_STANDARD_LIMITATIONS = [
    "This is Landsat's most recent suitable overpass, not live/continuous imagery "
    "(Landsat 8/9 combined revisit interval is roughly 8 days, plus a processing delay).",
    "Land Surface Temperature (roof/ground surface), not air temperature.",
    "TIRS' native thermal resolution is ~100 m, resampled to a 30 m grid -- this is a "
    "neighborhood-scale surface-temperature estimate, not a precise per-roof measurement.",
]


def fetch_thermal_raster(bbox_wgs84: tuple, config) -> SatelliteFetchResult:
    """
    Search, filter, retrieve, QA-mask, convert, clip, and cache a Landsat 8/9
    Collection 2 Level-2 Surface Temperature raster covering `bbox_wgs84`
    (minx, miny, maxx, maxy in EPSG:4326).

    Raises RemoteDataDisabled if config.use_remote_satellite_data is False
    (the caller should fall back to a local/mock raster in that case, not
    treat this as an error). Raises SatelliteServiceError subclasses for
    every other failure mode, with messages safe to show directly to a user.
    """
    if not config.use_remote_satellite_data:
        raise RemoteDataDisabled("Remote satellite data is disabled (USE_REMOTE_SATELLITE_DATA=false).")

    if not (bbox_wgs84 and len(bbox_wgs84) == 4 and bbox_wgs84[0] < bbox_wgs84[2] and bbox_wgs84[1] < bbox_wgs84[3]):
        raise SatelliteServiceError(f"Invalid study-area bounding box: {bbox_wgs84}")

    cache_key = _build_cache_key(bbox_wgs84, config)
    cached = _load_from_cache(cache_key, config.cache_dir, bbox_wgs84)
    if cached is not None:
        logger.info("Reusing cached Landsat thermal raster (key=%s).", cache_key)
        return cached

    items = _search_scenes(bbox_wgs84, config)

    if config.mode == "date_range" and config.composite and len(items) > 1:
        chosen_items = items[: config.max_scenes_for_composite]
        arrays, transform, crs = [], None, None
        used_scenes = []
        for item in chosen_items:
            try:
                arr, t, c = _process_one_scene(item, bbox_wgs84, config)
            except AllPixelsMaskedError:
                continue  # skip fully-clouded scenes in a composite; don't fail the whole composite
            except SceneRetrievalError as exc:
                logger.warning("Skipping scene %s in composite: %s", item.get("id"), exc)
                continue
            if transform is None:
                transform, crs = t, c
            elif arr.shape != arrays[0].shape:
                continue  # skip a misaligned grid rather than corrupt the stack
            arrays.append(arr)
            used_scenes.append(_item_to_metadata(item))
        if not arrays:
            raise AllPixelsMaskedError(
                "Every candidate scene in the date range was unusable (fully "
                "clouded, misaligned, or unreadable). Try a wider date range."
            )
        stack = np.stack(arrays, axis=0)
        composite = np.nanmedian(stack, axis=0)  # per-pixel median across cloud-masked scenes
        result_mode = "composite"
        source = (
            f"Microsoft Planetary Computer STAC — Landsat 8/9 C2 L2 "
            f"({len(used_scenes)}-scene cloud-masked median composite)"
        )
        limitations = _STANDARD_LIMITATIONS + [
            f"Composite built from {len(used_scenes)} of {len(chosen_items)} candidate scenes "
            "after excluding fully-clouded/unusable ones; per-pixel median of cloud-masked values, "
            "not a plain average of raw pixels."
        ]
        final_array, final_transform, final_crs, scenes_used = composite, transform, crs, used_scenes
    else:
        best_item = items[0] if config.mode == "latest" else min(
            items, key=lambda it: it.get("properties", {}).get("eo:cloud_cover", 100.0)
        )
        final_array, final_transform, final_crs = _process_one_scene(best_item, bbox_wgs84, config)
        scenes_used = [_item_to_metadata(best_item)]
        result_mode = config.mode
        source = "Microsoft Planetary Computer STAC — Landsat 8/9 Collection 2 Level-2"
        limitations = list(_STANDARD_LIMITATIONS)

    raster_path, _ = _cache_paths(cache_key, config.cache_dir)
    _write_cache_raster(raster_path, final_array, final_transform, final_crs)

    result = SatelliteFetchResult(
        raster_path=raster_path,
        scenes=scenes_used,
        mode=result_mode,
        source=source,
        is_cached=False,
        is_mock=False,
        study_area_bbox=bbox_wgs84,
        limitations=limitations,
    )
    _save_to_cache(cache_key, config.cache_dir, result)
    return result
