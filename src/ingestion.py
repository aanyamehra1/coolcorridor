import os
import geopandas as gpd
import numpy as np
import osmnx as ox
import rasterstats

def process_city_footprints(
    place_name="Downtown, Phoenix, Arizona, USA", 
    target_epsg=32612, 
    raster_path="data/raw/phoenix_landsat_lst.tif", 
    output_path="data/processed/phoenix_buildings.geojson"
):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 1. Pull building polygons from OpenStreetMap
    print(f"Fetching building footprints for: {place_name}...")
    tags = {"building": ["commercial", "industrial", "warehouse", "retail"]}
    gdf = ox.geometries_from_place(place_name, tags=tags)
    
    # Filter strictly for valid polygon geometries
    gdf = gdf[gdf.geometry.type == 'Polygon'].reset_index(drop=True)
    
    # 2. Reproject to local UTM zone (meters) to accurately measure area
    print(f"Reprojecting geometries to EPSG:{target_epsg}...")
    gdf = gdf.to_crs(epsg=target_epsg)
    gdf['roof_area'] = gdf.geometry.area
    
    # Filter out small residential structures (< 400 m²)
    gdf = gdf[gdf['roof_area'] >= 400].copy()
    
    # 3. Extract median Land Surface Temperature (LST) per building
    if os.path.exists(raster_path):
        print(f"Extracting thermal stats from {raster_path}...")
        stats = rasterstats.zonal_stats(gdf, raster_path, stats=['median'], nodata=-9999)
        gdf['lst_median'] = [s['median'] if s['median'] is not None else 35.0 for s in stats]
    else:
        print("Raster file not found. Generating mock LST temperatures for testing UI...")
        gdf['lst_median'] = np.random.uniform(32.0, 48.0, len(gdf))
    
    # 4. Cache processed spatial layer to disk
    gdf.to_file(output_path, driver="GeoJSON")
    print(f"Done! Cached {len(gdf)} building footprints to '{output_path}'.")

if __name__ == "__main__":
    process_city_footprints()