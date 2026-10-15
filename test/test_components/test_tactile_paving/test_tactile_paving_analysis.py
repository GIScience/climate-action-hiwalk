import geopandas as gpd
import geopandas.testing
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest
from ohsome_filter_to_sql import validate_filter

from walkability.components.tactile_paving.tactile_paving_analysis import (
    apply_tactile_paving_filters,
    get_tactile_paving,
    plot_tactile_paving,
    tactile_paving_categorisation,
    tactile_paving_infrastructure_categorisation,
    tactile_paving_ohsome_filter,
)
from walkability.components.utils.geometry import CAN_DEFAULT_CRS
from walkability.components.utils.misc import TactilePavingCategory, TactilePavingInfrastructureCategory


def test_get_tactile_paving(default_path_geometry, default_polygon_geometry):
    paths = gpd.GeoDataFrame(
        data={
            'osm_id': ['1', '2', '3', '4'],
            'osm_type': ['way', 'way', 'way', 'way'],
            'osm_tags': [
                {'highway': 'platform', 'tactile_paving': 'yes'},
                {'public_transport': 'platform', 'tactile_paving': 'primitive'},
                {'railway': 'platform'},
                {'highway': 'crossing'},
            ],
        },
        geometry=[
            default_path_geometry,
            default_path_geometry,
            default_polygon_geometry,
            default_path_geometry,
        ],
        crs=CAN_DEFAULT_CRS,
    )

    expected_tactile_paths_all = gpd.GeoDataFrame(
        index=[0, 1, 2, 3],
        data={
            'osm_id': ['1', '2', '3', '4'],
            'osm_type': ['way', 'way', 'way', 'way'],
            'osm_tags': [
                {'highway': 'platform', 'tactile_paving': 'yes'},
                {'public_transport': 'platform', 'tactile_paving': 'primitive'},
                {'railway': 'platform'},
                {'highway': 'crossing'},
            ],
            'geometry': [default_path_geometry, default_path_geometry, default_polygon_geometry, default_path_geometry],
            'infrastructure_category': [
                TactilePavingInfrastructureCategory.PLATFORMS,
                TactilePavingInfrastructureCategory.PLATFORMS,
                TactilePavingInfrastructureCategory.PLATFORMS,
                TactilePavingInfrastructureCategory.CROSSINGS,
            ],
            'tactile_paving': [
                TactilePavingCategory.YES,
                TactilePavingCategory.OTHER_SIGNS,
                TactilePavingCategory.UNKNOWN,
                TactilePavingCategory.UNKNOWN,
            ],
            'tactile_paving_rating': pd.Series([1, 0.5, np.nan, np.nan], dtype=object),
        },
        crs=CAN_DEFAULT_CRS,
    )

    received = get_tactile_paving(tactile_paths_all=paths).reset_index(drop=True)

    gpd.testing.assert_geodataframe_equal(received, expected_tactile_paths_all, check_dtype=False)


def test_tactile_paving_categorisation(default_path_geometry, default_polygon_geometry):
    geometries = gpd.GeoDataFrame(
        index=[1, 2, 3, 4],
        data={
            'osm_tags': [
                {'tactile_paving': 'yes'},
                {'tactile_paving': 'primitive'},
                {'tactile_paving': 'no'},
                {},
            ]
        },
        geometry=[
            default_path_geometry,
            default_path_geometry,
            default_polygon_geometry,
            default_polygon_geometry,
        ],
        crs=CAN_DEFAULT_CRS,
    )
    expected_tactile_paving_categorisation = gpd.GeoDataFrame(
        index=[1, 2, 3, 4],
        data={
            'osm_tags': [
                {'tactile_paving': 'yes'},
                {'tactile_paving': 'primitive'},
                {'tactile_paving': 'no'},
                {},
            ],
            'geometry': [
                default_path_geometry,
                default_path_geometry,
                default_polygon_geometry,
                default_polygon_geometry,
            ],
            'tactile_paving': [
                TactilePavingCategory.YES,
                TactilePavingCategory.OTHER_SIGNS,
                TactilePavingCategory.NO,
                TactilePavingCategory.UNKNOWN,
            ],
            'tactile_paving_rating': [1, 0.5, 0, None],
        },
        crs=CAN_DEFAULT_CRS,
    )
    received = tactile_paving_categorisation(geometries=geometries)
    gpd.testing.assert_geodataframe_equal(received, expected_tactile_paving_categorisation)


@pytest.mark.parametrize(
    'osm_tags,expected',
    [
        ({'highway': 'crossing'}, TactilePavingInfrastructureCategory.CROSSINGS),
        ({'highway': 'bus_stop'}, TactilePavingInfrastructureCategory.PLATFORMS),
        ({'highway': 'platform'}, TactilePavingInfrastructureCategory.PLATFORMS),
        ({'public_transport': 'platform'}, TactilePavingInfrastructureCategory.PLATFORMS),
        ({'railway': 'platform'}, TactilePavingInfrastructureCategory.PLATFORMS),
        ({'highway': 'steps'}, TactilePavingInfrastructureCategory.STAIRS),
        ({}, None),
        ({'highway': 'residential'}, None),
    ],
)
def test_tactile_paving_infrastructure_categorisation(osm_tags, expected):
    row = pd.Series({'osm_tags': osm_tags})
    assert tactile_paving_infrastructure_categorisation(row) == expected


@pytest.mark.parametrize(
    'tactile_paving_value,expected',
    [
        ('yes', TactilePavingCategory.YES),
        ('primitive', TactilePavingCategory.OTHER_SIGNS),
        ('partial', TactilePavingCategory.PARTIAL),
        ('no', TactilePavingCategory.NO),
        ('some_unrecognised_value', TactilePavingCategory.UNKNOWN),
    ],
)
def test_apply_tactile_paving_filters_match_cases(tactile_paving_value, expected):
    row = pd.Series({'osm_tags': {'tactile_paving': tactile_paving_value}})
    assert apply_tactile_paving_filters(row) == expected


def test_plot_tactile_paving():
    input_geoms = gpd.GeoDataFrame(
        data={
            'infrastructure_category': [TactilePavingInfrastructureCategory.CROSSINGS],
            'tactile_paving': [TactilePavingCategory.YES],
            'tactile_paving_rating': [1.0],
        },
    )
    fig = plot_tactile_paving(input_geoms)
    assert isinstance(fig, go.Figure)


@pytest.mark.parametrize('geometry_type', ['line', 'polygon'])
def test_ohsome_filter(geometry_type):
    validate_filter(tactile_paving_ohsome_filter(geometry_type))
