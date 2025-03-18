import geopandas as gpd
import shapely
from climatoology.base.artifact import Chart2dData, ChartType
from pydantic_extra_types.color import Color
from pyproj import CRS

from test.conftest import filter_start_matcher
from walkability.components.categorise_paths.path_summarisation import summarise_by_area
from walkability.components.utils.misc import PathCategory


def test_summarise_by_area(operator, default_aoi, responses_mock):
    with open('test/resources/ohsome_admin_response.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )
    expected_charts = {
        'Bergheim': Chart2dData(
            x=['Designated'],
            y=[0.12],
            color=[Color('#3b4cc0')],
            chart_type=ChartType.PIE,
        ),
        'Südstadt': Chart2dData(
            x=['Designated'],
            y=[0.12],
            color=[Color('#3b4cc0')],
            chart_type=ChartType.PIE,
        ),
    }

    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])
    polygon_geom = shapely.Polygon(((12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22), (12.3, 48.22)))

    input_paths = gpd.GeoDataFrame(
        data={
            'category': 2 * [PathCategory.DESIGNATED],
            'rating': 2 * [1.0],
            'geometry': [line_geom] + [polygon_geom],
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

    assert computed_charts == expected_charts


def test_summarise_by_area_no_boundaries(operator, default_aoi, responses_mock):
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

    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [line_geom],
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
    expected_charts = {
        'Innenstadt West': Chart2dData(
            x=['Designated'],
            y=[0.69],
            color=[Color('#3b4cc0')],
            chart_type=ChartType.PIE,
        )
    }

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

    assert computed_charts == expected_charts


def test_summarise_by_area_boundaries_no_name(operator, default_aoi, responses_mock):
    with open('test/resources/ohsome_admin_response_no_name.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )

    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [line_geom],
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


def test_summarise_by_area_two_types(operator, default_aoi, responses_mock):
    with open('test/resources/ohsome_admin_response.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )
    expected_charts = {
        'Bergheim': Chart2dData(
            x=['Designated', 'Unknown'],
            y=[0.12, 0.12],
            color=[Color('#3b4cc0'), Color('grey')],
            chart_type=ChartType.PIE,
        ),
        'Südstadt': Chart2dData(
            x=['Designated', 'Unknown'],
            y=[0.12, 0.12],
            color=[Color('#3b4cc0'), Color('grey')],
            chart_type=ChartType.PIE,
        ),
    }

    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.UNKNOWN, PathCategory.DESIGNATED],
            'geometry': 2 * [line_geom],
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

    assert computed_charts == expected_charts


def test_summarise_by_area_order_by_category_rating(operator, default_aoi, responses_mock):
    with open('test/resources/ohsome_admin_response.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )
    expected_charts = {
        'Bergheim': Chart2dData(
            x=['Designated', 'Shared with bikes', 'Unknown'],
            y=[0.12, 0.12, 0.12],
            color=[Color('#3b4cc0'), Color('#7b9ff9'), Color('grey')],
            chart_type=ChartType.PIE,
        ),
        'Südstadt': Chart2dData(
            x=['Designated', 'Shared with bikes', 'Unknown'],
            y=[0.12, 0.12, 0.12],
            color=[Color('#3b4cc0'), Color('#7b9ff9'), Color('grey')],
            chart_type=ChartType.PIE,
        ),
    }

    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.UNKNOWN, PathCategory.DESIGNATED, PathCategory.DESIGNATED_SHARED_WITH_BIKES],
            'geometry': 3 * [line_geom],
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

    assert computed_charts == expected_charts
