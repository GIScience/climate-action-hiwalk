import datetime as dt
import logging
from typing import List, Tuple

import geopandas as gpd
from climatoology.base.baseoperator import _Artifact
from climatoology.base.computation import ComputationResources
from climatoology.utility.Naturalness import NaturalnessIndex, NaturalnessUtility
from climatoology.utility.api import TimeRange

from walkability.components.naturalness.naturalness_artifacts import build_naturalness_artifact

log = logging.getLogger(__name__)


def naturalness_analysis(
    line_paths: gpd.GeoDataFrame,
    polygon_paths: gpd.GeoDataFrame,
    index: NaturalnessIndex,
    resources: ComputationResources,
    naturalness_utility: NaturalnessUtility,
) -> Tuple[_Artifact, gpd.GeoDataFrame]:
    log.info('Computing naturalness')
    naturalness_of_paths, naturalness_of_polygons = get_naturalness(
        paths=line_paths, polygons=polygon_paths, index=index, naturalness_utility=naturalness_utility
    )
    naturalness_artifact = build_naturalness_artifact(naturalness_of_paths, naturalness_of_polygons, resources)
    log.info('Finished computing Naturalness')
    return naturalness_artifact, naturalness_of_paths


def get_naturalness(
    paths: gpd.GeoDataFrame,
    polygons: gpd.GeoDataFrame,
    index: NaturalnessIndex,
    naturalness_utility: NaturalnessUtility,
) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Get NDVI along street within the AOI.

    :param naturalness_utility:
    :param index:
    :param paths:
    :return: RasterInfo objects with NDVI values along streets and places
    """
    paths_ndvi = fetch_naturalness_by_vector(
        naturalness_utility=naturalness_utility,
        time_range=TimeRange(end_date=dt.datetime.now().replace(day=1).date()),
        vectors=[paths.geometry],
        index=index,
    )
    polygons_ndvi = fetch_naturalness_by_vector(
        naturalness_utility=naturalness_utility,
        time_range=TimeRange(end_date=dt.datetime.now().replace(day=1).date()),
        vectors=[polygons.geometry],
        index=index,
    )
    return paths_ndvi, polygons_ndvi


def fetch_naturalness_by_vector(
    naturalness_utility: NaturalnessUtility,
    time_range: TimeRange,
    vectors: List[gpd.GeoSeries],
    index: NaturalnessIndex = NaturalnessIndex.NDVI,
    agg_stat: str = 'median',
    resolution: int = 30,
) -> gpd.GeoDataFrame:
    naturalness_gdf = naturalness_utility.compute_vector(
        index=index,
        aggregation_stats=[agg_stat],
        vectors=vectors,
        time_range=time_range,
        resolution=resolution,
    )

    naturalness_gdf = naturalness_gdf.rename(columns={agg_stat: 'naturalness'})
    return naturalness_gdf
