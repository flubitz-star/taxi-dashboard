import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, Format


@st.cache_data(ttl=300)
def load_data():
    """Load hourly ridership data through the Databricks SQL Statement Execution API."""
    response = WorkspaceClient().statement_execution.execute_statement(
        statement=(
            "SELECT pickup_hour_ts, pickup_dayofweek, is_weekend, trips, total_revenue "
            "FROM workspace.gold.hourly_ridership"
        ),
        warehouse_id="b4c5e8896d8800fe",
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
    if response.manifest is None:
        statement_id = response.statement_id or "unknown"
        raise RuntimeError(f"Query did not complete (status: {state}, id: {statement_id})")

    columns = [column.name for column in response.manifest.schema.columns]
    rows = response.result.data_array if response.result else []
    data = pd.DataFrame(rows or [], columns=columns)
    if data.empty:
        return data

    data["pickup_hour_ts"] = pd.to_datetime(data["pickup_hour_ts"])
    data["pickup_dayofweek"] = pd.to_numeric(data["pickup_dayofweek"], errors="coerce")
    data["trips"] = pd.to_numeric(data["trips"], errors="coerce")
    data["total_revenue"] = pd.to_numeric(data["total_revenue"], errors="coerce")
    data["is_weekend"] = data["is_weekend"].map(
        lambda value: value if isinstance(value, bool) else str(value).lower() == "true"
    )
    data["hour"] = data["pickup_hour_ts"].dt.hour
    data["month"] = data["pickup_hour_ts"].dt.strftime("%Y-%m")
    data["day_type"] = data["is_weekend"].map({False: "Werktag", True: "Wochenende"})
    return data


def peak_label(values):
    available = values.dropna()
    if available.empty:
        return "Keine Daten"
    peak = available.max()
    return ", ".join(f"{hour:02d}:00" for hour in available[available == peak].index)


def render_hourly_overview():
    st.caption(
        "Fahrten je beobachteter Stunde zeigen Nachfrage, nicht die Anzahl gleichzeitig "
        "benötigter Taxis."
    )

    try:
        df = load_data()
    except Exception as error:
        st.error(f"Fehler beim Abruf der Stundenfahrten: {error}")
        st.stop()

    if df.empty:
        st.info("Die Tabelle enthält keine Stundenfahrten.")
        st.stop()

    months = sorted(df["month"].dropna().unique())
    selected_month = st.selectbox("Monat", ["Alle verfügbaren Monate", *months])
    filtered = df if selected_month == "Alle verfügbaren Monate" else df[df["month"] == selected_month]

    day_names = {
        1: "Sonntag",
        2: "Montag",
        3: "Dienstag",
        4: "Mittwoch",
        5: "Donnerstag",
        6: "Freitag",
        7: "Samstag",
    }
    filtered = filtered.copy()
    filtered["weekday"] = filtered["pickup_dayofweek"].map(day_names)
    hours = list(range(24))
    hourly = (
        filtered.groupby(["hour", "day_type"], observed=True)
        .agg(
            trips=("trips", "mean"),
            revenue=("total_revenue", "mean"),
            observations=("trips", "count"),
        )
        .reset_index()
    )

    weekday = hourly[hourly["day_type"] == "Werktag"].set_index("hour")
    weekend = hourly[hourly["day_type"] == "Wochenende"].set_index("hour")
    weekday_values = weekday["trips"].reindex(hours)
    weekend_values = weekend["trips"].reindex(hours)

    weekday_peak = peak_label(weekday_values)
    weekend_peak = peak_label(weekend_values)
    weekday_mean = filtered.loc[~filtered["is_weekend"], "trips"].mean()
    weekend_mean = filtered.loc[filtered["is_weekend"], "trips"].mean()

    kpis = st.columns(4)
    kpis[0].metric("Peak-Stunde Werktag", weekday_peak)
    kpis[1].metric("Peak-Stunde Wochenende", weekend_peak)
    kpis[2].metric(
        "Ø Fahrten / Stunde Werktag",
        f"{weekday_mean:.1f}" if pd.notna(weekday_mean) else "Keine Daten",
    )
    kpis[3].metric(
        "Ø Fahrten / Stunde Wochenende",
        f"{weekend_mean:.1f}" if pd.notna(weekend_mean) else "Keine Daten",
    )

    comparison = pd.DataFrame(
        {"Werktag": weekday_values, "Wochenende": weekend_values}
    ).dropna()
    if not comparison.empty:
        differences = comparison["Werktag"] - comparison["Wochenende"]
        largest_hour = differences.abs().idxmax()
        st.info(
            f"Größter Unterschied: {largest_hour:02d}:00 — "
            f"Werktag {comparison.loc[largest_hour, 'Werktag']:.1f}, "
            f"Wochenende {comparison.loc[largest_hour, 'Wochenende']:.1f} "
            "Fahrten pro beobachteter Stunde."
        )

    st.subheader("Stundenprofile")
    profile = hourly.rename(columns={"trips": "Ø Fahrten pro Stunde"})
    profile_chart = go.Figure()
    for label, color in [("Werktag", "#2196F3"), ("Wochenende", "#FF9800")]:
        values = profile[profile["day_type"] == label].set_index("hour")["Ø Fahrten pro Stunde"]
        profile_chart.add_trace(
            go.Scatter(
                x=hours,
                y=values.reindex(hours),
                mode="lines+markers",
                name=label,
                connectgaps=False,
                line={"color": color},
            )
        )
    profile_chart.update_layout(
        xaxis_title="Stunde", yaxis_title="Ø Fahrten / beobachtete Stunde"
    )
    profile_chart.update_xaxes(tickmode="linear", dtick=1)
    st.plotly_chart(profile_chart, width="stretch")

    left, right = st.columns(2)
    with left:
        heatmap = (
            filtered.groupby(["weekday", "hour"], observed=True)["trips"]
            .mean()
            .unstack("hour")
            .reindex(
                [
                    "Montag",
                    "Dienstag",
                    "Mittwoch",
                    "Donnerstag",
                    "Freitag",
                    "Samstag",
                    "Sonntag",
                ]
            )
            .reindex(columns=hours)
        )
        heatmap_chart = px.imshow(
            heatmap,
            labels={"x": "Stunde", "y": "Wochentag", "color": "Ø Fahrten"},
            aspect="auto",
            color_continuous_scale="Blues",
        )
        heatmap_chart.update_xaxes(tickmode="linear", dtick=1)
        st.plotly_chart(heatmap_chart, width="stretch")

    with right:
        difference_chart = go.Figure(
            go.Bar(
                x=hours,
                y=weekday_values - weekend_values,
                marker_color="#424242",
            )
        )
        difference_chart.add_hline(y=0, line_color="#424242")
        difference_chart.update_layout(
            xaxis_title="Stunde",
            yaxis_title="Werktag minus Wochenende (Ø Fahrten)",
        )
        difference_chart.update_xaxes(tickmode="linear", dtick=1)
        st.plotly_chart(difference_chart, width="stretch")

    revenue_chart = px.line(
        hourly,
        x="hour",
        y="revenue",
        color="day_type",
        markers=True,
        color_discrete_map={"Werktag": "#2196F3", "Wochenende": "#FF9800"},
        labels={
            "hour": "Stunde",
            "revenue": "Ø Stundenumsatz",
            "day_type": "Tagesart",
        },
        title="Durchschnittlicher Stundenumsatz",
    )
    revenue_chart.update_xaxes(tickmode="linear", dtick=1)
    st.plotly_chart(revenue_chart, width="stretch")

    st.subheader("Details")
    details = hourly.rename(
        columns={
            "hour": "Stunde",
            "day_type": "Tagesart",
            "observations": "Beobachtungen",
            "trips": "Ø Fahrten",
            "revenue": "Ø Stundenumsatz",
        }
    )
    st.dataframe(
        details[
            ["Stunde", "Tagesart", "Beobachtungen", "Ø Fahrten", "Ø Stundenumsatz"]
        ].sort_values(["Stunde", "Tagesart"]),
        width="stretch",
        hide_index=True,
    )

    duplicate_count = int(filtered["pickup_hour_ts"].duplicated().sum())
    expected_rows = sum(
        period.days_in_month * 24
        for period in filtered["pickup_hour_ts"].dt.to_period("M").unique()
    )
    if duplicate_count or len(filtered) != expected_rows:
        st.warning(
            f"Datenprüfung: {len(filtered)} Stundenzeilen (erwartet {expected_rows}), "
            f"{duplicate_count} doppelte Zeitstempel. Mittelwerte beziehen sich nur auf "
            "vorhandene Zeilen; fehlende Stunden werden nicht als null gewertet."
        )
    else:
        st.caption(
            f"Datenprüfung: {len(filtered)} eindeutige Stundenzeilen; keine Stunden fehlen."
        )
