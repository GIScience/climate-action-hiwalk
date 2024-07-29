import logging
from enum import Enum
from typing import Dict, Union, Callable, Any, Tuple
from urllib.parse import parse_qsl

import geopandas as gpd
import matplotlib
import momepy
import networkx as nx
import pandas as pd
import shapely
from matplotlib.colors import to_hex
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color
from requests import PreparedRequest
from shapely import LineString, MultiLineString

log = logging.getLogger(__name__)


class PathCategory(Enum):
    EXCLUSIVE = 'exclusive'
    EXPLICIT = 'explicit'
    PROBABLE_YES = 'probable_yes'
    POTENTIAL_BUT_UNKNOWN = 'potential_but_unknown'
    INACCESSIBLE = 'inaccessible'


def construct_filters() -> Dict[PathCategory, str]:
    # TODO: Remove whitespace before sending to ohsome API
    # Potential: potentially walkable features (to be restricted by AND queries)
    potential_highway_values = (
        'primary',
        'primary_link',
        'secondary',
        'secondary_link',
        'tertiary',
        'tertiary_link',
        'unclassified',
        'residential',
        'service',
        'track',
        'road',
        'cycleway',
        'platform',
    )
    potential = f"""
    highway in ({','.join(potential_highway_values)}) or
    route=ferry
    """
    # For documentation:
    # ignored_primary = 'highway in (motorway,trunk,motorway_link,trunk_link,
    # primary_link,secondary_link,tertiary_link,bus_guideway,escape,raceway,busway,
    # brideleway,via_ferrata,cicleway'
    # ignored_secondary = 'sidewalk=no'
    ignore = """
    footway in (separate,no) or
    sidewalk=separate or
    sidewalk:both=separate or
    ((sidewalk:right=separate) and (sidewalk:left=separate)) or
    access in (no,private,permit,military,delivery,customers) or
    foot in (no,private,use_sidepath,discouraged,destination)
    """

    # Exclusive: Only for pedestrians
    # secondary tags
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

    _exclusive = f"""
    highway in (pedestrian,steps,corridor) or
    (
        highway=footway and
        ({exclusive_secondary})
    ) or
    (
        highway=path and
        ({exclusive_secondary})
    )
    """

    exclusive = f"""
    ({_exclusive}) and not
    ({ignore})
    """

    # Explicit: For pedestrians but not only (E.g. shared with bicycle)
    explicit_foot = 'foot in (yes,permissive,designated,official)'
    # secondary tags
    explicit_secondary = f"""
    {explicit_foot} or
    footway in (sidewalk,crossing,traffic_island,yes)
    """

    _explicit = f"""
    railway=platform or
    highway=living_street or
    (
        highway=footway and
        ({explicit_secondary})
    ) or
    (
        highway=path and
        ({explicit_secondary})
    ) or
    (
        ({potential}) and
        (
            sidewalk in (both,left,right,yes,lane) or
            sidewalk:left=yes or
            sidewalk:right=yes or
            sidewalk:both=yes or
            ({explicit_foot})
        )
    )
    """

    explicit = f"""
    ({_explicit}) and not
    (
        ({ignore}) or
        ({_exclusive})
    )
    """

    _inaccessible = f"""
    ({potential}) and
    (
        sidewalk=no or
        sidewalk:both=no or
        (sidewalk:left=no and sidewalk:right=no) or
        sidewalk=none or
        sidewalk:both=none or
        (sidewalk:left=none and sidewalk:right=none)
    )
    """
    inaccessible = f"""
    ({_inaccessible}) and not
    (
        ({ignore}) or
        ({_exclusive}) or
        ({_explicit})
    )
    """

    # Probable_yes: (E.g. forest tracks)
    _probable_yes = """
    highway in (track,service,path) or
    man_made=pier
    """
    probable_yes = f"""
    ({_probable_yes}) and not
    (
        ({ignore}) or
        ({_exclusive}) or
        ({_explicit}) or
        ({_inaccessible})
    )
    """

    potential_but_unknown = f"""
    ({potential}) and not
    (
        ({ignore}) or
        ({_exclusive}) or
        ({_explicit}) or
        ({_inaccessible}) or
        ({_probable_yes})
    )
    """
    # Remove empty lines for better readability
    exclusive = ''.join([s for s in exclusive.strip().splitlines(keepends=True) if s.strip()])
    explicit = ''.join([s for s in explicit.strip().splitlines(keepends=True) if s.strip()])
    probable_yes = ''.join([s for s in probable_yes.strip().splitlines(keepends=True) if s.strip()])
    potential_but_unknown = ''.join([s for s in potential_but_unknown.strip().splitlines(keepends=True) if s.strip()])
    inaccessible = ''.join([s for s in inaccessible.strip().splitlines(keepends=True) if s.strip()])
    return {
        PathCategory.EXCLUSIVE: exclusive,
        PathCategory.EXPLICIT: explicit,
        PathCategory.PROBABLE_YES: probable_yes,
        PathCategory.POTENTIAL_BUT_UNKNOWN: potential_but_unknown,
        PathCategory.INACCESSIBLE: inaccessible,
    }


def fetch_osm_data(aoi: shapely.MultiPolygon, osm_filter: str, ohsome: OhsomeClient) -> gpd.GeoDataFrame:
    elements = ohsome.elements.geometry.post(
        bpolys=aoi, clipGeometry=True, properties=None, filter=osm_filter
    ).as_dataframe()
    elements = elements.reset_index(drop=True)
    return elements[['geometry']]


def boost_route_members(
    aoi: shapely.MultiPolygon,
    paths_line: gpd.GeoDataFrame,
    ohsome: OhsomeClient,
    boost_to: PathCategory = PathCategory.EXPLICIT,
) -> pd.Series:
    trails = fetch_osm_data(aoi, 'route in (foot,hiking)', ohsome)
    trails.geometry = trails.geometry.apply(lambda geom: fix_geometry_collection(geom))

    paths_line = paths_line.copy()
    paths_line = gpd.sjoin(
        paths_line,
        trails,
        lsuffix='path',
        rsuffix='trail',
        how='left',
        predicate='within',
    )
    paths_line = paths_line[~paths_line.index.duplicated(keep='first')]

    return paths_line.apply(
        lambda row: boost_to
        if not pd.isna(row.index_trail)
        and row.category in (PathCategory.POTENTIAL_BUT_UNKNOWN, PathCategory.PROBABLE_YES)
        else row.category,
        axis=1,
    )


def fix_geometry_collection(
    geom: shapely.Geometry,
) -> Union[shapely.LineString, shapely.MultiLineString]:
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


def get_color(values: pd.Series, cmap_name: str = 'RdYlGn') -> pd.Series:
    cmap = matplotlib.colormaps.get_cmap(cmap_name)
    return values.apply(lambda v: Color(to_hex(cmap(v))))


def get_single_color(rating: float, cmap_name: str = 'RdYlGn') -> Color:
    cmap = matplotlib.colormaps.get_cmap(cmap_name)
    return Color(to_hex(cmap(rating)))


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


def geodataframe_to_graph(df: gpd.GeoDataFrame) -> nx.Graph:
    log.debug('Splitting paths at intersections')
    # PERF: `unary_union` might lead to performance issues ...
    # ... since it creates a single geometry
    # `unary_union`: self-intersection geometries
    # NOTE: All properties of the geodataframe are lost
    geom: MultiLineString = df.unary_union
    df_ = gpd.GeoDataFrame(data={'geometry': [geom]}, crs=df.crs).explode(index_parts=True)

    log.debug('Convert geodataframe to network graph')
    return momepy.gdf_to_nx(df_, multigraph=True, directed=False, length='length')
