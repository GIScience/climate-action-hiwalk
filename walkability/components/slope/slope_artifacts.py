from pathlib import Path
from typing import Tuple

import geopandas as gpd
import matplotlib
import pandas as pd
import plotly.graph_objects as go
from climatoology.base.artifact import ArtifactMetadata, ContinuousLegendData, Legend
from climatoology.base.artifact_creators import (
    create_plotly_chart_artifact,
    create_vector_artifact,
)
from climatoology.base.baseoperator import Artifact
from climatoology.base.computation import ComputationResources
from climatoology.base.exception import ClimatoologyUserError
from matplotlib.colors import to_hex
from pydantic_extra_types.color import Color


def clean_slope_data(slope: pd.Series) -> Tuple[pd.Series, pd.Series]:
    slope = slope.abs()

    norm = matplotlib.colors.Normalize(vmin=0.0, vmax=12.0)
    slope_color_value = slope.copy()
    slope_color_value.loc[slope_color_value > 12.0] = 12.0
    slope_color_value = slope_color_value.apply(norm)

    return slope, slope_color_value


def build_slope_artifact(
    slope: gpd.GeoDataFrame, resources: ComputationResources, cmap_name: str = 'coolwarm'
) -> Artifact:
    if slope.slope.isna().all():
        raise ClimatoologyUserError('There was an error calculating slope.')
    slope_values, slope_color_values = clean_slope_data(slope.slope)
    slope['slope_value'] = slope_values

    # Define colors and legend
    cmap = matplotlib.colormaps.get(cmap_name)
    cmap.set_under('#808080')
    slope['color'] = slope_color_values.apply(lambda v: Color(to_hex(cmap(v))))

    legend = ContinuousLegendData(
        cmap_name=cmap_name,
        ticks={
            'Flat (0%)': 0.0,
            'Very Gentle Slope (3%)': 0.25,
            'Moderate Slope (6%)': 0.5,
            'Considerable Slope (9%)': 0.75,
            'Steep (>12%)': 1.0,
        },
    )

    return create_vector_artifact(
        data=slope[['@osmId', 'color', 'slope_values']],
        metadata=ArtifactMetadata(
            name='Slope',
            filename='slope',
            summary=Path('resources/components/slope/caption.md').read_text(),
            description=Path('resources/components/slope/description.md').read_text(),
        ),
        label='slope_values',
        legend=Legend(legend_data=legend),
        resources=resources,
    )


def build_slope_summary_bar_artifact(aoi_aggregate: go.Figure, resources: ComputationResources) -> Artifact:
    return create_plotly_chart_artifact(
        figure=aoi_aggregate,
        metadata=ArtifactMetadata(
            name='Distribution of Slope Categories',
            summary='How is the total length of paths distributed across the slope categories?',
            filename='aggregation_aoi_slope_bar',
            primary=True,
        ),
        resources=resources,
    )
