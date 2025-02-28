from pathlib import Path
from typing import Tuple
from climatoology.base.baseoperator import _Artifact
from climatoology.base.computation import ComputationResources
from climatoology.base.artifact import ContinuousLegendData, create_geojson_artifact, create_markdown_artifact

import geopandas as gpd
import matplotlib
from matplotlib.colors import to_hex
import pandas as pd
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
) -> _Artifact:
    if slope.slope.isna().all():
        text = 'There was an error calculating slope in this computation. Contact the developers for more information.'
        return create_markdown_artifact(
            text=text,
            name='Slope (Error)',
            tl_dr=text,
            filename='slope',
            resources=resources,
        )
    slope_values, slope_color_values = clean_slope_data(slope.slope)

    # Define colors and legend
    cmap = matplotlib.colormaps.get(cmap_name)
    cmap.set_under('#808080')
    color = slope_color_values.apply(lambda v: Color(to_hex(cmap(v))))

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

    return create_geojson_artifact(
        features=slope.geometry,
        layer_name='Slope',
        caption=Path('resources/components/slope/caption.md').read_text(),
        description=Path('resources/components/slope/description.md').read_text(),
        label=slope_values.to_list(),
        color=color.to_list(),
        legend_data=legend,
        resources=resources,
        filename='slope',
    )
