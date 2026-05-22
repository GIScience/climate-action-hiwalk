import botocore.client
import geopandas as gpd
from climatoology.base.artifact_creators import Artifact
from climatoology.base.computation import ComputationResources
from climatoology.base.logging import get_climatoology_logger

from walkability.components.shade.utility import S3ShadeConfig, get_shaded_path_stats

log = get_climatoology_logger(__name__)


def shade_analysis(
    paths: gpd.GeoDataFrame,
    tile_spec: gpd.GeoDataFrame,
    shade_client: botocore.client.BaseClient,
    shade_config: S3ShadeConfig,
    resources: ComputationResources,
) -> list[Artifact]:
    get_shaded_path_stats(paths=paths, tile_spec=tile_spec, shade_client=shade_client, shade_config=shade_config)
    return []
