import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from climatoology.base.artifact import _Artifact
from pydantic_extra_types.color import Color

from walkability.components.network_analyses.detour_analysis import (
    DetourCategory,
    apply_color_and_label,
    build_detour_factor_artifact,
    summarise_detour,
)


def test_build_detour_factor_artifact(default_polygon_geometry, compute_resources):
    test_detour_df = gpd.GeoDataFrame(
        {'detour_factor': [1.0, 2.5, 3.5, np.nan]},
        geometry=[
            default_polygon_geometry,
            default_polygon_geometry,
            default_polygon_geometry,
            default_polygon_geometry,
        ],
        crs='EPSG:4326',
    )

    artifact = build_detour_factor_artifact(test_detour_df, compute_resources)

    assert isinstance(artifact, _Artifact)


def test_apply_detour_color_and_label(default_polygon_geometry):
    test_detour_df = gpd.GeoDataFrame(
        {'detour_factor': [1.0, 2.5, 3.5, np.nan]},
        geometry=[
            default_polygon_geometry,
            default_polygon_geometry,
            default_polygon_geometry,
            default_polygon_geometry,
        ],
        crs='EPSG:4326',
    )

    expected_detour_df = gpd.GeoDataFrame(
        {
            'detour_factor': [2.5, 3.5, np.nan],
            'geometry': [default_polygon_geometry, default_polygon_geometry, default_polygon_geometry],
            'detour_category': [DetourCategory.MEDIUM_DETOUR, DetourCategory.HIGH_DETOUR, DetourCategory.UNREACHABLE],
            'color': [Color('#eea321'), Color('#e75a13'), Color('#990404')],
            'label': ['Medium Detour', 'High Detour', 'Unreachable'],
        },
        crs='EPSG:4326',
    )

    received = apply_color_and_label(test_detour_df)
    pd.testing.assert_frame_equal(received.reset_index(drop=True), expected_detour_df)


def test_summarise_detour(default_polygon_geometry):
    input_hexgrid = gpd.GeoDataFrame(
        data={
            'detour_factor': [0, 3, 6, 10],
            'geometry': 4 * [default_polygon_geometry],
        },
        crs='EPSG:4326',
    )
    chart = summarise_detour(hexgrid=input_hexgrid)

    assert isinstance(chart, go.Figure)
    np.testing.assert_array_equal(chart['data'][0]['x'], ([0, 3, 6, 10]))


def test_summarise_detour_inf(default_polygon_geometry):
    input_hexgrid = gpd.GeoDataFrame(
        data={
            'detour_factor': [0, 3, 6, np.inf],
            'geometry': 4 * [default_polygon_geometry],
        },
        crs='EPSG:4326',
    )
    chart = summarise_detour(hexgrid=input_hexgrid)

    assert isinstance(chart, go.Figure)
    np.testing.assert_array_equal(chart['data'][0]['x'], ([0, 3, 6, np.inf]))
