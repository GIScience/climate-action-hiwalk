import pandas as pd
import plotly.graph_objects as go
from climatoology.base.artifact import Artifact, ArtifactModality

from walkability.components.shade.shade_analysis import (
    create_shade_paths_chart_artifact,
    create_shade_paths_vector_artifact,
    create_shade_plot,
    shade_analysis,
)


def test_shade_analysis(
    default_path, compute_resources, default_canopy_tiles, default_shade_client, default_shade_config
):
    artifacts = shade_analysis(
        paths=default_path,
        tile_spec=default_canopy_tiles,
        shade_client=default_shade_client,
        shade_config=default_shade_config,
        resources=compute_resources,
    )

    assert len(artifacts) == 2
    assert all([isinstance(a, Artifact) for a in artifacts])


def test_create_shade_paths_vector_artifact(default_path, compute_resources):
    vector_artifact = create_shade_paths_vector_artifact(shaded_paths=default_path, resources=compute_resources)

    assert isinstance(vector_artifact, Artifact)
    assert vector_artifact.modality == ArtifactModality.VECTOR_MAP_LAYER


def test_create_shade_paths_chart_artifact(default_path, compute_resources):
    chart_artifact = create_shade_paths_chart_artifact(shaded_paths=default_path, resources=compute_resources)

    assert isinstance(chart_artifact, Artifact)
    assert chart_artifact.modality == ArtifactModality.CHART_PLOTLY


def test_create_shade_plot():
    summary = pd.DataFrame(
        {
            'shade_category': ['Unshaded', 'Shaded'],
            'length': [2, 8],
            'percent': [20, 80],
        }
    )
    summary = summary.set_index('shade_category')

    bar_chart = create_shade_plot(summary)

    assert isinstance(bar_chart, go.Figure)
    assert bar_chart['data'][0]['name'] == 'Unshaded'
    assert bar_chart['data'][1]['name'] == 'Shaded'
    assert len(bar_chart.data) == 2
