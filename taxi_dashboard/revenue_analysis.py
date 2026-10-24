"""Backward-compatible imports for the revenue analysis page."""

from taxi_dashboard.analysis.revenue import load_revenue_data, render_revenue_analysis

__all__ = ["load_revenue_data", "render_revenue_analysis"]
