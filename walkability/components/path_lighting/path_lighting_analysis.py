import logging

import geopandas as gpd
import pandas as pd
from climatoology.base.artifact import Artifact
from climatoology.base.computation import ComputationResources
from geopandas import GeoDataFrame

from walkability.components.path_lighting.path_lighting_artifact import build_path_lighting_artifact
from walkability.components.utils.misc import PATH_LIGHTING_CATEGORY_RATING_MAP, PathLightingCategory

log = logging.getLogger(__name__)


def path_lighting_analysis(
    line_paths: gpd.GeoDataFrame,
    polygon_paths: gpd.GeoDataFrame,
    resources: ComputationResources,
) -> list[Artifact]:
    light_paths_all = get_path_lighting(line_paths=line_paths, polygon_paths=polygon_paths)
    light_path_artifact = build_path_lighting_artifact(light_locations=light_paths_all, resources=resources)
    return [light_path_artifact]


def get_path_lighting(line_paths: GeoDataFrame, polygon_paths: GeoDataFrame) -> GeoDataFrame:
    light_path = []
    if not line_paths.empty:
        paths_light = path_lighting_categorisation(geometries=line_paths)
        light_path.append(paths_light)
    if not polygon_paths.empty:
        polygons_light = path_lighting_categorisation(geometries=polygon_paths)
        light_path.append(polygons_light)
    light_paths_all: gpd.GeoDataFrame = pd.concat(light_path)
    return light_paths_all


def path_lighting_categorisation(
    geometries: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    log.debug('Path Lighting categorisation')
    geometries['path_lighting'] = geometries.apply(apply_path_lighting_filters, axis=1, result_type='reduce')

    geometries['path_lighting_rating'] = geometries.path_lighting.apply(
        lambda path_lighting: PATH_LIGHTING_CATEGORY_RATING_MAP[path_lighting]
    )
    return geometries


def apply_path_lighting_filters(row: pd.Series) -> PathLightingCategory:
    path_lighting_tag = row['@other_tags'].get('lit')

    if path_lighting_tag is None:
        if row['@other_tags'].get('lit_by_led') == 'yes' or row['@other_tags'].get('lit_by_gaslight') == 'yes':
            path_lighting_tag = 'yes'

    match path_lighting_tag:
        case 'yes' | '24/7':
            return PathLightingCategory.YES
        case 'automatic':
            return PathLightingCategory.AUTOMATIC
        case 'limited':
            return PathLightingCategory.LIMITED
        case 'no' | 'disused':
            return PathLightingCategory.NO
        case _:
            return PathLightingCategory.UNKNOWN
