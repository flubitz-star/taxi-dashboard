import unittest

import pandas as pd

from taxi_dashboard.metrics.hourly import peak_label


class HourlyMetricsTests(unittest.TestCase):
    def test_peak_label_reports_all_tied_hours(self) -> None:
        """Include each hour tied for the maximum value."""
        values = pd.Series([3, 5, 5], index=[8, 12, 18])

        self.assertEqual(peak_label(values), "12:00, 18:00")

    def test_peak_label_reports_no_data_for_empty_values(self) -> None:
        """Return the dashboard's no-data label when all values are missing."""
        values = pd.Series([float("nan")], index=[8])

        self.assertEqual(peak_label(values), "Keine Daten")


if __name__ == "__main__":
    unittest.main()
