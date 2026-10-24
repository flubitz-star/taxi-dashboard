# Dashboard architecture

## Overview

The dashboard is a Streamlit application. `app.py` configures the app and
registers the pages. The page entry points in `app_pages/` delegate to functions
in the Python package `taxi_dashboard/`.

```text
app.py
  └── app_pages/                 Streamlit page entry points
        └── taxi_dashboard/      Data access, preparation and presentation
              ├── config.py      Shared configuration
              ├── data/          Databricks access
              ├── analysis/      Hourly, weather and revenue analyses
              └── *.py           Thin re-exports of the analysis functions
```

## Pages and data sources

| Page | Entry point | Analysis module | Gold table |
| --- | --- | --- | --- |
| Home | `app_pages/home.py` | – | – |
| Hourly Overview | `app_pages/hourly_overview.py` | `analysis/hourly.py` | `taxi_dev.gold.hourly_ridership` |
| Weather & mobility | `app_pages/weather_comparison.py` | `analysis/weather.py` | `taxi_dev.gold.mobility_daily_comparison`, `taxi_dev.gold.mobility_hourly_comparison` |
| Revenue by pickup zone | `app_pages/revenue_analysis.py` | `analysis/revenue.py` | `taxi_dev.gold.zone_revenue_hourly` |

All pages read exclusively from the Gold layer; Silver tables are not queried.

### Data contracts and interpretation

The dashboard consumes curated Gold tables and expects these row-level
granularities:

| Gold table | Expected granularity | Notes |
| --- | --- | --- |
| `taxi_dev.gold.hourly_ridership` | One row per calendar date and hour | Missing hours are not filled with zero; hourly averages use observed rows. |
| `taxi_dev.gold.mobility_daily_comparison` | One row per date | Daily taxi and bike counts are used for totals and the monthly taxi share. |
| `taxi_dev.gold.mobility_hourly_comparison` | One row per date and hour | Weather buckets count observed hourly rows. |
| `taxi_dev.gold.zone_revenue_hourly` | One row per pickup zone and hour | Revenue totals are summed; hourly and zone-level source averages are not automatically trip-weighted. |

These are application assumptions, not runtime-enforced uniqueness
constraints. Weather and hourly pages report selected data-quality issues;
the revenue page does not currently perform an equivalent duplicate-row check.
The app does not determine source freshness or enforce a fixed date range. Check
the Gold tables when the dashboard appears stale or the expected period is
missing.

The meaning of an average depends on the page:

- Hourly overview demand and hourly revenue compare means over observed rows.
- The weather month-level taxi share is weighted by total taxi and bike trips;
  shares in temperature and rain buckets are means of hourly shares. Those
  bucket values are not the share of all trips in the bucket.
- Revenue per trip is calculated from summed revenue divided by summed trips.
  Tip averages (`avg_tip`) are weighted by trips for the overall KPI and
  breakdowns. Other source average columns, such as `avg_fare`, are currently
  simple means of hourly rows; interpret them as averages of source averages,
  not necessarily per-trip averages.

## Running and deployment

- Local development uses Python 3.12 in `run_dashboard.ps1`; the script creates
  `.venv` if needed, installs `requirements.txt`, and starts `app.py`.
- `app.yaml` configures `streamlit run app.py` as the application command. It
  does not itself provision Python dependencies or Databricks credentials.
- `WorkspaceClient()` uses the Databricks SDK's configured authentication. The
  local script defaults `DATABRICKS_CONFIG_PROFILE` to `dbc-b5503989-0919` when
  it is not already set. Provide a valid profile or another supported SDK
  authentication configuration in the runtime; do not store credentials in
  application code or this repository.
- `WAREHOUSE_ID` in `taxi_dashboard/config.py` identifies the SQL warehouse; it
  is configuration, not an authentication credential. It is currently fixed
  in code.
- `requirements.txt` lists direct dependencies without version pins. Recreating
  the exact environment may therefore install different package versions over
  time.

## Runtime and scaling notes

Page loaders cache data for five minutes. The shared Databricks helper selects
requested columns but does not add date filters or aggregations; it retrieves
all result chunks before converting the result to a DataFrame. This is suitable
for the current curated showcase tables. If those tables grow substantially,
push date filters and aggregations into SQL before loading data into the app.

## Layers and responsibilities

### Application entry point: `app.py`

- Sets the page title, icon and layout.
- Defines the navigation with `st.navigation`.
- Runs the selected page.

New dashboard pages are registered here and get their own entry point in
`app_pages/`.

### Pages: `app_pages/`

The files in this folder are thin Streamlit entry points. They import the
responsible render function and call it. Data access and calculations should not
be added here.

### Configuration: `taxi_dashboard/config.py`

Contains shared values such as the warehouse ID, table names and chart color
groups. New shared configuration values belong here instead of being defined
several times in individual pages.

### Data access: `taxi_dashboard/data/`

`data/databricks.py` provides shared functions for the Databricks SQL queries:

- `query_table(...)` runs the query, checks for errors and expected columns, and
  returns a `pandas.DataFrame`. Databricks returns large results in several parts
  (chunks); the function reads all parts so the table is loaded completely. All
  values are returned as strings and are converted to dates, numbers and booleans
  in the analysis modules.
- `normalize_boolean(...)` normalizes boolean values returned by Databricks.

The pages cache the query results for a limited time with `st.cache_data`. The
cache duration is currently five minutes.

### Analysis and presentation: `taxi_dashboard/analysis/`

`analysis/hourly.py` contains the data loading, preparation and Streamlit
presentation code for the hourly overview. Pure calculations such as
`peak_label(...)` live in `taxi_dashboard/metrics/hourly.py`; the shared
trip-weighted average helper lives in `taxi_dashboard/metrics/averages.py`.

`analysis/weather.py` loads the Gold tables
`taxi_dev.gold.mobility_daily_comparison` and
`taxi_dev.gold.mobility_hourly_comparison`. They contain taxi, bike and weather
metrics and render comparisons of the mobility types with temperature and
precipitation. Type conversion, taxi-share calculations, weather buckets, and
data-quality messages are implemented in the Streamlit-independent
`taxi_dashboard/metrics/weather.py`; Plotly chart construction and page rendering
remain in `analysis/weather.py`.

`analysis/revenue.py` loads `taxi_dev.gold.zone_revenue_hourly` and presents the
revenue analysis by pickup zone. The page offers a date-range filter, revenue
KPIs and breakdowns by pickup borough, zone, hour and weekday. A pickup borough
(`pu_borough`, e.g. Manhattan) contains several pickup zones (`pu_zone`, e.g.
JFK Airport). The German weekday names are derived from `pickup_dayofweek`
(1 = Sunday … 7 = Saturday) because the table provides English names.

Pure revenue breakdown calculations live in
`taxi_dashboard/metrics/revenue.py`. They and the shared trip-weighted average
helper do not import Streamlit and can be tested independently from page
rendering.

The files `taxi_dashboard/hourly_overview.py`, `weather_comparison.py` and
`revenue_analysis.py` are only re-exports of the functions in `analysis/`. The
entry points in `app_pages/` import the render functions through them.

The analysis modules still combine data loading and UI rendering. The reusable
calculations and preparation code used by the dashboard is separated into
`taxi_dashboard/metrics/`; Plotly chart construction and Streamlit rendering
remain in `analysis/`.

## Data flow

1. `app.py` shows the navigation and runs the selected page.
2. An entry point in `app_pages/` calls the render function.
3. The render function loads data through a cached loader function.
4. The shared data access queries Databricks and validates the response.
5. Metric helpers prepare data and calculate reusable values; the analysis
   module renders Streamlit components and Plotly charts.

## Current state and next steps

- **Add tests:** Weather, hourly and revenue metric tests cover the current pure
  calculations. Add focused data-access error tests as that layer changes.
- **Complete type hints:** Public loader and analysis functions should get clear
  parameter and return types.
- **Make the demo reproducible:** Pin or lock dependency versions if the app
  needs to be recreated reliably in another environment.

These steps can be done incrementally. Existing pages should continue to be
started through their `app_pages/` entry points.
