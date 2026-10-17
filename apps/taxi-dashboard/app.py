import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, Format, StatementState, State

TAXI_YELLOW = "#FFB800"

# ── Databricks SQL helper ─────────────────────────────────────────────


@st.cache_resource
def get_workspace_client():
    return WorkspaceClient()


@st.cache_resource
def get_warehouse_id() -> str:
    """Find a usable SQL warehouse ID."""
    w = get_workspace_client()
    warehouses = list(w.warehouses.list())
    for wh in warehouses:
        if wh.state == State.RUNNING:
            return wh.id
    if warehouses:
        return warehouses[0].id
    raise RuntimeError("Kein SQL Warehouse gefunden!")


@st.cache_data(ttl=6000, show_spinner=False)
def run_sql(query: str) -> pd.DataFrame:
    w = get_workspace_client()
    resp = w.statement_execution.execute_statement(
        statement=query,
        warehouse_id=get_warehouse_id(),
        wait_timeout="50s",
        disposition=Disposition.INLINE,
        format=Format.JSON_ARRAY,
    )
    if resp.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"SQL-Ausführung fehlgeschlagen: {resp.status.state}")
    columns = [c.name for c in resp.manifest.schema.columns]
    return pd.DataFrame(resp.result.data_array, columns=columns)


# ── Data loaders ─────────────────────────────────────────────────────


@st.cache_data(ttl=600, show_spinner="Lade Tagesdaten …")
def load_daily_metrics():
    return run_sql("SELECT * FROM workspace.gold.daily_metrics ORDER BY trip_date")


@st.cache_data(ttl=600, show_spinner="Lade Stundendaten …")
def load_hourly_ridership():
    return run_sql("SELECT * FROM workspace.gold.hourly_ridership ORDER BY pickup_hour_ts")


@st.cache_data(ttl=600, show_spinner="Lade Wetterdaten …")
def load_daily_with_weather():
    return run_sql(
        """
        SELECT
            d.trip_date,
            d.trips,
            d.total_revenue,
            d.avg_trip_duration_min,
            d.avg_distance_miles,
            d.avg_passengers,
            d.avg_temperature_c,
            d.rain_hours,
            d.snowfall_hours,
            d.pickup_weekday,
            d.is_weekend
        FROM workspace.gold.daily_metrics d
        ORDER BY d.trip_date
        """
    )


# ── Streamlit UI ─────────────────────────────────────────────────────

st.set_page_config(page_title="NYC Taxi Dashboard", page_icon="🚕", layout="wide")

st.title("🚕 NYC Taxi Dashboard")
st.caption("Taxi-Nutzung & Wetter-Korrelation — Unity Catalog Gold Tables")

# Load data
try:
    df_daily = load_daily_metrics()
    df_hourly = load_hourly_ridership()
    df_weather = load_daily_with_weather()
except Exception as e:
    st.error(f"Fehler beim Laden der Daten: {e}")
    st.stop()

if df_daily.empty:
    st.error("Keine Daten in workspace.gold.daily_metrics gefunden!")
    st.stop()

# Ensure correct types
df_daily["trip_date"] = pd.to_datetime(df_daily["trip_date"])
df_hourly["pickup_hour_ts"] = pd.to_datetime(df_hourly["pickup_hour_ts"])

date_min = df_daily["trip_date"].min()
date_max = df_daily["trip_date"].max()
st.sidebar.info(f"Datenbereich: {date_min.date()} – {date_max.date()}")

# Date range filter
sel = st.sidebar.date_input("Datumsbereich", [date_min.date(), date_max.date()])
if len(sel) == 2:
    mask = (df_daily["trip_date"].dt.date >= sel[0]) & (df_daily["trip_date"].dt.date <= sel[1])
    df_daily_f = df_daily[mask].copy()
    mask_h = (df_hourly["pickup_hour_ts"].dt.date >= sel[0]) & (df_hourly["pickup_hour_ts"].dt.date <= sel[1])
    df_hourly_f = df_hourly[mask_h].copy()
else:
    df_daily_f = df_daily.copy()
    df_hourly_f = df_hourly.copy()

# ── KPI Tiles ────────────────────────────────────────────────────────
latest = df_daily_f.iloc[-1] if not df_daily_f.empty else df_daily.iloc[-1]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Trips / Tag", f"{int(latest['trips']):,}")
c2.metric("Revenue / Tag", f"${latest['total_revenue']:,.0f}")
c3.metric("Ø Dauer", f"{latest['avg_trip_duration_min']:.1f} min")
c4.metric("Ø Distanz", f"{latest['avg_distance_miles']:.1f} mi")
c5.metric("Ø Passagiere", f"{latest['avg_passengers']:.2f}")

st.divider()

# ── Daily Time Series ────────────────────────────────────────────────
fig_ts = go.Figure()
fig_ts.add_trace(go.Scatter(x=df_daily_f["trip_date"], y=df_daily_f["trips"], name="Trips", line=dict(color=TAXI_YELLOW)))
fig_ts.add_trace(go.Scatter(x=df_daily_f["trip_date"], y=df_daily_f["total_revenue"], name="Revenue", yaxis="y2", line=dict(color="#333")))
fig_ts.update_layout(
    title="Tägliche Fahrten & Einnahmen",
    xaxis_title="Datum",
    yaxis=dict(title="Trips"),
    yaxis2=dict(title="Revenue ($)", overlaying="y", side="right"),
    height=350,
)
st.plotly_chart(fig_ts, use_container_width=True)

# ── Weekday vs Weekend ──────────────────────────────────────────────
weekday_avg = df_daily_f.groupby("pickup_weekday")["trips"].mean().reindex(
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
).reset_index()
colors = [TAXI_YELLOW if d not in ("Saturday", "Sunday") else "#888" for d in weekday_avg["pickup_weekday"]]
fig_wd = px.bar(weekday_avg, x="pickup_weekday", y="trips", title="Ø Fahrten pro Wochentag", color=weekday_avg["pickup_weekday"], color_discrete_sequence=colors)
fig_wd.update_layout(show_legend=False, height=300, xaxis_title="", yaxis_title="Ø Trips")
st.plotly_chart(fig_wd, use_container_width=True)

# ── Hourly Patterns ─────────────────────────────────────────────────
df_hourly_f["hour"] = df_hourly_f["pickup_hour_ts"].dt.hour
filter_opt = st.radio("Filter", ["Alle Tage", "Werktags", "Wochenende"], horizontal=True)
h_f = df_hourly_f.copy()
if filter_opt == "Werktags":
    h_f = h_f[h_f["is_weekend"] == False]
elif filter_opt == "Wochenende":
    h_f = h_f[h_f["is_weekend"] == True]
hourly_avg = h_f.groupby("hour")["trips"].mean().reset_index()
fig_hr = px.bar(hourly_avg, x="hour", y="trips", title="Ø Fahrten pro Stunde", color_discrete_sequence=[TAXI_YELLOW])
fig_hr.update_layout(height=300, xaxis_title="Stunde", yaxis_title="Ø Trips", xaxis=dict(dtick=1))
st.plotly_chart(fig_hr, use_container_width=True)

st.divider()

# ── Weather Correlation ──────────────────────────────────────────────
fig_rain = go.Figure()
fig_rain.add_trace(go.Bar(x=df_daily_f["trip_date"], y=df_daily_f["rain_hours"], name="Regenstunden", opacity=0.4, marker_color="#3b8bbb"))
fig_rain.add_trace(go.Scatter(x=df_daily_f["trip_date"], y=df_daily_f["trips"], name="Trips", yaxis="y2", line=dict(color=TAXI_YELLOW)))
fig_rain.update_layout(
    title="Trips vs Regenstunden",
    xaxis_title="Datum",
    yaxis=dict(title="Regenstunden"),
    yaxis2=dict(title="Trips", overlaying="y", side="right"),
    height=350,
)
st.plotly_chart(fig_rain, use_container_width=True)

col_a, col_b = st.columns(2)
with col_a:
    fig_sc1 = px.scatter(df_daily_f, x="avg_temperature_c", y="trips", title="Temperatur vs Fahrten", trendline="ols")
    fig_sc1.update_layout(height=300, xaxis_title="Ø Temperatur (°C)", yaxis_title="Trips")
    st.plotly_chart(fig_sc1, use_container_width=True)

with col_b:
    fig_sc2 = px.scatter(df_daily_f, x="avg_temperature_c", y="avg_distance_miles", title="Temperatur vs Ø Distanz", trendline="ols")
    fig_sc2.update_layout(height=300, xaxis_title="Ø Temperatur (°C)", yaxis_title="Ø Distanz (mi)")
    st.plotly_chart(fig_sc2, use_container_width=True)

# ── Rainy vs Dry ─────────────────────────────────────────────────────
df_daily_f["is_rainy"] = df_daily_f["rain_hours"] > 0
rain_compare = df_daily_f.groupby("is_rainy").agg(
    avg_trips=("trips", "mean"),
    avg_revenue=("total_revenue", "mean"),
    avg_distance=("avg_distance_miles", "mean"),
).reset_index()
rain_compare["label"] = rain_compare["is_rainy"].map({True: "Regentag", False: "Trocken"})

fig_rv = go.Figure()
fig_rv.add_trace(go.Bar(x=rain_compare["label"], y=rain_compare["avg_trips"], name="Ø Trips", marker_color=TAXI_YELLOW))
fig_rv.add_trace(go.Bar(x=rain_compare["label"], y=rain_compare["avg_distance"], name="Ø Distanz", marker_color="#888"))
fig_rv.update_layout(title="Regentag vs Trockener Tag", barmode="group", height=300, xaxis_title="", yaxis_title="Ø Wert")
st.plotly_chart(fig_rv, use_container_width=True)
