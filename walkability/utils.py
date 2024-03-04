from enum import Enum
from typing import Dict, Union, Callable, Any, Tuple
from urllib.parse import parse_qsl

import geopandas as gpd
import matplotlib
import pandas as pd
import shapely
from matplotlib.colors import to_hex
from ohsome import OhsomeClient
from pydantic import BaseModel
from pydantic_extra_types.color import Color
from requests import PreparedRequest
from shapely import LineString


class FilterGroups(BaseModel):
    exclusive: str
    explicit: str
    probable: str
    inaccessible: str


class Rating(Enum):
    EXCLUSIVE = 1.0
    EXPLICIT = 0.75
    PROBABLE = 0.5
    INACCESSIBLE = 0.0


def construct_filter() -> Dict[Rating, str]:
    potential = 'highway in (primary,secondary,tertiary,unclassified,residential,service,track,road)'
    # For documentation:
    # ignored_primary = 'highway in (motorway,trunk,motorway_link,trunk_link,primary_link,secondary_link,tertiary_link,bus_guideway,escape,raceway,busway,brideleway,via_ferrata,cicleway'
    # ignored_secondary = 'sidewalk=no'
    excluded = (
        'footway in (separate,no) or '
        'sidewalk=separate or '
        'sidewalk:left=separate or '
        'sidewalk:right=separate or '
        'access in (no,private,permit,military,delivery,customers) or '
        'foot in (no,private,use_sidepath,discouraged)'
    )

    exclusive_secondary = """
    (
        foot in (designated,official) or
        foot!=*
    ) or
    (
        footway in (access_aisle,alley,residential,link,path) or
        footway!=*
    )
    """

    exclusive = f"""
    highway in (pedestrian,steps,corridor) or
    (
        highway=footway and
        (
            {exclusive_secondary}
        )
    ) or
    (
        highway=path and
        (
            {exclusive_secondary}
        )
    )
    """

    explict_foot = 'foot in (yes,permissive)'
    explicit_secondary = f'{explict_foot} or footway in (sidewalk,crossing,traffic_island)'
    explicit = f"""
    (
        highway=living_street or
        (
            highway=footway and
            (
                {explicit_secondary}
            )
        ) or
        (
            highway=path and
            (
                {explicit_secondary}
            )
        ) or
        (
            {potential} and
            (
                sidewalk in (both,left,right) or
                {explict_foot}
            )
        )
    ) and not
    (
        {excluded}
    )
    """

    probable = f'highway in (track,service) and not ({excluded})'

    inaccessible = f'{potential} and not ({explicit}) and not ({probable}) and not ({excluded})'

    return {
        Rating.EXCLUSIVE: exclusive,
        Rating.EXPLICIT: explicit,
        Rating.PROBABLE: probable,
        Rating.INACCESSIBLE: inaccessible,
    }


def fetch_osm_data(
    aoi: shapely.MultiPolygon, osm_filter: str, rating: Rating, ohsome: OhsomeClient
) -> gpd.GeoDataFrame:
    elements = ohsome.elements.geometry.post(
        bpolys=aoi, clipGeometry=True, properties=None, filter=osm_filter
    ).as_dataframe()
    elements = elements.reset_index(drop=True)
    elements['category'] = rating
    return elements[['category', 'geometry']]


def boost_route_members(aoi: shapely.MultiPolygon, paths_line: gpd.GeoDataFrame, ohsome: OhsomeClient) -> pd.Series:
    trails = fetch_osm_data(aoi, 'route in (foot,hiking)', Rating.EXPLICIT, ohsome)

    trails.geometry = trails.geometry.apply(lambda geom: fix_geometry_collection(geom))

    paths_line = paths_line.copy()
    paths_line = gpd.sjoin(paths_line, trails, lsuffix='path', rsuffix='trail', how='left', predicate='within')
    paths_line = paths_line[~paths_line.index.duplicated(keep='first')]
    paths_line.loc[paths_line.category_trail.isnull(), 'category_trail'] = Rating.INACCESSIBLE

    return paths_line.apply(
        lambda row: row.category_path if row.category_path.value >= row.category_trail.value else row.category_trail,
        axis=1,
    )


def fix_geometry_collection(geom: shapely.Geometry) -> Union[shapely.LineString, shapely.MultiLineString]:
    # Hack due to https://github.com/GIScience/oshdb/issues/463
    if geom.geom_type == 'GeometryCollection':
        inner_geoms = []
        for inner_geom in geom.geoms:
            if inner_geom.geom_type in ('LineString', 'MultiLineString'):
                inner_geoms.append(inner_geom)
        geom = shapely.union_all(inner_geoms)

    if geom.geom_type in ('LineString', 'MultiLineString'):
        return geom
    else:
        return LineString()


def get_color(categories: pd.Series) -> pd.Series:
    cmap = matplotlib.colormaps.get_cmap('RdYlGn')
    return categories.apply(lambda c: Color(to_hex(cmap(c.value))))


def filter_start_matcher(filter_start: str) -> Callable[..., Any]:
    def match(request: PreparedRequest) -> Tuple[bool, str]:
        request_body = request.body
        qsl_body = dict(parse_qsl(request_body, keep_blank_values=False)) if request_body else {}

        if request_body is None:
            return False, 'The given request has no body'
        elif qsl_body.get('filter') is None:
            return False, 'Filter parameter not set'
        else:
            valid = qsl_body.get('filter', '').startswith(filter_start)
            return (True, '') if valid else (False, f'The filter parameter does not start with {filter_start}')

    return match
