import numpy as np
import pandas as pd
import pulp


def calculate_hecs(
    df: pd.DataFrame,
    gamma: float = 1.0,
    unit_cost: float = 15.0,
) -> pd.DataFrame:
  """Evaluates intervention urgency (HECS) and coating cost using NumPy."""
  # 1. Thermal Anomaly: Delta T_i = max(0, median_lst - baseline)
  baseline_temp = float(df["median_lst"].mean())
  df["lst_anomaly"] = np.maximum(0.0, df["median_lst"] - baseline_temp)

  # 2. Heat Exposure Contribution Score: Area * Delta T * (1 + gamma * SVI)
  # Balances thermal mass, surface area, and community vulnerability
  df["hecs"] = (
      df["roof_area"] * df["lst_anomaly"] * (1.0 + gamma * df["svi_weight"])
  )

  # 3. Capital Intervention Cost
  df["cost"] = df["roof_area"] * unit_cost
  return df


def solve_knapsack(
    df: pd.DataFrame, budget: float
) -> tuple[pd.DataFrame, dict]:
  """Solves the 0-1 Knapsack problem using PuLP and returns a binary selection mask."""
  n = len(df)
  prob = pulp.LpProblem("CoolCorridor_Knapsack", pulp.LpMaximize)

  # Binary decision variables: x_i in {0, 1}
  x = [pulp.LpVariable(f"x_{i}", cat=pulp.LpBinary) for i in range(n)]

  # Objective: Maximize total heat mitigation score (HECS)
  prob += pulp.lpSum([x[i] * df.loc[i, "hecs"] for i in range(n)])

  # Budget Constraint: sum(x_i * cost_i) <= Budget
  prob += (
      pulp.lpSum([x[i] * df.loc[i, "cost"] for i in range(n)]) <= budget,
      "Budget_Ceiling",
  )

  # Solve using PuLP's default bundled solver (CBC) quietly
  prob.solve(pulp.PULP_CBC_CMD(msg=False))

  # Extract binary mask: 1 = coated, 0 = untreated
  df["selected"] = [int(pulp.value(x[i])) for i in range(n)]

  # Summary performance statistics
  selected_subset = df[df["selected"] == 1]
  metrics = {
      "status": pulp.LpStatus[prob.status],
      "total_budget": budget,
      "allocated_budget": float(selected_subset["cost"].sum()),
      "buildings_selected": int(selected_subset["selected"].sum()),
      "total_area_treated_m2": float(selected_subset["roof_area"].sum()),
      "total_hecs_mitigated": float(selected_subset["hecs"].sum()),
  }

  return df, metrics


# --- SANITY TEST ---
if __name__ == "__main__":
  # Generate a test batch of candidate buildings
  np.random.seed(42)
  num_bld = 50
  sample_data = pd.DataFrame({
      "building_id": [f"BLD_{i:03d}" for i in range(num_bld)],
      "roof_area": np.random.uniform(400, 3500, size=num_bld).round(1),
      "median_lst": np.random.normal(loc=47.0, scale=3.5, size=num_bld).round(
          2
      ),
      "svi_weight": np.random.uniform(0.1, 1.0, size=num_bld).round(2),
  })

  scored_df = calculate_hecs(sample_data, gamma=1.2, unit_cost=15.0)
  optimized_df, summary = solve_knapsack(scored_df, budget=150000.0)

  print(f"Solver Status: {summary['status']}")
  print(
      f"Budget: ${summary['total_budget']:,.2f} | Spent:"
      f" ${summary['allocated_budget']:,.2f}"
  )
  print(
      f"Targeted Roofs: {summary['buildings_selected']} buildings"
      f" ({summary['total_area_treated_m2']:,.1f} m²)"
  )
  print(
      "\nTop 5 Interventions Selected:\n",
      optimized_df[optimized_df["selected"] == 1][[
          "building_id",
          "roof_area",
          "lst_anomaly",
          "cost",
          "hecs",
      ]].head(),
  )