from pathlib import Path
from typing import Optional

import botocore.client
import geopandas as gpd
from botocore.exceptions import ClientError
from climatoology.base.exception import ClimatoologyUserError
from climatoology.base.logging import get_climatoology_logger

from walkability.components.shade.utility.config import S3ShadeConfig
from walkability.components.utils.geometry import CAN_DEFAULT_CRS

log = get_climatoology_logger(__name__)


def download_tile_spec(
    shade_client: botocore.client.BaseClient,
    shade_config: S3ShadeConfig,
    download_dir: Path,
) -> gpd.GeoSeries:
    """
    Download the tile specification for the tree canopy data.

    :param shade_client: client for requesting the data
    :param shade_config: S3 config for the tree canopy dataset
    :param download_dir: directory to download the tile specification to
    :return: a GeoSeries containing the tile specification
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
    tiles = gpd.read_file(local_path).to_crs(CAN_DEFAULT_CRS)
    return tiles.set_index('tile').geometry


def download_shade_tile(
    tile_id: str,
    shade_client: botocore.client.BaseClient,
    shade_config: S3ShadeConfig,
) -> Path:
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

    mask_file = shade_config.cloud_mask_path / f'{tile_id}.tif.msk'
    mask_file = download_data(
        s3_client=shade_client,
        bucket=shade_config.bucket,
        s3_path=mask_file,
        download_dir=shade_config.cache_dir,
    )
    if mask_file is None:
        log.debug(f'{mask_file} was unable to be downloaded')

    return canopy_file


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
    if not local_file.exists() or overwrite:
        log.debug(f"Downloading file '{s3_path}' from bucket '{bucket}' to: {download_dir}")
        try:
            s3_client.download_file(bucket, str(s3_path), local_file)
        except ClientError:
            local_file = None
            log.warning(f'Failed to download {s3_path} from {bucket}, to local directory {download_dir}', exc_info=True)
    return local_file
