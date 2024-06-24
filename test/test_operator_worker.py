import geopandas as gpd
import shapely
from climatoology.base.artifact import Chart2dData, ChartType
from geopandas import testing
from pydantic_extra_types.color import Color

from walkability.utils import Rating, filter_start_matcher


def test_get_paths(operator, expected_compute_input, ohsome_api):
    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])
    polygon_geom = shapely.Polygon(((12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22), (12.3, 48.22)))

    expected_lines = gpd.GeoDataFrame(
        data={
            'category': [
                Rating.EXCLUSIVE,
                Rating.EXPLICIT,
                Rating.PROBABLE_YES,
                Rating.PROBABLE_NO,
                Rating.INACCESSIBLE,
            ],
            'geometry': 5 * [line_geom],
        },
        crs='EPSG:4326',
    )
    expected_polygons = gpd.GeoDataFrame(
        data={
            'category': [
                Rating.EXCLUSIVE,
                Rating.EXPLICIT,
                Rating.PROBABLE_YES,
                Rating.PROBABLE_NO,
                Rating.INACCESSIBLE,
            ],
            'geometry': 5 * [polygon_geom],
        },
        crs='EPSG:4326',
    )
    computed_lines, computed_polygons = operator.get_paths(expected_compute_input.get_aoi_geom())

    testing.assert_geodataframe_equal(
        computed_lines,
        expected_lines,
        check_like=True,
        check_geom_type=True,
        check_less_precise=True,
    )
    testing.assert_geodataframe_equal(
        computed_polygons,
        expected_polygons,
        check_like=True,
        check_geom_type=True,
        check_less_precise=True,
    )


def test_aggregate(operator, expected_compute_input, responses_mock):
    with open('resources/test/ohsome_admin_response.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )
    expected_charts = {
        'Bergheim': Chart2dData(
            x=['EXCLUSIVE'],
            y=[0.12],
            color=[Color('#006837')],
            chart_type=ChartType.PIE,
        ),
        'Südstadt': Chart2dData(
            x=['EXCLUSIVE'],
            y=[0.12],
            color=[Color('#006837')],
            chart_type=ChartType.PIE,
        ),
    }

    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])
    polygon_geom = shapely.Polygon(((12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22), (12.3, 48.22)))

    input_paths = gpd.GeoDataFrame(
        data={
            'category': 2 * [Rating.EXCLUSIVE],
            'color': 2 * [Color('#006837')],
            'geometry': [line_geom] + [polygon_geom],
        },
        crs='EPSG:4326',
    )
    computed_charts = operator.summarise_by_area(input_paths, expected_compute_input.get_aoi_geom(), 9)

    assert computed_charts == expected_charts
