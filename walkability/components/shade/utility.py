import logging
import os
from pathlib import Path
from typing import Any, Optional

import botocore.client
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.mask
import shapely
from botocore.exceptions import ClientError
from climatoology.base.exception import ClimatoologyUserError
from climatoology.base.logging import get_climatoology_logger
from pydantic import Field, computed_field
from pydantic.dataclasses import dataclass
from pyproj import CRS, Transformer
from rasterio import MemoryFile
from rasterio.enums import MaskFlags
from rasterstats import zonal_stats
from shapely import MultiPolygon
from tqdm import tqdm

logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('s3transfer').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('rasterio').setLevel(logging.WARNING)

log = get_climatoology_logger(__name__)

MIN_TREE_HEIGHT = 2


@dataclass
class S3ShadeConfig:
    cache_dir: Path = Field(description='A directory to cache downloaded files to.')
    bucket: str = Field(
        description='The AWS bucket containing the tree canopy data.',
        default='dataforgood-fb-data',
    )
    base_path: Path = Field(
        description="The base path to the tree canopy data. All 'object' and 'subdir' values are relative to this base path.",
        default=Path('forests/v1/alsgedi_global_v6_float'),
    )
    tiles_object: str = Field(
        description='The object name for the tile specification (relative to base_path).',
        default='tiles.geojson',
    )
    canopy_heights_subdir: str = Field(
        description='The subdirectory path for the canopy heights data (relative to base_path).',
        default='chm',
    )
    cloud_mask_subdir: str = Field(
        description='The subdirectory path for the masks data (relative to base_path).',
        default='msk',
    )
    metadata_subdir: str = Field(
        description='The subdirectory path for the metadata (relative to base_path).',
        default='metadata',
    )

    @computed_field
    @property
    def canopy_heights_path(self) -> Path:
        return self.base_path / f'{self.canopy_heights_subdir}'

    @computed_field
    @property
    def cloud_mask_path(self) -> Path:
        return self.base_path / f'{self.cloud_mask_subdir}'

    @computed_field
    @property
    def metadata_path(self) -> Path:
        return self.base_path / f'{self.metadata_path}'


def download_tile_spec(
    shade_client: botocore.client.BaseClient,
    shade_config: S3ShadeConfig,
    download_dir: Path,
) -> gpd.GeoDataFrame:
    """
    Download the tile specification for the tree canopy data.

    :param shade_client: client for requesting the data
    :param shade_config: S3 config for the tree canopy dataset
    :param download_dir: directory to download the tile specification to
    :return: a GeoDataFrame containing the tile specification
    """
    log.debug('Getting tree canopy tile specification')
    local_path = download_data(
        s3_client=shade_client,
        bucket=shade_config.bucket,
        s3_path=shade_config.base_path / shade_config.tiles_object,
        download_dir=download_dir,
    )
    if local_path is None:
        raise ClimatoologyUserError('Failed to download tile specification for tree canopy dataset')
    tiles = gpd.read_file(local_path).to_crs('epsg:4326')
    return tiles


def subset_tiles(tiles: gpd.GeoDataFrame, paths: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Subset the `tiles` and return only the tiles that intersect with the `paths`."""
    target_idx = tiles.sindex.intersection(paths.total_bounds)
    target_tiles = tiles.iloc[target_idx]
    target_idx_full = [i for i, t in target_tiles.iterrows() if paths.intersects(t.geometry).any()]
    return target_tiles.loc[target_idx_full]


def download_data(
    s3_client: botocore.client.BaseClient,
    bucket: str,
    s3_path: Path,
    download_dir: Path,
    *,
    overwrite: bool = False,
) -> Optional[Path]:
    """
    Download data from S3.

    :param s3_client: client for requesting data
    :param bucket: name of the bucket containing data
    :param s3_path: path to the S3 data within the bucket
    :param download_dir: local directory to download the files to
    :param overwrite: whether or not to overwrite the file if it already exists in `download_dir`
    :return: the location of the file, or None if download failed
    """
    local_file = download_dir / s3_path.name
    if not os.path.exists(local_file) or overwrite:
        log.debug(f"Downloading file '{s3_path}' from bucket '{bucket}' to: {download_dir}")
        try:
            s3_client.download_file(bucket, str(s3_path), local_file)
        except ClientError:
            local_file = None
            log.warning(f'Failed to download {s3_path} from {bucket}, to local directory {download_dir}', exc_info=True)
    return local_file


def mask_and_crop(
    file: Path,
    aoi: MultiPolygon,
    aoi_crs: CRS,
    min_value: float = None,
    nodata=255,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Get the raster from `file`, clip it to the AOI, apply the mask file, and mask out values lower than `min_value`.

    :param file: location of raw raster file
    :param aoi: aoi to clip the raster to
    :param aoi_crs: crs of the AOI
    :param min_value: if provided, mask all raster cells where the value is less than `min_value`
    :param nodata: nodata value for the resulting raster file
    :return: tuple containing: the array of the masked data, and its rasterio profile
    """
    with rasterio.open(file) as src:
        data = src.read()
        profile = src.meta

        if src.mask_flag_enums[0] == [MaskFlags.per_dataset]:
            log.debug(f'Applying mask for {file.name}')
            mask = src.read_masks()
            data[mask == 255] = nodata  # 255 is the nodata value in the .msk files according to the docs
        elif src.mask_flag_enums[0] == [MaskFlags.all_valid]:
            log.debug(f'No mask found for {file.name}')
        else:
            raise RuntimeError(
                f"Mask for raster file at {file} with mask_flag_enums={src.mask_flag_enums} can't be handled"
            )

    transformer = Transformer.from_crs(aoi_crs, profile['crs'], always_xy=True)
    aoi = shapely.ops.transform(transformer.transform, aoi)

    with MemoryFile() as memfile:
        with memfile.open(**profile) as src:
            src.write(data)

            aoi = shapely.buffer(aoi, distance=max(src.res))
            masked_data, masked_transform = rasterio.mask.mask(src, [aoi], crop=True, nodata=nodata, all_touched=False)
            profile.update(
                {
                    'height': masked_data.shape[1],
                    'width': masked_data.shape[2],
                    'transform': masked_transform,
                    'nodata': nodata,
                    'compress': 'DEFLATE',
                }
            )

            if min_value:
                masked_data[masked_data < min_value] = nodata

    return masked_data, profile


def compute_coverage(
    paths: gpd.GeoDataFrame, shade_raster: np.ndarray, canopy_profile: dict[str, Any]
) -> gpd.GeoDataFrame:
    """
    Compute the coverage of the provided raster over each of the paths.
    """
    if shade_raster.ndim > 2:
        shade_raster = np.squeeze(shade_raster)
    if shade_raster.ndim < 2:
        # In case it was squeezed the whole way down to a 1D array, expand back to 2D
        shade_raster = np.expand_dims(shade_raster, axis=1)

    crs_in = paths.crs
    paths = paths.to_crs(canopy_profile['crs'])

    zstat = zonal_stats(
        vectors=paths,
        raster=shade_raster,
        affine=canopy_profile['transform'],
        nodata=canopy_profile['nodata'],
        stats=['count', 'nodata'],
        all_touched=True,
        geojson_out=True,
    )

    covered_paths = gpd.GeoDataFrame.from_features(zstat, crs=canopy_profile['crs'])
    covered_paths['prop_shaded'] = covered_paths['count'] / covered_paths[['count', 'nodata']].sum(axis='columns')
    covered_paths = covered_paths.drop(columns=['count', 'nodata'])
    covered_paths = covered_paths.to_crs(crs_in)

    return covered_paths


def get_shaded_path_stats(
    paths: gpd.GeoDataFrame,
    tile_spec: gpd.GeoDataFrame,
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
    tiles_in_aoi = subset_tiles(tiles=tile_spec, paths=paths)

    paths_out = []
    progbar = tqdm(tiles_in_aoi.iterrows(), total=len(tiles_in_aoi), desc='Beginning shade calculation')
    for _, tile in progbar:
        tile_id = tile['tile']
        clipped_paths = paths.clip(tile['geometry'])

        progbar.set_description(f'Downloading canopy height ({tile_id})')
        canopy_file = shade_config.canopy_heights_path / f'{tile_id}.tif'
        canopy_file = download_data(
            s3_client=shade_client,
            bucket=shade_config.bucket,
            s3_path=canopy_file,
            download_dir=shade_config.cache_dir,
        )
        if canopy_file is None:
            log.error(f'Failed to download tree canopy data for tile {tile_id}, cancelling shade computation')
            raise ClimatoologyUserError('Failed to download tree canopy tiles, please try again later')

        progbar.set_description(f'Downloading mask ({tile_id})')
        mask_file = shade_config.cloud_mask_path / f'{tile_id}.tif.msk'
        mask_file = download_data(
            s3_client=shade_client,
            bucket=shade_config.bucket,
            s3_path=mask_file,
            download_dir=shade_config.cache_dir,
        )
        if mask_file is None:
            log.debug(f'{mask_file} was unable to be downloaded')

        progbar.set_description(f'Cleaning raster ({tile_id})')
        canopy_data, canopy_profile = mask_and_crop(
            file=canopy_file,
            aoi=shapely.geometry.box(*clipped_paths.total_bounds),
            aoi_crs=clipped_paths.crs,
            min_value=min_tree_height,
        )

        progbar.set_description(f'Computing coverage stats ({tile_id})')
        covered_paths = compute_coverage(paths=clipped_paths, shade_raster=canopy_data, canopy_profile=canopy_profile)
        paths_out.append(covered_paths)

    shaded_paths = pd.concat(paths_out)
    shaded_paths = (
        shaded_paths.to_crs(shaded_paths.estimate_utm_crs())
        .assign(length=shaded_paths.length, length_shaded=shaded_paths.length * shaded_paths['prop_shaded'])
        .to_crs(paths.crs)
        .drop(columns='prop_shaded')
    )

    return shaded_paths
