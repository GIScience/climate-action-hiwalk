from unittest.mock import Mock

import geopandas as gpd
import plotly.graph_objects as go
import pytest
import shapely
from pyproj import CRS

from walkability.components.categorise_paths.path_summarisation import (
    summarise_aoi,
    summarise_by_area,
)
from walkability.components.utils.geometry import CAN_DEFAULT_CRS
from walkability.components.utils.misc import PathCategory, PavementQuality


@pytest.mark.vcr
def test_summarise_by_area(parametrized_ohsome_client, small_aoi, small_aoi_paths):
    computed_charts = summarise_by_area(
        paths=small_aoi_paths,
        aoi=small_aoi,
        admin_level=9,
        projected_crs=CRS.from_user_input(32632),
        ohsome_client=parametrized_ohsome_client,
    )

    assert isinstance(computed_charts, dict)
    assert all(
        isinstance(chart, go.Figure) and city in ['Bergheim', 'Weststadt'] for city, chart in computed_charts.items()
    )
    assert computed_charts['Bergheim']['data'][0]['x'] == (100,)
    assert computed_charts['Weststadt']['data'][0]['x'] == (100,)


def test_summarise_by_area_no_boundaries(default_ohsome_client_v2, default_aoi, default_path_geometry):
    # Ohsome response is mocked, so don't parametrize
    empty_boundary_response = gpd.GeoDataFrame(columns=['geom']).set_geometry('geom')
    features_extraction_mock = Mock(return_value=empty_boundary_response)
    default_ohsome_client_v2.features_extraction = features_extraction_mock

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [default_path_geometry],
        },
        crs=CAN_DEFAULT_CRS,
    )

    computed_charts = summarise_by_area(
        paths=input_paths,
        aoi=default_aoi,
        admin_level=9,
        projected_crs=CRS.from_user_input(32632),
        ohsome_client=default_ohsome_client_v2,
    )

    assert computed_charts == dict()


def test_summarise_by_area_mixed_geometry_boundaries(default_ohsome_client_v2, default_aoi):
    # Ohsome response is mocked, so don't parametrize
    extracted_features = gpd.read_file('test/resources/ohsome_boundaries_mixed_geometries.geojson')
    features_extraction_mock = Mock(return_value=extracted_features.rename_geometry('geom'))
    default_ohsome_client_v2.features_extraction = features_extraction_mock

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [shapely.LineString([[7.42, 51.51], [7.43, 51.51]])],
        },
        crs=CAN_DEFAULT_CRS,
    )
    computed_charts = summarise_by_area(
        paths=input_paths,
        aoi=default_aoi,
        admin_level=9,
        projected_crs=CRS.from_user_input(32632),
        ohsome_client=default_ohsome_client_v2,
    )

    assert len(computed_charts.items()) == 1
    assert isinstance(computed_charts['Innenstadt West'], go.Figure)


def test_summarise_by_area_boundaries_no_name(default_ohsome_client_v2, default_aoi, default_path_geometry):
    # Ohsome response is mocked, so don't parametrize
    extracted_features = gpd.read_file('test/resources/ohsome_admin_response_no_name.geojson')
    features_extraction_mock = Mock(return_value=extracted_features.rename_geometry('geom'))
    default_ohsome_client_v2.features_extraction = features_extraction_mock

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [default_path_geometry],
        },
        crs=CAN_DEFAULT_CRS,
    )
    computed_charts = summarise_by_area(
        paths=input_paths,
        aoi=default_aoi,
        admin_level=9,
        projected_crs=CRS.from_user_input(32632),
        ohsome_client=default_ohsome_client_v2,
    )

    assert computed_charts == dict()


@pytest.mark.vcr
def test_summarise_by_area_two_path_categories(parametrized_ohsome_client, default_aoi, default_path_geometry):
    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.UNKNOWN, PathCategory.DESIGNATED],
            'geometry': 2 * [default_path_geometry],
        },
        crs=CAN_DEFAULT_CRS,
    )
    computed_charts = summarise_by_area(
        paths=input_paths,
        aoi=default_aoi,
        admin_level=9,
        projected_crs=CRS.from_user_input(32632),
        ohsome_client=parametrized_ohsome_client,
    )

    assert all(chart['data'][0]['name'] == 'Pedestrians Exclusive' for _, chart in computed_charts.items())
    assert all(chart['data'][1]['name'] == 'Unknown' for _, chart in computed_charts.items())


@pytest.mark.vcr
def test_summarise_by_area_order_by_category_rating(parametrized_ohsome_client, default_aoi, default_path_geometry):
    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.UNKNOWN, PathCategory.DESIGNATED, PathCategory.DESIGNATED_SHARED_WITH_BIKES],
            'geometry': 3 * [default_path_geometry],
        },
        crs=CAN_DEFAULT_CRS,
    )
    computed_charts = summarise_by_area(
        paths=input_paths,
        aoi=default_aoi,
        admin_level=9,
        projected_crs=CRS.from_user_input(32632),
        ohsome_client=parametrized_ohsome_client,
    )

    assert all(chart['data'][0]['name'] == 'Bikes' for _, chart in computed_charts.items())
    assert all(chart['data'][1]['name'] == 'Pedestrians Exclusive' for _, chart in computed_charts.items())
    assert all(chart['data'][2]['name'] == 'Unknown' for _, chart in computed_charts.items())


def test_summarise_aoi(default_path_geometry, default_polygon_geometry):
    input_paths = gpd.GeoDataFrame(
        data={
            'category': 2 * [PathCategory.DESIGNATED],
            'quality': 2 * [PavementQuality.GOOD],
            'geometry': [default_path_geometry] + [default_polygon_geometry],
        },
        crs=CAN_DEFAULT_CRS,
    )
    (
        category_stacked_bar_chart,
        quality_stacked_bar_chart,
    ) = summarise_aoi(paths=input_paths, projected_crs=CRS.from_user_input(32632))

    assert isinstance(category_stacked_bar_chart, go.Figure)
    assert isinstance(quality_stacked_bar_chart, go.Figure)
    assert category_stacked_bar_chart['data'][0]['y'] == ('Path Types',)
    assert category_stacked_bar_chart['data'][0]['x'] == (100,)
    assert quality_stacked_bar_chart['data'][0]['y'] == ('Surface Quality Types',)
    assert quality_stacked_bar_chart['data'][0]['x'] == (100,)


def test_summarise_aoi_unknown(default_path_geometry):
    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED, PathCategory.UNKNOWN],
            'quality': [PavementQuality.GOOD, PavementQuality.UNKNOWN],
            'geometry': 2 * [default_path_geometry],
        },
        crs=CAN_DEFAULT_CRS,
    )
    category_stacked_bar_chart, quality_stacked_bar_chart = summarise_aoi(
        paths=input_paths, projected_crs=CRS.from_user_input(32632)
    )

    assert isinstance(category_stacked_bar_chart, go.Figure)
    assert isinstance(quality_stacked_bar_chart, go.Figure)

    assert category_stacked_bar_chart['data'][0]['y'] == ('Path Types',)
    assert category_stacked_bar_chart['data'][0]['x'] == (50,)
    assert quality_stacked_bar_chart['data'][0]['y'] == ('Surface Quality Types',)
    assert quality_stacked_bar_chart['data'][0]['x'] == (50,)
