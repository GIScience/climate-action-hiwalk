import datetime as dt
import logging
import math
from typing import List

import geopandas as gpd
import shapely
import shapely.ops
from climatoology.base.baseoperator import _Artifact
from climatoology.base.computation import ComputationResources
from climatoology.utility.Naturalness import NaturalnessIndex, NaturalnessUtility
from climatoology.utility.api import TimeRange
from pyproj import Transformer, CRS

from walkability.components.naturalness.naturalness_artifacts import build_naturalness_artifact
from walkability.components.utils.geometry import get_utm_zone

log = logging.getLogger(__name__)


def naturalness_analysis(
    line_paths: gpd.GeoDataFrame,
    aoi: shapely.geometry.MultiPolygon,
    index: NaturalnessIndex,
    resources: ComputationResources,
    naturalness_utility: NaturalnessUtility,
) -> _Artifact:
    log.info('Computing naturalness')
    try:
        naturalness_of_paths = get_naturalness(
            paths=line_paths, aoi=aoi, index=index, naturalness_utility=naturalness_utility
        )
    except Exception as error:
        log.warning(error, exc_info=True)
        naturalness_of_paths = line_paths.copy()
        naturalness_of_paths['naturalness'] = None
    naturalness_artifact = build_naturalness_artifact(naturalness_of_paths, resources)
    log.info('Finished computing Naturalness')
    return naturalness_artifact


def get_naturalness(
    aoi: shapely.MultiPolygon, paths: gpd.GeoDataFrame, index: NaturalnessIndex, naturalness_utility: NaturalnessUtility
) -> gpd.GeoDataFrame:
    """
    Get NDVI along street within the AOI.

    :param naturalness_utility:
    :param index:
    :param paths:
    :param aoi:
    :return: RasterInfo objects with NDVI values along streets and places
    """
    # Trim the aoi, pending smarter usage of Sentinel Hub credits: https://gitlab.heigit.org/climate-action/utilities/naturalness-utility/-/issues/35
    aoi_trimmed = subset_aoi(aoi=aoi)

    # Temporarily clip paths to aoi, pending: https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/154
    paths_clipped = gpd.clip(paths, aoi_trimmed, keep_geom_type=True)

    paths_ndvi = fetch_naturalness_by_vector(
        naturalness_utility=naturalness_utility,
        time_range=TimeRange(end_date=dt.datetime.now().replace(day=1).date()),
        vectors=[paths_clipped.geometry],
        index=index,
    )

    return paths_ndvi


def fetch_naturalness_by_vector(
    naturalness_utility: NaturalnessUtility,
    time_range: TimeRange,
    vectors: List[gpd.GeoSeries],
    index: NaturalnessIndex = NaturalnessIndex.NDVI,
    agg_stat: str = 'median',
) -> gpd.GeoDataFrame:
    naturalness_gdf = naturalness_utility.compute_vector(
        index=index, aggregation_stats=[agg_stat], vectors=vectors, time_range=time_range
    )

    naturalness_gdf = naturalness_gdf.rename(columns={agg_stat: 'naturalness'})
    return naturalness_gdf


def subset_aoi(aoi: shapely.MultiPolygon, max_area: float = 50_000_000) -> shapely.Polygon:
    """For temporary HotFix of resource over-consumption only:
    Return a sample of the AOI with area less than max_area m2.

    1. If the largest polygon of the aoi is less than max_area, return it
    2. Otherwise, return the centroid of the largest polygon within aoi, buffered by sqrt(max_area/pi)
    """
    # Get the largest polygon of the aoi and reproject it
    utm = get_utm_zone(aoi)
    transform = Transformer.from_crs(CRS.from_epsg(4326), utm).transform
    aoi_trimmed: shapely.Polygon = max(list(aoi.geoms), key=lambda a: a.area)
    aoi_trimmed = shapely.ops.transform(transform, aoi_trimmed)

    # If the aoi is too large, create a buffer around its centroid
    if aoi_trimmed.area > max_area:
        aoi_trimmed = shapely.centroid(aoi_trimmed).buffer(math.sqrt(max_area / math.pi))

    # Reproject back to WGS84
    transform_r = Transformer.from_crs(utm, CRS.from_epsg(4326)).transform
    aoi_trimmed = shapely.ops.transform(transform_r, aoi_trimmed)

    # Clip by original aoi
    aoi_trimmed = aoi_trimmed.intersection(aoi)

    return aoi_trimmed
