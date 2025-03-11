import logging
from enum import Enum
from typing import Dict, Tuple, List, Optional

import geopandas as gpd
import matplotlib as mpl
from numpy import number
import pandas as pd
import shapely
from matplotlib.colors import to_hex
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
    elements = elements.reset_index(drop=False)
    return elements[['@osmId', 'geometry', '@other_tags']]


def get_qualitative_color(category, cmap_name: str, class_name) -> Color:
    norm = mpl.colors.Normalize(0, 1)
    cmap = mpl.cm.ScalarMappable(norm=norm, cmap=cmap_name).get_cmap()
    cmap.set_under('#808080')

    category_norm = {name: idx / (len(class_name) - 1) for idx, name in enumerate(class_name)}

    if category == class_name.UNKNOWN:
        return Color(to_hex(cmap(-9999)))
    else:
        return Color(to_hex(cmap(category_norm[category])))


def generate_colors(
    color_by: pd.Series, cmap_name: str = 'coolwarm_r', min: number | None = None, max: number | None = None
) -> list[Color]:
    """
    Function to generate a list of colors based on a linear normalization for each element in `color_by`.
    ## Params
    :param:`color_by`: `pandas.Series` with numerical values to map colors to.
    :param:`cmap_name`: optional name of matplotlib colormap approved in climatoology. Default `'coolwarm_r'`
    :param:`min`: optional minimal value of the normalization, numerical or `None`. If `None` minimum value of `color_by` is used.
    :param:`max`: optional maxmial value of the normalization, numerical or `None`. If `None` maximum value of `color_by` is used.
    ## Returns
    :return:`mapped_colors`: list of colors matching values of `color_by`
    """
    if min is None:
        min = color_by.min()
    if max is None:
        max = color_by.max()

    norm = mpl.colors.Normalize(vmin=min, vmax=max)
    cmap = mpl.colormaps[cmap_name]
    cmap.set_under('#808080')

    mapped_colors = [Color(mpl.colors.to_hex(cmap(norm(val)))) for val in color_by]
    return mapped_colors


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
