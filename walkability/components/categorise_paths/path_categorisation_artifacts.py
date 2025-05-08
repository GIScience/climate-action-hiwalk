import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

import geopandas as gpd
import pandas as pd
from climatoology.base.artifact import (
    create_geojson_artifact,
    create_plotly_chart_artifact,
)
from climatoology.base.baseoperator import _Artifact
from climatoology.base.computation import ComputationResources
from plotly.graph_objects import Figure

from walkability.components.categorise_paths.path_categorisation import (
    read_pavement_quality_rankings,
    subset_walkable_paths,
)
from walkability.components.utils.misc import (
    PathCategory,
    generate_colors,
    get_path_rating_legend,
    get_smoothness_legend,
    get_surface_quality_legend,
    get_surface_type_legend,
)


def build_path_categorisation_artifact(
    paths_line: gpd.GeoDataFrame,
    paths_polygon: gpd.GeoDataFrame,
    areal_summaries: Dict[str, Figure],
    aoi_summary_category_stacked_bar: Figure,
    aoi_summary_quality_stacked_bar: Figure,
    walkable_categories: Set[PathCategory],
    resources: ComputationResources,
) -> List[_Artifact]:
    logging.debug('Building paths artifacts')

    walkable_paths = build_walkable_paths_artifact(
        paths_line=paths_line, paths_polygon=paths_polygon, resources=resources
    )

    surface_quality = build_surface_quality_artifact(
        paths_line=paths_line,
        walkable_categories=walkable_categories,
        resources=resources,
    )

    smoothness = build_smoothness_artifact(paths_line=paths_line, resources=resources)

    surface_type = build_surface_artifact(paths_line=paths_line, resources=resources)

    summary_artifacts = []
    if areal_summaries:
        summary_artifacts = build_areal_summary_artifacts(regional_aggregates=areal_summaries, resources=resources)

    aoi_summary_category_stacked_bar_artifact = build_aoi_summary_category_stacked_bar_artifact(
        aoi_aggregate=aoi_summary_category_stacked_bar, resources=resources
    )

    aoi_summary_quality_stacked_bar_artifact = build_aoi_summary_quality_stacked_bar_artifact(
        aoi_aggregate=aoi_summary_quality_stacked_bar, resources=resources
    )

    return [
        walkable_paths,
        surface_quality,
        smoothness,
        surface_type,
        aoi_summary_category_stacked_bar_artifact,
        aoi_summary_quality_stacked_bar_artifact,
    ] + summary_artifacts


def build_walkable_paths_artifact(
    paths_line: gpd.GeoDataFrame, paths_polygon: gpd.GeoDataFrame, resources: ComputationResources
) -> _Artifact:
    walkable_locations = pd.concat([paths_line, paths_polygon], ignore_index=True)

    walkable_locations['color'] = generate_colors(walkable_locations.rating, min=0.0, max=1.0, cmap_name='coolwarm_r')

    return create_geojson_artifact(
        features=walkable_locations.geometry,
        layer_name='Walkable Path Category',
        caption=Path('resources/components/categorise_paths/path_categorisation_caption.md').read_text(),
        description=Path('resources/components/categorise_paths/path_categorisation_description.md').read_text(),
        label=walkable_locations.category.apply(lambda r: r.value).to_list(),
        color=walkable_locations.color.to_list(),
        legend_data=get_path_rating_legend(),
        resources=resources,
        filename='walkable',
    )


def generate_detailed_pavement_quality_mapping_info() -> str:
    rankings = read_pavement_quality_rankings()
    text = ''
    for key, value_map in rankings.items():
        text += f' ### Key `{key}`: \n'
        text += ' |Value|Ranking| \n'
        text += ' |:----|:------| \n'
        for value, ranking in value_map.items():
            text += f' |{value} | {ranking.value.replace("_", " ").title()}| \n'
    return text


def build_surface_quality_artifact(
    paths_line: gpd.GeoDataFrame, walkable_categories: Set[PathCategory], resources: ComputationResources
) -> Optional[_Artifact]:
    paths_line = next(subset_walkable_paths(paths_line, walkable_categories=walkable_categories))
    if paths_line.empty:
        return
    paths_line['color'] = generate_colors(paths_line.quality_rating, min=0.0, max=1.0, cmap_name='coolwarm_r')
    return create_geojson_artifact(
        features=paths_line.geometry,
        layer_name='Surface Quality',
        caption=Path('resources/components/categorise_paths/surface_quality_caption.md').read_text(),
        description=Path('resources/components/categorise_paths/surface_quality_description.md').read_text()
        + generate_detailed_pavement_quality_mapping_info(),
        label=paths_line.quality.apply(lambda r: r.value).to_list(),
        color=paths_line.color.to_list(),
        legend_data=get_surface_quality_legend(),
        resources=resources,
        filename='pavement_quality',
    )


def build_smoothness_artifact(paths_line: gpd.GeoDataFrame, resources: ComputationResources) -> _Artifact:
    paths_line['color'] = generate_colors(paths_line.smoothness_rating, cmap_name='coolwarm_r', min=0.0, max=1.0)
    return create_geojson_artifact(
        features=paths_line.geometry,
        layer_name='Smoothness',
        caption=Path('resources/components/categorise_paths/smoothness_caption.md').read_text(),
        description=Path('resources/components/categorise_paths/smoothness_description.md').read_text(),
        label=paths_line.smoothness.apply(lambda r: r.name).to_list(),
        color=paths_line.color.to_list(),
        legend_data=get_smoothness_legend(),
        resources=resources,
        filename='smoothness',
        primary=False,
    )


def build_surface_artifact(paths_line: gpd.GeoDataFrame, resources: ComputationResources) -> _Artifact:
    paths_line['color'] = generate_colors(paths_line.surface_rating, cmap_name='tab10', min=0.0, max=1.0)
    return create_geojson_artifact(
        features=paths_line.geometry,
        layer_name='Surface Type',
        caption=Path('resources/components/categorise_paths/surface_caption.md').read_text(),
        description=Path('resources/components/categorise_paths/surface_description.md').read_text(),
        label=paths_line.surface.apply(lambda r: r.name).to_list(),
        color=paths_line.color.to_list(),
        legend_data=get_surface_type_legend(),
        resources=resources,
        filename='surface_type',
        primary=False,
    )


def build_areal_summary_artifacts(
    regional_aggregates: Dict[str, Figure], resources: ComputationResources
) -> List[_Artifact]:
    chart_artifacts = []
    for region, figure in regional_aggregates.items():
        sanitised_region = region.translate({ord(character): None for character in '/<>|:&'})
        chart_artifact = create_plotly_chart_artifact(
            figure=figure,
            title=f'Distribution of Path Categories in {region}',
            caption=f'How is the total length of paths distributed across the path categories in {region}?',
            resources=resources,
            filename=f'aggregation_{sanitised_region}',
            primary=False,
        )
        chart_artifacts.append(chart_artifact)
    return chart_artifacts


def build_aoi_summary_category_stacked_bar_artifact(
    aoi_aggregate: Figure, resources: ComputationResources
) -> _Artifact:
    return create_plotly_chart_artifact(
        figure=aoi_aggregate,
        title='Distribution of Path Categories',
        caption='How is the total length of paths distributed across the path categories?',
        resources=resources,
        filename='aggregation_aoi_category_stacked_bar',
        primary=True,
    )


def build_aoi_summary_quality_stacked_bar_artifact(aoi_aggregate: Figure, resources: ComputationResources) -> _Artifact:
    return create_plotly_chart_artifact(
        figure=aoi_aggregate,
        title='Distribution of Surface Quality',
        caption='How is the total length of paths distributed across the surface quality categories?',
        resources=resources,
        filename='aggregation_aoi_quality_stacked_bar',
        primary=True,
    )
