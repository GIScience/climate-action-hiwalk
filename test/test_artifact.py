import pandas as pd

from walkability.artifact import clean_slope_data


def test_clean_negative_slope():
    raw_slope = pd.Series([-0.5, -2.0, 1.0])
    slope_cleaned_values, _ = clean_slope_data(raw_slope)
    pd.testing.assert_series_equal(slope_cleaned_values, pd.Series([0.5, 2.0, 1.0]))


def test_scale_slope():
    raw_slope = pd.Series([0.0, 6.0, 12.0])
    _, slope_color_values = clean_slope_data(raw_slope)
    pd.testing.assert_series_equal(slope_color_values, pd.Series([0.0, 0.5, 1.0]))


def test_scale_steep_slope():
    raw_slope = pd.Series([0.0, 6.0, 12.0, 13.0])
    _, slope_color_values = clean_slope_data(raw_slope)
    pd.testing.assert_series_equal(slope_color_values, pd.Series([0.0, 0.5, 1.0, 1.0]))
