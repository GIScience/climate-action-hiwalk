from pathlib import Path
from climatoology.base.baseoperator import _Artifact
from climatoology.base.computation import ComputationResources
from climatoology.base.artifact import ContinuousLegendData, create_geojson_artifact, create_markdown_artifact
import geopandas as gpd
import matplotlib
from matplotlib.colors import to_hex
from pydantic_extra_types.color import Color


def build_naturalness_artifact(
    naturalness: gpd.GeoDataFrame,
    resources: ComputationResources,
    cmap_name: str = 'YlGn',
) -> _Artifact:
    # If no good data is returned (e.g. due to an error), return a text artifact with a simple message
    if naturalness['naturalness'].isna().all():
        text = 'There was an error calculating naturalness in this computation. Contact the developers for more information.'
        return create_markdown_artifact(
            text=text,
            name='Naturalness Score (Error)',
            tl_dr=text,
            filename='path_naturalness',
            resources=resources,
        )

    # Set negative values (e.g. water) to 0, and set nan's to -999 to colour grey for unknown
    naturalness['naturalness_col'] = naturalness['naturalness'].copy()
    naturalness.loc[naturalness['naturalness'] < 0, 'naturalness_col'] = 0
    naturalness.loc[naturalness['naturalness'].isna(), 'naturalness_col'] = -999

    # Clean data for labels
    naturalness['naturalness'] = naturalness['naturalness'].round(2)

    # Define colors and legend
    cmap = matplotlib.colormaps.get(cmap_name)
    cmap.set_under('#808080')
    color = naturalness['naturalness_col'].apply(lambda v: Color(to_hex(cmap(v))))
    legend = ContinuousLegendData(
        cmap_name=cmap_name,
        ticks={'Low naturalness (Score=0)': 0.0, 'Moderate naturalness': 0.5, 'High naturalness (Score=1)': 1.0},
    )

    # Build artifact
    return create_geojson_artifact(
        features=naturalness.geometry,
        layer_name='Naturalness Score',
        caption=Path('resources/components/naturalness/caption.md').read_text(),
        description=Path('resources/components/naturalness/description.md').read_text(),
        label=naturalness.naturalness.to_list(),
        color=color,
        legend_data=legend,
        resources=resources,
        filename='path_naturalness',
    )
