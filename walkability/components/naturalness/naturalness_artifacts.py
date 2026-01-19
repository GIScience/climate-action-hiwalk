from pathlib import Path

import geopandas as gpd
import matplotlib
import pandas as pd
import plotly.graph_objects as go
from climatoology.base.artifact import ContinuousLegendData
from climatoology.base.artifact_creators import (
    ArtifactMetadata,
    Legend,
    create_plotly_chart_artifact,
    create_vector_artifact,
)
from climatoology.base.baseoperator import Artifact
from climatoology.base.computation import ComputationResources
from climatoology.base.exception import ClimatoologyUserError
from matplotlib.colors import to_hex
from pydantic_extra_types.color import Color

from walkability.components.utils.misc import Topics


def build_naturalness_artifact(
    naturalness_line_paths: gpd.GeoDataFrame,
    naturalness_polygon_paths: gpd.GeoDataFrame,
    resources: ComputationResources,
    cmap_name: str = 'YlGn',
) -> Artifact:
    naturalness_locations = pd.concat([naturalness_line_paths, naturalness_polygon_paths], ignore_index=True)
    # If no good data is returned (e.g. due to an error), return a text artifact with a simple message
    if naturalness_locations['naturalness'].isna().all():
        raise ClimatoologyUserError(
            'There was an error calculating greenness in this computation. Contact the developers for more information.'
        )

    # Set negative values (e.g. water) to 0, and set nan's to -999 to colour grey for unknown
    naturalness_locations['naturalness_col'] = naturalness_locations['naturalness'].copy()
    naturalness_locations.loc[naturalness_locations['naturalness'] < 0, 'naturalness_col'] = 0
    naturalness_locations.loc[naturalness_locations['naturalness'].isna(), 'naturalness_col'] = -999

    # Clean data for labels
    naturalness_locations['naturalness'] = naturalness_locations['naturalness'].round(2)

    # Define colors and legend
    cmap = matplotlib.colormaps.get(cmap_name)
    cmap.set_under('#808080')
    naturalness_locations['color'] = naturalness_locations['naturalness_col'].apply(lambda v: Color(to_hex(cmap(v))))
    legend = ContinuousLegendData(
        cmap_name=cmap_name,
        ticks={'Low (0)': 0.0, 'High (1)': 1.0},
    )

    # Build artifact
    return create_vector_artifact(
        data=naturalness_locations,
        metadata=ArtifactMetadata(
            name='Path Greenness',
            summary=Path('resources/components/naturalness/caption.md').read_text(),
            description=Path('resources/components/naturalness/description.md').read_text(),
            filename='path_greenness',
            tags={Topics.GREENNESS, Topics.COMFORT},
        ),
        resources=resources,
        label='naturalness',
        legend=Legend(legend_data=legend),
    )


def build_naturalness_summary_bar_artifact(aoi_aggregate: go.Figure, resources: ComputationResources) -> Artifact:
    return create_plotly_chart_artifact(
        figure=aoi_aggregate,
        metadata=ArtifactMetadata(
            name='Distribution of Greenness',
            summary='What length of paths has low, mid, and high NDVI?',
            filename='aggregation_aoi_naturalness_bar',
            primary=True,
            tags={Topics.GREENNESS, Topics.COMFORT, Topics.SUMMARY},
        ),
        resources=resources,
    )
