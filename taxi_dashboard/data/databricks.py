"""Shared Databricks SQL helpers used by the dashboard pages."""

from __future__ import annotations

import pandas as pd
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, Format

from taxi_dashboard.config import WAREHOUSE_ID


def normalize_boolean(value: object) -> bool | None:
    """Convert Databricks boolean-like values into Python booleans.

    The SQL statement API returns every value as a string, so booleans arrive as
    "true"/"false". Returns None for missing or unrecognized values.
    """
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
    """Select the given columns from a table and return them as a DataFrame.

    Args:
        table: Fully qualified table name, e.g. `taxi_dev.gold.zone_revenue_hourly`.
        columns: Column names to select. All of them must exist in the result.
        warehouse_id: SQL warehouse that executes the statement.

    Returns:
        A DataFrame with all values as strings; callers convert the types.

    Raises:
        RuntimeError: If the statement fails, does not finish within the wait
            timeout, or the table lacks one of the requested columns.
    """
    client = WorkspaceClient()
    response = client.statement_execution.execute_statement(
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

    # Large results are split into chunks; follow next_chunk_index to read them all,
    # otherwise only the first chunk (a part of the table) would be returned.
    rows: list = []
    result = response.result
    while result is not None:
        rows.extend(result.data_array or [])
        next_chunk = result.next_chunk_index
        if next_chunk is None:
            break
        result = client.statement_execution.get_statement_result_chunk_n(
            response.statement_id, next_chunk
        )
    return pd.DataFrame(rows, columns=names)
