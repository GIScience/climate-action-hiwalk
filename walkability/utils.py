import logging
import math
from enum import Enum
from typing import Dict, Union, Callable, Any, Tuple, List, Optional
from urllib.parse import parse_qsl

import geopandas as gpd
import matplotlib
import momepy
import networkx as nx
import pandas as pd
import shapely
import yaml
from matplotlib.colors import to_hex, Normalize
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color
from requests import PreparedRequest
from shapely import LineString, MultiLineString
from collections import OrderedDict

log = logging.getLogger(__name__)


class PathCategory(Enum):
    # GOOD
    # |
    # v
    # BAD
    DEDICATED_EXCLUSIVE = 'dedicated_exclusive'
    # Dedicated footway without other traffic close by
    DEDICATED_SEPARATED = 'dedicated_separated'
    # Separate footway with other traffic close by, (e.g. sidewalk or sign 241)
    SHARED_WITH_BIKES = 'shared_with_bikes'
    # sign 240 or 1022-10
    SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED = 'shared_with_motorized_traffic_low_speed'
    # living streets, parking lots, service ways
    SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED = 'shared_with_motorized_traffic_medium_speed'
    # streets with no sidewalk with max speed limit 30 km/h
    SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED = 'shared_with_motorized_traffic_high_speed'
    # streets with no sidewalk with max speed limit 50 km/h
    INACCESSIBLE = 'inaccessible'
    MISSING_DATA = 'missing_data'


class PavementQuality(Enum):
    EXCELLENT = 'excellent'
    POTENTIALLY_EXCELLENT = 'potentially_excellent'
    GOOD = 'good'
    POTENTIALLY_GOOD = 'potentially_good'
    MEDIOCRE = 'mediocre'
    POTENTIALLY_MEDIOCRE = 'potentially_mediocre'
    POOR = 'poor'
    POTENTIALLY_POOR = 'potentially_poor'
    UNKNOWN = 'unknown'


PavementQualityRating = {
    PavementQuality.EXCELLENT: 1.0,
    PavementQuality.POTENTIALLY_EXCELLENT: 0.95,
    PavementQuality.GOOD: 0.75,
    PavementQuality.POTENTIALLY_GOOD: 0.70,
    PavementQuality.MEDIOCRE: 0.5,
    PavementQuality.POTENTIALLY_MEDIOCRE: 0.45,
    PavementQuality.POOR: 0.15,
    PavementQuality.POTENTIALLY_POOR: 0.10,
    PavementQuality.UNKNOWN: -9999,
}


def construct_filters() -> Dict[PathCategory, str]:
    # Potential: potentially walkable features (to be restricted by AND queries)
    potential_highway_values = (
        'primary',
        'primary_link',
        'secondary',
        'secondary_link',
        'tertiary',
        'tertiary_link',
        'road',
        'cycleway',
        'unclassified',
        'residential',
        'track',
    )
    potential_highway_values_low_speed = (
        'living_street',
        'service',
    )
    potential_highway_values_all = potential_highway_values + potential_highway_values_low_speed

    def _potential(d: Dict) -> bool:
        return d.get('highway') in potential_highway_values_all or d.get('route') == 'ferry'

    # Exclusive: Only for pedestrians
    # TODO: Platforms exclusive or separated
    def _exclusive(d: Dict) -> bool:
        return (
            d.get('highway') in ['steps', 'corridor', 'pedestrian', 'platform']
            or d.get('railway') == 'platform'
            or (
                d.get('highway') == 'path'
                and (
                    d.get('foot') in ['yes', 'designated', 'official']
                    or d.get('footway') in ['access_aisle', 'alley', 'residential', 'link', 'path']
                    or d.get('bicycle') == 'no'
                )
                or (
                    d.get('highway') == 'footway'
                    and d.get('bicycle') != 'yes'
                    and d.get('footway') not in ['sidewalk', 'crossing', 'traffic_island', 'yes']
                )
                and d.get('motor_vehicle') != 'yes'
                and d.get('vehicle') != 'yes'
            )
        ) and d.get('bicycle') not in ['yes', 'designated']

    # TODO: check permissive for bikes
    def _shared_with_bikes(d: Dict) -> bool:
        return d.get('bicycle') in ['yes', 'designated'] and (
            d.get('segregated') != 'yes' or d.get('segregated') == 'no'
        )

    def exclusive(d: Dict) -> bool:
        return _exclusive(d) and not _shared_with_bikes(d)

    def _separated_foot(d: Dict) -> bool:
        return d.get('foot') in ['yes', 'permissive', 'designated', 'official'] and d.get('maxspeed') is None

    def _separated(d: Dict) -> bool:
        return (
            d.get('highway') == 'footway'
            or (
                d.get('highway') in ['path', 'cycleway']
                and (
                    _separated_foot(d)
                    or d.get('footway') in ['sidewalk', 'crossing', 'traffic_island', 'yes']
                    or d.get('segregated') == 'yes'
                )
            )
        ) or (
            (_potential(d))
            and (
                _separated_foot(d)
                or d.get('sidewalk') in ['both', 'left', 'right', 'yes', 'lane']
                or d.get('sidewalk:left') == 'yes'
                or d.get('sidewalk:right') == 'yes'
                or d.get('sidewalk:both') == 'yes'
            )
        )

    def separated(d: Dict) -> bool:
        return _separated(d) and not _shared_with_bikes(d)

    def shared_with_bikes(d: Dict) -> bool:
        return ((_exclusive(d) or _separated(d)) and _shared_with_bikes(d)) or (
            d.get('highway') in ['path', 'track', 'pedestrian']
            and d.get('motor_vehicle') != 'yes'
            and d.get('vehicle') != 'yes'
            and d.get('segregated') != 'yes'
        )

    def shared_with_low_speed(d: Dict) -> bool:
        return d.get('highway') in potential_highway_values_low_speed

    # TODO: ,5␣mph,10␣mph,15␣ mph,20␣mph
    # TODO: Should 5 be in low_speed?
    # TODO: exclude {_exclusive}
    def shared_with_medium_speed(d: Dict) -> bool:
        return d.get('maxspeed') in ['5', '10', '15', '20', '25', '30'] or d.get('zone:maxspeed') in ['DE:30', '30']

    # TODO: and sidewalk... redundant?
    def shared_with_high_speed(d: Dict) -> bool:
        return (
            _potential(d)
            and (
                d.get('sidewalk') == 'no'
                or d.get('sidewalk:both') == 'no'
                or (d.get('sidewalk:left') == 'no' and d.get('sidewalk:right') == 'no')
                or d.get('sidewalk') == 'none'
                or d.get('sidewalk:both') == 'none'
                or (d.get('sidewalk:left') == 'none' and d.get('sidewalk:right') == 'none')
            )
            and not (
                d.get('maxspeed') in ['60', '70', '80', '100']
                or d.get('maxspeed:backward') in ['60', '70', '80', '100']
                or d.get('maxspeed:forward') in ['60', '70', '80', '100']
            )
        )

    # For documentation:
    # ignored_primary = 'highway in (motorway,trunk,motorway_link,trunk_link,
    # primary_link,secondary_link,tertiary_link,bus_guideway,escape,raceway,busway,
    # brideleway,via_ferrata,cicleway'
    # ignored_secondary = 'sidewalk=no'
    def inaccessible(d: Dict) -> bool:
        return (
            d.get('highway')
            not in [
                *potential_highway_values_all,
                'pedestrian',
                'steps',
                'corridor',
                'platform',
                'path',
                'track',
                'cycleway',
                'footway',
            ]
            or d.get('footway') == 'no'
            or d.get('access') in ['no', 'private', 'permit', 'military', 'delivery', 'customers']
            or d.get('foot') in ['no', 'private', 'use_sidepath', 'discouraged', 'destination']
            or d.get('maxspeed') in ['60', '70', '80', '100']
            or d.get('maxspeed:backward') in ['60', '70', '80', '100']
            or d.get('maxspeed:forward') in ['60', '70', '80', '100']
        )

    # TODO: exclude {_exclusive}
    def missing_data(d: Dict) -> bool:
        return True

    return OrderedDict(
        [
            (PathCategory.INACCESSIBLE, inaccessible),
            (PathCategory.DEDICATED_EXCLUSIVE, exclusive),
            (PathCategory.DEDICATED_SEPARATED, separated),
            (PathCategory.SHARED_WITH_BIKES, shared_with_bikes),
            (PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED, shared_with_low_speed),
            (PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED, shared_with_medium_speed),
            (PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED, shared_with_high_speed),
            (PathCategory.MISSING_DATA, missing_data),
        ]
    )


def fetch_osm_data(aoi: shapely.MultiPolygon, osm_filter: str, ohsome: OhsomeClient) -> gpd.GeoDataFrame:
    elements = ohsome.elements.geometry.post(
        bpolys=aoi, clipGeometry=True, properties='tags', filter=osm_filter
    ).as_dataframe()
    if elements.empty:
        return gpd.GeoDataFrame(
            crs='epsg:4326', columns=['geometry', '@other_tags']
        )  # TODO: remove once https://github.com/GIScience/ohsome-py/pull/165 is resolved
    elements = elements.reset_index(drop=True)
    if elements.empty:
        return elements
    return elements[['geometry', '@other_tags']]


def apply_path_category_filters(row: gpd.GeoSeries, filters):
    for category, filter_func in filters:
        if filter_func(row['@other_tags']):
            return category
    return None


def boost_route_members(
    aoi: shapely.MultiPolygon,
    paths_line: gpd.GeoDataFrame,
    ohsome: OhsomeClient,
    boost_to: PathCategory = PathCategory.SHARED_WITH_BIKES,
) -> pd.Series:
    trails = fetch_osm_data(aoi, 'route in (foot,hiking,bicycle)', ohsome)
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
        if not pd.isna(row.index_trail) and row.category in (PathCategory.MISSING_DATA, PathCategory.SHARED_WITH_BIKES)
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
    norm = Normalize(0, 1)
    cmap = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap_name).get_cmap()
    cmap.set_under('#808080')
    return values.apply(lambda v: Color(to_hex(cmap(v))))


def get_single_color(rating: float, cmap_name: str = 'RdYlGn') -> Color:
    norm = Normalize(0, 1)
    cmap = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap_name).get_cmap()
    cmap.set_under('#808080')
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


def generate_detailed_pavement_quality_mapping_info() -> str:
    rankings = read_pavement_quality_rankings()
    text = ''
    for key, value_map in rankings.items():
        text += f' ### Key `{key}`: ### \n'
        text += ' |Value|Ranking| \n'
        text += ' |:----|:------| \n'
        for value, ranking in value_map.items():
            text += f' |{value} | {ranking.value.replace("_", " ").title()}| \n'
    return text


def read_pavement_quality_rankings() -> Dict[str, Dict[str, PavementQuality]]:
    with open('./resources/pavement_quality/value_ranking.yaml') as f:
        ranking_list = yaml.safe_load(f)

    result = {}
    for key, value_list in ranking_list.items():
        rankings = {item['value']: PavementQuality(item['ranking']) for item in value_list}
        result[key] = rankings
    return result


def get_sidewalk_key_combinations() -> Dict[str, List[str]]:
    sidewalk_tag_combinations = {}
    for tag in ['smoothness', 'surface']:
        combi = []
        for side in ['both', 'right', 'left']:
            combi.append(f'sidewalk:{side}:{tag}')
        combi.append(f'footway:{tag}')
        sidewalk_tag_combinations[tag] = combi

    return sidewalk_tag_combinations


def get_flat_key_combinations() -> List[str]:
    combinations = get_sidewalk_key_combinations()
    explode_tags = combinations['smoothness'] + combinations['surface'] + ['smoothness', 'surface', 'tracktype']
    return explode_tags


def get_first_match(ordered_keys: List[str], tags: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    match_key = None
    match_value = None
    for key in ordered_keys:
        match_value = tags.get(key)
        if match_value:
            match_key = key
            break

    return match_key, match_value


def euclidian_distance(point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
    return math.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)
