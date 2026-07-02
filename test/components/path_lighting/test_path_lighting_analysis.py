import geopandas as gpd

from walkability.components.path_lighting.path_lighting_analysis import (
    get_path_lighting,
    path_lighting_categorisation,
)
from walkability.components.utils.geometry import CAN_DEFAULT_CRS
from walkability.components.utils.misc import PathLightingCategory


def test_get_path_lighting(default_path_geometry, default_polygon_geometry):
    line_paths = gpd.GeoDataFrame(
        data={'@osmId': ['way/1', 'way/2'], '@other_tags': [{'lit': 'yes'}, {'lit': 'automatic'}]},
        geometry=[
            default_path_geometry,
            default_path_geometry,
        ],
        crs=CAN_DEFAULT_CRS,
    )

    polygon_paths = gpd.GeoDataFrame(
        data={'@osmId': ['way/3'], '@other_tags': [{}]},
        geometry=[default_polygon_geometry],
        crs=CAN_DEFAULT_CRS,
    )

    expected_light_paths_all = gpd.GeoDataFrame(
        index=[0, 1, 2],
        data={
            '@osmId': ['way/1', 'way/2', 'way/3'],
            '@other_tags': [{'lit': 'yes'}, {'lit': 'automatic'}, {}],
            'geometry': [default_path_geometry, default_path_geometry, default_polygon_geometry],
            'path_lighting': [PathLightingCategory.YES, PathLightingCategory.AUTOMATIC, PathLightingCategory.UNKNOWN],
            'path_lighting_rating': [1, 0.8, None],
        },
        crs=CAN_DEFAULT_CRS,
    )

    received = get_path_lighting(line_paths=line_paths, polygon_paths=polygon_paths).reset_index(drop=True)

    gpd.testing.assert_geodataframe_equal(received, expected_light_paths_all)


def test_path_lighting_categorisation(default_path_geometry, default_polygon_geometry):
    geometries = gpd.GeoDataFrame(
        index=[1, 2, 3, 4, 5],
        data={
            '@other_tags': [
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
            '@other_tags': [
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
