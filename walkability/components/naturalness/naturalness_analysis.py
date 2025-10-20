import datetime as dt
import logging
from typing import List, Tuple

import geopandas as gpd
import plotly.graph_objects as go
from climatoology.base.baseoperator import _Artifact
from climatoology.base.computation import ComputationResources
from climatoology.utility.api import TimeRange
from climatoology.utility.Naturalness import NaturalnessIndex, NaturalnessUtility

from walkability.components.naturalness.naturalness_artifacts import (
    build_naturalness_artifact,
    build_naturalness_summary_bar_artifact,
)
from walkability.components.utils.geometry import calculate_length
from walkability.components.utils.misc import generate_colors

log = logging.getLogger(__name__)


def naturalness_analysis(
    line_paths: gpd.GeoDataFrame,
    polygon_paths: gpd.GeoDataFrame,
    index: NaturalnessIndex,
    resources: ComputationResources,
    naturalness_utility: NaturalnessUtility,
) -> list[_Artifact]:
    log.info('Computing naturalness')
    naturalness_of_paths, naturalness_of_polygons = get_naturalness(
        paths=line_paths, polygons=polygon_paths, index=index, naturalness_utility=naturalness_utility
    )
    naturalness_artifact = build_naturalness_artifact(naturalness_of_paths, naturalness_of_polygons, resources)
    log.info('Finished computing Naturalness')

    naturalness_summary_bar = summarise_naturalness(paths=naturalness_of_paths)
    naturalness_summary_bar_artifact = build_naturalness_summary_bar_artifact(
        aoi_aggregate=naturalness_summary_bar, resources=resources
    )
    return [naturalness_artifact, naturalness_summary_bar_artifact]


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


def summarise_naturalness(
    paths: gpd.GeoDataFrame,
    length_resolution_m: int = 1000,
) -> go.Figure:
    log.info('Summarising naturalness stats')
    stats = calculate_length(length_resolution_m, paths, paths.estimate_utm_crs())

    # Categorize naturalness values and set negative values (e.g. water) to 0
    stats['naturalness_rating'] = stats['naturalness'].apply(lambda x: 0 if x < 0.3 else (0.5 if x < 0.6 else 1))

    # Add naturalness categories for labels
    naturalness_map = {
        0: 'Low (< 0.3) ',
        0.5: 'Medium (0.3 to 0.6)',
        1: 'High (> 0.6)',
        -999: 'Unknown greenness',
    }
    stats['naturalness_category'] = stats['naturalness_rating'].map(naturalness_map)

    stats = stats.sort_values(
        by=['naturalness_rating'],
        ascending=False,
    )
    summary = stats.groupby(['naturalness_rating', 'naturalness_category'], sort=True)['length'].sum().reset_index()

    bar_colors = generate_colors(color_by=summary.naturalness_rating, min_value=0.0, max_value=1.0, cmap_name='YlGn')

    bar_fig = go.Figure(
        data=go.Bar(
            x=summary['naturalness_category'],
            y=summary['length'],
            marker_color=[c.as_hex() for c in bar_colors],
            hovertemplate='%{x}: %{y} km <extra></extra>',
        )
    )
    bar_fig.update_layout(
        title=dict(
            subtitle=dict(text='Length (km)', font=dict(size=14)),
        ),
        xaxis_title='Length of paths with different greenness levels',
        yaxis_title=None,
        margin=dict(t=30, b=60, l=80, r=30),
    )
    return bar_fig
