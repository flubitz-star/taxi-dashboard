"""Shared dashboard configuration and Databricks table names."""

WAREHOUSE_ID = "b4c5e8896d8800fe"
DAILY_TABLE = "taxi_dev.gold.mobility_daily_comparison"
HOURLY_RIDERSHIP_TABLE = "taxi_dev.gold.hourly_ridership"
HOURLY_TABLE = "taxi_dev.gold.mobility_hourly_comparison"

TAXI_COLOR = "#FF9800"
BIKE_COLOR = "#21F387"
TEMP_BUCKETS = ["<15°C", "15–20°C", "20–25°C", "25–30°C", "≥30°C"]
RAIN_BUCKETS = ["0 mm", "0–0.5 mm", "0.5–2 mm", "≥2 mm"]
