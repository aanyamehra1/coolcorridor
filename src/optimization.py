import geopandas as gpd
import numpy as np
import pulp


def run_roof_optimization(
    geojson_path="data/processed/phoenix_buildings.geojson",
    budget=250000.0,
    unit_cost=15.0,
    equity_gamma=1.0,
):
    # 1. Load cached spatial footprint layer
    gdf = gpd.read_file(geojson_path)

    if len(gdf) == 0:
        raise ValueError("The provided GeoJSON contains no building footprints.")

    # 2. Compute local heat anomaly relative to district mean
    baseline_lst = gdf["lst_median"].mean()
    gdf["lst_anomaly"] = np.maximum(0, gdf["lst_median"] - baseline_lst)

    # Inject mock Social Vulnerability Index if census layer is unattached
    if "svi_score" not in gdf.columns:
        np.random.seed(42)
        gdf["svi_score"] = np.random.uniform(0.1, 0.9, len(gdf))

    # 3. Calculate impact score (HECS) and total coating cost per roof
    gdf["hecs"] = (
        gdf["roof_area"]
        * gdf["lst_anomaly"]
        * (1.0 + equity_gamma * gdf["svi_score"])
    )
    gdf["cost"] = gdf["roof_area"] * unit_cost

    # 4. Formulate 0-1 Integer Linear Program
    prob = pulp.LpProblem("CoolCorridor_Knapsack", pulp.LpMaximize)

    # Define binary decision variables (1 = convert roof, 0 = ignore)
    var_keys = [f"x_{i}" for i in range(len(gdf))]
    x = pulp.LpVariable.dicts("TargetRoof", var_keys, cat="Binary")

    # Objective Function: Maximize total cumulative HECS score
    prob += pulp.lpSum(
        [x[var_keys[i]] * gdf.iloc[i]["hecs"] for i in range(len(gdf))]
    )

    # Constraint: Total coating cost cannot exceed available budget
    prob += (
        pulp.lpSum(
            [x[var_keys[i]] * gdf.iloc[i]["cost"] for i in range(len(gdf))]
        )
        <= budget
    )

    # 5. Execute solver
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # 6. Extract binary results back into GeoDataFrame
    gdf["selected"] = [
        int(pulp.value(x[var_keys[i]])) for i in range(len(gdf))
    ]

    return gdf


if __name__ == "__main__":
    optimized_gdf = run_roof_optimization(budget=250000.0)
    targeted = optimized_gdf[optimized_gdf["selected"] == 1]

    print("--- OPTIMIZATION RESULTS ---")
    print(f"Total Buildings Evaluated: {len(optimized_gdf)}")
    print(f"Optimal Roofs Selected:   {len(targeted)}")
    print(f"Total Area to Coat:       {targeted['roof_area'].sum():,.1f} m²")
    print(f"Total Spend:             ${targeted['cost'].sum():,.2f}")