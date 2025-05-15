from typing import Dict, Tuple, List, Set, Generator

import geopandas as gpd
import pandas as pd
import yaml

from walkability.components.categorise_paths.PathCategoryFilters import PathCategoryFilters
from walkability.components.utils.misc import (
    PathCategory,
    PavementQuality,
    get_first_match,
    PATH_RATING_MAP,
    PAVEMENT_QUALITY_RATING_MAP,
    SmoothnessCategory,
    SurfaceType,
    SMOOTHNESS_CATEGORY_RATING_MAP,
    SURFACE_TYPE_RATING_MAP,
)


def path_categorisation(
    paths_line: gpd.GeoDataFrame,
    paths_polygon: gpd.GeoDataFrame,
) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    rankings = read_pavement_quality_rankings()
    keys = get_flat_key_combinations()

    paths_line['category'] = paths_line.apply(apply_path_category_filters, axis=1)
    paths_line['quality'] = paths_line.apply(lambda row: evaluate_quality(row, keys, rankings), axis=1)
    paths_line['smoothness'] = paths_line.apply(apply_path_smoothness_filters, axis=1)
    paths_line['surface'] = paths_line.apply(apply_path_surface_filters, axis=1)

    if paths_polygon.empty:
        paths_polygon['category'] = pd.Series()
        paths_polygon['quality'] = pd.Series()
        paths_polygon['smoothness'] = pd.Series()
        paths_polygon['surface'] = pd.Series()
    else:
        paths_polygon['category'] = paths_polygon.apply(apply_path_category_filters, axis=1)
        paths_polygon['quality'] = paths_polygon.apply(lambda row: evaluate_quality(row, keys, rankings), axis=1)
        paths_polygon['smoothness'] = paths_polygon.apply(apply_path_smoothness_filters, axis=1)
        paths_polygon['surface'] = paths_polygon.apply(apply_path_surface_filters, axis=1)

    paths_line['rating'] = paths_line.category.apply(lambda category: PATH_RATING_MAP[category])
    paths_polygon['rating'] = paths_polygon.category.apply(lambda category: PATH_RATING_MAP[category])

    paths_line['quality_rating'] = paths_line.quality.apply(lambda quality: PAVEMENT_QUALITY_RATING_MAP[quality])
    paths_polygon['quality_rating'] = paths_polygon.quality.apply(lambda quality: PAVEMENT_QUALITY_RATING_MAP[quality])

    paths_line['smoothness_rating'] = paths_line.smoothness.apply(
        lambda smoothness: SMOOTHNESS_CATEGORY_RATING_MAP[smoothness]
    )
    paths_polygon['smoothness_rating'] = paths_polygon.smoothness.apply(
        lambda smoothness: SMOOTHNESS_CATEGORY_RATING_MAP[smoothness]
    )

    paths_line['surface_rating'] = paths_line.surface.apply(lambda surface: SURFACE_TYPE_RATING_MAP[surface])
    paths_polygon['surface_rating'] = paths_polygon.surface.apply(lambda surface: SURFACE_TYPE_RATING_MAP[surface])

    return paths_line, paths_polygon


def apply_path_category_filters(row: pd.Series) -> PathCategory:
    tags = row['@other_tags']
    filters = PathCategoryFilters(tags=tags)
    match tags:
        case x if filters.inaccessible(x):
            return PathCategory.INACCESSIBLE
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
        case x if filters.shared_with_very_high_speed(x):
            return PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_VERY_HIGH_SPEED
        case x if filters.shared_with_unknown_speed(x):
            return PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED
        case _:
            return PathCategory.UNKNOWN


def evaluate_quality(
    row: pd.Series, keys: List[str], evaluation_dict: Dict[str, Dict[str, PavementQuality]]
) -> PavementQuality:
    if row['category'] == PathCategory.UNKNOWN:
        return PavementQuality.UNKNOWN

    tags = row['@other_tags']

    match_key, match_value = get_first_match(keys, tags)

    match match_key:
        # Decision: We don't re-check if the sidewalk is actually mapped, we rely on the smoothnes/surface tagging
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
            if PathCategoryFilters.has_sidewalk(tags):
                return PavementQuality.UNKNOWN
        case 'surface':
            # If the tag is generic and the path is NOT a road, evaluate quality based on this value
            # Or, if the tag is generic and the path IS a road, the surface probably refers to the road surface
            if PathCategoryFilters.has_sidewalk(tags):
                return PavementQuality.UNKNOWN
        case 'tracktype':
            # If none of the more specific tags was given, take tracktype (if applicable)
            if PathCategoryFilters.has_sidewalk(tags):
                return PavementQuality.UNKNOWN
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


def subset_walkable_paths(
    *args: gpd.GeoDataFrame,
    walkable_categories: Set[PathCategory],
) -> Generator[gpd.GeoDataFrame, None, None]:
    for path in args:
        yield path[path['category'].isin(walkable_categories)]


def apply_path_smoothness_filters(row: pd.Series) -> SmoothnessCategory:
    smoothness_tag = row['@other_tags'].get('smoothness')
    match smoothness_tag:
        case 'very_bad' | 'horrible' | 'very_horrible' | 'impassable':
            return SmoothnessCategory.VERY_POOR
        case 'bad':
            return SmoothnessCategory.POOR
        case 'intermediate':
            return SmoothnessCategory.MEDIOCRE
        case 'good' | 'excellent':
            return SmoothnessCategory.GOOD
        case _:
            return SmoothnessCategory.UNKNOWN


def apply_path_surface_filters(row: pd.Series) -> SurfaceType:
    surface_tag = row['@other_tags'].get('surface')
    match surface_tag:
        case 'asphalt' | 'concrete':
            return SurfaceType.CONTINUOUS_PAVEMENT
        case 'concrete:lanes' | 'concrete:plates' | 'paving_stones' | 'paving_stones:lanes':
            return SurfaceType.MODULAR_PAVEMENT
        case 'cobblestones' | 'sett' | 'unhewn_cobblestone':
            return SurfaceType.COBBLESTONE
        case (
            'chipseal'
            | 'grass_paver'
            | 'bricks'
            | 'metal'
            | 'metal_grid'
            | 'wood'
            | 'stepping_stones'
            | 'rubber'
            | 'tiles'
            | 'paved'
        ):
            return SurfaceType.OTHER_PAVED
        case 'compacted' | 'fine_gravel' | 'gravel':
            return SurfaceType.GRAVEL
        case 'ground' | 'dirt' | 'earth':
            return SurfaceType.GROUND
        case (
            'shells'
            | 'rock'
            | 'pebblestone'
            | 'ground'
            | 'dirt'
            | 'earth'
            | 'grass'
            | 'mud'
            | 'sand'
            | 'snow'
            | 'woodchips'
            | 'ice'
            | 'salt'
            | 'unpaved'
        ):
            return SurfaceType.OTHER_UNPAVED
        case _:
            return SurfaceType.UNKNOWN
