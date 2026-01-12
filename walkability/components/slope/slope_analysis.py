import logging
import math
from typing import Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import shapely
from climatoology.base.baseoperator import Artifact
from climatoology.base.computation import ComputationResources
from mobility_tools.ors_settings import ORSSettings
from pyproj import CRS

from walkability.components.slope.slope_artifacts import build_slope_artifact
from walkability.components.utils.geometry import calculate_length, get_utm_zone
from walkability.components.utils.misc import generate_colors

log = logging.getLogger(__name__)


def slope_analysis(
    line_paths: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    ors_settings: ORSSettings,
    resources: ComputationResources,
) -> Tuple[Artifact, gpd.GeoDataFrame]:
    log.info('Computing slope')
    slope = get_slope(paths=line_paths, aoi=aoi, ors_settings=ors_settings)
    slope_artifact = build_slope_artifact(slope=slope, resources=resources)
    log.info('Finished computing slope')

    return slope_artifact, slope


def get_slope(
    paths: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    ors_settings: ORSSettings,
    request_chunk_size: int = 2000,
) -> gpd.GeoDataFrame:
    """Retrieve the slope of paths.

    :param ors_settings:
    :param paths:
    :param aoi:
    :param request_chunk_size: Maximum number of elevation to be requested from the server. The server has a limit set that must be respected.
    :return:
    """
    utm = get_utm_zone(aoi)

    paths['start_ele'] = pd.Series(dtype='float64')
    paths['end_ele'] = pd.Series(dtype='float64')
    paths['start_point'] = shapely.get_point(shapely.get_geometry(paths.geometry, 0), 0)
    paths['end_point'] = shapely.get_point(shapely.get_geometry(paths.geometry, -1), -1)
    points: pd.Series = pd.concat([paths['start_point'], paths['end_point']])
    points = points.drop_duplicates().sort_values()

    num_chunks = math.ceil(len(points) / request_chunk_size)

    # PERF: do parallel calls (using async?)
    for chunk in np.array_split(points, num_chunks):
        polyline = list(zip(chunk.x, chunk.y))
        response = ors_settings.client.elevation_line(
            format_in='polyline', format_out='polyline', dataset='srtm', geometry=polyline
        )

        coords = response['geometry']
        for coord in coords:
            point = shapely.Point(coord[0:2])
            ele = coord[2]

            start_point_match = paths['start_point'].geom_equals_exact(
                point, tolerance=ors_settings.ors_coordinate_precision
            )
            end_point_match = paths['end_point'].geom_equals_exact(
                point, tolerance=ors_settings.ors_coordinate_precision
            )

            paths.loc[start_point_match, 'start_ele'] = ele
            paths.loc[end_point_match, 'end_ele'] = ele

    paths['slope'] = (paths.end_ele - paths.start_ele) / (paths.geometry.to_crs(utm).length / 100.0)
    paths.slope = paths.slope.round(2)

    return paths[['@osmId', 'slope', 'geometry']]


def summarise_slope(
    paths: gpd.GeoDataFrame,
    projected_crs: CRS,
    length_resolution_m: int = 1000,
) -> go.Figure:
    log.info('Summarising slope stats')
    stats = calculate_length(length_resolution_m, paths, projected_crs)

    # Categorize slope values
    slope_categories = [
        stats['slope'] == 0,
        (stats['slope'] > 0) & (stats['slope'] <= 4),
        (stats['slope'] > 4) & (stats['slope'] <= 8),
        (stats['slope'] > 8) & (stats['slope'] <= 12),
        stats['slope'] > 12,
    ]
    slope_ratings = [0, 0.25, 0.5, 0.75, 1]
    stats['slope_rating'] = np.select(slope_categories, slope_ratings)

    # Add slope categories for labels
    slope_map = {
        0: 'Flat (0%)',
        0.25: 'Gentle slope (0-4%)',
        0.5: 'Moderate slope (4-8%)',
        0.75: 'Considerable slope (8-12%)',
        1: 'Steep (>12%)',
    }
    stats['slope_category'] = stats['slope_rating'].map(slope_map)

    stats = stats.sort_values(by=['slope_rating'])

    summary = stats.groupby(['slope_rating', 'slope_category'], sort=True)['length'].sum().reset_index()

    bar_colors = generate_colors(color_by=summary.slope_rating, min_value=0.0, max_value=1.0, cmap_name='coolwarm')

    bar_fig = go.Figure(
        data=go.Bar(
            x=summary['slope_category'],
            y=summary['length'],
            marker_color=[c.as_hex() for c in bar_colors],
            hovertemplate='%{x}: %{y} km <extra></extra>',
        )
    )
    bar_fig.update_layout(
        title=dict(
            subtitle=dict(text='Length (km)', font=dict(size=14)),
        ),
        xaxis_title=f'Proportionate length of the {round(sum(summary["length"]), 2)} km of paths in each slope category',
        yaxis_title=None,
        margin=dict(t=30, b=60, l=80, r=30),
    )
    return bar_fig
