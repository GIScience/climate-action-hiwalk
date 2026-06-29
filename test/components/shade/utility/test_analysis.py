import geopandas as gpd
import numpy as np
import pytest
import shapely
from geopandas.testing import assert_geodataframe_equal, assert_geoseries_equal
from numpy.testing import assert_almost_equal
from rasterio import Affine
from shapely import LineString, Point

from test.conftest import TEST_RESOURCES_DIR
from walkability.components.shade.utility.analysis import (
    compute_coverage,
    create_tile_windows,
    filter_tiles_to_paths,
    get_shaded_path_stats,
    mask_and_crop,
)
from walkability.components.utils.geometry import CAN_DEFAULT_CRS


@pytest.mark.parametrize(
    ['min_tree_height', 'expected_shaded_length'],
    [
        (None, [400.55, 200.27]),
        (2, [200.27, 200.27]),
    ],
)
def test_get_shaded_path_stats(
    min_tree_height, expected_shaded_length, operator, default_canopy_tiles, default_shade_path
):
    """Assert that the lines were clipped to the tiles, the mask was applied, and then min_tree_height was applied."""
    expected_path_lengths = [400.55, 400.55]

    shaded_paths = get_shaded_path_stats(
        paths=default_shade_path,
        tile_spec=default_canopy_tiles,
        min_tree_height=min_tree_height,
        shade_client=operator.shade_client,
        shade_config=operator.shade_config,
    )

    assert_almost_equal(shaded_paths['length'], expected_path_lengths, decimal=2)
    assert_almost_equal(shaded_paths['length_shaded'], expected_shaded_length, decimal=2)


def test_filter_tiles_to_paths(default_path, default_canopy_tiles):
    expected_tiles = {'mock_tree_raster1'}

    target_tiles = filter_tiles_to_paths(tiles=default_canopy_tiles, paths=default_path)

    assert set(target_tiles.index) == expected_tiles


def test_filter_tiles_to_paths_small_paths(default_canopy_tiles):
    """If the paths are very small (e.g. a point), still return the correct tile."""
    expected_tiles = {'mock_tree_raster1'}

    paths = gpd.GeoDataFrame(geometry=[Point(12.3025, 48.22)], crs=CAN_DEFAULT_CRS)

    target_tiles = filter_tiles_to_paths(tiles=default_canopy_tiles, paths=paths)

    assert set(target_tiles.index) == expected_tiles


def test_filter_tiles_to_paths_multiple_ignore_holes(default_canopy_tiles):
    """Don't return tiles that don't intersect any paths, even if it's because of a 'hole'."""
    expected_tiles = {
        'mock_tree_raster1',
        'mock_tree_raster2',
        'dummy1',
        'dummy2',
        'dummy4',
        'dummy5',
        'dummy6',
        'dummy7',
    }

    paths = gpd.GeoDataFrame(
        geometry=[LineString(([12.30, 48.22], [12.313, 48.22], [12.313, 48.211], [12.30, 48.211], [12.30, 48.22]))],
        crs=CAN_DEFAULT_CRS,
    )

    target_tiles = filter_tiles_to_paths(tiles=default_canopy_tiles, paths=paths)

    assert set(target_tiles.index) == expected_tiles


def test_create_tile_windows():
    input_bounds = (1_370_000, 6_140_000, 1_390_000, 6_160_000)

    expected = gpd.GeoSeries(
        [
            shapely.geometry.box(1_370_000, 6_140_000, 1_380_000, 6_150_000),
            shapely.geometry.box(1_370_000, 6_150_000, 1_380_000, 6_160_000),
            shapely.geometry.box(1_380_000, 6_140_000, 1_390_000, 6_150_000),
            shapely.geometry.box(1_380_000, 6_150_000, 1_390_000, 6_160_000),
        ],
        index=['0_0', '0_1', '1_0', '1_1'],
    )
    received = create_tile_windows(bounds=input_bounds, resolution=10, max_length_pixels=1000)

    assert_geoseries_equal(expected, received)


def test_create_tile_windows_bounds_smaller_than_resolution():
    input_bounds = (1369300, 6143300, 1369304, 6143400)

    expected = gpd.GeoSeries(
        [
            shapely.geometry.box(1369300, 6143300, 1369310, 6143400),
        ],
        index=['0_0'],
    )
    received = create_tile_windows(bounds=input_bounds, resolution=10, max_length_pixels=20)

    assert_geoseries_equal(expected, received)


def test_mask_and_crop_with_mask_file():
    received_masked_data, _ = mask_and_crop(
        raster_file=TEST_RESOURCES_DIR / 'shade/mock_tree_raster2.tif',
    )

    assert isinstance(received_masked_data, np.ndarray)

    # the cloud mask covers all the `1` values
    assert set(np.unique(received_masked_data)) == {3, 255}


def test_mask_and_crop_missing_mask_file():
    received_masked_data, _ = mask_and_crop(
        raster_file=TEST_RESOURCES_DIR / 'shade/mock_tree_raster1.tif',
    )

    # no `nodata` values because nothing is masked out
    assert set(np.unique(received_masked_data)) == {1, 3}


def test_mask_and_crop_with_min_value():
    received_masked_data, _ = mask_and_crop(
        raster_file=TEST_RESOURCES_DIR / 'shade/mock_tree_raster1.tif',
        min_value=2,
    )

    # `1` values were set to `nodata`, i.e. 'unshaded'
    assert set(np.unique(received_masked_data)) == {3, 255}


def test_mask_and_crop_is_cropped():
    received_masked_data, _ = mask_and_crop(
        raster_file=TEST_RESOURCES_DIR / 'shade/mock_tree_raster1.tif',
        windowed_bounds=(1.3692e06, 6.1432e06, 1.3695e06, 6.1435e06),
    )

    assert received_masked_data.shape == (30, 30)


def test_mask_and_crop_always_2d():
    window_bounds = [1369300, 6143300, 1369310, 6143400]

    received_data, _ = mask_and_crop(
        raster_file=TEST_RESOURCES_DIR / 'shade/mock_tree_raster1.tif',
        windowed_bounds=window_bounds,
    )

    assert received_data.shape == (10, 1)


def test_mask_and_crop_profile_matches_data():
    received_masked_data, received_profile = mask_and_crop(
        raster_file=TEST_RESOURCES_DIR / 'shade/mock_tree_raster1.tif',
        windowed_bounds=(1.3692e06, 6.1432e06, 1.3695e06, 6.1435e06),
    )

    assert received_masked_data.shape[0] == received_profile['height']
    assert received_masked_data.shape[1] == received_profile['width']

    expected_transform = Affine(a=10, b=0, c=1.3692e06, d=0, e=-10, f=6.1435e06)

    assert received_profile['transform'] == expected_transform


def test_compute_coverage_mixed_classes(default_shade_path_small, default_canopy_raster_profile):
    """Coverage with some clouds, some coverage, and some 'no coverage'"""
    expected_shade_path = default_shade_path_small.copy()
    expected_shade_path['prop_shaded'] = 0.5

    canopy_data = np.ones((4, 20))
    canopy_data[:, :5] = 255  # no cover
    canopy_data[:, -5:] = 255  # masked by clouds (keep separate for now in case we distinguish between them later)

    covered_paths = compute_coverage(
        paths=default_shade_path_small, shade_raster=canopy_data, shade_profile=default_canopy_raster_profile
    )

    assert_geodataframe_equal(covered_paths, expected_shade_path, check_like=True)
