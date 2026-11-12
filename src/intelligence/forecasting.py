"""
PREDICT Stage: Short-Horizon Risk Forecasting Engine.

Projects near-term credit portfolio trajectory with explicit uncertainty ranges:
- PAR trajectory forecasting across a 3 to 6 month forward horizon.
- Roll forward flow rate projections estimating default migration amounts.
- Quantified confidence bands (Upper / Expected / Lower bounds).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RiskForecast:
    """Projected risk metric with explicit uncertainty intervals."""

    metric_name: str
    horizon_months: int
    current_value: float
    expected_value: float
    lower_bound: float
    upper_bound: float
    trajectory_table: pd.DataFrame
    methodology: str


def forecast_par_trajectory(
    historical_par: pd.DataFrame,
    par_col: str = "par30_rate_%",
    horizon: int = 3,
) -> RiskForecast:
    """Forecast future PAR percentage using momentum extrapolation with volatility bands.

    Args:
        historical_par: Historical monthly delinquency trend dataframe.
        par_col: Metric column name.
        horizon: Months ahead to project (default: 3).

    Returns:
        RiskForecast dataclass with forecasted trajectory.
    """
    if len(historical_par) < 3:
        # Fallback if insufficient history
        return RiskForecast(
            metric_name=par_col,
            horizon_months=horizon,
            current_value=0.0,
            expected_value=0.0,
            lower_bound=0.0,
            upper_bound=0.0,
            trajectory_table=pd.DataFrame(),
            methodology="Insufficient historical data for projection.",
        )

    series = historical_par[par_col].astype(float).values
    current_val = float(series[-1])

    # Recent momentum (last 3-6 months linear trend)
    window = min(6, len(series))
    recent = series[-window:]
    x = np.arange(window)
    slope, intercept = np.polyfit(x, recent, deg=1)

    # Volatility of historical residuals
    predicted_recent = slope * x + intercept
    std_residual = float(np.std(recent - predicted_recent))
    if std_residual <= 0.05:
        std_residual = 0.20

    # Project future periods
    future_x = np.arange(window, window + horizon)
    projected_vals = slope * future_x + intercept

    # Enforce non-negative and bound trajectory
    projected_vals = np.clip(projected_vals, 0.5, 30.0)

    last_date = pd.to_datetime(historical_par["month"].iloc[-1])
    forecast_rows = []
    for step in range(1, horizon + 1):
        future_dt = last_date + pd.DateOffset(months=step)
        exp_val = float(projected_vals[step - 1])
        # Uncertainty widens with sqrt(time)
        sigma_t = std_residual * np.sqrt(step) * 1.645  # 90% confidence interval
        forecast_rows.append(
            {
                "month": future_dt.strftime("%Y-%m"),
                "step": f"+{step}M",
                "expected_%": round(exp_val, 2),
                "lower_bound_%": round(max(0.2, exp_val - sigma_t), 2),
                "upper_bound_%": round(exp_val + sigma_t, 2),
            }
        )

    proj_df = pd.DataFrame(forecast_rows)
    final_row = proj_df.iloc[-1]

    return RiskForecast(
        metric_name=par_col,
        horizon_months=horizon,
        current_value=round(current_val, 2),
        expected_value=float(final_row["expected_%"]),
        lower_bound=float(final_row["lower_bound_%"]),
        upper_bound=float(final_row["upper_bound_%"]),
        trajectory_table=proj_df,
        methodology=f"Linear momentum regression with expanding volatility bounds (90% CI, {window}-month base window).",
    )
