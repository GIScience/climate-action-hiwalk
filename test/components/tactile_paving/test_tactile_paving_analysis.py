import geopandas as gpd

from walkability.components.tactile_paving.tactile_paving_analysis import (
    get_tactile_paving,
    tactile_paving_categorisation,
)
from walkability.components.utils.geometry import CAN_DEFAULT_CRS
from walkability.components.utils.misc import TactilePavingCategory


def test_get_tactile_paving(default_path_geometry, default_polygon_geometry):
    line_paths = gpd.GeoDataFrame(
        data={'@osmId': ['way/1', 'way/2'], '@other_tags': [{'tactile_paving': 'yes'}, {'tactile_paving': 'unpaved'}]},
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

    expected_tactile_paths_all = gpd.GeoDataFrame(
        index=[0, 1, 2],
        data={
            '@osmId': ['way/1', 'way/2', 'way/3'],
            '@other_tags': [{'tactile_paving': 'yes'}, {'tactile_paving': 'unpaved'}, {}],
            'geometry': [default_path_geometry, default_path_geometry, default_polygon_geometry],
            'tactile_paving': [
                TactilePavingCategory.YES,
                TactilePavingCategory.OTHER_SIGNS,
                TactilePavingCategory.UNKNOWN,
            ],
            'tactile_paving_rating': [1, 0.5, None],
        },
        crs=CAN_DEFAULT_CRS,
    )

    received = get_tactile_paving(line_paths=line_paths, polygon_paths=polygon_paths).reset_index(drop=True)

    gpd.testing.assert_geodataframe_equal(received, expected_tactile_paths_all)


def test_tactile_paving_categorisation(default_path_geometry, default_polygon_geometry):
    geometries = gpd.GeoDataFrame(
        index=[1, 2, 3, 4],
        data={
            '@other_tags': [
                {'tactile_paving': 'yes'},
                {'tactile_paving': 'yes', 'tactile_paving: surface': 'unpaved'},
                {'tactile_paving: surface': 'paving_stones'},
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
            '@other_tags': [
                {'tactile_paving': 'yes'},
                {'tactile_paving': 'yes', 'tactile_paving: surface': 'unpaved'},
                {'tactile_paving: surface': 'paving_stones'},
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
                TactilePavingCategory.YES,
                TactilePavingCategory.UNKNOWN,
            ],
            'tactile_paving_rating': [1, 0.5, 1, None],
        },
        crs=CAN_DEFAULT_CRS,
    )
    received = tactile_paving_categorisation(geometries=geometries)
    gpd.testing.assert_geodataframe_equal(received, expected_tactile_paving_categorisation)
