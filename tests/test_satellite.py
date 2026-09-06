"""
Unit tests for services.satellite -- deliberately limited to logic that
needs no network access or real raster files (see README.md: tests run
without network/raster). End-to-end acquisition against the live Planetary
Computer STAC API is exercised manually / in the running app, not here.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from config.settings import SatelliteConfig
from services.satellite import (
    RemoteDataDisabled,
    _build_cache_key,
    _qa_bad_mask,
    fetch_thermal_raster,
)


def test_qa_bad_mask_flags_fill_cloud_cirrus_dilated_and_shadow():
    # bit 0=fill, 1=dilated cloud, 2=cirrus, 3=cloud, 4=cloud shadow
    qa = np.array([
        0b00000,  # clear
        0b00001,  # fill
        0b00010,  # dilated cloud
        0b00100,  # cirrus
        0b01000,  # cloud
        0b10000,  # cloud shadow
        0b01010,  # cloud + dilated cloud
    ])
    bad = _qa_bad_mask(qa)
    assert bad.tolist() == [False, True, True, True, True, True, True]


def test_qa_bad_mask_ignores_unrelated_bits():
    # A high bit unrelated to fill/cloud/shadow should not trip the mask.
    qa = np.array([0b1000000000])
    assert _qa_bad_mask(qa).tolist() == [False]


def test_fetch_thermal_raster_raises_when_disabled_without_any_network_call():
    config = SatelliteConfig(use_remote_satellite_data=False)
    with pytest.raises(RemoteDataDisabled):
        fetch_thermal_raster((-112.1, 33.44, -112.07, 33.46), config)


def test_fetch_thermal_raster_rejects_invalid_bbox():
    config = SatelliteConfig(use_remote_satellite_data=True)
    from services.satellite import SatelliteServiceError
    # minx > maxx is invalid and must be caught before any network call.
    with pytest.raises(SatelliteServiceError):
        fetch_thermal_raster((-112.0, 33.4, -113.0, 33.5), config)


def test_build_cache_key_is_deterministic_for_same_inputs():
    config = SatelliteConfig(mode="date_range", date_range=("2026-01-01", "2026-01-31"))
    bbox = (-112.08, 33.44, -112.07, 33.45)
    key1 = _build_cache_key(bbox, config)
    key2 = _build_cache_key(bbox, config)
    assert key1 == key2


def test_build_cache_key_differs_for_different_bbox():
    config = SatelliteConfig(mode="date_range", date_range=("2026-01-01", "2026-01-31"))
    key1 = _build_cache_key((-112.08, 33.44, -112.07, 33.45), config)
    key2 = _build_cache_key((-100.0, 30.0, -99.9, 30.1), config)
    assert key1 != key2


def test_build_cache_key_differs_for_composite_vs_single():
    config_single = SatelliteConfig(mode="date_range", date_range=("2026-01-01", "2026-01-31"), composite=False)
    config_composite = SatelliteConfig(mode="date_range", date_range=("2026-01-01", "2026-01-31"), composite=True)
    bbox = (-112.08, 33.44, -112.07, 33.45)
    assert _build_cache_key(bbox, config_single) != _build_cache_key(bbox, config_composite)
