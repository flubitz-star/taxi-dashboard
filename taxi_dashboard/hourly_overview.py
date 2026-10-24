"""Backward-compatible imports for the hourly dashboard page."""

from taxi_dashboard.analysis.hourly import (
    load_data,
    peak_label,
    render_hourly_overview,
    weighted_trip_average,
)

__all__ = ["load_data", "peak_label", "render_hourly_overview", "weighted_trip_average"]
