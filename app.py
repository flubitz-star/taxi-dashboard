import streamlit as st
import pandas as pd
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, Format

st.set_page_config(page_title="Taxi Dashboard", page_icon="🚕")

st.title("🚕 Taxi Dashboard")
st.markdown("Verbindungstest zu den Gold-Tabellen")

@st.cache_data(ttl=300)
def query_table(sql: str):
    """Execute SQL via Databricks SDK Statement Execution API."""
    w = WorkspaceClient()
    resp = w.statement_execution.execute_statement(
        statement=sql,
        warehouse_id="b4c5e8896d8800fe",
        disposition=Disposition.INLINE,
        format=Format.JSON_ARRAY,
        wait_timeout="50s",
    )
    status = resp.status
    state = status.state if status else "unknown"
    if str(state).upper().endswith("FAILED"):
        error = status.error
        error_code = error.error_code if error else "unknown"
        message = error.message if error and error.message else "No error message returned"
        raise RuntimeError(f"Databricks SQL error ({error_code}): {message}")
    if resp.manifest is None:
        statement_id = resp.statement_id or "unknown"
        raise RuntimeError(
            f"Statement did not complete in time (status: {state}, id: {statement_id})"
        )
    columns = [c.name for c in resp.manifest.schema.columns]
    type_map = {c.name: c.type_text for c in resp.manifest.schema.columns}
    rows = []
    for raw in resp.result.data_array or []:
        row = {}
        for i, col in enumerate(columns):
            val = raw[i]
            if val is None:
                row[col] = None
                continue
            t = type_map.get(col, "")
            if t in ("DATE", "TIMESTAMP"):
                row[col] = pd.to_datetime(val)
            elif t in ("INT", "BIGINT", "LONG"):
                row[col] = int(val)
            elif t in ("DOUBLE", "FLOAT"):
                row[col] = float(val)
            elif t == "BOOLEAN":
                row[col] = val == "true"
            else:
                row[col] = val
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)

try:
    df = query_table("SELECT * FROM workspace.gold.daily_metrics LIMIT 10")
    st.success(f"✅ Verbindung hergestellt — {len(df)} Zeilen aus `workspace.gold.daily_metrics`")
    st.dataframe(df, use_container_width=True)
except Exception as e:
    st.error(f"❌ Fehler beim Abruf der Daten: {e}")