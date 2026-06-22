from pathlib import Path

import botocore.client
import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
from climatoology.base.artifact import ArtifactMetadata, ContinuousLegendData, Legend
from climatoology.base.artifact_creators import Artifact, create_plotly_chart_artifact, create_vector_artifact
from climatoology.base.computation import ComputationResources
from climatoology.base.logging import get_climatoology_logger

from walkability.components.shade.utility import S3ShadeConfig, get_shaded_path_stats
from walkability.components.utils.misc import Topics, generate_colors

log = get_climatoology_logger(__name__)


def shade_analysis(
    paths: gpd.GeoDataFrame,
    tile_spec: gpd.GeoDataFrame,
    shade_client: botocore.client.BaseClient,
    shade_config: S3ShadeConfig,
    resources: ComputationResources,
) -> list[Artifact]:
    shaded_paths = get_shaded_path_stats(
        paths=paths, tile_spec=tile_spec, shade_client=shade_client, shade_config=shade_config
    )

    shade_artifact = create_shade_paths_vector_artifact(shaded_paths, resources)
    shade_chart_artifact = create_shade_paths_chart_artifact(shaded_paths, resources)

    return [shade_artifact, shade_chart_artifact]


def create_shade_paths_vector_artifact(shaded_paths: gpd.GeoDataFrame, resources: ComputationResources) -> Artifact:
    cmap = 'YlGn'
    shaded_paths['prop_shaded'] = shaded_paths['length_shaded'] / shaded_paths['length']
    shaded_paths['color'] = generate_colors(
        color_by=shaded_paths['prop_shaded'], cmap_name=cmap, min_value=0, max_value=1
    )
    shaded_paths['label'] = shaded_paths['prop_shaded'].apply(lambda x: '{:.0f}%'.format(round(x * 100)))
    shaded_paths = shaded_paths[['@osmId', 'color', 'label', 'geometry']]

    shade_metadata = ArtifactMetadata(
        name='Shaded Paths',
        summary='Is this path shaded by tree canopies?',
        description=Path('resources/components/shade/description.md').read_text(),
        tags={Topics.SHADE, Topics.COMFORT},
        primary=False,
    )
    shade_artifact = create_vector_artifact(
        data=shaded_paths,
        metadata=shade_metadata,
        resources=resources,
        legend=Legend(
            title='Proportion Shaded',
            legend_data=ContinuousLegendData(cmap_name=cmap, ticks={'0%': 0.0, '100%': 1.0}),
        ),
    )  # type: ignore
    return shade_artifact


def create_shade_paths_chart_artifact(shaded_paths: gpd.GeoDataFrame, resources: ComputationResources) -> Artifact:
    len_unshaded = shaded_paths['length'] - shaded_paths['length_shaded']

    summary = pd.DataFrame(
        {
            'shade_category': ['Unshaded', 'Shaded'],
            'length': [
                len_unshaded.sum() / 1000,
                shaded_paths['length_shaded'].sum() / 1000,
            ],
        }
    )
    summary['percent'] = summary['length'] / summary['length'].sum() * 100
    summary = summary.set_index('shade_category')
    shade_chart = create_shade_plot(summary)

    shade_chart_metadata = ArtifactMetadata(
        name='Distribution of Shade',
        summary='What length of paths is shaded?',
        tags={Topics.SHADE, Topics.COMFORT},
        primary=False,
    )
    shade_chart_artifact = create_plotly_chart_artifact(
        figure=shade_chart,
        metadata=shade_chart_metadata,
        resources=resources,
    )

    return shade_chart_artifact


def create_shade_plot(summary: pd.DataFrame) -> go.Figure:
    colors = ['#f9fdc2', '#004529']

    data = go.Figure()
    for i, (category, row) in enumerate(summary.iterrows()):
        data.add_trace(
            go.Bar(
                y=['Shade'],  # placeholder for y axis label (which is hidden anyway)
                x=[row['percent']],
                name=category,
                orientation='h',
                marker_color=colors[i],
                hovertemplate=f'{category}: {row["length"]:.0f} km ({row["percent"]:.1f}%)<extra></extra>',
                showlegend=True,
                legendrank=len(summary) - i,
            )
        )
        data.update_layout(
            barmode='stack',
            height=300,
            margin=dict(t=30, b=80, l=30, r=30),
            xaxis_title=f'Percentage of the {summary["length"].sum():.0f} km of paths that are shaded.',
            yaxis=dict(showticklabels=False),
            legend=dict(
                orientation='h',
                yanchor='top',
                y=-1,
                xanchor='center',
                x=0.5,
                font=dict(size=12),
            ),
        )

    return data
