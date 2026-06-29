from pathlib import Path
from typing import Any

import botocore.client
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.mask
import shapely
from climatoology.base.logging import get_climatoology_logger
from rasterio.enums import MaskFlags
from rasterio.windows import Window
from rasterio.windows import from_bounds as window_from_bounds
from rasterstats import zonal_stats
from tqdm import tqdm

from walkability.components.shade.utility.config import S3ShadeConfig
from walkability.components.shade.utility.download import download_shade_tile

log = get_climatoology_logger(__name__)

MIN_TREE_HEIGHT = 2
MAX_RASTER_EDGE_LENGTH = 4096


def get_shaded_path_stats(
    paths: gpd.GeoDataFrame,
    tile_spec: gpd.GeoSeries,
    shade_client: botocore.client.BaseClient,
    shade_config: S3ShadeConfig,
    min_tree_height: int = MIN_TREE_HEIGHT,
) -> gpd.GeoDataFrame:
    """
    Download tree canopy tiles and calculate coverage of paths.

    :param paths: paths to compute coverage of
    :param tile_spec: a GeoDataFrame of polygons representing the tiles, e.g. from `download_tile_spec`
    :param shade_client: client for requesting the data
    :param shade_config: S3 config for the tree canopy dataset
    :param min_tree_height: if provided, only include tree canopies greater than this value
    :return: paths with the additional columns of `length` and `length_shaded`
    """
    tiles_in_aoi = filter_tiles_to_paths(tiles=tile_spec, paths=paths)

    paths_out = []
    tiles_progbar = tqdm(tiles_in_aoi.index)
    for tile_id in tiles_progbar:
        tiles_progbar.set_description(f'Downloading {tile_id} ...')
        canopy_path = download_shade_tile(tile_id=tile_id, shade_client=shade_client, shade_config=shade_config)

        with rasterio.open(canopy_path, 'r') as src:
            raster_crs = src.profile['crs']
            raster_bounds = src.bounds
            resolution = min(abs(src.transform.a), abs(src.transform.e))

        tile_windows = create_tile_windows(
            bounds=raster_bounds, resolution=resolution, max_length_pixels=MAX_RASTER_EDGE_LENGTH
        )

        tiles_progbar.set_description(f'Clipping paths for {tile_id} ...')
        projected_paths = paths.to_crs(raster_crs)

        for w_id, window in tile_windows.items():
            tiles_progbar.set_description(f'Processing tile {tile_id}, window {w_id} ...')

            clipped_paths = projected_paths.clip(window)
            if clipped_paths.empty:
                continue

            canopy_data, canopy_profile = mask_and_crop(
                raster_file=canopy_path,
                windowed_bounds=window.bounds,
                min_value=min_tree_height,
            )

            covered_paths = compute_coverage(
                paths=clipped_paths, shade_raster=canopy_data, shade_profile=canopy_profile
            )
            paths_out.append(covered_paths)

    shaded_paths = pd.concat(paths_out)
    shaded_paths = shaded_paths.to_crs(shaded_paths.estimate_utm_crs())
    shaded_paths = (
        shaded_paths.assign(length=shaded_paths.length, length_shaded=shaded_paths.length * shaded_paths['prop_shaded'])
        .to_crs(paths.crs)
        .drop(columns='prop_shaded')
    )

    return shaded_paths


def filter_tiles_to_paths(tiles: gpd.GeoDataFrame, paths: gpd.GeoDataFrame) -> gpd.GeoSeries:
    """Subset the `tiles` and return only the tiles that intersect with the `paths`."""
    target_idx = tiles.sindex.intersection(paths.total_bounds)
    target_tiles = tiles.iloc[target_idx]
    target_idx_intersects = [i for i, t in target_tiles.items() if paths.intersects(t).any()]
    return target_tiles.loc[target_idx_intersects]


def create_tile_windows(
    bounds: tuple[float, float, float, float], resolution: float, max_length_pixels: int
) -> gpd.GeoSeries:
    """
    Create windows provided `bounds`, such that each window has an edge length of less than `max_length_pixels`, at the
    given `resolution` (also in pixels).
    """
    min_x, min_y, max_x, max_y = [b for b in bounds]

    def _create_window(minv, maxv):
        if maxv - minv < resolution:
            maxv = minv + resolution

        vals = list(np.arange(minv, maxv, step=max_length_pixels * resolution))
        if vals[-1] != maxv:
            vals.append(maxv)
        return vals

    xs = _create_window(min_x, max_x)
    ys = _create_window(min_y, max_y)

    subtiles = gpd.GeoSeries()
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            subtiles.loc[f'{i}_{j}'] = shapely.geometry.box(xs[i], ys[j], xs[i + 1], ys[j + 1])

    return subtiles


def mask_and_crop(
    raster_file: Path,
    windowed_bounds: tuple[int, int, int, int] = None,
    min_value: float = None,
    nodata: int = 255,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Read the `windowed_bounds` from the `raster_file`, and use the `nodata` value to apply the raster's mask and to
    mask out any values lower than `min_value`.

    :param raster_file: location of raw raster file
    :param windowed_bounds: bounds to read from the raster in `raster_file`
    :param min_value: if provided, mask all raster cells where the value is less than `min_value`
    :param nodata: nodata value to apply for the mask
    :return: tuple containing: the 2D array of the masked data, and its rasterio profile
    """

    with rasterio.open(raster_file) as src:
        profile = src.meta

        if windowed_bounds is None:
            window = Window(col_off=0, row_off=0, width=src.shape[1], height=src.shape[0])
        else:
            window = window_from_bounds(*windowed_bounds, transform=src.transform)

        data = src.read(window=window)

        if src.mask_flag_enums[0] == [MaskFlags.per_dataset]:
            log.debug(f'Applying mask for {raster_file.name}')

            mask = src.read_masks(window=window)

            data[mask == 255] = nodata  # 255 is the nodata value in the .msk files according to the docs

        elif all([m in (MaskFlags.all_valid, MaskFlags.nodata) for m in src.mask_flag_enums[0]]):
            log.debug('Mask already applied to raw data')

        else:
            raise RuntimeError(
                f"Mask for raster file at {raster_file} with mask_flag_enums={src.mask_flag_enums} can't be handled"
            )

        if min_value:
            data[data < min_value] = nodata

    # Remove dimension for raster bands, if present
    if data.ndim > 2:
        data = np.squeeze(data, axis=0)

    profile.update(
        {'nodata': nodata, 'transform': src.window_transform(window), 'width': data.shape[1], 'height': data.shape[0]}
    )

    return data, profile


def compute_coverage(
    paths: gpd.GeoDataFrame, shade_raster: np.ndarray, shade_profile: dict[str, Any]
) -> gpd.GeoDataFrame:
    """
    Compute the coverage of the provided 2D raster (array and profile) over each of the paths. A 'nodata' value in
    `shade_raster` is considered unshaded, while any valid values are considered shaded.

    Return a GeoDataFrame of the paths with the added column `prop_shaded`.
    """
    crs_in = paths.crs
    paths = paths.to_crs(shade_profile['crs'])

    zstat = zonal_stats(
        vectors=paths,
        raster=shade_raster,
        affine=shade_profile['transform'],
        nodata=shade_profile['nodata'],
        stats=['count', 'nodata'],
        all_touched=True,
        geojson_out=True,
    )

    covered_paths = gpd.GeoDataFrame.from_features(zstat, crs=shade_profile['crs'])
    covered_paths['prop_shaded'] = covered_paths['count'] / covered_paths[['count', 'nodata']].sum(axis='columns')
    covered_paths = covered_paths.drop(columns=['count', 'nodata'])
    covered_paths = covered_paths.to_crs(crs_in)

    return covered_paths
