import logging

import geopandas as gpd
import pandas as pd
from climatoology.base.artifact import Artifact
from climatoology.base.computation import ComputationResources
from geopandas import GeoDataFrame

from walkability.components.tactile_paving.tactile_paving_artifact import build_tactile_paving_artifact
from walkability.components.utils.misc import TACTILE_PAVING_CATEGORY_RATING_MAP, TactilePavingCategory

log = logging.getLogger(__name__)


def tactile_paving_analysis(
    line_paths: gpd.GeoDataFrame,
    polygon_paths: gpd.GeoDataFrame,
    resources: ComputationResources,
) -> list[Artifact]:
    tactile_paving_all = get_tactile_paving(line_paths=line_paths, polygon_paths=polygon_paths)
    tactile_paving_artifact = build_tactile_paving_artifact(tactile_locations=tactile_paving_all, resources=resources)
    return [tactile_paving_artifact]


def get_tactile_paving(line_paths: GeoDataFrame, polygon_paths: GeoDataFrame) -> GeoDataFrame:
    tactile_path = []
    if not line_paths.empty:
        paths_tactile = tactile_paving_categorisation(geometries=line_paths)
        tactile_path.append(paths_tactile)
    if not polygon_paths.empty:
        polygons_tactile = tactile_paving_categorisation(geometries=polygon_paths)
        tactile_path.append(polygons_tactile)
    tactile_paths_all: gpd.GeoDataFrame = pd.concat(tactile_path)
    return tactile_paths_all


def tactile_paving_categorisation(
    geometries: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    log.debug('Tactile paving categorisation')
    geometries['tactile_paving'] = geometries.apply(apply_tactile_paving_filters, axis=1, result_type='reduce')

    geometries['tactile_paving_rating'] = geometries.tactile_paving.apply(
        lambda tactile_paving: TACTILE_PAVING_CATEGORY_RATING_MAP[tactile_paving]
    )
    return geometries


def apply_tactile_paving_filters(row: pd.Series) -> TactilePavingCategory:
    tactile_paving_tag = row['@other_tags'].get('tactile_paving')

    if tactile_paving_tag == 'yes':
        if row['@other_tags'].get('tactile_paving: surface') == 'unpaved':
            tactile_paving_tag = 'unpaved'
        if row['@other_tags'].get('tactile_paving: condition') in ['bad', 'very_bad']:
            tactile_paving_tag = 'partial'

    if tactile_paving_tag is None:
        if row['@other_tags'].get('tactile_paving: contrast') == '*':
            tactile_paving_tag = 'contrasted'
        if row['@other_tags'].get('tactile_paving: surface') == 'unpaved':
            tactile_paving_tag = 'unpaved'
        if row['@other_tags'].get('tactile_paving: surface') in ['cobblestone', 'paving_stones', 'sett']:
            tactile_paving_tag = 'yes'
        if row['@other_tags'].get('tactile_paving: segregated') == 'yes':
            tactile_paving_tag = 'yes'
        if row['@other_tags'].get('tactile_paving: type') == '*':
            tactile_paving_tag = 'yes'
        if row['@other_tags'].get('tactile_paving: condition') in ['excellent', 'good', 'intermediate']:
            tactile_paving_tag = 'yes'
        if row['@other_tags'].get('tactile_paving: condition') in ['bad', 'very_bad']:
            tactile_paving_tag = 'partial'
        if row['@other_tags'].get('tactile_paving: colour') == '*':
            tactile_paving_tag = 'yes'
        if row['@other_tags'].get('tactile_paving: material') == '*':
            tactile_paving_tag = 'yes'
        if row['@other_tags'].get('tactile_paving: pattern') == '*':
            tactile_paving_tag = 'yes'
        if row['@other_tags'].get('tactile_paving: slab_size') == '*':
            tactile_paving_tag = 'yes'

    match tactile_paving_tag:
        case (
            'yes'
            | 'cobblestone'
            | 'both'
            | 'standard'
            | 'separate'
            | 'studs'
            | 'platform'
            | 'directional'
            | 'contrasted'
        ):
            return TactilePavingCategory.YES
        case 'primitive' | 'unpaved':
            return TactilePavingCategory.OTHER_SIGNS
        case (
            'partial'
            | 'half'
            | 'kerb'
            | 'guideway'
            | 'warning'
            | 'crossing'
            | 'guide'
            | 'reversible'
            | 'incorrect'
            | 'limited'
            | 'wrong'
            | 'bad'
        ):
            return TactilePavingCategory.PARTIAL
        case 'no':
            return TactilePavingCategory.NO
        case _:
            return TactilePavingCategory.UNKNOWN
