"""Data access layer for Databricks-backed dashboard queries."""

from taxi_dashboard.data.databricks import normalize_boolean, query_table

__all__ = ["normalize_boolean", "query_table"]
