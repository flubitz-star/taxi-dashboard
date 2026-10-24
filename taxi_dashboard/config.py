"""Shared dashboard configuration and Databricks table names."""

# SQL warehouse used for all Databricks queries.
WAREHOUSE_ID = "b4c5e8896d8800fe"

# Gold-layer tables (catalog.schema.table).
# Daily taxi vs. bike-share trips with daily weather values.
DAILY_TABLE = "taxi_dev.gold.mobility_daily_comparison"
# Taxi trips and revenue per hour (one row per hour).
HOURLY_RIDERSHIP_TABLE = "taxi_dev.gold.hourly_ridership"
# Hourly taxi vs. bike-share trips with hourly weather values.
HOURLY_TABLE = "taxi_dev.gold.mobility_hourly_comparison"
# Taxi trips and revenue per pickup zone and hour.
ZONE_REVENUE_TABLE = "taxi_dev.gold.zone_revenue_hourly"

# Chart colors shared by the mobility charts.
TAXI_COLOR = "#FF9800"
BIKE_COLOR = "#21F387"

# Ordered bucket labels for temperature (°C) and hourly rain (mm) groupings.
TEMP_BUCKETS = ["<15°C", "15–20°C", "20–25°C", "25–30°C", "≥30°C"]
RAIN_BUCKETS = ["0 mm", "0–0.5 mm", "0.5–2 mm", "≥2 mm"]
