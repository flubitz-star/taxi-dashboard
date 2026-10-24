import unittest

import pandas as pd

from taxi_dashboard.analysis.weather import (
    _monthly_chart,
)
from taxi_dashboard.config import RAIN_BUCKETS, TEMP_BUCKETS
from taxi_dashboard.metrics.weather import (
    data_quality_messages,
    prepare_weather_data,
    rain_groups,
    share_from_counts,
    temperature_groups,
)


class WeatherAnalysisTests(unittest.TestCase):
    def test_share_from_counts_handles_normal_and_zero_totals(self) -> None:
        """Calculate taxi share normally and return NaN when there are no trips."""
        share = share_from_counts(pd.Series([60, 0]), pd.Series([40, 0]))

        self.assertEqual(share.iloc[0], 60)
        self.assertTrue(pd.isna(share.iloc[1]))

    def test_temperature_groups_include_bucket_boundaries(self) -> None:
        """Assign observations at temperature boundaries to the correct buckets."""
        hourly = pd.DataFrame(
            {
                "temperature_2m_c": [14.9, 15, 20, 25, 30],
                "taxi_share_pct": [50] * 5,
                "taxi_trips": [1] * 5,
                "bike_trips": [1] * 5,
            }
        )

        grouped = temperature_groups(hourly)

        self.assertEqual(grouped["temp_bucket"].tolist(), TEMP_BUCKETS)
        self.assertEqual(grouped["observations"].tolist(), [1] * 5)

    def test_rain_groups_clip_negative_values_and_include_boundaries(self) -> None:
        """Clip negative rainfall to zero and group observations at bucket boundaries."""
        hourly = pd.DataFrame(
            {
                "rain_mm": [-1, 0, 0.01, 0.5, 2],
                "taxi_share_pct": [50] * 5,
            }
        )

        grouped = rain_groups(hourly)

        self.assertEqual(grouped["rain_bucket"].tolist(), RAIN_BUCKETS)
        self.assertEqual(grouped["observations"].tolist(), [2, 1, 1, 1])

    def test_data_quality_messages_report_duplicates_invalid_dates_and_negative_trips(
        self,
    ) -> None:
        """Report duplicate rows, invalid dates, and negative trip counts."""
        daily = pd.DataFrame(
            {
                "pickup_date": [pd.Timestamp("2026-01-01")] * 2,
                "taxi_trips": [-1, 2],
                "bike_trips": [0, 0],
            }
        )
        hourly = pd.DataFrame(
            {
                "pickup_date": [pd.NaT, pd.NaT],
                "pickup_hour": [1, 1],
                "taxi_trips": [0, 0],
                "bike_trips": [0, 0],
            }
        )

        messages = data_quality_messages(daily, hourly)

        self.assertEqual(
            messages,
            [
                "Tagesdaten: 1 doppelte Zeilen.",
                "Stundendaten: 1 doppelte Zeilen.",
                "Einige Zeilen haben kein gültiges Datum und werden nicht ausgewertet.",
                "Negative Trip-Zahlen entdeckt; bitte die Quelldaten prüfen.",
            ],
        )

    def test_prepare_weather_data_converts_columns_and_fills_missing_share(self) -> None:
        """Normalize source values and calculate taxi share when it is absent."""
        daily = pd.DataFrame(
            {
                "pickup_date": ["2026-01-01"],
                "taxi_trips": ["60"],
                "bike_trips": ["40"],
                "bike_share_pct": [None],
                "avg_temp_c": ["10"],
                "max_temp_c": ["12"],
                "min_temp_c": ["8"],
                "total_rain_mm": ["1.5"],
                "hours_rain": ["2"],
                "has_rain": ["true"],
            }
        )
        hourly = pd.DataFrame(
            {
                "pickup_date": ["2026-01-01"],
                "pickup_hour": ["8"],
                "taxi_trips": ["3"],
                "bike_trips": ["1"],
                "temperature_2m_c": ["9"],
                "rain_mm": ["0.5"],
                "has_rain": ["false"],
            }
        )

        prepared_daily, prepared_hourly = prepare_weather_data(daily, hourly)

        self.assertEqual(prepared_daily.loc[0, "taxi_share_pct"], 60)
        self.assertEqual(prepared_hourly.loc[0, "taxi_share_pct"], 75)
        self.assertEqual(prepared_daily.loc[0, "month"], "2026-01")
        self.assertTrue(prepared_daily.loc[0, "has_rain"])
        self.assertFalse(prepared_hourly.loc[0, "has_rain"])
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(prepared_daily["pickup_date"]))

    def test_prepare_weather_data_preserves_derived_columns_for_empty_tables(self) -> None:
        """Keep the expected schema available when a source table has no rows."""
        daily = pd.DataFrame(
            columns=[
                "pickup_date",
                "taxi_trips",
                "bike_trips",
                "bike_share_pct",
                "avg_temp_c",
                "max_temp_c",
                "min_temp_c",
                "total_rain_mm",
                "hours_rain",
                "has_rain",
            ]
        )
        hourly = pd.DataFrame(
            columns=[
                "pickup_date",
                "pickup_hour",
                "taxi_trips",
                "bike_trips",
                "temperature_2m_c",
                "rain_mm",
                "has_rain",
            ]
        )

        prepared_daily, prepared_hourly = prepare_weather_data(daily, hourly)

        self.assertIn("month", prepared_daily.columns)
        self.assertIn("taxi_share_pct", prepared_daily.columns)
        self.assertIn("month", prepared_hourly.columns)
        self.assertIn("taxi_share_pct", prepared_hourly.columns)

    def test_monthly_chart_is_empty_without_daily_data(self) -> None:
        """Return an empty figure when there are no valid daily observations."""
        daily = pd.DataFrame({"pickup_date": pd.to_datetime([])})

        figure = _monthly_chart(daily)

        self.assertEqual(len(figure.data), 0)


if __name__ == "__main__":
    unittest.main()
