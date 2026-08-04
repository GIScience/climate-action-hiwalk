import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from climatoology.base.artifact_creators import Artifact
from pydantic_extra_types.color import Color

from walkability.components.network_analyses.detour_analysis import (
    DetourCategory,
    apply_color_and_label,
    build_detour_factor_artifact,
    summarise_detour,
)
from walkability.components.utils.geometry import CAN_DEFAULT_CRS


def test_build_detour_factor_artifact(default_polygon_geometry, compute_resources):
    test_detour_df = gpd.GeoDataFrame(
        {'index': [1, 2, 3, 4], 'detour_factor': [1.0, 2.5, 3.5, np.nan]},
        geometry=[
            default_polygon_geometry,
            default_polygon_geometry,
            default_polygon_geometry,
            default_polygon_geometry,
        ],
        crs=CAN_DEFAULT_CRS,
    )

    artifact = build_detour_factor_artifact(test_detour_df, compute_resources)

    assert isinstance(artifact, Artifact)


def test_apply_detour_color_and_label(default_polygon_geometry):
    test_detour_df = gpd.GeoDataFrame(
        {'detour_factor': [1.0, 2.5, 3.5, np.nan]},
        geometry=[
            default_polygon_geometry,
            default_polygon_geometry,
            default_polygon_geometry,
            default_polygon_geometry,
        ],
        crs=CAN_DEFAULT_CRS,
    )

    expected_detour_df = gpd.GeoDataFrame(
        {
            'detour_factor': [1.0, 2.5, 3.5, np.nan],
            'geometry': [
                default_polygon_geometry,
                default_polygon_geometry,
                default_polygon_geometry,
                default_polygon_geometry,
            ],
            'detour_category': [
                DetourCategory.LOW_DETOUR,
                DetourCategory.MEDIUM_DETOUR,
                DetourCategory.HIGH_DETOUR,
                DetourCategory.UNREACHABLE,
            ],
            'color': [Color('#FFFFE0'), Color('#eea321'), Color('#e75a13'), Color('#808080')],
            'label': ['Low Detour', 'Medium Detour', 'High Detour', 'Unreachable'],
        },
        crs=CAN_DEFAULT_CRS,
    )

    received = apply_color_and_label(test_detour_df)
    pd.testing.assert_frame_equal(received.reset_index(drop=True), expected_detour_df)


def test_summarise_detour(default_polygon_geometry):
    input_hexgrid = gpd.GeoDataFrame(
        data={
            'detour_factor': [0, 3, 6, 10],
            'color': [Color('#FFFFE0'), Color('#eea321'), Color('#e75a13'), Color('#e75a13')],
            'label': ['Low Detour', 'Medium Detour', 'High Detour', 'High Detour'],
            'geometry': 4 * [default_polygon_geometry],
        },
        crs=CAN_DEFAULT_CRS,
    )
    expected_avg_value = 4.75

    chart, avg_value = summarise_detour(detour_factor_data=input_hexgrid)

    assert expected_avg_value == avg_value
    assert isinstance(chart, go.Figure)
    np.testing.assert_array_equal(
        chart['data'][0]['x'], (['Low Detour (0 to 1.99)', 'Medium Detour (2.0 to 2.99)', 'High Detour (>= 3)'])
    )


def test_summarise_detour_inf(default_polygon_geometry):
    input_hexgrid = gpd.GeoDataFrame(
        data={
            'detour_factor': [2.5, 3.5, np.nan, 0, np.nan],
            'color': [Color('#eea321'), Color('#e75a13'), Color('#808080'), Color('#FFFFE0'), Color('#808080')],
            'label': ['Medium Detour', 'High Detour', 'Unreachable', 'Low Detour', 'Unreachable'],
            'geometry': 5 * [default_polygon_geometry],
        },
        crs=CAN_DEFAULT_CRS,
    )
    expected_avg_value = 2

    chart, avg_value = summarise_detour(detour_factor_data=input_hexgrid)

    assert expected_avg_value == avg_value
    assert isinstance(chart, go.Figure)
    np.testing.assert_array_equal(
        chart['data'][0]['x'],
        (['Low Detour (0 to 1.99)', 'Medium Detour (2.0 to 2.99)', 'High Detour (>= 3)', 'Unreachable']),
    )
    np.testing.assert_array_equal(chart['data'][0]['y'], ([20, 20, 20, 40]))
