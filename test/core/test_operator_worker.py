from unittest.mock import patch

import geopandas as gpd
import pytest
import shapely
from climatoology.base.exception import ClimatoologyUserError
from geopandas import testing

from walkability.components.utils.geometry import CAN_DEFAULT_CRS
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
        crs=CAN_DEFAULT_CRS,
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
        crs=CAN_DEFAULT_CRS,
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

    with pytest.raises(
        ClimatoologyUserError,
        match=r'No accessible paths for walking were found in your area. Please select a larger area',
    ):
        operator._get_paths(
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


def test_get_paths_empty_ohsome_response(operator, default_aoi):
    with patch('walkability.core.operator_worker.fetch_osm_data') as mock:
        mock.return_value = gpd.GeoDataFrame(columns=['@osmId', 'geometry', '@other_tags'])
        with pytest.raises(
            ClimatoologyUserError,
            match=r'No accessible paths for walking were found in your area. Please select a larger area',
        ):
            operator._get_paths(aoi=default_aoi)


# There are paths in the AOI, but they are removed by path_categorisation because they are in PathCategory.INACCESSIBLE
def test_get_paths_inaccessible_ohsome_response(default_path_geometry, operator, default_aoi):
    with patch('walkability.core.operator_worker.fetch_osm_data') as mock:
        mock.return_value = gpd.GeoDataFrame(
            data={
                '@osmId': ['way/1'],
                'geometry': [default_path_geometry],
                '@other_tags': [{'highway': 'motorway'}],
            },
        )
        with pytest.raises(
            ClimatoologyUserError,
            match=r'No accessible paths for walking were found in your area. Please select a larger area',
        ):
            operator._get_paths(aoi=default_aoi)


def test_clean_geometries_tiny_remnants(operator):
    aoi = shapely.box(xmin=-0.1, xmax=1, ymin=-0.1, ymax=1.1)

    big_path = shapely.LineString([(0.0, 1.0), (0.0, 0.0)])
    path_that_should_collapse = shapely.LineString([(0.00000004, 0.0), (0.0, 0.0)])

    paths = gpd.GeoDataFrame(data={'expected': [True, False]}, geometry=[big_path, path_that_should_collapse])

    received = operator.clean_geometries(aoi=aoi, geometries=paths, geom_name='String')

    assert received[~received['expected']].empty
