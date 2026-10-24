import unittest

import pandas as pd

from taxi_dashboard.analysis.weather import (
    _data_quality_messages,
    _monthly_chart,
    _rain_groups,
    _share_from_counts,
    _temperature_groups,
)
from taxi_dashboard.config import RAIN_BUCKETS, TEMP_BUCKETS


class WeatherAnalysisTests(unittest.TestCase):
    def test_share_from_counts_handles_normal_and_zero_totals(self) -> None:
        """Calculate taxi share normally and return NaN when there are no trips."""
        share = _share_from_counts(pd.Series([60, 0]), pd.Series([40, 0]))

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

        grouped = _temperature_groups(hourly)

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

        grouped = _rain_groups(hourly)

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

        messages = _data_quality_messages(daily, hourly)

        self.assertEqual(
            messages,
            [
                "Tagesdaten: 1 doppelte Zeilen.",
                "Stundendaten: 1 doppelte Zeilen.",
                "Einige Zeilen haben kein gültiges Datum und werden nicht ausgewertet.",
                "Negative Trip-Zahlen entdeckt; bitte die Quelldaten prüfen.",
            ],
        )

    def test_monthly_chart_is_empty_without_daily_data(self) -> None:
        """Return an empty figure when there are no valid daily observations."""
        daily = pd.DataFrame({"pickup_date": pd.to_datetime([])})

        figure = _monthly_chart(daily)

        self.assertEqual(len(figure.data), 0)


if __name__ == "__main__":
    unittest.main()
