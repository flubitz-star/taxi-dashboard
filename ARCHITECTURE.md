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

`analysis/hourly.py` contains the data loading, preparation, calculation and
Streamlit presentation code for the hourly overview. The calculations
`peak_label(...)` and `weighted_trip_average(...)` are also defined there.

`analysis/weather.py` loads the Gold tables
`taxi_dev.gold.mobility_daily_comparison` and
`taxi_dev.gold.mobility_hourly_comparison`. They contain taxi, bike and weather
metrics and allow comparing the mobility types with temperature and
precipitation.

`analysis/revenue.py` loads `taxi_dev.gold.zone_revenue_hourly` and presents the
revenue analysis by pickup zone. The page offers a date-range filter, revenue
KPIs and breakdowns by pickup borough, zone, hour and weekday. A pickup borough
(`pu_borough`, e.g. Manhattan) contains several pickup zones (`pu_zone`, e.g.
JFK Airport). The German weekday names are derived from `pickup_dayofweek`
(1 = Sunday … 7 = Saturday) because the table provides English names.

The files `taxi_dashboard/hourly_overview.py`, `weather_comparison.py` and
`revenue_analysis.py` are only re-exports of the functions in `analysis/`. The
entry points in `app_pages/` import the render functions through them.

This layer is not yet fully separated into analysis and presentation: the files
use Streamlit and Plotly directly. Pure calculations should be moved into
Streamlit-independent functions where needed, so they are easier to test and
reuse.

## Data flow

1. `app.py` shows the navigation and runs the selected page.
2. An entry point in `app_pages/` calls the render function.
3. The render function loads data through a cached loader function.
4. The shared data access queries Databricks and validates the response.
5. The page logic converts data types, calculates metrics and renders Streamlit
   components and Plotly charts.

## Current state and next steps

- **Separate calculations from the UI:** Aggregations and KPI calculations should
  gradually be separated from the `st.*` calls.
- **Add tests:** Pure conversion and calculation functions are well suited for
  unit tests. Data access errors and empty results should also be covered.
- **Complete type hints:** Public loader and analysis functions should get clear
  parameter and return types.

These steps can be done incrementally. Existing pages should continue to be
started through their `app_pages/` entry points.
