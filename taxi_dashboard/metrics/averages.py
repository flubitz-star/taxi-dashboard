"""Shared calculations for trip-weighted averages."""

import pandas as pd


def weighted_trip_average(data: pd.DataFrame, column: str) -> float:
    """Compute a trip-weighted average, ignoring missing values and non-positive trips."""
    valid = data[column].notna() & data["trips"].gt(0)
    if not valid.any():
        return float("nan")
    return (data.loc[valid, column] * data.loc[valid, "trips"]).sum() / data.loc[
        valid, "trips"
    ].sum()
