import geopandas as gpd
import shapely
from geopandas import testing

from walkability.components.utils.misc import (
    PathCategory,
    PavementQuality,
    SmoothnessCategory,
    SurfaceType,
)


def test_get_line_paths(operator, ohsome_api):
    line_geom = [
        shapely.LineString([(12.3, 48.22), (12.3, 48.2205)]),
        shapely.LineString([(12.3, 48.2205), (12.3005, 48.22)]),
    ]

    expected_lines = gpd.GeoDataFrame(
        data={
            '@osmId': ['way/171574582', 'way/171574582'],
            'category': [PathCategory.DESIGNATED, PathCategory.DESIGNATED],
            'rating': [1.0, 1.0],
            'quality': [PavementQuality.UNKNOWN, PavementQuality.UNKNOWN],
            'quality_rating': [None, None],
            'smoothness': [SmoothnessCategory.UNKNOWN, SmoothnessCategory.UNKNOWN],
            'smoothness_rating': [None, None],
            'surface': [SurfaceType.UNKNOWN, SurfaceType.UNKNOWN],
            'surface_rating': [None, None],
            'geometry': line_geom,
            '@other_tags': [{'highway': 'pedestrian'}, {'highway': 'pedestrian'}],
        },
        crs='EPSG:4326',
    )

    computed_lines, _ = operator._get_paths(
        aoi=shapely.MultiPolygon(
            polygons=[
                [
                    [
                        [12.3, 48.22],
                        [12.3, 48.34],
                        [12.48, 48.34],
                        [12.48, 48.22],
                        [12.3, 48.22],
                    ]
                ]
            ]
        )
    )

    testing.assert_geodataframe_equal(
        computed_lines,
        expected_lines,
        check_like=True,
        check_geom_type=True,
        check_less_precise=True,
    )


def test_get_polygon_paths(operator, default_aoi, ohsome_api):
    polygon_geom = shapely.Polygon(((12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22), (12.3, 48.22)))

    expected_polygons = gpd.GeoDataFrame(
        data={
            '@osmId': ['way/171574582'],
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [polygon_geom],
            '@other_tags': [{'highway': 'platform', 'area': 'yes'}],
            'quality': [PavementQuality.UNKNOWN],
            'quality_rating': [None],
            'smoothness': [SmoothnessCategory.UNKNOWN],
            'smoothness_rating': [None],
            'surface': [SurfaceType.UNKNOWN],
            'surface_rating': [None],
        },
        crs='EPSG:4326',
    )

    _, computed_polygons = operator._get_paths(aoi=default_aoi)

    testing.assert_geodataframe_equal(
        computed_polygons,
        expected_polygons,
        check_like=True,
        check_geom_type=True,
    )


def test_get_paths_with_erroneous_clipping(operator, responses_mock):
    with (
        open('test/resources/ohsome_erroneous_clipping.geojson', 'r') as point_instead_of_line,
    ):
        body = point_instead_of_line.read()

    responses_mock.post('https://api.ohsome.org/v1/elements/geometry', body=body)

    computed_lines, computed_polygons = operator._get_paths(
        aoi=shapely.MultiPolygon(
            polygons=[
                [
                    [
                        [8.676042, 49.418866],
                        [8.676042, 49.4190311],
                        [8.6765357, 49.4190311],
                        [8.6765357, 49.418866],
                        [8.676042, 49.418866],
                    ]
                ]
            ]
        )
    )

    assert computed_lines.empty
    assert computed_polygons.empty
