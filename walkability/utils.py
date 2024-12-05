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
from pyproj import CRS, Transformer
import shapely
import yaml
from geopandas import GeoDataFrame
from matplotlib.colors import to_hex, Normalize
from networkx.classes import set_node_attributes
from ohsome import OhsomeClient
from osmnx import simplify_graph
from pydantic_extra_types.color import Color
from requests import PreparedRequest
from shapely import LineString, MultiLineString
from shapely.ops import transform


log = logging.getLogger(__name__)


class PathCategory(Enum):
    # GOOD
    # |
    # v
    # BAD
    DESIGNATED = 'designated'
    # Designated footway with or without other traffic close by, (e.g. dedicated footway, sidewalk or sign 241)
    DESIGNATED_SHARED_WITH_BIKES = 'designated_shared_with_bikes'
    # sign 240 or 1022-10
    SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED = 'shared_with_motorized_traffic_low_speed'
    # living streets, parking lots, service ways
    SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED = 'shared_with_motorized_traffic_medium_speed'
    # streets with no sidewalk with max speed limit 30 km/h
    SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED = 'shared_with_motorized_traffic_high_speed'
    # streets with no sidewalk with max speed limit 50 km/h
    NOT_WALKABLE = 'not_walkable'
    # category replacing missing data
    UNKNOWN = 'unknown'


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


class PathCategoryFilters:
    def __init__(self):
        # Potential: potentially walkable features (to be restricted by AND queries)
        self._potential_highway_values = (
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
        self._potential_highway_values_low_speed = (
            'living_street',
            'service',
        )
        self._potential_highway_values_all = self._potential_highway_values + self._potential_highway_values_low_speed

    def _potential(self, d: Dict) -> bool:
        return d.get('highway') in self._potential_highway_values_all or d.get('route') == 'ferry'

    # Exclusive: Only for pedestrians
    def _exclusive(self, d: Dict) -> bool:
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

    def _shared_with_bikes(self, d: Dict) -> bool:
        return d.get('bicycle') in ['yes', 'designated'] and (
            d.get('segregated') != 'yes' or d.get('segregated') == 'no'
        )

    def _separated_foot(self, d: Dict) -> bool:
        return d.get('foot') in ['yes', 'permissive', 'designated', 'official'] and d.get('maxspeed') is None

    def _separated(self, d: Dict) -> bool:
        return (
            d.get('highway') == 'footway'
            or (
                d.get('highway') in ['path', 'cycleway']
                and (
                    self._separated_foot(d)
                    or d.get('footway') in ['sidewalk', 'crossing', 'traffic_island', 'yes']
                    or d.get('segregated') == 'yes'
                )
            )
        ) or (
            (self._potential(d))
            and (
                self._separated_foot(d)
                or d.get('sidewalk') in ['both', 'left', 'right', 'yes', 'lane']
                or d.get('sidewalk:left') == 'yes'
                or d.get('sidewalk:right') == 'yes'
                or d.get('sidewalk:both') == 'yes'
            )
        )

    def designated(self, d: Dict) -> bool:
        return (self._exclusive(d) or self._separated(d)) and not self._shared_with_bikes(d)

    def designated_shared_with_bikes(self, d: Dict) -> bool:
        return ((self._exclusive(d) or self._separated(d)) and self._shared_with_bikes(d)) or (
            d.get('highway') in ['path', 'track', 'pedestrian']
            and d.get('motor_vehicle') != 'yes'
            and d.get('vehicle') != 'yes'
            and d.get('segregated') != 'yes'
        )

    def shared_with_low_speed(self, d: Dict) -> bool:
        return d.get('highway') in self._potential_highway_values_low_speed

    def shared_with_medium_speed(self, d: Dict) -> bool:
        return d.get('maxspeed') in ['5', '10', '15', '20', '25', '30'] or d.get('zone:maxspeed') in ['DE:30', '30']

    def shared_with_high_speed(self, d: Dict) -> bool:
        return (
            self._potential(d)
            and (
                d.get('sidewalk') == 'no'
                or d.get('sidewalk:both') == 'no'
                or (d.get('sidewalk:left') == 'no' and d.get('sidewalk:right') == 'no')
                or d.get('sidewalk') == 'none'
                or d.get('sidewalk:both') == 'none'
                or (d.get('sidewalk:left') == 'none' and d.get('sidewalk:right') == 'none')
                or d.get('sidewalk') != '*'
                or d.get('sidewalk:both') != '*'
                or (d.get('sidewalk:left') != '*' and d.get('sidewalk:right') != '*')
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
    # bridleway,via_ferrata,cycleway'
    # ignored_secondary = 'sidewalk=no'
    def inaccessible(self, d: Dict) -> bool:
        return (
            (
                d.get('highway')
                not in [
                    *self._potential_highway_values_all,
                    'pedestrian',
                    'steps',
                    'corridor',
                    'platform',
                    'path',
                    'track',
                    'cycleway',
                    'footway',
                ]
                and d.get('railway') != 'platform'
            )
            or d.get('footway') == 'no'
            or d.get('access') in ['no', 'private', 'permit', 'military', 'delivery', 'customers']
            or d.get('foot') in ['no', 'private', 'use_sidepath', 'discouraged', 'destination']
            or d.get('maxspeed') in ['60', '70', '80', '100']
            or d.get('maxspeed:backward') in ['60', '70', '80', '100']
            or d.get('maxspeed:forward') in ['60', '70', '80', '100']
            or (d.get('highway') == 'service' and d.get('bus') in ['designated', 'yes'])
            or d.get('ford') == 'yes'
        )


def fetch_osm_data(aoi: shapely.MultiPolygon, osm_filter: str, ohsome: OhsomeClient) -> gpd.GeoDataFrame:
    elements = ohsome.elements.geometry.post(
        bpolys=aoi, clipGeometry=True, properties='tags', filter=osm_filter
    ).as_dataframe()
    elements = elements.reset_index(drop=True)
    return elements[['geometry', '@other_tags']]


def apply_path_category_filters(row: pd.Series) -> PathCategory:
    filters = PathCategoryFilters()
    match row['@other_tags']:
        case x if filters.inaccessible(x):
            return PathCategory.NOT_WALKABLE
        case x if filters.designated(x):
            return PathCategory.DESIGNATED
        case x if filters.designated_shared_with_bikes(x):
            return PathCategory.DESIGNATED_SHARED_WITH_BIKES
        case x if filters.shared_with_low_speed(x):
            return PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED
        case x if filters.shared_with_medium_speed(x):
            return PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED
        case x if filters.shared_with_high_speed(x):
            return PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED
        case _:
            return PathCategory.UNKNOWN


def boost_route_members(
    aoi: shapely.MultiPolygon,
    paths_line: gpd.GeoDataFrame,
    ohsome: OhsomeClient,
    boost_to: PathCategory = PathCategory.DESIGNATED,
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
        if not pd.isna(row.index_trail) and row.category in (PathCategory.UNKNOWN, PathCategory.DESIGNATED)
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


def get_qualitative_color(category, cmap_name: str, class_name) -> pd.Series:
    norm = Normalize(0, 1)
    cmap = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap_name).get_cmap()
    cmap.set_under('#808080')

    category_norm = {name: idx / (len(class_name) - 1) for idx, name in enumerate(class_name)}

    if category == class_name.UNKNOWN:
        return Color(to_hex(cmap(-9999)))
    else:
        return Color(to_hex(cmap(category_norm[category])))


def get_color(values: pd.Series, cmap_name: str = 'coolwarm_r') -> pd.Series:
    norm = Normalize(0, 1)
    cmap = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap_name).get_cmap()
    cmap.set_under('#808080')
    return values.apply(lambda v: Color(to_hex(cmap(v))))


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
    df = df.drop(errors='ignore', labels='@other_tags', axis=1)
    df.geometry = df.geometry.apply(lambda geom: MultiLineString([geom]) if isinstance(geom, LineString) else geom)
    df_ = (
        df.assign(
            geometry=df.geometry.apply(
                lambda geom: list(
                    list(map(LineString, zip(geom_part.coords[:-1], geom_part.coords[1:]))) for geom_part in geom.geoms
                )
            )
        )
        .explode('geometry')
        .explode('geometry')
    )
    # PERF: `unary_union` might lead to performance issues ...
    # ... since it creates a single geometry
    # `unary_union`: self-intersection geometries
    # NOTE: All properties of the geodataframe are lost
    # geom: MultiLineString = df.unary_union
    # df_ = gpd.GeoDataFrame(data={'geometry': [geom], 'foo': ["bar"]}, crs=df.crs).explode(index_parts=True)
    df_ = GeoDataFrame(df_).set_crs(df.crs)

    log.debug('Convert geodataframe to network graph')
    G = momepy.gdf_to_nx(df_, multigraph=True, directed=False, length='length')
    node_data = dict()
    for node in G.nodes():
        node_data[node] = {'x': node[0], 'y': node[1]}
    set_node_attributes(G, node_data)
    G_ = simplify_graph(G.to_directed(), remove_rings=False, edge_attrs_differ=['rating'])
    return G_.to_undirected()


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


def ohsome_filter(geometry_type: str) -> str:
    if geometry_type == 'relation':
        # currently unused, here as a blueprint if we want to query for relations
        return str(f'type:{geometry_type} and ' 'route=ferry')

    return str(
        f'geometry:{geometry_type} and '
        '(highway=* or route=ferry or railway=platform or '
        '(waterway=lock_gate and foot in (yes, designated, official, permissive))) and not '
        '(footway=separate or sidewalk=separate or sidewalk:both=separate or '
        '(sidewalk:right=separate and sidewalk:left=separate) or '
        '(sidewalk:right=separate and sidewalk:left=no) or (sidewalk:right=no and sidewalk:left=separate))'
    )


pathratings_legend_fix = {
    'shared_with_motorized_traffic_low_speed': 'shared_with_motorized_traffic_low_speed_(=walking_speed)',
    'shared_with_motorized_traffic_medium_speed': 'shared_with_motorized_traffic_medium_speed_(<=30_km/h)',
    'shared_with_motorized_traffic_high_speed': 'shared_with_motorized_traffic_high_speed_(<=50_km/h)',
}


def get_utm_zone(aoi: shapely.MultiPolygon) -> CRS:
    return gpd.GeoSeries(data=aoi, crs='EPSG:4326').estimate_utm_crs()


def get_buffered_aoi(aoi: shapely.MultiPolygon, distance: float) -> shapely.MultiPolygon:
    wgs84 = CRS('EPSG:4326')
    utm = get_utm_zone(aoi)

    geographic_projection_function = Transformer.from_crs(wgs84, utm, always_xy=True).transform
    wgs84_projection_function = Transformer.from_crs(utm, wgs84, always_xy=True).transform
    projected_aoi = transform(geographic_projection_function, aoi)
    buffered_aoi = projected_aoi.buffer(distance)
    return transform(wgs84_projection_function, buffered_aoi)
