import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from geopandas.testing import assert_geodataframe_equal
from pyproj import CRS
from rasterio import Affine
from shapely import LineString, Point

from test.conftest import TEST_RESOURCES_DIR
from walkability.components.shade.utility import (
    compute_coverage,
    download_tile_spec,
    get_shaded_path_stats,
    mask_and_crop,
    subset_tiles,
)
from walkability.components.utils.misc import PathCategory


@pytest.fixture
def default_shade_path() -> gpd.GeoDataFrame:
    """A default shade path which overlaps with both `mock_tree_raster1.tif` and `mock_tree_raster2.tif`."""
    return gpd.GeoDataFrame(
        data={
            '@osmId': ['test'],
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            '@other_tags': [{}],
            'geometry': [LineString([[12.30, 48.22], [12.31, 48.22]])],
        },
        crs='EPSG:4326',
    )


@pytest.fixture
def default_shade_path_small() -> gpd.GeoDataFrame:
    """A default shade path which is covered by only `mock_tree_raster1.tif` and can be used with
    `default_canopy_raster_profile` for unit testing.
    """
    return gpd.GeoDataFrame(
        data={
            '@osmId': ['test'],
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            '@other_tags': [{}],
            'geometry': [LineString([[12.30, 48.22], [12.305, 48.22]])],
        },
        crs='EPSG:4326',
    )


@pytest.fixture
def default_canopy_raster_profile():
    """This is a default raster profile for an array of shape (4, 20), which covers all of `default_shade_path_small`."""
    return {
        'driver': 'GTiff',
        'dtype': 'float32',
        'nodata': 255,
        'width': 20,
        'height': 4,
        'count': 1,
        'crs': CRS.from_epsg(4326),
        'transform': Affine(0.00024999999999995024, 0.0, 12.3, 0.0, -0.00024999999999995024, 48.2205),
    }


def test_download_tiles(operator, compute_resources):
    tiles = download_tile_spec(
        shade_config=operator.shade_config,
        shade_client=operator.shade_client,
        download_dir=compute_resources.computation_dir,
    )

    assert isinstance(tiles, gpd.GeoDataFrame)


def test_subset_tiles(default_path, default_canopy_tiles):
    expected_tiles = {'mock_tree_raster1'}

    target_tiles = subset_tiles(tiles=default_canopy_tiles, paths=default_path)

    assert set(target_tiles['tile']) == expected_tiles


def test_subset_tiles_small_paths(default_canopy_tiles):
    """If the paths are very small (e.g. a point), still return the correct tile."""
    expected_tiles = {'mock_tree_raster1'}

    paths = gpd.GeoDataFrame(geometry=[Point(12.3025, 48.22)], crs='epsg:4326')

    target_tiles = subset_tiles(tiles=default_canopy_tiles, paths=paths)

    assert set(target_tiles['tile']) == expected_tiles


def test_subset_tiles_multiple_ignore_holes(default_canopy_tiles):
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
        geometry=[LineString(([12.30, 48.22], [12.315, 48.22], [12.315, 48.19], [12.30, 48.19], [12.30, 48.22]))],
        crs='epsg:4326',
    )

    target_tiles = subset_tiles(tiles=default_canopy_tiles, paths=paths)

    assert set(target_tiles['tile']) == expected_tiles


def test_mask_and_crop_with_mask_file(default_aoi):
    received_masked_data, _ = mask_and_crop(
        file=TEST_RESOURCES_DIR / 'mock_tree_raster2.tif',
        aoi=default_aoi,
        aoi_crs=CRS.from_epsg(4326),
    )

    assert isinstance(received_masked_data, np.ndarray)

    # the cloud mask covers all the `1` values
    assert set(np.unique(received_masked_data)) == {3, 255}


def test_mask_and_crop_missing_mask_file(default_aoi):
    received_masked_data, _ = mask_and_crop(
        file=TEST_RESOURCES_DIR / 'mock_tree_raster1.tif',
        aoi=default_aoi,
        aoi_crs=CRS.from_epsg(4326),
    )

    # no `nodata` values because nothing is masked out
    assert set(np.unique(received_masked_data)) == {1, 3}


def test_mask_and_crop_with_min_value(default_aoi):
    received_masked_data, _ = mask_and_crop(
        file=TEST_RESOURCES_DIR / 'mock_tree_raster1.tif',
        aoi=default_aoi,
        aoi_crs=CRS.from_epsg(4326),
        min_value=2,
    )

    # `1` values were set to `nodata`, i.e. 'unshaded'
    assert set(np.unique(received_masked_data)) == {3, 255}


def test_mask_and_crop_is_cropped():
    mask_aoi = shapely.box(12.301, 48.215, 12.304, 48.225)
    received_masked_data, _ = mask_and_crop(
        file=TEST_RESOURCES_DIR / 'mock_tree_raster1.tif',
        aoi=mask_aoi,
        aoi_crs=CRS.from_epsg(4326),
    )

    assert received_masked_data.shape == (1, 44, 11)


def test_mask_and_crop_tiny_aoi():
    """Return a valid raster even if the AOI is smaller than the pixel resolution."""
    aoi = shapely.box(12.30243, 48.2103, 12.30245, 48.210315)
    received_masked_data, _ = mask_and_crop(
        file=TEST_RESOURCES_DIR / 'mock_tree_raster1.tif',
        aoi=aoi,
        aoi_crs=CRS.from_epsg(4326),
    )

    assert received_masked_data.shape == (1, 2, 3)


def test_mask_and_crop_out_of_bounds():
    aoi = shapely.box(0, 0, 1, 1)
    with pytest.raises(ValueError, match=r'Input shapes do not overlap raster.'):
        mask_and_crop(
            file=TEST_RESOURCES_DIR / 'mock_tree_raster1.tif',
            aoi=aoi,
            aoi_crs=CRS.from_epsg(4326),
        )


@pytest.mark.parametrize('extra_raster_dimension', [True, False])
def test_compute_coverage(extra_raster_dimension, default_shade_path_small, default_canopy_raster_profile):
    expected_shade_path = default_shade_path_small.copy()
    expected_shade_path['prop_shaded'] = 1.0

    canopy_data = np.ones((4, 20))
    if extra_raster_dimension:
        canopy_data = np.expand_dims(canopy_data, axis=0)

    covered_paths = compute_coverage(
        paths=default_shade_path_small, shade_raster=canopy_data, canopy_profile=default_canopy_raster_profile
    )

    assert_geodataframe_equal(covered_paths, expected_shade_path, check_like=True)


def test_compute_coverage_mixed_classes(default_shade_path_small, default_canopy_raster_profile):
    """Coverage with some clouds, some coverage, and some 'no coverage'"""
    expected_shade_path = default_shade_path_small.copy()
    expected_shade_path['prop_shaded'] = 0.5

    canopy_data = np.ones((4, 20))
    canopy_data[:, :5] = 255  # no cover
    canopy_data[:, -5:] = 255  # masked by clouds (keep separate for now in case we distinguish between them later)

    covered_paths = compute_coverage(
        paths=default_shade_path_small, shade_raster=canopy_data, canopy_profile=default_canopy_raster_profile
    )

    assert_geodataframe_equal(covered_paths, expected_shade_path, check_like=True)


@pytest.mark.parametrize(['min_tree_height', 'expected_shaded_length'], [(None, [371.6, 185.8]), (2, [185.8, 185.8])])
def test_get_shaded_path_stats(
    min_tree_height, expected_shaded_length, operator, default_canopy_tiles, default_shade_path
):
    """Assert that the lines were clipped to the tiles, the mask was applied, and then min_tree_height was applied."""
    expected_shade_result = default_shade_path.copy()

    expected_shaded_paths = pd.concat([expected_shade_result] * 2)
    expected_shaded_paths['geometry'] = [
        shapely.LineString([(12.3, 48.22), (12.305, 48.22)]),
        shapely.LineString([(12.305, 48.22), (12.31, 48.22)]),
    ]
    expected_shaded_paths['length_shaded'] = expected_shaded_length
    expected_shaded_paths['length'] = [371.6, 371.6]

    shaded_paths = get_shaded_path_stats(
        paths=default_shade_path,
        tile_spec=default_canopy_tiles,
        min_tree_height=min_tree_height,
        shade_client=operator.shade_client,
        shade_config=operator.shade_config,
    )
    shaded_paths[['length', 'length_shaded']] = shaded_paths[['length', 'length_shaded']].apply(round, args=(1,))

    assert_geodataframe_equal(shaded_paths, expected_shaded_paths, check_like=True, check_less_precise=True)
