import json

tracts = [
    {
        "tract_id": "04013112500",
        "tract_name": "Downtown Core / Central Ave Corridor",
        "bbox": [-112.0836, 33.4444, -112.0637, 33.4540],
        "base_lst": 44.2,
        "lst_rate": 0.22,
        "base_ndvi": 0.12,
        "ndvi_rate": -0.003,
        "base_svi": 0.65,
        "svi_rate": 0.010,
        "base_poverty": 0.24,
        "base_elderly": 0.11,
        "base_impervious": 0.85,
        "base_heat_days": 42
    },
    {
        "tract_id": "04013112600",
        "tract_name": "Warehouse District & South Rail Corridor",
        "bbox": [-112.0850, 33.4350, -112.0630, 33.4444],
        "base_lst": 46.1,
        "lst_rate": 0.48,  # Accelerating heat
        "base_ndvi": 0.08,
        "ndvi_rate": -0.008, # Rapid canopy loss
        "base_svi": 0.82,
        "svi_rate": 0.015,
        "base_poverty": 0.35,
        "base_elderly": 0.16,
        "base_impervious": 0.91,
        "base_heat_days": 48
    },
    {
        "tract_id": "04013112700",
        "tract_name": "East Van Buren Commercial Corridor",
        "bbox": [-112.0637, 33.4444, -112.0480, 33.4590],
        "base_lst": 45.4,
        "lst_rate": 0.42, # High heat rate
        "base_ndvi": 0.10,
        "ndvi_rate": -0.007,
        "base_svi": 0.86,
        "svi_rate": 0.012,
        "base_poverty": 0.38,
        "base_elderly": 0.18,
        "base_impervious": 0.88,
        "base_heat_days": 45
    },
    {
        "tract_id": "04013112800",
        "tract_name": "Garfield Historic District",
        "bbox": [-112.0637, 33.4590, -112.0480, 33.4700],
        "base_lst": 43.1,
        "lst_rate": 0.15,
        "base_ndvi": 0.18,
        "ndvi_rate": -0.002,
        "base_svi": 0.68,
        "svi_rate": -0.005,
        "base_poverty": 0.22,
        "base_elderly": 0.14,
        "base_impervious": 0.72,
        "base_heat_days": 38
    },
    {
        "tract_id": "04013114200",
        "tract_name": "Roosevelt Row Arts District",
        "bbox": [-112.0836, 33.4540, -112.0637, 33.4680],
        "base_lst": 42.8,
        "lst_rate": 0.08, # Stable / cooling slightly
        "base_ndvi": 0.16,
        "ndvi_rate": 0.005, # Green canopy expansion
        "base_svi": 0.45,
        "svi_rate": -0.015, # Gentrifying / declining vulnerability
        "base_poverty": 0.14,
        "base_elderly": 0.09,
        "base_impervious": 0.76,
        "base_heat_days": 36
    },
    {
        "tract_id": "04013114300",
        "tract_name": "Capitol & Government Mall",
        "bbox": [-112.1000, 33.4400, -112.0836, 33.4590],
        "base_lst": 44.5,
        "lst_rate": 0.25,
        "base_ndvi": 0.14,
        "ndvi_rate": -0.004,
        "base_svi": 0.60,
        "svi_rate": 0.005,
        "base_poverty": 0.20,
        "base_elderly": 0.12,
        "base_impervious": 0.83,
        "base_heat_days": 41
    }
]

years = [2018, 2019, 2020, 2021, 2022, 2023]
city_baselines = {
    2018: 41.5,
    2019: 41.8,
    2020: 42.3,
    2021: 42.1,
    2022: 42.7,
    2023: 43.0,
}

features = []

for t in tracts:
    minx, miny, maxx, maxy = t["bbox"]
    poly_coords = [
        [minx, miny],
        [maxx, miny],
        [maxx, maxy],
        [minx, maxy],
        [minx, miny]
    ]
    
    for i, yr in enumerate(years):
        lst = round(t["base_lst"] + i * t["lst_rate"], 2)
        baseline = city_baselines[yr]
        anomaly = round(lst - baseline, 2)
        ndvi = round(max(0.01, t["base_ndvi"] + i * t["ndvi_rate"]), 3)
        svi = round(min(0.99, max(0.01, t["base_svi"] + i * t["svi_rate"])), 3)
        poverty = round(min(0.99, max(0.01, t["base_poverty"] + i * (t["svi_rate"] * 0.8))), 3)
        elderly = round(min(0.99, max(0.01, t["base_elderly"] + i * 0.003)), 3)
        impervious = round(min(0.99, t["base_impervious"] + i * 0.005), 3)
        heat_days = int(t["base_heat_days"] + i * 1.5 + (1 if anomaly > 3 else 0))
        
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [poly_coords]
            },
            "properties": {
                "tract_id": t["tract_id"],
                "tract_name": t["tract_name"],
                "year": yr,
                "lst_median_c": lst,
                "lst_anomaly_c": anomaly,
                "ndvi_mean": ndvi,
                "svi_score": svi,
                "poverty_rate": poverty,
                "elderly_pct": elderly,
                "impervious_pct": impervious,
                "extreme_heat_days": heat_days
            }
        }
        features.append(feature)

geojson = {
    "type": "FeatureCollection",
    "crs": {
        "type": "name",
        "properties": {
            "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
        }
    },
    "features": features
}

out_path = "/Users/samikshaaprakash08/.gemini/antigravity/scratch/coolcorridor/data/raw/phoenix_neighborhood_history.geojson"
with open(out_path, "w") as f:
    json.dump(geojson, f, indent=2)

print(f"Generated {len(features)} historical tract-year records to {out_path}.")
