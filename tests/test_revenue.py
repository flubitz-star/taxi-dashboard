import unittest

import pandas as pd

from taxi_dashboard.metrics.averages import weighted_trip_average
from taxi_dashboard.metrics.revenue import weighted_averages_by


class RevenueAnalysisTests(unittest.TestCase):
    def test_weighted_trip_average_uses_trip_counts(self) -> None:
        """Weight hourly average tips by trips rather than by row count."""
        data = pd.DataFrame(
            {
                "avg_tip": [1.0, 5.0],
                "trips": [9, 1],
            }
        )

        self.assertEqual(weighted_trip_average(data, "avg_tip"), 1.4)

    def test_weighted_trip_average_ignores_missing_tips_and_nonpositive_trips(self) -> None:
        """Ignore rows that cannot contribute to a per-trip average."""
        data = pd.DataFrame(
            {
                "avg_tip": [2.0, 100.0, None],
                "trips": [2, 0, 5],
            }
        )

        self.assertEqual(weighted_trip_average(data, "avg_tip"), 2.0)

    def test_weighted_trip_average_returns_nan_without_eligible_rows(self) -> None:
        """Return NaN when no row has both a tip average and positive trips."""
        data = pd.DataFrame({"avg_tip": [3.0], "trips": [0]})

        self.assertTrue(pd.isna(weighted_trip_average(data, "avg_tip")))

    def test_grouped_weighted_averages_use_trip_counts(self) -> None:
        """Compute each group's weighted average independently."""
        data = pd.DataFrame(
            {
                "zone": ["A", "A", "B"],
                "avg_tip": [1.0, 5.0, 3.0],
                "trips": [9, 1, 2],
            }
        )

        result = weighted_averages_by(data, ["zone"], "avg_tip").set_index("zone")

        self.assertEqual(result.loc["A", "avg_tip"], 1.4)
        self.assertEqual(result.loc["B", "avg_tip"], 3.0)


if __name__ == "__main__":
    unittest.main()
