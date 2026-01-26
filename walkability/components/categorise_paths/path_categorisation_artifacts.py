import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
from climatoology.base.artifact_creators import (
    ArtifactMetadata,
    Legend,
    create_plotly_chart_artifact,
    create_vector_artifact,
)
from climatoology.base.baseoperator import Artifact
from climatoology.base.computation import ComputationResources

from walkability.components.categorise_paths.path_categorisation import (
    read_pavement_quality_rankings,
    subset_walkable_paths,
)
from walkability.components.utils.misc import (
    PathCategory,
    Topics,
    generate_colors,
    get_path_rating_legend,
    get_smoothness_legend,
    get_surface_quality_legend,
    get_surface_type_legend,
    sanitize_filenames,
)


def build_path_categorisation_artifact(
    paths_line: gpd.GeoDataFrame,
    paths_polygon: gpd.GeoDataFrame,
    areal_summaries: dict[str, go.Figure],
    aoi_summary_category_stacked_bar: go.Figure,
    aoi_summary_quality_stacked_bar: go.Figure,
    walkable_categories: set[PathCategory],
    resources: ComputationResources,
) -> list[Artifact]:
    logging.debug('Building paths artifacts')

    walkable_paths = build_walkable_paths_artifact(
        paths_line=paths_line, paths_polygon=paths_polygon, resources=resources
    )

    surface_quality = build_surface_quality_artifact(
        paths_line=paths_line,
        paths_polygon=paths_polygon,
        walkable_categories=walkable_categories,
        resources=resources,
    )

    smoothness = build_smoothness_artifact(paths_line=paths_line, paths_polygon=paths_polygon, resources=resources)

    surface_type = build_surface_artifact(paths_line=paths_line, paths_polygon=paths_polygon, resources=resources)

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
) -> Artifact:
    walkable_paths: gpd.GeoDataFrame = pd.concat([paths_line, paths_polygon], ignore_index=True)  # type: ignore

    walkable_paths['color'] = generate_colors(
        walkable_paths.rating, min_value=0.0, max_value=1.0, cmap_name='coolwarm_r'
    )
    walkable_paths['label'] = walkable_paths['category'].apply(lambda x: x.value)

    return create_vector_artifact(
        data=walkable_paths[['@osmId', 'color', 'label', 'geometry']],
        metadata=ArtifactMetadata(
            name='Path Categories',
            summary=Path(
                'resources/components/categorise_paths/path_categorisation_caption.md',
            ).read_text(),
            description=Path(
                'resources/components/categorise_paths/path_categorisation_description.md',
            ).read_text(),
            filename='walkable',
            tags={Topics.TRAFFIC},
        ),
        resources=resources,
        legend=Legend(title='Who Shares This Path with Me?', legend_data=get_path_rating_legend()),
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
    paths_line: gpd.GeoDataFrame,
    paths_polygon: gpd.GeoDataFrame,
    walkable_categories: set[PathCategory],
    resources: ComputationResources,
) -> Artifact | None:
    paths_line = next(subset_walkable_paths(paths_line, walkable_categories=walkable_categories))
    surface_quality_locations: gpd.GeoDataFrame = pd.concat([paths_line, paths_polygon], ignore_index=True)  # type: ignore
    if surface_quality_locations.empty:
        return
    surface_quality_locations['color'] = generate_colors(
        surface_quality_locations.quality_rating, min_value=0.0, max_value=1.0, cmap_name='coolwarm_r'
    )
    surface_quality_locations['label'] = surface_quality_locations.quality.apply(lambda r: r.value)

    return create_vector_artifact(
        data=surface_quality_locations[['@osmId', 'color', 'label', 'geometry']],
        metadata=ArtifactMetadata(
            name='Surface Quality',
            summary=Path('resources/components/categorise_paths/surface_quality_caption.md').read_text(),
            description=Path('resources/components/categorise_paths/surface_quality_description.md').read_text()
            + generate_detailed_pavement_quality_mapping_info(),
            filename='pavement_quality',
            tags={Topics.SURFACE},
        ),
        resources=resources,
        legend=Legend(legend_data=get_surface_quality_legend()),
    )


def build_smoothness_artifact(
    paths_line: gpd.GeoDataFrame, paths_polygon: gpd.GeoDataFrame, resources: ComputationResources
) -> Artifact:
    smoothness_locations: gpd.GeoDataFrame = pd.concat([paths_line, paths_polygon], ignore_index=True)  # type: ignore
    smoothness_locations['color'] = generate_colors(
        smoothness_locations.smoothness_rating, cmap_name='coolwarm_r', min_value=0.0, max_value=1.0
    )
    smoothness_locations['label'] = smoothness_locations.smoothness.apply(lambda r: r.name)
    return create_vector_artifact(
        data=smoothness_locations[['@osmId', 'color', 'label', 'geometry']],
        metadata=ArtifactMetadata(
            name='Smoothness',
            summary=Path('resources/components/categorise_paths/smoothness_caption.md').read_text(),
            description=Path('resources/components/categorise_paths/smoothness_description.md').read_text(),
            filename='smoothness',
            primary=False,
            tags={Topics.SURFACE},
        ),
        resources=resources,
        legend=Legend(legend_data=get_smoothness_legend()),
    )


def build_surface_artifact(
    paths_line: gpd.GeoDataFrame, paths_polygon: gpd.GeoDataFrame, resources: ComputationResources
) -> Artifact:
    surface_locations: gpd.GeoDataFrame = pd.concat([paths_line, paths_polygon], ignore_index=True)  # type: ignore
    surface_locations['color'] = generate_colors(
        surface_locations.surface_rating, cmap_name='tab10', min_value=0.0, max_value=1.0
    )
    surface_locations['label'] = surface_locations.surface.apply(lambda r: r.name)
    return create_vector_artifact(
        data=surface_locations[['@osmId', 'color', 'label', 'geometry']],
        metadata=ArtifactMetadata(
            name='Surface Type',
            summary=Path('resources/components/categorise_paths/surface_caption.md').read_text(),
            description=Path('resources/components/categorise_paths/surface_description.md').read_text(),
            filename='surface_type',
            primary=False,
            tags={Topics.SURFACE},
        ),
        resources=resources,
        legend=Legend(
            legend_data=get_surface_type_legend(),
        ),
    )


def build_areal_summary_artifacts(
    regional_aggregates: dict[str, go.Figure], resources: ComputationResources
) -> list[Artifact]:
    chart_artifacts = []
    for region, figure in regional_aggregates.items():
        sanitized_region = sanitize_filenames(region)
        chart_artifact = create_plotly_chart_artifact(
            figure=figure,
            metadata=ArtifactMetadata(
                name=f'Distribution of Path Categories in {region}',
                summary=f'How is the total length of paths distributed across the path categories in {region}? '
                f'Each category indicates with which other road users pedestrians share the path.',
                primary=False,
                filename=f'path_category_summary_{sanitized_region}',
                tags={Topics.SUMMARY, Topics.TRAFFIC},
            ),
            resources=resources,
        )
        chart_artifacts.append(chart_artifact)
    return chart_artifacts


def build_aoi_summary_category_stacked_bar_artifact(
    aoi_aggregate: go.Figure, resources: ComputationResources
) -> Artifact:
    return create_plotly_chart_artifact(
        figure=aoi_aggregate,
        metadata=ArtifactMetadata(
            name='Distribution of Path Categories',
            summary='How is the total length of paths distributed across the path categories? '
            'Each category indicates with which other road users pedestrians share the path.',
            filename='aggregation_aoi_category_stacked_bar',
            primary=True,
            tags={Topics.SUMMARY, Topics.TRAFFIC},
        ),
        resources=resources,
    )


def build_aoi_summary_quality_stacked_bar_artifact(
    aoi_aggregate: go.Figure, resources: ComputationResources
) -> Artifact:
    return create_plotly_chart_artifact(
        figure=aoi_aggregate,
        metadata=ArtifactMetadata(
            name='Distribution of Surface Quality',
            summary='How is the total length of paths distributed across the surface quality categories?',
            filename='aggregation_aoi_quality_stacked_bar',
            primary=True,
            tags={Topics.SUMMARY, Topics.SURFACE},
        ),
        resources=resources,
    )
