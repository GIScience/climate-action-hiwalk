import logging
from enum import Enum, StrEnum
from typing import Dict, List, Optional, Tuple
from typing import SupportsFloat as Numeric

import geopandas as gpd
import matplotlib as mpl
import pandas as pd
import shapely
from climatoology.base.exception import ClimatoologyUserError
from ohsome import OhsomeClient
from ohsome.exceptions import OhsomeException
from pydantic_extra_types.color import Color

log = logging.getLogger(__name__)


class Topics(StrEnum):
    TRAFFIC = 'traffic'
    SURFACE = 'surface'
    SUMMARY = 'summary'
    CONNECTIVITY = 'connectivity'
    BARRIERS = 'barriers'
    GREENNESS = 'greenness'
    COMFORT = 'comfort'


class PathCategory(Enum):
    DESIGNATED = 'Pedestrians Exclusive'
    DESIGNATED_SHARED_WITH_BIKES = 'Bikes'
    SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED = 'Cars up to 15 km/h'
    SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED = 'Cars up to 30 km/h'
    SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED = 'Cars up to 50 km/h'
    SHARED_WITH_MOTORIZED_TRAFFIC_VERY_HIGH_SPEED = 'Cars above 50 km/h'
    SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED = 'Cars of unknown speed'
    INACCESSIBLE = 'No access'
    UNKNOWN = 'Unknown'

    @classmethod
    def get_hidden(cls):
        return [cls.INACCESSIBLE]

    @classmethod
    def get_visible(cls):
        return [category for category in cls if category not in cls.get_hidden()]


PATH_RATING_MAP = {
    PathCategory.DESIGNATED: 1.0,
    PathCategory.DESIGNATED_SHARED_WITH_BIKES: 0.8,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED: 0.6,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED: 0.4,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED: 0.2,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_VERY_HIGH_SPEED: 0.0,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED: 0.0,
    PathCategory.UNKNOWN: None,
}


WALKABLE_CATEGORIES = {
    PathCategory.DESIGNATED,
    PathCategory.DESIGNATED_SHARED_WITH_BIKES,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED,
    PathCategory.UNKNOWN,
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
    try:
        elements = ohsome.elements.geometry.post(
            bpolys=aoi, clipGeometry=True, properties='tags', filter=osm_filter
        ).as_dataframe()
    except OhsomeException as e:
        if e.error_code in [500, 501, 502, 503, 507]:
            raise ClimatoologyUserError('There was an error collecting OSM data. Please try again later.')
        else:
            raise e

    elements = elements.reset_index(drop=False)
    return elements[['@osmId', 'geometry', '@other_tags']]


def _dict_to_legend(d: dict, cmap_name: str = 'coolwarm_r') -> Dict[str, Color]:
    data = pd.DataFrame.from_records(data=list(d.items()), columns=['category', 'rating'])
    data['color'] = generate_colors(color_by=data.rating, cmap_name=cmap_name, min_value=0.0, max_value=1.0)
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
    color_by: pd.Series,
    cmap_name: str,
    min_value: Numeric | None = None,
    max_value: Numeric | None = None,
    bad_color='#808080',
) -> pd.Series:
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

    norm = mpl.colors.Normalize(vmin=min_value, vmax=max_value)
    cmap = mpl.colormaps[cmap_name]

    cmap.set_extremes(bad=bad_color, under=bad_color, over=bad_color)

    mapped_colors = [Color(mpl.colors.to_hex(col)) for col in cmap(norm(color_by))]
    colors = pd.Series(data=mapped_colors, index=color_by.index)
    return colors


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


def check_paths_count_limit(aoi: shapely.MultiPolygon, ohsome: OhsomeClient, count_limit: int) -> None:
    """
    Check whether paths count is over than limit. (NOTE: just check path_lines)
    """

    ohsome_responses = ohsome.elements.count.post(bpolys=aoi, filter=ohsome_filter('line')).data
    path_lines_count = sum([response['value'] for response in ohsome_responses['result']])
    log.info(f'There are {path_lines_count} paths selected.')
    if path_lines_count > count_limit:
        raise ClimatoologyUserError(
            f'There are too many path segments in the selected area: {path_lines_count} path segments. '
            f'Currently, only areas with a maximum of {count_limit} path segments are allowed. '
            f'Please select a smaller area or a sub-region of your selected area.'
        )


def sanitize_filenames(name: str) -> str:
    without_fs_characters = name.translate({ord(character): None for character in '/<>|:&'})
    ascii_string = without_fs_characters.encode(encoding='ascii', errors='ignore').decode()
    return ascii_string
