from typing import Dict, Tuple, List

import geopandas as gpd
import pandas as pd
import shapely
import yaml
from ohsome import OhsomeClient

from walkability.components.utils.geometry import fix_geometry_collection
from walkability.components.utils.misc import (
    PathCategory,
    fetch_osm_data,
    PavementQuality,
    get_first_match,
)
from walkability.components.categorise_paths.PathCategoryFilters import PathCategoryFilters


def path_categorisation(
    ohsome,
    paths_line: gpd.GeoDataFrame,
    paths_polygon: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    rating_map: Dict[PathCategory, float],
) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    paths_line['category'] = paths_line.apply(apply_path_category_filters, axis=1)
    paths_line['category'] = boost_route_members(aoi=aoi, paths_line=paths_line, ohsome=ohsome)

    paths_polygon['category'] = paths_polygon.apply(apply_path_category_filters, axis=1)

    paths_line['rating'] = paths_line.category.apply(lambda category: rating_map[category])
    paths_polygon['rating'] = paths_polygon.category.apply(lambda category: rating_map[category])

    rankings = read_pavement_quality_rankings()
    keys = get_flat_key_combinations()

    paths_line['quality'] = paths_line.apply(lambda row: evaluate_quality(row, keys, rankings), axis=1)

    return paths_line, paths_polygon


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


def evaluate_quality(
    row: pd.Series, keys: List[str], evaluation_dict: Dict[str, Dict[str, PavementQuality]]
) -> PavementQuality:
    tags = row['@other_tags']

    match_key, match_value = get_first_match(keys, tags)

    match match_key:
        case (
            'sidewalk:both:smoothness'
            | 'sidewalk:left:smoothness'
            | 'sidewalk:right:smoothness'
            | 'footway:smoothness'
        ):
            # If the tag refers specifically to the sidewalk, evaluate quality based on this value
            match_key = 'smoothness'
        case 'sidewalk:both:surface' | 'sidewalk:left:surface' | 'sidewalk:right:surface' | 'footway:surface':
            # If the tag refers specifically to the sidewalk, evaluate quality based on this value
            match_key = 'surface'
        case 'smoothness':
            # If the tag is generic and the path is NOT a road, evaluate quality based on this value
            # Or, if the tag is generic and the path IS a road, the smoothness probably refers to the road surface
            # TODO: why is PathCategory.DESIGNATED included in the if statement?
            if row.category not in [
                PathCategory.DESIGNATED,
                PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED,
                PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
                PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED,
            ] and tags.get('highway') not in ['path', 'footway', 'cycleway', 'track']:
                return PavementQuality.UNKNOWN
        case 'surface':
            # If the tag is generic and the path is NOT a road, evaluate quality based on this value
            # Or, if the tag is generic and the path IS a road, the surface probably refers to the road surface
            # TODO: why is PathCategory.DESIGNATED included in the if statement?
            if row.category not in [
                PathCategory.DESIGNATED,
                PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED,
                PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
                PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED,
            ] and tags.get('highway') not in ['path', 'footway', 'cycleway', 'track']:
                return PavementQuality.UNKNOWN
        case 'tracktype':
            # If none of the more specific tags was given, take tracktype (if applicable)
            pass
        case _:
            return PavementQuality.UNKNOWN
    return evaluation_dict.get(match_key, {}).get(match_value, PavementQuality.UNKNOWN)


def read_pavement_quality_rankings() -> Dict[str, Dict[str, PavementQuality]]:
    with open('resources/components/categorise_paths/value_ranking.yaml') as f:
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
