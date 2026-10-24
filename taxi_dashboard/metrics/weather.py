"""Streamlit-independent preparation and calculations for weather analyses."""

import pandas as pd

from taxi_dashboard.config import RAIN_BUCKETS, TEMP_BUCKETS
from taxi_dashboard.data.databricks import normalize_boolean

DAILY_NUMERIC_COLUMNS = (
    "taxi_trips",
    "bike_trips",
    "bike_share_pct",
    "avg_temp_c",
    "max_temp_c",
    "min_temp_c",
    "total_rain_mm",
    "hours_rain",
)
HOURLY_NUMERIC_COLUMNS = (
    "pickup_hour",
    "taxi_trips",
    "bike_trips",
    "temperature_2m_c",
    "rain_mm",
)


def prepare_weather_data(
    daily: pd.DataFrame, hourly: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert source columns and add taxi-share and month helper columns."""
    daily = daily.copy()
    hourly = hourly.copy()

    for frame, numeric_columns in (
        (daily, DAILY_NUMERIC_COLUMNS),
        (hourly, HOURLY_NUMERIC_COLUMNS),
    ):
        frame["pickup_date"] = pd.to_datetime(frame["pickup_date"], errors="coerce")
        for column in numeric_columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if "has_rain" in frame:
            frame["has_rain"] = frame["has_rain"].map(normalize_boolean)

    daily["taxi_share_pct"] = 100 - daily["bike_share_pct"]
    computed_share = share_from_counts(daily["taxi_trips"], daily["bike_trips"])
    daily["taxi_share_pct"] = daily["taxi_share_pct"].where(
        daily["taxi_share_pct"].notna(), computed_share
    )
    daily["month"] = daily["pickup_date"].dt.strftime("%Y-%m")

    hourly["taxi_share_pct"] = share_from_counts(hourly["taxi_trips"], hourly["bike_trips"])
    hourly["month"] = hourly["pickup_date"].dt.strftime("%Y-%m")

    return daily, hourly


def share_from_counts(taxi: pd.Series, bike: pd.Series) -> pd.Series:
    """Return taxi trips as a percentage of all taxi and bike trips."""
    total = taxi + bike
    return (100 * taxi / total).where(total > 0)


def temperature_groups(hourly: pd.DataFrame) -> pd.DataFrame:
    """Summarize hourly taxi share and trip counts in temperature buckets.

    The taxi share is the mean of hourly shares; observations count hourly rows,
    not individual trips.
    """
    data = hourly.dropna(subset=["temperature_2m_c", "taxi_share_pct"]).copy()
    data["temp_bucket"] = pd.cut(
        data["temperature_2m_c"],
        bins=[-float("inf"), 15, 20, 25, 30, float("inf")],
        labels=TEMP_BUCKETS,
        right=False,
    )
    return (
        data.groupby("temp_bucket", observed=False)
        .agg(
            taxi_share=("taxi_share_pct", "mean"),
            taxi_trips=("taxi_trips", "mean"),
            bike_trips=("bike_trips", "mean"),
            observations=("taxi_share_pct", "count"),
        )
        .reindex(TEMP_BUCKETS)
        .reset_index()
    )


def rain_groups(hourly: pd.DataFrame) -> pd.DataFrame:
    """Summarize mean hourly taxi share and observation count by rain bucket."""
    data = hourly.dropna(subset=["rain_mm", "taxi_share_pct"]).copy()
    data["rain_bucket"] = pd.cut(
        data["rain_mm"].clip(lower=0),
        bins=[-float("inf"), 0.01, 0.5, 2, float("inf")],
        labels=RAIN_BUCKETS,
        right=False,
    )
    return (
        data.groupby("rain_bucket", observed=False)
        .agg(
            taxi_share=("taxi_share_pct", "mean"),
            observations=("taxi_share_pct", "count"),
        )
        .reindex(RAIN_BUCKETS)
        .reset_index()
    )


def data_quality_messages(daily: pd.DataFrame, hourly: pd.DataFrame) -> list[str]:
    """Return warnings for duplicate records, invalid dates, and negative counts."""
    messages = []
    for label, frame, key in (
        ("Tagesdaten", daily, "pickup_date"),
        ("Stundendaten", hourly, ["pickup_date", "pickup_hour"]),
    ):
        duplicates = int(frame.duplicated(subset=key).sum())
        if duplicates:
            messages.append(f"{label}: {duplicates} doppelte Zeilen.")
    if daily["pickup_date"].isna().any() or hourly["pickup_date"].isna().any():
        messages.append("Einige Zeilen haben kein gültiges Datum und werden nicht ausgewertet.")
    if (daily[["taxi_trips", "bike_trips"]] < 0).any().any() or (
        hourly[["taxi_trips", "bike_trips"]] < 0
    ).any().any():
        messages.append("Negative Trip-Zahlen entdeckt; bitte die Quelldaten prüfen.")
    return messages
