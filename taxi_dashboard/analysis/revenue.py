"""Revenue analysis by pickup zone.

Reads the Gold table `taxi_dev.gold.zone_revenue_hourly` (one row per pickup zone
and hour) and renders KPIs plus revenue breakdowns by borough, zone, hour of day
and weekday. A pickup zone is a TLC taxi zone; each zone belongs to one borough.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from taxi_dashboard.config import ZONE_REVENUE_TABLE
from taxi_dashboard.data.databricks import normalize_boolean, query_table

# Maps Spark's dayofweek (1 = Sunday ... 7 = Saturday) to the German display names.
# The table's own `pickup_weekday` column is English, so it is not used for display.
WEEKDAY_NAMES = {
    1: "Sonntag",
    2: "Montag",
    3: "Dienstag",
    4: "Mittwoch",
    5: "Donnerstag",
    6: "Freitag",
    7: "Samstag",
}
# Display order for charts and tables (week starts on Monday).
WEEKDAY_ORDER = [
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
]


@st.cache_data(ttl=300)
def load_revenue_data() -> pd.DataFrame:
    """Load and normalize hourly pickup-zone revenue from the Gold table.

    Databricks returns every value as a string, so dates, numbers and booleans are
    converted here. The result is cached for five minutes.

    Returns:
        One row per pickup zone and hour. `avg_trip_distance` is renamed to
        `avg_distance_miles`, `pickup_weekday` holds German weekday names, and
        missing zones/boroughs are filled with "Unknown" / "N/A".
    """
    data = query_table(
        ZONE_REVENUE_TABLE,
        [
            "pickup_date",
            "pickup_hour",
            "pickup_dayofweek",
            "pickup_weekday",
            "is_weekend",
            "pu_zone",
            "pu_borough",
            "trips",
            "total_revenue",
            "avg_fare",
            "avg_tip",
            "avg_trip_distance",
            "avg_trip_duration_min",
        ],
    )
    if data.empty:
        return data

    data = data.rename(columns={"avg_trip_distance": "avg_distance_miles"})
    data["pickup_date"] = pd.to_datetime(data["pickup_date"], errors="coerce")
    for column in (
        "pickup_hour",
        "pickup_dayofweek",
        "trips",
        "total_revenue",
        "avg_fare",
        "avg_tip",
        "avg_distance_miles",
        "avg_trip_duration_min",
    ):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["is_weekend"] = data["is_weekend"].map(normalize_boolean)
    # Derived from pickup_dayofweek to get German names in a stable order.
    data["pickup_weekday"] = data["pickup_dayofweek"].map(WEEKDAY_NAMES)
    data["pu_zone"] = data["pu_zone"].fillna("Unknown")
    data["pu_borough"] = data["pu_borough"].fillna("N/A")
    return data


def _money(value: float, decimals: int = 0) -> str:
    """Format a dollar amount such as `$1,234`, or "Keine Daten" for missing values."""
    if pd.isna(value):
        return "Keine Daten"
    return f"${value:,.{decimals}f}"


def _count(value: float) -> str:
    """Format a count with thousands separators, or "Keine Daten" if missing."""
    return f"{value:,.0f}" if pd.notna(value) else "Keine Daten"


def render_revenue_analysis() -> None:
    """Render the pickup-zone revenue dashboard.

    Layout: date-range filter in the sidebar, KPI row, revenue by borough, top 15
    zones (chart and table), revenue by hour of day, and revenue by weekday.
    """
    try:
        data = load_revenue_data()
    except Exception as error:
        st.error(f"Fehler beim Abruf der Umsatzdaten: {error}")
        st.stop()

    if data.empty:
        st.info("Die Gold-Tabelle enthält keine Umsatzdaten.")
        st.stop()

    dates = data["pickup_date"].dropna()
    if dates.empty:
        st.error("Die Tabelle enthält keine gültigen Abholdaten.")
        st.stop()

    with st.sidebar:
        st.subheader("Filter")
        selected_dates = st.date_input(
            "Zeitraum",
            value=(dates.min().date(), dates.max().date()),
            min_value=dates.min().date(),
            max_value=dates.max().date(),
        )

    # st.date_input returns a tuple while the user has picked only part of a range,
    # and a single date in other cases; normalize both to start_date/end_date.
    if isinstance(selected_dates, (tuple, list)):
        selected_dates = [value for value in selected_dates if value is not None]
        if not selected_dates:
            st.info("Bitte wähle mindestens ein Datum aus.")
            st.stop()
        start_date = selected_dates[0]
        end_date = selected_dates[-1]
        if len(selected_dates) == 1:
            end_date = start_date
        filtered = data.loc[
            data["pickup_date"].dt.date.between(start_date, end_date)
        ].copy()
    else:
        start_date = end_date = selected_dates
        filtered = data.loc[data["pickup_date"].dt.date == start_date].copy()

    if filtered.empty:
        st.info("Für den ausgewählten Zeitraum liegen keine Umsatzdaten vor.")
        st.stop()

    # KPIs: revenue per trip is total revenue / total trips (not a mean of row
    # averages), so busy hours and zones are weighted correctly.
    total_revenue = filtered["total_revenue"].sum(min_count=1)
    total_trips = filtered["trips"].sum(min_count=1)
    revenue_per_trip = (
        total_revenue / total_trips
        if pd.notna(total_revenue) and pd.notna(total_trips) and total_trips > 0
        else float("nan")
    )
    avg_tip = filtered["avg_tip"].mean()
    zone_revenue = filtered.groupby("pu_zone")["total_revenue"].sum()
    borough_revenue = filtered.groupby("pu_borough")["total_revenue"].sum()
    top_zone = zone_revenue.idxmax() if not zone_revenue.empty else "Keine Daten"
    top_borough = (
        borough_revenue.idxmax() if not borough_revenue.empty else "Keine Daten"
    )
    top_zone_amount = zone_revenue.max() if not zone_revenue.empty else float("nan")
    top_borough_amount = (
        borough_revenue.max() if not borough_revenue.empty else float("nan")
    )

    st.caption(f"Zeitraum: {start_date:%d.%m.%Y} – {end_date:%d.%m.%Y}")
    kpis = st.columns(6)
    kpis[0].metric("Gesamtumsatz", _money(total_revenue))
    kpis[1].metric("Gesamtfahrten", _count(total_trips))
    kpis[2].metric("Ø Umsatz pro Fahrt", _money(revenue_per_trip, 2))
    kpis[3].metric("Ø Trinkgeld", _money(avg_tip, 2))
    kpis[4].metric("Top-Zone", top_zone, help=_money(top_zone_amount))
    kpis[5].metric("Top-Abhol-Bezirk", top_borough, help=_money(top_borough_amount))

    # Revenue by pickup borough, including each borough's share of revenue and trips.
    borough_data = (
        filtered.groupby("pu_borough", as_index=False)
        .agg(trips=("trips", "sum"), total_revenue=("total_revenue", "sum"))
        .sort_values("total_revenue", ascending=True)
    )
    borough_data["revenue_share_pct"] = (
        borough_data["total_revenue"] / borough_data["total_revenue"].sum() * 100
    )
    borough_data["trip_share_pct"] = (
        borough_data["trips"] / borough_data["trips"].sum() * 100
    )
    borough_data["revenue_per_trip"] = (
        borough_data["total_revenue"]
        / borough_data["trips"].where(borough_data["trips"] > 0)
    )
    st.subheader("Umsatz nach Abhol-Bezirk")
    borough_chart = px.bar(
        borough_data,
        x="total_revenue",
        y="pu_borough",
        orientation="h",
        labels={"total_revenue": "Umsatz ($)", "pu_borough": "Abhol-Bezirk"},
        hover_data={
            "trips": ":,.0f",
            "revenue_share_pct": ":.2f",
            "trip_share_pct": ":.2f",
            "revenue_per_trip": ":.2f",
        },
    )
    borough_chart.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(
        borough_chart,
        width="stretch",
        alt="Horizontaler Balkenvergleich des Gesamtumsatzes je Abhol-Bezirk.",
    )

    # Top 15 pickup zones by total revenue; averages are simple means over hourly rows.
    zone_data = (
        filtered.groupby(["pu_zone", "pu_borough"], as_index=False)
        .agg(
            trips=("trips", "sum"),
            total_revenue=("total_revenue", "sum"),
            avg_fare=("avg_fare", "mean"),
            avg_tip=("avg_tip", "mean"),
            avg_distance_miles=("avg_distance_miles", "mean"),
            avg_trip_duration_min=("avg_trip_duration_min", "mean"),
        )
        .sort_values("total_revenue", ascending=False)
        .head(15)
    )
    zone_data["revenue_per_trip"] = (
        zone_data["total_revenue"] / zone_data["trips"].where(zone_data["trips"] > 0)
    )
    st.subheader("Top 15 Pickup-Zonen nach Umsatz")
    zone_chart = px.bar(
        zone_data.sort_values("total_revenue", ascending=True),
        x="total_revenue",
        y="pu_zone",
        color="pu_borough",
        orientation="h",
        labels={
            "total_revenue": "Umsatz ($)",
            "pu_zone": "Pickup-Zone",
            "pu_borough": "Abhol-Bezirk",
        },
        hover_data={
            "trips": ":,.0f",
            "revenue_per_trip": ":.2f",
            "avg_fare": ":.2f",
            "avg_tip": ":.2f",
            "avg_distance_miles": ":.2f",
            "avg_trip_duration_min": ":.2f",
        },
    )
    st.plotly_chart(
        zone_chart,
        width="stretch",
        alt="Top 15 Pickup-Zonen nach Umsatz, eingefärbt nach Abhol-Bezirk.",
    )
    st.dataframe(
        zone_data[
            [
                "pu_zone",
                "pu_borough",
                "total_revenue",
                "trips",
                "revenue_per_trip",
                "avg_fare",
                "avg_tip",
                "avg_distance_miles",
                "avg_trip_duration_min",
            ]
        ].rename(
            columns={
                "pu_zone": "Zone",
                "pu_borough": "Abhol-Bezirk",
                "total_revenue": "Umsatz ($)",
                "trips": "Fahrten",
                "revenue_per_trip": "Umsatz/Fahrt ($)",
                "avg_fare": "Ø Fare ($)",
                "avg_tip": "Ø Tip ($)",
                "avg_distance_miles": "Ø Distanz (mi)",
                "avg_trip_duration_min": "Ø Dauer (min)",
            }
        ),
        hide_index=True,
        alt="Detailtabelle der 15 umsatzstärksten Pickup-Zonen.",
    )

    st.subheader("Umsatz nach Stunde des Tages")
    # Average revenue per zone-hour for each hour of the day (0-23).
    hourly_data = (
        filtered.groupby("pickup_hour", as_index=False)
        .agg(
            avg_revenue=("total_revenue", "mean"),
            avg_trips=("trips", "mean"),
            avg_fare=("avg_fare", "mean"),
            avg_tip=("avg_tip", "mean"),
        )
        .sort_values("pickup_hour")
    )
    hourly_chart = px.line(
        hourly_data,
        x="pickup_hour",
        y="avg_revenue",
        markers=True,
        labels={"pickup_hour": "Stunde", "avg_revenue": "Ø Umsatz je Zone-Stunde ($)"},
    )
    hourly_chart.update_xaxes(tickmode="linear", dtick=1)
    st.plotly_chart(
        hourly_chart,
        width="stretch",
        alt="Durchschnittlicher Umsatz je Zone-Stunde im Tagesverlauf.",
    )

    # Revenue per weekday; avg_revenue_per_day divides by the number of distinct
    # dates of that weekday in the selected range.
    weekday_data = (
        filtered.groupby(
            ["pickup_dayofweek", "pickup_weekday", "is_weekend"], as_index=False
        )
        .agg(
            trips=("trips", "sum"),
            total_revenue=("total_revenue", "sum"),
            days=("pickup_date", "nunique"),
            avg_fare=("avg_fare", "mean"),
            avg_tip=("avg_tip", "mean"),
        )
    )
    weekday_data["avg_revenue_per_day"] = (
        weekday_data["total_revenue"]
        / weekday_data["days"].where(weekday_data["days"] > 0)
    )
    weekday_data["pickup_weekday"] = pd.Categorical(
        weekday_data["pickup_weekday"], categories=WEEKDAY_ORDER, ordered=True
    )
    weekday_data = weekday_data.sort_values("pickup_weekday")
    weekday_data["weekend_label"] = weekday_data["is_weekend"].map(
        {True: "Ja", False: "Nein"}
    )
    st.subheader("Umsatz nach Wochentag")
    weekday_chart = px.bar(
        weekday_data,
        x="pickup_weekday",
        y="total_revenue",
        color="weekend_label",
        color_discrete_map={"Ja": "#FF9800", "Nein": "#2196F3"},
        labels={
            "pickup_weekday": "Wochentag",
            "total_revenue": "Umsatz ($)",
            "weekend_label": "Wochenende",
        },
        category_orders={"pickup_weekday": WEEKDAY_ORDER},
    )
    st.plotly_chart(
        weekday_chart,
        width="stretch",
        alt="Umsatz je Wochentag; die Farbe unterscheidet Wochenende und Werktage.",
    )
    st.dataframe(
        weekday_data[
            [
                "pickup_weekday",
                "weekend_label",
                "total_revenue",
                "trips",
                "avg_revenue_per_day",
                "avg_fare",
                "avg_tip",
            ]
        ].rename(
            columns={
                "pickup_weekday": "Wochentag",
                "weekend_label": "Wochenende?",
                "total_revenue": "Umsatz ($)",
                "trips": "Fahrten",
                "avg_revenue_per_day": "Ø Umsatz/Tag ($)",
                "avg_fare": "Ø Fare ($)",
                "avg_tip": "Ø Tip ($)",
            }
        ),
        hide_index=True,
        alt="Umsatz, Fahrten und Durchschnittswerte je Wochentag.",
    )
