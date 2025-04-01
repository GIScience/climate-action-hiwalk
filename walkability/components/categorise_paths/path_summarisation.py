import logging
from typing import Dict

import geopandas as gpd
import plotly.graph_objects as go
import shapely
from ohsome import OhsomeClient
from plotly.graph_objects import Figure
from pyproj import CRS

from walkability.components.utils.misc import PATH_RATING_MAP, PathCategory, generate_colors

log = logging.getLogger(__name__)


def summarise_by_area(
    paths: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    admin_level: int,
    projected_crs: CRS,
    ohsome_client: OhsomeClient,
    length_resolution_m: int = 1000,
) -> Dict[str, Figure]:
    log.info('Summarising walkability stats by area')

    stats = paths.copy()
    stats = stats.loc[stats.geometry.geom_type.isin(('MultiLineString', 'LineString'))]

    minimum_keys = ['admin_level', 'name']
    boundaries = ohsome_client.elements.geometry.post(
        properties='tags',
        bpolys=aoi,
        filter=f'geometry:polygon and boundary=administrative and admin_level={admin_level}',
        clipGeometry=True,
    ).as_dataframe(explode_tags=minimum_keys)
    boundaries = boundaries.loc[boundaries.geometry.geom_type.isin(('MultiPolygon', 'Polygon'))]
    boundaries = boundaries[boundaries.is_valid]
    boundaries = boundaries.reset_index(drop=True)
    log.debug(f'Summarising paths into {boundaries.shape[0]} boundaries')

    stats = stats.overlay(boundaries, how='identity')
    stats = stats.to_crs(projected_crs)
    stats['length'] = stats.length / length_resolution_m

    stats['category'] = stats.category.apply(lambda cat: cat.value)
    stats = stats.groupby(['name', 'category']).aggregate({'length': 'sum'})

    stats['length'] = round(stats['length'], 2)
    stats = stats.reset_index()
    stats_group = stats.groupby('name')

    data = {}
    for name, group in stats_group:
        group['rating'] = group.category.apply(lambda category: PATH_RATING_MAP[PathCategory(category)])
        group = group.sort_values(
            by=['rating'],
            ascending=False,
        )
        colors = generate_colors(color_by=group.rating, min=0.0, max=1.0, cmap_name='coolwarm_r')
        data[name] = Figure(
            data=go.Pie(
                labels=group['category'].tolist(),
                values=group['length'].tolist(),
                marker_colors=[c.as_hex() for c in colors],
                hovertemplate='%{label}: %{value}km (%{percent}) <extra></extra>',
            )
        )

    return data
