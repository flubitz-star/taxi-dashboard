"""Backward-compatible entry point for the taxi and weather dashboard page."""

from taxi_dashboard.analysis.weather import load_weather_data, render_weather_comparison

__all__ = ["load_weather_data", "render_weather_comparison"]
