from pathlib import Path

import geopandas as gpd
import matplotlib
import pandas as pd
from climatoology.base.artifact import (
    ContinuousLegendData,
    create_markdown_artifact,
    create_plotly_chart_artifact,
)
from climatoology.base.baseoperator import _Artifact
from climatoology.base.computation import ComputationResources
from matplotlib.colors import to_hex
from plotly.graph_objects import Figure
from pydantic_extra_types.color import Color

from walkability.components.utils.misc import create_multicolumn_geojson_artifact


def build_naturalness_artifact(
    naturalness_line_paths: gpd.GeoDataFrame,
    naturalness_polygon_paths: gpd.GeoDataFrame,
    resources: ComputationResources,
    cmap_name: str = 'YlGn',
) -> _Artifact:
    naturalness_locations = pd.concat([naturalness_line_paths, naturalness_polygon_paths], ignore_index=True)
    # If no good data is returned (e.g. due to an error), return a text artifact with a simple message
    if naturalness_locations['naturalness'].isna().all():
        text = (
            'There was an error calculating greenness in this computation. Contact the developers for more information.'
        )
        return create_markdown_artifact(
            text=text,
            name='Greenness (Error)',
            tl_dr=text,
            filename='path_naturalness',
            resources=resources,
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
    color = naturalness_locations['naturalness_col'].apply(lambda v: Color(to_hex(cmap(v))))
    legend = ContinuousLegendData(
        cmap_name=cmap_name,
        ticks={'Low (0)': 0.0, 'High (1)': 1.0},
    )

    # Build artifact
    return create_multicolumn_geojson_artifact(
        features=naturalness_locations.geometry,
        layer_name='Greenness',
        caption=Path('resources/components/naturalness/caption.md').read_text(),
        description=Path('resources/components/naturalness/description.md').read_text(),
        label=naturalness_locations.naturalness.to_list(),
        color=color,
        legend_data=legend,
        resources=resources,
        filename='path_greenness',
    )


def build_naturalness_summary_bar_artifact(aoi_aggregate: Figure, resources: ComputationResources) -> _Artifact:
    return create_plotly_chart_artifact(
        figure=aoi_aggregate,
        title='Distribution of Greenness',
        caption='What length of paths has low, mid, and high NDVI?',
        resources=resources,
        filename='aggregation_aoi_naturalness_bar',
        primary=True,
    )
