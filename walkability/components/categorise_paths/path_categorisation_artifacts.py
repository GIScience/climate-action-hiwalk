import logging
from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import pandas as pd
from climatoology.base.artifact import Chart2dData
from climatoology.base.artifact import create_chart_artifact, create_geojson_artifact
from climatoology.base.baseoperator import _Artifact
from climatoology.base.computation import ComputationResources

from walkability.components.categorise_paths.path_categorisation import read_pavement_quality_rankings
from walkability.components.utils.misc import (
    PathCategory,
    PavementQuality,
)
from walkability.components.utils.misc import get_qualitative_color

path_ratings_name_mapping = {
    'shared_with_motorized_traffic_low_speed': 'shared_with_motorized_traffic_low_speed_(=walking_speed)',
    'shared_with_motorized_traffic_medium_speed': 'shared_with_motorized_traffic_medium_speed_(<=30_km/h)',
    'shared_with_motorized_traffic_high_speed': 'shared_with_motorized_traffic_high_speed_(<=50_km/h)',
}


def build_path_categorisation_artifact(
    paths_line: gpd.GeoDataFrame,
    paths_polygon: gpd.GeoDataFrame,
    areal_summaries: Dict[str, Chart2dData],
    resources: ComputationResources,
    cmap_name: str = 'RdYlBu_r',
) -> List[_Artifact]:
    logging.debug('Building paths artifacts')

    walkable_paths = build_walkable_paths_artifact(
        paths_line=paths_line, paths_polygon=paths_polygon, cmap_name=cmap_name, resources=resources
    )

    surface_quality = build_surface_quality_artifact(paths_line=paths_line, cmap_name=cmap_name, resources=resources)

    summary_artifacts = build_areal_summary_artifacts(regional_aggregates=areal_summaries, resources=resources)

    return [walkable_paths, surface_quality] + summary_artifacts


def build_walkable_paths_artifact(
    paths_line: gpd.GeoDataFrame, paths_polygon: gpd.GeoDataFrame, cmap_name: str, resources: ComputationResources
) -> _Artifact:
    walkable_locations = pd.concat([paths_line, paths_polygon], ignore_index=True)

    walkable_locations['color'] = walkable_locations.category.apply(
        get_qualitative_color, cmap_name=cmap_name, class_name=PathCategory
    )
    return create_geojson_artifact(
        features=walkable_locations.geometry,
        layer_name='Walkable Path Categories',
        caption=Path('resources/components/categorise_paths/path_categorisation_caption.md').read_text(),
        description=Path('resources/components/categorise_paths/path_categorisation_description.md').read_text(),
        label=walkable_locations.category.apply(lambda r: r.name).to_list(),
        color=walkable_locations.color.to_list(),
        legend_data={
            path_ratings_name_mapping.get(category.value, category.value): get_qualitative_color(
                category, cmap_name, PathCategory
            )
            for category in PathCategory
        },
        resources=resources,
        filename='walkable',
    )


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


def build_surface_quality_artifact(
    paths_line: gpd.GeoDataFrame, cmap_name: str, resources: ComputationResources
) -> _Artifact:
    paths_line['color'] = paths_line.quality.apply(
        get_qualitative_color, cmap_name=cmap_name, class_name=PavementQuality
    )
    return create_geojson_artifact(
        features=paths_line.geometry,
        layer_name='Surface Quality',
        caption=Path('resources/components/categorise_paths/surface_quality_caption.md').read_text(),
        description=Path('resources/components/categorise_paths/surface_quality_description.md').read_text()
        + generate_detailed_pavement_quality_mapping_info(),
        label=paths_line.quality.apply(lambda r: r.name).to_list(),
        color=paths_line.color.to_list(),
        legend_data={
            path_ratings_name_mapping.get(quality.value, quality.value): get_qualitative_color(
                quality, cmap_name, PavementQuality
            )
            for quality in PavementQuality
        },
        resources=resources,
        filename='pavement_quality',
    )


def build_areal_summary_artifacts(
    regional_aggregates: Dict[str, Chart2dData], resources: ComputationResources
) -> List[_Artifact]:
    chart_artifacts = []
    for region, data in regional_aggregates.items():
        chart_artifact = create_chart_artifact(
            data=data,
            title=f'Distribution of Path Categories in {region}',
            caption=f'Fraction of the total length of paths for each category compared to the total path length '
            f'of {sum(data.y)} km in this area.',
            resources=resources,
            filename=f'aggregation_{region}',
            primary=False,
        )
        chart_artifacts.append(chart_artifact)
    return chart_artifacts
