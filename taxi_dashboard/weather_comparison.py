"""Weather comparison for taxi and bike-share trips."""

# Fetches and visualizes mobility data from the Databricks Gold layer, comparing
# taxi demand with bike-share usage across daily and hourly weather conditions.

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, Format
from plotly.subplots import make_subplots


# Databricks SQL configuration for the warehouse and the curated data tables used
# by this dashboard page.
WAREHOUSE_ID = "b4c5e8896d8800fe"
DAILY_TABLE = "workspace.gold.mobility_daily_comparison"
HOURLY_TABLE = "workspace.gold.mobility_hourly_comparison"

# Color palette used consistently across all charts for quick visual comparison.
TAXI_COLOR = "#FF9800"
BIKE_COLOR = "#21F387"
TEMP_BUCKETS = ["<15°C", "15–20°C", "20–25°C", "25–30°C", "≥30°C"]
RAIN_BUCKETS = ["0 mm", "0–0.5 mm", "0.5–2 mm", "≥2 mm"]


def _query_table(table: str, columns: list[str]) -> pd.DataFrame:
    # Executes a lightweight SQL query against the Databricks warehouse and returns
    # the selected columns as a pandas DataFrame for downstream analysis.
    response = WorkspaceClient().statement_execution.execute_statement(
        statement=f"SELECT {', '.join(columns)} FROM {table}",
        warehouse_id=WAREHOUSE_ID,
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
        raise RuntimeError(
            f"Query did not complete (status: {state}, id: {statement_id})"
        )

    names = [column.name for column in response.manifest.schema.columns]
    missing = sorted(set(columns) - set(names))
    if missing:
        raise RuntimeError(
            f"{table} is missing expected columns: {', '.join(missing)}"
        )
    rows = response.result.data_array if response.result else []
    return pd.DataFrame(rows or [], columns=names)


@st.cache_data(ttl=300)
def load_weather_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and prepare the compact daily and hourly Gold comparison tables."""
    # Load both curated tables and normalize the field types so the analysis logic
    # can safely aggregate dates, counts, temperatures, and rain values.
    daily = _query_table(
        DAILY_TABLE,
        [
            "pickup_date",
            "taxi_trips",
            "bike_trips",
            "total_trips",
            "bike_share_pct",
            "avg_temp_c",
            "max_temp_c",
            "min_temp_c",
            "total_rain_mm",
            "hours_rain",
            "has_rain",
        ],
    )
    hourly = _query_table(
        HOURLY_TABLE,
        [
            "pickup_date",
            "pickup_hour",
            "taxi_trips",
            "bike_trips",
            "temperature_2m_c",
            "rain_mm",
            "has_rain",
        ],
    )

    for frame, numeric_columns in (
        (
            daily,
            [
                "taxi_trips",
                "bike_trips",
                "total_trips",
                "bike_share_pct",
                "avg_temp_c",
                "max_temp_c",
                "min_temp_c",
                "total_rain_mm",
                "hours_rain",
            ],
        ),
        (
            hourly,
            [
                "pickup_hour",
                "taxi_trips",
                "bike_trips",
                "temperature_2m_c",
                "rain_mm",
            ],
        ),
    ):
        frame["pickup_date"] = pd.to_datetime(frame["pickup_date"], errors="coerce")
        for column in numeric_columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if "has_rain" in frame:
            frame["has_rain"] = frame["has_rain"].map(_to_bool)

    daily["taxi_share_pct"] = 100 - daily["bike_share_pct"]
    computed_share = _share_from_counts(daily["taxi_trips"], daily["bike_trips"])
    daily["taxi_share_pct"] = daily["taxi_share_pct"].where(
        daily["taxi_share_pct"].notna(), computed_share
    )
    hourly["total_trips"] = hourly["taxi_trips"] + hourly["bike_trips"]
    hourly["taxi_share_pct"] = _share_from_counts(
        hourly["taxi_trips"], hourly["bike_trips"]
    )
    daily["month"] = daily["pickup_date"].dt.strftime("%Y-%m")
    hourly["month"] = hourly["pickup_date"].dt.strftime("%Y-%m")
    return daily, hourly


def _to_bool(value: object) -> bool | None:
    # Converts flexible boolean-like values from Databricks into consistent Python
    # booleans for the rain flag used in daily summaries.
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


def _share_from_counts(taxi: pd.Series, bike: pd.Series) -> pd.Series:
    # Calculate taxi share from raw counts while guarding against zero totals.
    total = taxi + bike
    return (100 * taxi / total).where(total > 0)


def _format_number(value: float, suffix: str = "") -> str:
    # Format large numeric values so the KPI cards remain compact and readable.
    return f"{value:,.0f}{suffix}" if pd.notna(value) else "Keine Daten"


def _format_percent(value: float) -> str:
    # Keep percentage values with a single decimal place for clean dashboard output.
    return f"{value:.1f}%" if pd.notna(value) else "Keine Daten"


def _temperature_groups(hourly: pd.DataFrame) -> pd.DataFrame:
    # Aggregate hourly trips by temperature bucket to compare trip demand and taxi share.
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


def _rain_groups(hourly: pd.DataFrame) -> pd.DataFrame:
    # Group hourly records by rain intensity to reveal how precipitation affects taxi demand.
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


def _monthly_chart(daily: pd.DataFrame) -> go.Figure:
    # Main monthly trend chart combining trip counts, taxi share, and temperature range.
    data = daily.dropna(subset=["pickup_date"]).sort_values("pickup_date")
    fig = go.Figure()
    if data.empty:
        return fig

    dates = data["pickup_date"]
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=data["min_temp_c"],
            yaxis="y3",
            mode="lines",
            line={"width": 0, "color": "rgba(255,152,0,0)"},
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=data["max_temp_c"],
            yaxis="y3",
            mode="lines",
            line={"width": 0, "color": "rgba(255,152,0,0)"},
            fill="tonexty",
            fillcolor="rgba(255,152,0,0.14)",
            name="Temperaturspanne",
            hovertemplate="%{x|%d.%m.}: %{y:.1f}°C<extra></extra>",
        )
    )
    for column, label, color in (
        ("taxi_trips", "Taxi-Trips", TAXI_COLOR),
        ("bike_trips", "Bike-Trips", BIKE_COLOR),
    ):
        fig.add_trace(
            go.Bar(
                x=dates,
                y=data[column],
                name=label,
                marker_color=color,
                hovertemplate="%{x|%d.%m.}: %{y:,.0f}<extra>" + label + "</extra>",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=data["taxi_share_pct"],
            yaxis="y2",
            mode="lines+markers",
            name="Taxi-Share",
            line={"color": "#263238", "width": 2},
            marker={"size": 6},
            hovertemplate="%{x|%d.%m.}: %{y:.1f}%<extra>Taxi-Share</extra>",
        )
    )
    for row in data.loc[data["has_rain"].eq(True)].itertuples():
        day = row.pickup_date.normalize()
        fig.add_vrect(
            x0=day,
            x1=day + pd.Timedelta(days=1),
            fillcolor="rgba(25,118,210,0.07)",
            line_width=0,
            layer="below",
        )
    fig.update_layout(
        barmode="stack",
        height=430,
        margin={"r": 90},
        xaxis_title="Datum",
        yaxis={"title": "Trips pro Tag"},
        yaxis2={
            "title": "Taxi-Share",
            "overlaying": "y",
            "side": "right",
            "range": [0, 100],
            "ticksuffix": "%",
        },
        yaxis3={
            "title": "Temperatur",
            "overlaying": "y",
            "side": "right",
            "position": 1,
            "anchor": "free",
            "ticksuffix": "°C",
            "showgrid": False,
        },
        legend={"orientation": "h", "y": 1.12},
        hovermode="x unified",
    )
    return fig


def _temperature_chart(hourly: pd.DataFrame) -> go.Figure:
    # Plot average trip counts and taxi share grouped by hourly temperature bands.
    summary = _temperature_groups(hourly)
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Ø Trips pro beobachteter Stunde", "Taxi-Share und Stichprobe"),
        horizontal_spacing=0.16,
    )
    for label, column, color in (
        ("Taxi", "taxi_trips", TAXI_COLOR),
        ("Bike", "bike_trips", BIKE_COLOR),
    ):
        fig.add_trace(
            go.Bar(
                x=summary["temp_bucket"].astype(str),
                y=summary[column],
                name=label,
                marker_color=color,
                hovertemplate="%{x}: %{y:.1f} Trips/Stunde<extra>" + label + "</extra>",
            ),
            row=1,
            col=1,
        )
    palette = ["#E53935", "#FB8C00", "#FDD835", "#43A047", "#1E88E5"]
    fig.add_trace(
        go.Bar(
            x=summary["temp_bucket"].astype(str),
            y=summary["taxi_share"],
            marker_color=palette,
            text=[
                f"{value:.1f}%<br>n={int(count)}" if pd.notna(value) else "n=0"
                for value, count in zip(summary["taxi_share"], summary["observations"])
            ],
            textposition="outside",
            showlegend=False,
            hovertemplate="%{x}: %{y:.1f}%<extra>Taxi-Share</extra>",
        ),
        row=1,
        col=2,
    )
    fig.update_layout(
        barmode="group",
        height=430,
        legend={"orientation": "h", "y": 1.12},
        margin={"t": 90},
    )
    fig.update_yaxes(title_text="Ø Trips / Stunde", row=1, col=1)
    fig.update_yaxes(title_text="Ø Taxi-Share", ticksuffix="%", row=1, col=2)
    return fig


def _rain_daily_chart(daily: pd.DataFrame) -> go.Figure:
    # Scatter plot for daily rainfall and taxi share, with color intensity showing rainy hours.
    fig = go.Figure()
    points = daily.dropna(subset=["total_rain_mm", "taxi_share_pct"]).copy()
    fig.add_trace(
        go.Scatter(
            x=points["total_rain_mm"],
            y=points["taxi_share_pct"],
            mode="markers",
            marker={
                "size": 10,
                "color": points["hours_rain"],
                "colorscale": "YlOrRd",
                "showscale": True,
                "colorbar": {"title": "Regen-<br>stunden"},
            },
            text=points["pickup_date"].dt.strftime("%d.%m.%Y"),
            customdata=points[["hours_rain"]],
            hovertemplate="%{text}<br>Regen: %{x:.1f} mm<br>Taxi-Share: %{y:.1f}%"
            "<br>Regenstunden: %{customdata[0]}<extra></extra>",
            name="Tage",
        )
    )
    fig.update_layout(height=430, margin={"t": 90})
    fig.update_xaxes(title_text="Tagesniederschlag (mm)")
    fig.update_yaxes(title_text="Taxi-Share", ticksuffix="%")
    return fig


def _hourly_rain_chart(hourly: pd.DataFrame) -> go.Figure:
    # Compare taxi share across hourly rain intensities to reveal weather sensitivity.
    summary = _rain_groups(hourly)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=summary["rain_bucket"].astype(str),
            y=summary["taxi_share"],
            marker_color=["#43A047", "#FDD835", "#FB8C00", "#E53935"],
            text=[
                f"{value:.1f}%<br>n={int(count)}" if pd.notna(value) else "n=0"
                for value, count in zip(summary["taxi_share"], summary["observations"])
            ],
            textposition="outside",
            showlegend=False,
            hovertemplate="%{x}: %{y:.1f}%<extra>Taxi-Share</extra>",
        )
    )
    dry_share = summary.loc[summary["rain_bucket"].astype(str) == "0 mm", "taxi_share"]
    dry_share = dry_share.iloc[0] if not dry_share.empty else float("nan")
    if pd.notna(dry_share):
        fig.add_hline(
            y=dry_share,
            line_dash="dot",
            line_color="#424242",
            annotation_text=f"Trocken: {dry_share:.1f}%",
        )
    fig.update_layout(height=430, margin={"t": 90})
    fig.update_xaxes(title_text="Stündliche Regenintensität")
    fig.update_yaxes(title_text="Ø Taxi-Share", ticksuffix="%")
    return fig


def _data_quality_messages(daily: pd.DataFrame, hourly: pd.DataFrame) -> list[str]:
    # Validate the selected month for duplicate rows, missing timestamps, or invalid counts.
    messages = []
    for label, frame, key, expected_per_day in (
        ("Tagesdaten", daily, "pickup_date", 1),
        ("Stundendaten", hourly, ["pickup_date", "pickup_hour"], 24),
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


def render_weather_comparison() -> None:
    # Render the dashboard page for the chosen month, including KPI cards and weather-driven charts.
    st.caption(
        "Vergleicht Taxi- und Bike-Nachfrage mit Temperatur und Niederschlag. "
        "Wetter-Zusammenhänge sind Beobachtungen, keine Kausalitätsnachweise."
    )
    try:
        daily, hourly = load_weather_data()
    except Exception as error:
        st.error(f"Fehler beim Abruf der Wetterdaten: {error}")
        st.stop()

    if daily.empty and hourly.empty:
        st.info("Die Gold-Tabellen enthalten keine Wetter- und Mobilitätsdaten.")
        st.stop()
    if daily.empty:
        st.warning("Keine Tagesdaten verfügbar; Monatsübersicht und Tagesanalyse entfallen.")
    if hourly.empty:
        st.warning("Keine Stundendaten verfügbar; Temperatur- und Regenintensitätsanalyse entfallen.")

    available_months = sorted(
        set(daily["month"].dropna().unique()) | set(hourly["month"].dropna().unique())
    )
    if not available_months:
        st.info("Für die Daten ist kein gültiger Monat bestimmbar.")
        st.stop()
    selected_month = st.selectbox("Monat", available_months, index=len(available_months) - 1)
    month_daily = daily.loc[daily["month"] == selected_month].copy()
    month_hourly = hourly.loc[hourly["month"] == selected_month].copy()
    quality_messages = _data_quality_messages(month_daily, month_hourly)
    for message in quality_messages:
        st.warning(f"Datenprüfung: {message}")

    st.subheader(f"Monatsübersicht — {selected_month}")
    taxi_total = month_daily["taxi_trips"].sum(min_count=1)
    bike_total = month_daily["bike_trips"].sum(min_count=1)
    total = taxi_total + bike_total
    weighted_share = 100 * taxi_total / total if pd.notna(total) and total > 0 else float("nan")
    temperatures = month_daily["avg_temp_c"].dropna()
    temp_range = (
        f"{month_daily['min_temp_c'].min():.0f}–{month_daily['max_temp_c'].max():.0f}°C"
        if month_daily["min_temp_c"].notna().any() and month_daily["max_temp_c"].notna().any()
        else "Keine Daten"
    )
    rainy_days = int(month_daily["has_rain"].eq(True).sum())
    metrics = st.columns(6)
    metrics[0].metric("Taxi-Trips", _format_number(taxi_total))
    metrics[1].metric("Bike-Trips", _format_number(bike_total))
    metrics[2].metric("Taxi-Share", _format_percent(weighted_share))
    metrics[3].metric(
        "Ø Temperatur",
        f"{temperatures.mean():.1f}°C" if not temperatures.empty else "Keine Daten",
        help=temp_range,
    )
    metrics[4].metric(
        "Heiße Tage (≥25°C)",
        _format_number(month_daily["max_temp_c"].ge(25).sum()),
    )
    metrics[5].metric(
        "Regentage",
        f"{rainy_days} / {month_daily['pickup_date'].nunique()}",
    )
    max_rain = month_daily["total_rain_mm"].max()
    st.caption(f"Maximaler Tagesniederschlag: {_format_number(max_rain, ' mm')}")

    st.plotly_chart(
        _monthly_chart(month_daily),
        width="stretch",
        alt="Tägliche Taxi- und Bike-Trips mit Taxi-Anteil, Temperaturspanne und Markierung von Regentagen.",
    )

    if not month_hourly.empty:
        st.subheader("Wärmere Stunden und Taxi-Share")
        st.plotly_chart(
            _temperature_chart(month_hourly),
            width="stretch",
            alt="Durchschnittliche Taxi- und Bike-Trips sowie Taxi-Anteil nach stündlichen Temperaturbereichen.",
        )

    st.subheader("Täglicher Niederschlag und Taxi-Share")
    if not month_daily.empty:
        st.plotly_chart(
            _rain_daily_chart(month_daily),
            width="stretch",
            alt="Täglicher Niederschlag im Vergleich zum Taxi-Anteil; die Farbe zeigt die Regenstunden.",
        )
    else:
        st.info("Für den Vergleich von Tagesregen und Taxi-Anteil liegen keine Tagesdaten vor.")

    if not month_hourly.empty:
        st.subheader("Taxi-Anteil nach stündlicher Regenintensität")
        st.plotly_chart(
            _hourly_rain_chart(month_hourly),
            width="stretch",
            alt="Durchschnittlicher Taxi-Anteil nach stündlicher Regenintensität.",
        )
