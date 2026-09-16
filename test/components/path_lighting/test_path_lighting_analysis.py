import geopandas as gpd
import geopandas.testing
import pandas as pd
import plotly.graph_objects as go
from climatoology.base.artifact import Artifact

from walkability.components.path_lighting.path_lighting_analysis import (
    create_path_lighting_chart_plot,
    get_path_lighting,
    path_lighting_analysis,
    path_lighting_categorisation,
    summarise_path_lighting,
)
from walkability.components.utils.geometry import CAN_DEFAULT_CRS
from walkability.components.utils.misc import PathLightingCategory


def test_path_lighting_analysis(default_path_geometry, default_polygon_geometry, compute_resources):
    line_paths = gpd.GeoDataFrame(
        data={'osm_id': ['1', '2'], 'osm_type': ['way', 'way'], 'osm_tags': [{'lit': 'yes'}, {'lit': 'automatic'}]},
        geometry=[default_path_geometry, default_path_geometry],
        crs=CAN_DEFAULT_CRS,
    )
    polygon_paths = gpd.GeoDataFrame(
        data={'osm_id': ['3'], 'osm_type': ['way'], 'osm_tags': [{}]},
        geometry=[default_polygon_geometry],
        crs=CAN_DEFAULT_CRS,
    )

    artifacts = path_lighting_analysis(line_paths=line_paths, polygon_paths=polygon_paths, resources=compute_resources)

    assert len(artifacts) == 2
    assert all(isinstance(artifact, Artifact) for artifact in artifacts)


def test_get_path_lighting(default_path_geometry, default_polygon_geometry):
    line_paths = gpd.GeoDataFrame(
        data={'osm_id': ['1', '2'], 'osm_type': ['way', 'way'], 'osm_tags': [{'lit': 'yes'}, {'lit': 'automatic'}]},
        geometry=[
            default_path_geometry,
            default_path_geometry,
        ],
        crs=CAN_DEFAULT_CRS,
    )

    polygon_paths = gpd.GeoDataFrame(
        data={'osm_id': ['3'], 'osm_type': ['way'], 'osm_tags': [{}]},
        geometry=[default_polygon_geometry],
        crs=CAN_DEFAULT_CRS,
    )

    expected_light_paths_all = gpd.GeoDataFrame(
        index=[0, 1, 2],
        data={
            'osm_id': ['1', '2', '3'],
            'osm_type': ['way', 'way', 'way'],
            'osm_tags': [{'lit': 'yes'}, {'lit': 'automatic'}, {}],
            'geometry': [default_path_geometry, default_path_geometry, default_polygon_geometry],
            'path_lighting': [PathLightingCategory.YES, PathLightingCategory.AUTOMATIC, PathLightingCategory.UNKNOWN],
            'path_lighting_rating': pd.Series([1, 0.8, None], dtype=object),
        },
        crs=CAN_DEFAULT_CRS,
    )

    received = get_path_lighting(line_paths=line_paths, polygon_paths=polygon_paths).reset_index(drop=True)

    gpd.testing.assert_geodataframe_equal(received, expected_light_paths_all, check_dtype=False)


def test_path_lighting_categorisation(default_path_geometry, default_polygon_geometry):
    geometries = gpd.GeoDataFrame(
        index=[1, 2, 3, 4, 5],
        data={
            'osm_tags': [
                {'lit': '24/7', 'lit_by_led': 'yes'},
                {'lit': 'limited', 'lit_by_led': 'yes'},
                {'lit': 'no'},
                {'lit_by_led': 'yes'},
                {},
            ]
        },
        geometry=[
            default_path_geometry,
            default_path_geometry,
            default_polygon_geometry,
            default_polygon_geometry,
            default_polygon_geometry,
        ],
        crs=CAN_DEFAULT_CRS,
    )
    expected_path_lighting_categorisation = gpd.GeoDataFrame(
        index=[1, 2, 3, 4, 5],
        data={
            'osm_tags': [
                {'lit': '24/7', 'lit_by_led': 'yes'},
                {'lit': 'limited', 'lit_by_led': 'yes'},
                {'lit': 'no'},
                {'lit_by_led': 'yes'},
                {},
            ],
            'geometry': [
                default_path_geometry,
                default_path_geometry,
                default_polygon_geometry,
                default_polygon_geometry,
                default_polygon_geometry,
            ],
            'path_lighting': [
                PathLightingCategory.YES,
                PathLightingCategory.LIMITED,
                PathLightingCategory.NO,
                PathLightingCategory.YES,
                PathLightingCategory.UNKNOWN,
            ],
            'path_lighting_rating': [1, 0.3, 0.0, 1, None],
        },
        crs=CAN_DEFAULT_CRS,
    )
    received = path_lighting_categorisation(geometries=geometries)
    gpd.testing.assert_geodataframe_equal(received, expected_path_lighting_categorisation)


def test_summarise_path_lighting(default_path_geometry, default_polygon_geometry):
    light_paths_all = gpd.GeoDataFrame(
        data={
            'path_lighting': [PathLightingCategory.YES, PathLightingCategory.NO, PathLightingCategory.YES],
            'path_lighting_rating': [1.0, 0.0, 1.0],
        },
        geometry=[default_path_geometry, default_path_geometry, default_polygon_geometry],
        crs=CAN_DEFAULT_CRS,
    )

    summary_figure = summarise_path_lighting(light_paths_all)

    assert isinstance(summary_figure, go.Figure)
    assert len(summary_figure.data) == 2  # only rows with line geometry should remain


def test_create_path_lighting_chart_plot():
    summary = pd.DataFrame(
        {
            'rating': [0.0, 1.0],
            'length': [3.0, 7.0],
            'percent': [30.0, 70.0],
        },
        index=pd.Index(['No', 'Yes'], name='path_lighting_label'),
    )

    summary_chart = create_path_lighting_chart_plot(summary)

    assert isinstance(summary_chart, go.Figure)
    assert summary_chart['data'][0]['name'] == 'No'  # name=category
    assert summary_chart['data'][1]['name'] == 'Yes'
    assert summary_chart['data'][0]['x'] == (30.0,)  # x=percent
    assert summary_chart['data'][1]['x'] == (70.0,)
