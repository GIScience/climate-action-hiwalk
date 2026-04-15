import logging
from pathlib import Path

import geopandas as gpd
import matplotlib.colors as mcolors
import matplotlib.pyplot as pyplt
import numpy as np
import plotly.graph_objects as go
from climatoology.base.artifact import Artifact, ArtifactMetadata, ContinuousLegendData, Legend
from climatoology.base.artifact_creators import create_plotly_chart_artifact, create_vector_artifact
from climatoology.base.computation import ComputationResources
from climatoology.base.exception import ClimatoologyUserError
from mobility_tools.settings import S3Settings
from mobility_tools.slope import get_paths_slopes
from plotly.graph_objs import Figure

from walkability.components.categorise_paths.path_categorisation import PathCategory
from walkability.components.utils.misc import Topics, generate_colors

log = logging.getLogger(__name__)


def compute_slope_analysis(
    paths: gpd.GeoDataFrame, s3settings: S3Settings, resources: ComputationResources
) -> list[Artifact]:
    log.debug('Computing slopes for paths')

    multi_line_paths = paths.loc[paths.category.isin(PathCategory.get_visible())].copy(deep=False)
    line_string_paths = multi_line_paths.set_index('@osmId').explode(ignore_index=False)
    line_string_paths = line_string_paths[line_string_paths.geom_type.str.contains('LineString')].reset_index()

    if line_string_paths.empty:
        raise ClimatoologyUserError('No linear paths to calculate slope for.')

    # Calculate the slope for each path segment.
    paths_with_slopes = get_paths_slopes(line_string_paths, s3settings, segment_length=15)
    paths_with_slopes['slope'] = paths_with_slopes['slope'].abs()

    slope_artifact = build_slope_artifact(path_slopes_data=paths_with_slopes, resources=resources)

    slope_summary = summarise_slope(paths_with_slopes)
    slope_summary_artifact = build_slope_summary_artifact(slope_summary, resources)

    return [slope_artifact, slope_summary_artifact]


def build_slope_artifact(
    path_slopes_data: gpd.GeoDataFrame,
    resources: ComputationResources,
    cmap_name: str = 'coolwarm',
) -> Artifact:
    legend_lower_bound, legend_upper_bound = 0, 12
    path_slopes_data['color'] = generate_colors(
        path_slopes_data['slope'],
        cmap_name,
        min_value=legend_lower_bound,
        max_value=legend_upper_bound,
    )

    legend = Legend(
        legend_data=ContinuousLegendData(
            cmap_name=cmap_name,
            ticks={
                f'Flat {legend_lower_bound}%': 0.0,
                'Very Gentle Slope (3%)': 0.25,
                'Moderate Slope (6%)': 0.5,
                'Considerable Slope (9%)': 0.75,
                f'Steep (> {legend_upper_bound}%)': 1.0,
            },
        )
    )

    metadata = ArtifactMetadata(
        name='Slope',
        primary=True,
        tags={Topics.BARRIERS},
        filename='slope',
        summary='How steep is my path?',
        description=Path('resources/components/slope/description.md').read_text(),
    )

    return create_vector_artifact(
        data=path_slopes_data,
        metadata=metadata,
        resources=resources,
        label='slope',
        legend=legend,
    )


def summarise_slope(
    path_slopes_data: gpd.GeoDataFrame,
    cmap_name: str = 'coolwarm',
) -> Figure:
    log.info('Summarising slope stats')
    stats = path_slopes_data.dropna(how='any')

    lower_bound, upper_bound = 0, 12
    clipped = stats['slope'].clip(lower=lower_bound, upper=upper_bound)

    bins = 13
    counts, bin_edges = np.histogram(clipped, bins=bins)

    cmap = pyplt.get_cmap(cmap_name, len(counts))
    colors = [mcolors.to_hex(cmap(i)) for i in range(len(counts))]

    histogram = go.Histogram(
        x=clipped,
        nbinsx=20,
        histnorm='percent',
        marker=dict(color=colors),
        hovertemplate='Range: %{x}<br>Percentage: %{y:.2f}%<extra></extra>',
        xbins=dict(start=lower_bound, end=upper_bound, size=(upper_bound - lower_bound) / bins),
    )

    slope_fig = go.Figure(data=[histogram])

    # Replace the last tick label with '>12'
    tick_vals = list(bin_edges[::3])  # every 3rd edge to avoid crowding
    tick_text = [str(round(v)) for v in tick_vals]
    tick_text[-1] = '≥12'

    slope_fig.update_layout(
        title=dict(
            subtitle=dict(text='Frequency', font=dict(size=14)),
        ),
        xaxis=dict(
            title='Slope [%]',
            range=[lower_bound, upper_bound],
            tickvals=tick_vals,
            ticktext=tick_text,
        ),
        yaxis_title=None,
        margin=dict(t=30, b=60, l=80, r=30),
    )

    return slope_fig


def build_slope_summary_artifact(aoi_aggregate: Figure, resources: ComputationResources) -> Artifact:
    metadata = ArtifactMetadata(
        name='Histogram of Slope Values',
        primary=True,
        tags={Topics.BARRIERS, Topics.SUMMARY},
        filename='aggregation_aoi_slope',
        summary='How are slope values distributed?',
    )

    return create_plotly_chart_artifact(figure=aoi_aggregate, metadata=metadata, resources=resources)
