import logging
from typing import Dict
import geopandas as gpd
from pyproj import CRS
from ohsome import OhsomeClient
import shapely

from walkability.components.utils.misc import PathCategory, get_qualitative_color
from climatoology.base.artifact import Chart2dData, ChartType

log = logging.getLogger(__name__)


def summarise_by_area(
    paths: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    admin_level: int,
    projected_crs: CRS,
    ohsome_client: OhsomeClient,
    length_resolution_m: int = 1000,
) -> Dict[str, Chart2dData]:
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

    stats = stats.groupby(['name', 'category', 'rating']).aggregate({'length': 'sum'})
    stats['length'] = round(stats['length'], 2)
    stats = stats.reset_index()
    stats_group = stats.groupby('name')

    data = {}
    for name, group in stats_group:
        group = group.sort_values(by=['category'], ascending=False)
        colors = [
            get_qualitative_color(category=PathCategory(category), cmap_name='RdYlBu_r', class_name=PathCategory)
            for category in group.category
        ]
        data[name] = Chart2dData(
            x=group.category.tolist(),
            y=group.length.tolist(),
            color=colors,
            chart_type=ChartType.PIE,
        )
    return data
