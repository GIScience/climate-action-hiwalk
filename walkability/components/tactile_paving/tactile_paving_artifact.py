import logging
from pathlib import Path

import geopandas as gpd
import plotly.graph_objects as go
from climatoology.base.artifact_creators import (
    Artifact,
    ArtifactMetadata,
    Legend,
    create_plotly_chart_artifact,
    create_vector_artifact,
)
from climatoology.base.computation import ComputationResources

from walkability.components.utils.misc import Topics, generate_colors, get_tactile_paving_legend

log = logging.getLogger(__name__)


def build_tactile_paving_artifact(tactile_locations: gpd.GeoDataFrame, resources: ComputationResources) -> Artifact:
    log.debug('Building tactile paving artifact')
    tactile_locations['color'] = generate_colors(
        color_by=tactile_locations.tactile_paving_rating, cmap_name='coolwarm_r', min_value=0.0, max_value=1.0
    )
    tactile_locations['label'] = tactile_locations.tactile_paving.apply(lambda r: r.value)
    return create_vector_artifact(
        data=tactile_locations[['osm_id', 'osm_type', 'color', 'label', 'geometry']],
        metadata=ArtifactMetadata(
            name='Tactile Paving',
            summary='Presence of tactile paving at pedestrian crossings (displayed as points), platforms, and stairs',
            description=Path('resources/components/tactile_paving/tactile_paving_description.md').read_text(),
            filename='tactile_paving',
            primary=False,
            tags={Topics.SAFETY},
        ),
        resources=resources,
        legend=Legend(legend_data=get_tactile_paving_legend()),
    )


def build_tactile_paving_chart_artifact(figure: go.Figure, resources: ComputationResources) -> Artifact:
    return create_plotly_chart_artifact(
        figure=figure,
        metadata=ArtifactMetadata(
            name='Distribution of Tactile Paving Categories',
            summary='What percentage of crossings, platforms, and stairs have tactile paving?',
            filename='tactile_paving_summary',
            primary=False,
            tags={Topics.SAFETY},
        ),
        resources=resources,
    )
