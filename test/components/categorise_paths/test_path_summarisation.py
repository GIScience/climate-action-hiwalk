import geopandas as gpd
import plotly.graph_objects as go
import shapely
from pyproj import CRS

from test.conftest import filter_start_matcher
from walkability.components.categorise_paths.path_summarisation import (
    summarise_aoi,
    summarise_by_area,
)
from walkability.components.utils.misc import PathCategory, PavementQuality


def test_summarise_by_area(operator, default_aoi, responses_mock, default_path_geometry, default_polygon_geometry):
    with open('test/resources/ohsome_admin_response.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )

    input_paths = gpd.GeoDataFrame(
        data={
            'category': 2 * [PathCategory.DESIGNATED],
            'rating': 2 * [1.0],
            'geometry': [default_path_geometry] + [default_polygon_geometry],
        },
        crs='EPSG:4326',
    )
    computed_charts = summarise_by_area(
        paths=input_paths,
        aoi=default_aoi,
        admin_level=9,
        projected_crs=CRS.from_user_input(32632),
        ohsome_client=operator.ohsome,
    )

    assert isinstance(computed_charts, dict)
    assert all(
        isinstance(chart, go.Figure) and city in ['Bergheim', 'Südstadt'] for city, chart in computed_charts.items()
    )
    assert computed_charts['Bergheim']['data'][0]['x'] == (100,)
    assert computed_charts['Südstadt']['data'][0]['x'] == (100,)


def test_summarise_by_area_no_boundaries(operator, default_aoi, responses_mock, default_path_geometry):
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body="""{
  "attribution" : {
    "url" : "https://ohsome.org/copyrights",
    "text" : "© OpenStreetMap contributors"
  },
  "apiVersion" : "1.10.4",
  "type" : "FeatureCollection",
  "features" : []
}""",
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [default_path_geometry],
        },
        crs='EPSG:4326',
    )
    computed_charts = summarise_by_area(
        paths=input_paths,
        aoi=default_aoi,
        admin_level=9,
        projected_crs=CRS.from_user_input(32632),
        ohsome_client=operator.ohsome,
    )

    assert computed_charts == dict()


def test_summarise_by_area_mixed_geometry_boundaries(operator, default_aoi, responses_mock):
    with open('test/resources/ohsome_boundaries_mixed_geometries.geojson', 'r') as response_file:
        response_body = response_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=response_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [shapely.LineString([[7.42, 51.51], [7.43, 51.51]])],
        },
        crs='EPSG:4326',
    )
    computed_charts = summarise_by_area(
        paths=input_paths,
        aoi=default_aoi,
        admin_level=9,
        projected_crs=CRS.from_user_input(32632),
        ohsome_client=operator.ohsome,
    )

    assert len(computed_charts.items()) == 1
    assert isinstance(computed_charts['Innenstadt West'], go.Figure)


def test_summarise_by_area_boundaries_no_name(operator, default_aoi, responses_mock, default_path_geometry):
    with open('test/resources/ohsome_admin_response_no_name.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [default_path_geometry],
        },
        crs='EPSG:4326',
    )
    computed_charts = summarise_by_area(
        paths=input_paths,
        aoi=default_aoi,
        admin_level=9,
        projected_crs=CRS.from_user_input(32632),
        ohsome_client=operator.ohsome,
    )

    assert computed_charts == dict()


def test_summarise_by_area_two_types(operator, default_aoi, responses_mock, default_path_geometry):
    with open('test/resources/ohsome_admin_response.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.UNKNOWN, PathCategory.DESIGNATED],
            'geometry': 2 * [default_path_geometry],
        },
        crs='EPSG:4326',
    )
    computed_charts = summarise_by_area(
        paths=input_paths,
        aoi=default_aoi,
        admin_level=9,
        projected_crs=CRS.from_user_input(32632),
        ohsome_client=operator.ohsome,
    )

    assert all(chart['data'][0]['name'] == 'Pedestrians Exclusive' for _, chart in computed_charts.items())
    assert all(chart['data'][1]['name'] == 'Unknown' for _, chart in computed_charts.items())


def test_summarise_by_area_order_by_category_rating(operator, default_aoi, responses_mock, default_path_geometry):
    with open('test/resources/ohsome_admin_response.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.UNKNOWN, PathCategory.DESIGNATED, PathCategory.DESIGNATED_SHARED_WITH_BIKES],
            'geometry': 3 * [default_path_geometry],
        },
        crs='EPSG:4326',
    )
    computed_charts = summarise_by_area(
        paths=input_paths,
        aoi=default_aoi,
        admin_level=9,
        projected_crs=CRS.from_user_input(32632),
        ohsome_client=operator.ohsome,
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
        crs='EPSG:4326',
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
        crs='EPSG:4326',
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
