import logging
from enum import Enum
from pathlib import Path

import geopandas as gpd
import matplotlib.colors as mcolors
import matplotlib.pyplot as pyplt
import numpy as np
import plotly.graph_objects as go
import shapely
from climatoology.base.artifact import (
    _Artifact,
    create_geojson_artifact,
    create_plotly_chart_artifact,
)
from climatoology.base.computation import ComputationResources
from climatoology.utility.exception import ClimatoologyUserError
from mobility_tools.detour_factors import get_detour_factors
from mobility_tools.ors_settings import ORSSettings
from mobility_tools.utils.exceptions import SizeLimitExceededError
from pydantic_extra_types.color import Color

from walkability.components.utils.misc import Topics

log = logging.getLogger(__name__)


def detour_factor_analysis(
    aoi: shapely.MultiPolygon,
    paths: gpd.GeoDataFrame,
    ors_settings: ORSSettings,
    resources: ComputationResources,
) -> list[_Artifact]:
    try:
        detour_factors = get_detour_factors(aoi=aoi, paths=paths, ors_settings=ors_settings, profile='foot-walking')
    except SizeLimitExceededError:
        raise ClimatoologyUserError('Detour Factors failed on an aoi too large for computation timeout.')

    hexcell_artifact = build_detour_factor_artifact(detour_factor_data=detour_factors, resources=resources)

    summary = summarise_detour(detour_factors)
    summary_artifact = build_detour_summary_artifact(summary, resources=resources)

    return [hexcell_artifact, summary_artifact]


def build_detour_factor_artifact(
    detour_factor_data: gpd.GeoDataFrame, resources: ComputationResources, cmap_name: str = 'YlOrRd'
) -> _Artifact:
    """Artifact containing a GeoJSON with hex-grid cells and the Detour Factor."""

    data = apply_color_and_label(detour_factor_data, cmap_name)

    return create_geojson_artifact(
        features=data.geometry,
        layer_name='Detour Factor',
        filename='hexgrid_detours',
        caption='Can I reach my surroundings without big detours?',
        description=Path('resources/components/network_analyses/detour_factor/description.md').read_text(),
        label=data.label.to_list(),
        color=data.color.to_list(),
        resources=resources,
        tags={Topics.CONNECTIVITY, Topics.BARRIERS},
    )


class DetourCategory(Enum):
    LOW_DETOUR = 0.0
    MEDIUM_DETOUR = 2.0
    HIGH_DETOUR = 3.0
    UNREACHABLE = np.nan


def apply_color_and_label(detour_factor_data: gpd.GeoDataFrame, cmap_name: str = 'YlOrRd') -> gpd.GeoDataFrame:
    def categorize_detour(detour_value):
        if detour_value < DetourCategory.MEDIUM_DETOUR.value:
            return DetourCategory.LOW_DETOUR
        elif detour_value < DetourCategory.HIGH_DETOUR.value:
            return DetourCategory.MEDIUM_DETOUR
        elif detour_value >= DetourCategory.HIGH_DETOUR.value:
            return DetourCategory.HIGH_DETOUR
        else:
            return DetourCategory.UNREACHABLE

    detour_factor_data['detour_category'] = detour_factor_data['detour_factor'].apply(categorize_detour)
    detour_factor_data_no_low = detour_factor_data[detour_factor_data['detour_category'] != DetourCategory.LOW_DETOUR]

    detour_factor_data_no_low['color'] = detour_factor_data_no_low['detour_category'].map(DETOUR_FACTOR_COLOR_MAP)

    detour_factor_data_no_low['label'] = detour_factor_data_no_low.detour_category.apply(apply_labels)

    return detour_factor_data_no_low


def apply_labels(detour_category: DetourCategory) -> str:
    match detour_category:
        case DetourCategory.MEDIUM_DETOUR:
            return 'Medium Detour'
        case DetourCategory.HIGH_DETOUR:
            return 'High Detour'
        case DetourCategory.UNREACHABLE:
            return 'Unreachable'


def build_detour_summary_artifact(aoi_aggregate: go.Figure, resources: ComputationResources) -> _Artifact:
    n_inf = sum(np.isinf(aoi_aggregate['data'][0]['x']))
    return create_plotly_chart_artifact(
        figure=aoi_aggregate,
        title='Histogram of Detour Factors',
        caption='How are detour factor values distributed?',
        description=f'The area contains {n_inf} (partly) unreachable hexagon{"" if n_inf == 1 else "s"}.',
        resources=resources,
        filename='aggregation_aoi_detour',
        primary=True,
        tags={Topics.CONNECTIVITY, Topics.BARRIERS, Topics.SUMMARY},
    )


def summarise_detour(
    hexgrid: gpd.GeoDataFrame,
) -> go.Figure:
    log.info('Summarising detour factor stats')
    stats = hexgrid.dropna(how='any')

    min_value = stats['detour_factor'].min()
    max_value = stats.loc[stats['detour_factor'] != np.inf, 'detour_factor'].max()
    counts, bin_edges = np.histogram(stats['detour_factor'], bins=30, range=(min_value, max_value))

    cmap = pyplt.get_cmap('YlOrRd', len(counts))
    colors = [mcolors.to_hex(cmap(i)) for i in range(len(counts))]

    histogram = go.Histogram(
        x=stats['detour_factor'],
        nbinsx=30,
        histnorm='percent',
        marker=dict(color=colors),
        hovertemplate='Range: %{x}<br>Percentage: %{y:.2f}%<extra></extra>',
    )

    detour_fig = go.Figure(data=[histogram])

    detour_fig.update_layout(
        title=dict(
            subtitle=dict(text='Percentage', font=dict(size=14)),
        ),
        xaxis_title='Detour Factor',
        yaxis_title=None,
        margin=dict(t=30, b=60, l=80, r=30),
    )
    return detour_fig


DETOUR_FACTOR_COLOR_MAP = {
    DetourCategory.MEDIUM_DETOUR: Color('#eea321'),
    DetourCategory.HIGH_DETOUR: Color('#e75a13'),
    DetourCategory.UNREACHABLE: Color('#990404'),
}
