"""Shared Databricks SQL helpers used by the dashboard pages."""

from __future__ import annotations

import pandas as pd
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, Format

from taxi_dashboard.config import WAREHOUSE_ID


def normalize_boolean(value: object) -> bool | None:
    """Convert Databricks boolean-like values into Python booleans."""
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def query_table(table: str, columns: list[str], warehouse_id: str = WAREHOUSE_ID) -> pd.DataFrame:
    """Execute a SELECT query and return the result as a DataFrame."""
    response = WorkspaceClient().statement_execution.execute_statement(
        statement=f"SELECT {', '.join(columns)} FROM {table}",
        warehouse_id=warehouse_id,
        disposition=Disposition.INLINE,
        format=Format.JSON_ARRAY,
        wait_timeout="50s",
    )
    status = response.status
    state = status.state if status else "unknown"
    if str(state).upper().endswith("FAILED"):
        error = status.error
        code = error.error_code if error else "unknown"
        message = error.message if error and error.message else "No error message returned"
        raise RuntimeError(f"Databricks SQL error ({code}): {message}")
    if response.manifest is None or response.manifest.schema is None:
        statement_id = response.statement_id or "unknown"
        raise RuntimeError(f"Query did not complete (status: {state}, id: {statement_id})")

    names = [column.name for column in response.manifest.schema.columns]
    missing = sorted(set(columns) - set(names))
    if missing:
        raise RuntimeError(f"{table} is missing expected columns: {', '.join(missing)}")

    rows = response.result.data_array if response.result else []
    return pd.DataFrame(rows or [], columns=names)
