import logging
from enum import Enum
from typing import Dict, Tuple, List, Optional

import geopandas as gpd
import matplotlib as mpl
import pandas as pd
import shapely
from numpy import number
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color

log = logging.getLogger(__name__)


class PathCategory(Enum):
    DESIGNATED = 'Designated'
    DESIGNATED_SHARED_WITH_BIKES = 'Shared with bikes'
    SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED = 'Shared with slow cars'
    SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED = 'Shared with medium speed cars'
    SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED = 'Shared with fast cars'
    SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED = 'Shared with cars of unknown speed'
    NOT_WALKABLE = 'Not walkable'
    UNKNOWN = 'Unknown'


PATH_RATING_MAP = {
    PathCategory.DESIGNATED: 1.0,
    PathCategory.DESIGNATED_SHARED_WITH_BIKES: 0.8,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED: 0.6,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED: 0.4,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED: 0.2,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED: 0.1,
    PathCategory.NOT_WALKABLE: 0.0,
    PathCategory.UNKNOWN: None,
}


class PavementQuality(Enum):
    GOOD = 'good'
    POTENTIALLY_GOOD = 'potentially_good'
    MEDIOCRE = 'mediocre'
    POTENTIALLY_MEDIOCRE = 'potentially_mediocre'
    POOR = 'poor'
    UNKNOWN = 'unknown'


PAVEMENT_QUALITY_RATING_MAP = {
    PavementQuality.GOOD: 1.0,
    PavementQuality.POTENTIALLY_GOOD: 0.8,
    PavementQuality.MEDIOCRE: 0.5,
    PavementQuality.POTENTIALLY_MEDIOCRE: 0.3,
    PavementQuality.POOR: 0.0,
    PavementQuality.UNKNOWN: None,
}


class SmoothnessCategory(Enum):
    GOOD = 'good'
    MEDIOCRE = 'mediocre'
    POOR = 'poor'
    VERY_POOR = 'very_poor'
    UNKNOWN = 'unknown'


SMOOTHNESS_CATEGORY_RATING_MAP = {
    SmoothnessCategory.GOOD: 1.0,
    SmoothnessCategory.MEDIOCRE: 0.5,
    SmoothnessCategory.POOR: 0.2,
    SmoothnessCategory.VERY_POOR: 0.0,
    SmoothnessCategory.UNKNOWN: None,
}


class SurfaceType(Enum):
    CONTINUOUS_PAVEMENT = 'continuous_pavement'
    MODULAR_PAVEMENT = 'modular_pavement'
    COBBLESTONE = 'cobblestone'
    OTHER_PAVED = 'other_paved_surfaces'
    GRAVEL = 'gravel'
    GROUND = 'ground'
    OTHER_UNPAVED = 'other_unpaved_surfaces'
    UNKNOWN = 'unknown'


SURFACE_TYPE_RATING_MAP = {
    SurfaceType.CONTINUOUS_PAVEMENT: 1.0,
    SurfaceType.MODULAR_PAVEMENT: 0.85,
    SurfaceType.COBBLESTONE: 0.6,
    SurfaceType.OTHER_PAVED: 0.5,
    SurfaceType.GRAVEL: 0.4,
    SurfaceType.GROUND: 0.2,
    SurfaceType.OTHER_UNPAVED: 0.0,
    SurfaceType.UNKNOWN: None,
}


def fetch_osm_data(aoi: shapely.MultiPolygon, osm_filter: str, ohsome: OhsomeClient) -> gpd.GeoDataFrame:
    elements = ohsome.elements.geometry.post(
        bpolys=aoi, clipGeometry=True, properties='tags', filter=osm_filter
    ).as_dataframe()
    elements = elements.reset_index(drop=False)
    return elements[['@osmId', 'geometry', '@other_tags']]


def _dict_to_legend(d: dict, cmap_name: str = 'coolwarm_r') -> Dict[str, Color]:
    data = pd.DataFrame.from_records(data=list(d.items()), columns=['category', 'rating'])
    data['color'] = generate_colors(color_by=data.rating, cmap_name=cmap_name, min=0.0, max=1.0)
    data['category'] = data.category.apply(lambda cat: cat.value)
    return dict(zip(data['category'], data['color']))


def get_path_rating_legend() -> Dict[str, Color]:
    return _dict_to_legend(PATH_RATING_MAP, cmap_name='coolwarm_r')


def get_surface_quality_legend() -> Dict[str, Color]:
    return _dict_to_legend(PAVEMENT_QUALITY_RATING_MAP, cmap_name='coolwarm_r')


def get_smoothness_legend() -> Dict[str, Color]:
    return _dict_to_legend(SMOOTHNESS_CATEGORY_RATING_MAP, cmap_name='coolwarm_r')


def get_surface_type_legend() -> Dict[str, Color]:
    return _dict_to_legend(SURFACE_TYPE_RATING_MAP, cmap_name='tab10')


def generate_colors(
    color_by: pd.Series, cmap_name: str, min: number | None = None, max: number | None = None
) -> list[Color]:
    """
    Function to generate a list of colors based on a linear normalization for each element in `color_by`.
    ## Params
    :param:`color_by`: `pandas.Series` with numerical values to map colors to.
    :param:`cmap_name`: name of matplotlib colormap approved in climatoology.
    :param:`min`: optional minimal value of the normalization, numerical or `None`. If `None` minimum value of `color_by` is used.
    :param:`max`: optional maxmial value of the normalization, numerical or `None`. If `None` maximum value of `color_by` is used.
    ## Returns
    :return:`mapped_colors`: list of colors matching values of `color_by`
    """
    color_by = color_by.astype(float)
    if min is None:
        min = color_by.min()
    if max is None:
        max = color_by.max()

    norm = mpl.colors.Normalize(vmin=min, vmax=max)
    cmap = mpl.colormaps[cmap_name]
    cmap.set_bad(color='#808080')

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


def safe_string_to_float(potential_number: str | float) -> float:
    try:
        return float(potential_number)
    except (TypeError, ValueError):
        return -1
