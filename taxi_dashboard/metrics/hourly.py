"""Pure calculations for the hourly overview."""

import pandas as pd

from taxi_dashboard.metrics.averages import weighted_trip_average


def peak_label(values: pd.Series) -> str:
    """Return the hour(s) with the highest value, or "Keine Daten" if empty."""
    available = values.dropna()
    if available.empty:
        return "Keine Daten"
    peak = available.max()
    return ", ".join(f"{hour:02d}:00" for hour in available[available == peak].index)


__all__ = ["peak_label", "weighted_trip_average"]
