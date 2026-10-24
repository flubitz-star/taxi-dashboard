"""Pure calculations for revenue analysis."""

import pandas as pd


def weighted_averages_by(
    data: pd.DataFrame, group_columns: list[str], value_column: str
) -> pd.DataFrame:
    """Compute trip-weighted source averages for each group."""
    valid = data.loc[
        data[value_column].notna() & data["trips"].gt(0),
        [*group_columns, value_column, "trips"],
    ].copy()
    valid["_weighted_value"] = valid[value_column] * valid["trips"]
    summary = (
        valid.groupby(group_columns, as_index=False, observed=True)
        .agg(_weighted_value=("_weighted_value", "sum"), _weight=("trips", "sum"))
    )
    summary[value_column] = summary["_weighted_value"] / summary["_weight"]
    return summary[[*group_columns, value_column]]
