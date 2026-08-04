import logging
from enum import Enum
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import shapely
from climatoology.base.artifact_creators import (
    Artifact,
    ArtifactMetadata,
    create_plotly_chart_artifact,
    create_vector_artifact,
)
from climatoology.base.computation import ComputationResources
from climatoology.base.exception import ClimatoologyUserError
from mobility_tools.detour_factors import get_detour_factors
from mobility_tools.settings import ORSSettings
from mobility_tools.utils.exceptions import SizeLimitExceededError
from pydantic_extra_types.color import Color

from walkability.components.utils.misc import Topics

log = logging.getLogger(__name__)


def detour_factor_analysis(
    aoi: shapely.MultiPolygon,
    paths: gpd.GeoDataFrame,
    ors_settings: ORSSettings,
    resources: ComputationResources,
) -> list[Artifact]:
    try:
        detour_factors = get_detour_factors(aoi=aoi, paths=paths, ors_settings=ors_settings, profile='foot-walking')
    except SizeLimitExceededError:
        raise ClimatoologyUserError('Detour Factors failed on an aoi too large for computation timeout.')

    hexcell_artifact = build_detour_factor_artifact(detour_factor_data=detour_factors, resources=resources)

    summary = summarise_detour(detour_factors)
    n_inf = sum(np.isinf(detour_factors['detour_factor']))
    summary_artifact = build_detour_summary_artifact(summary, n_inf, resources=resources)

    return [hexcell_artifact, summary_artifact]


def build_detour_factor_artifact(
    detour_factor_data: gpd.GeoDataFrame, resources: ComputationResources, cmap_name: str = 'YlOrRd'
) -> Artifact:
    """Artifact containing a GeoJSON with hex-grid cells and the Detour Factor."""

    data = apply_color_and_label(detour_factor_data, cmap_name)
    data = data[data['detour_category'] != DetourCategory.LOW_DETOUR]

    return create_vector_artifact(
        data=data[['index', 'geometry', 'detour_factor', 'color', 'label']],
        metadata=ArtifactMetadata(
            name='Detour Factor',
            filename='hexgrid_detours',
            summary='Can I reach my surroundings without big detours?',
            description=Path('resources/components/network_analyses/detour_factor/description.md').read_text(),
            tags={Topics.CONNECTIVITY, Topics.BARRIERS},
        ),
        resources=resources,
    )


class DetourCategory(Enum):
    LOW_DETOUR = 0.0
    MEDIUM_DETOUR = 2.0
    HIGH_DETOUR = 3.0
    UNREACHABLE = np.nan


def apply_color_and_label(detour_factor_data: gpd.GeoDataFrame, cmap_name: str = 'YlOrRd') -> gpd.GeoDataFrame:
    def categorize_detour(detour_value):
        if np.isinf(detour_value) or pd.isna(detour_value):
            return DetourCategory.UNREACHABLE
        elif detour_value < DetourCategory.MEDIUM_DETOUR.value:
            return DetourCategory.LOW_DETOUR
        elif detour_value < DetourCategory.HIGH_DETOUR.value:
            return DetourCategory.MEDIUM_DETOUR
        else:
            return DetourCategory.HIGH_DETOUR

    detour_factor_data['detour_category'] = detour_factor_data['detour_factor'].apply(categorize_detour)

    detour_factor_data['color'] = detour_factor_data['detour_category'].map(DETOUR_FACTOR_COLOR_MAP)

    detour_factor_data['label'] = detour_factor_data.detour_category.apply(apply_labels)

    return detour_factor_data


def apply_labels(detour_category: DetourCategory) -> str:
    match detour_category:
        case DetourCategory.MEDIUM_DETOUR:
            return 'Medium Detour'
        case DetourCategory.HIGH_DETOUR:
            return 'High Detour'
        case DetourCategory.LOW_DETOUR:
            return 'Low Detour'
        case DetourCategory.UNREACHABLE:
            return 'Unreachable'


def build_detour_summary_artifact(aoi_aggregate: go.Figure, n_inf: int, resources: ComputationResources) -> Artifact:
    return create_plotly_chart_artifact(
        figure=aoi_aggregate,
        metadata=ArtifactMetadata(
            name='Histogram of Detour Factors',
            summary='How are detour factor values distributed?',
            description=f'The area contains {n_inf} (partly) unreachable hexagon{"" if n_inf == 1 else "s"}.',
            filename='aggregation_aoi_detour',
            primary=True,
            tags={Topics.CONNECTIVITY, Topics.BARRIERS, Topics.SUMMARY},
        ),
        resources=resources,
    )


def summarise_detour(
    detour_factor_data: gpd.GeoDataFrame,
) -> go.Figure:
    log.info('Summarising detour factor stats')

    # Add detour factor categories for labels
    detour_factor_range = {
        'Low Detour': 'Low Detour (0 to 1.99)',
        'Medium Detour': 'Medium Detour (2.0 to 2.99)',
        'High Detour': 'High Detour (>= 3)',
        'Unreachable': 'Unreachable',
    }
    detour_factor_data['label'] = detour_factor_data['label'].map(detour_factor_range)
    detour_factor_data = detour_factor_data.sort_values(
        by='detour_factor',
        ascending=True,
    )

    stats = detour_factor_data.groupby(['label', 'color'], sort=False).size().reset_index(name='count')
    totals = stats['count'].sum()
    colors = stats['color']

    bar_fig = go.Figure(
        data=go.Bar(
            x=stats['label'],
            y=(stats['count'] / totals) * 100,
            marker_color=[c.as_hex() for c in colors],
            hovertemplate='Range: %{x}<br>Percentage: %{y:.2f}%<extra></extra>',
        )
    )

    bar_fig.update_layout(
        title=dict(
            subtitle=dict(text='Percentage', font=dict(size=14)),
        ),
        xaxis_title='Detour Class',
        yaxis_title=None,
        margin=dict(t=30, b=60, l=80, r=30),
    )
    return bar_fig


DETOUR_FACTOR_COLOR_MAP = {
    DetourCategory.LOW_DETOUR: Color('#FFFFE0'),
    DetourCategory.MEDIUM_DETOUR: Color('#eea321'),
    DetourCategory.HIGH_DETOUR: Color('#e75a13'),
    DetourCategory.UNREACHABLE: Color('#808080'),
}
