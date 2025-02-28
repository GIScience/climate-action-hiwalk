import logging
from enum import Enum
from typing import Dict, Tuple, List, Optional

import geopandas as gpd
import matplotlib
import pandas as pd
import shapely
from matplotlib.colors import to_hex, Normalize
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color

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


def fetch_osm_data(aoi: shapely.MultiPolygon, osm_filter: str, ohsome: OhsomeClient) -> gpd.GeoDataFrame:
    elements = ohsome.elements.geometry.post(
        bpolys=aoi, clipGeometry=True, properties='tags', filter=osm_filter
    ).as_dataframe()
    elements = elements.reset_index(drop=True)
    return elements[['geometry', '@other_tags']]


def get_qualitative_color(category, cmap_name: str, class_name) -> Color:
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


def get_first_match(ordered_keys: List[str], tags: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    match_key = None
    match_value = None
    for key in ordered_keys:
        match_value = tags.get(key)
        if match_value:
            match_key = key
            break

    return match_key, match_value


def ohsome_filter(geometry_type: str) -> str:
    if geometry_type == 'relation':
        # currently unused, here as a blueprint if we want to query for relations
        return str(f'type:{geometry_type} and route=ferry')

    return str(
        f'geometry:{geometry_type} and '
        '(highway=* or route=ferry or railway=platform or '
        '(waterway=lock_gate and foot in (yes, designated, official, permissive))) and not '
        '(footway=separate or sidewalk=separate or sidewalk:both=separate or '
        '(sidewalk:right=separate and sidewalk:left=separate) or '
        '(sidewalk:right=separate and sidewalk:left=no) or (sidewalk:right=no and sidewalk:left=separate))'
    )
