import geopandas as gpd
import shapely
from geopandas import testing

from walkability.components.utils.misc import (
    PathCategory,
    PavementQuality,
)


def test_get_buffered_line_paths(operator, expected_compute_input, default_aoi, ohsome_api):
    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])

    expected_lines = gpd.GeoDataFrame(
        data={
            '@osmId': ['way/171574582'],
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'quality': [PavementQuality.UNKNOWN],
            'quality_rating': [None],
            'geometry': [line_geom],
            '@other_tags': [{'highway': 'pedestrian'}],
        },
        crs='EPSG:4326',
    )

    _, computed_lines_buffered, _ = operator._get_paths(
        aoi=default_aoi,
        max_walking_distance=expected_compute_input.max_walking_distance,
    )

    testing.assert_geodataframe_equal(
        computed_lines_buffered,
        expected_lines,
        check_like=True,
        check_geom_type=True,
        check_less_precise=True,
    )


def test_get_line_paths(operator, expected_compute_input, ohsome_api):
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
            'geometry': line_geom,
            '@other_tags': [{'highway': 'pedestrian'}, {'highway': 'pedestrian'}],
        },
        crs='EPSG:4326',
    )

    computed_lines, _, _ = operator._get_paths(
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
        ),
        max_walking_distance=expected_compute_input.max_walking_distance,
    )

    testing.assert_geodataframe_equal(
        computed_lines,
        expected_lines,
        check_like=True,
        check_geom_type=True,
        check_less_precise=True,
    )


def test_get_polygon_paths(operator, expected_compute_input, default_aoi, ohsome_api):
    polygon_geom = shapely.Polygon(((12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22), (12.3, 48.22)))

    expected_polygons = gpd.GeoDataFrame(
        data={
            '@osmId': ['way/171574582'],
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [polygon_geom],
            '@other_tags': [{'highway': 'platform', 'area': 'yes'}],
        },
        crs='EPSG:4326',
    )

    _, _, computed_polygons = operator._get_paths(
        aoi=default_aoi,
        max_walking_distance=expected_compute_input.max_walking_distance,
    )

    testing.assert_geodataframe_equal(
        computed_polygons,
        expected_polygons,
        check_like=True,
        check_geom_type=True,
        check_less_precise=True,
    )
