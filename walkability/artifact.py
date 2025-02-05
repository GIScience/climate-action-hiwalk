from pathlib import Path
from typing import List, Dict, Tuple

import geopandas as gpd
import matplotlib
import matplotlib as mpl
import pandas as pd
import shapely
from climatoology.base.artifact import (
    _Artifact,
    Chart2dData,
    ContinuousLegendData,
    create_chart_artifact,
    create_geojson_artifact,
    create_markdown_artifact,
)
from climatoology.base.computation import ComputationResources
from matplotlib.colors import to_hex
from pydantic_extra_types.color import Color

from walkability.input import PathRating
from walkability.utils import (
    get_color,
    generate_detailed_pavement_quality_mapping_info,
    pathratings_legend_fix,
    get_qualitative_color,
    PavementQuality,
    PathCategory,
)


def build_paths_artifact(
    paths_line: gpd.GeoDataFrame,
    paths_polygon: gpd.GeoDataFrame,
    ratings: PathRating,
    clip_aoi: shapely.MultiPolygon,
    resources: ComputationResources,
    cmap_name: str = 'RdYlBu_r',
) -> _Artifact:
    paths_line = paths_line.clip(clip_aoi, keep_geom_type=True)
    paths_polygon = paths_polygon.clip(clip_aoi, keep_geom_type=True)
    sidewalks = pd.concat([paths_line, paths_polygon], ignore_index=True)

    sidewalks['color'] = sidewalks.category.apply(get_qualitative_color, cmap_name=cmap_name, class_name=PathCategory)
    return create_geojson_artifact(
        features=sidewalks.geometry,
        layer_name='Walkable Path Categories',
        caption=Path('resources/info/path_categories/caption.md').read_text(),
        description=Path('resources/info/path_categories/description.md').read_text(),
        label=sidewalks.category.apply(lambda r: r.name).to_list(),
        color=sidewalks.color.to_list(),
        legend_data={
            pathratings_legend_fix.get(category.value, category.value): get_qualitative_color(
                category, cmap_name, PathCategory
            )
            for category in PathCategory
        },
        resources=resources,
        filename='walkable',
    )


def build_connectivity_artifact(
    connectivity: gpd.GeoDataFrame,
    clip_aoi: shapely.MultiPolygon,
    resources: ComputationResources,
    cmap_name: str = 'coolwarm_r',
) -> _Artifact:
    connectivity = connectivity.clip(clip_aoi, keep_geom_type=True)
    color = get_color(connectivity.connectivity, cmap_name).to_list()
    legend = ContinuousLegendData(
        cmap_name=cmap_name, ticks={'High Connectivity': 1, 'Medium Connectivity': 0.5, 'Low Connectivity': 0}
    )

    return create_geojson_artifact(
        features=connectivity.geometry,
        layer_name='Connectivity',
        filename='connectivity',
        caption=Path('resources/info/connectivity/caption.md').read_text(),
        description=Path('resources/info/connectivity/description.md').read_text(),
        label=connectivity.connectivity.to_list(),
        color=color,
        legend_data=legend,
        resources=resources,
    )


def build_pavement_quality_artifact(
    paths_line: gpd.GeoDataFrame,
    clip_aoi: shapely.MultiPolygon,
    resources: ComputationResources,
    cmap_name: str = 'RdYlBu_r',
) -> _Artifact:
    paths_line = paths_line.clip(clip_aoi, keep_geom_type=True)
    paths_line['color'] = paths_line.quality.apply(
        get_qualitative_color, cmap_name=cmap_name, class_name=PavementQuality
    )
    return create_geojson_artifact(
        features=paths_line.geometry,
        layer_name='Surface Quality',
        caption=Path('resources/info/surface_quality/caption.md').read_text(),
        description=Path('resources/info/surface_quality/description.md').read_text()
        + generate_detailed_pavement_quality_mapping_info(),
        label=paths_line.quality.apply(lambda r: r.name).to_list(),
        color=paths_line.color.to_list(),
        legend_data={
            pathratings_legend_fix.get(quality.value, quality.value): get_qualitative_color(
                quality, cmap_name, PavementQuality
            )
            for quality in PavementQuality
        },
        resources=resources,
        filename='pavement_quality',
    )


def build_areal_summary_artifacts(
    regional_aggregates: Dict[str, Chart2dData], resources: ComputationResources
) -> List[_Artifact]:
    chart_artifacts = []
    for region, data in regional_aggregates.items():
        chart_artifact = create_chart_artifact(
            data=data,
            title=f'Distribution of Path Categories in {region}',
            caption=f'Fraction of the total length of paths for each category compared to the total path length '
            f'of {sum(data.y)} km in this area.',
            resources=resources,
            filename=f'aggregation_{region}',
            primary=False,
        )
        chart_artifacts.append(chart_artifact)
    return chart_artifacts


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
            name='naturalness Score',
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
        caption=Path('resources/info/naturalness/caption.md').read_text(),
        description=Path('resources/info/naturalness/description.md').read_text(),
        label=naturalness.naturalness.to_list(),
        color=color,
        legend_data=legend,
        resources=resources,
        filename='path_naturalness',
    )


def clean_slope_data(slope: pd.Series) -> Tuple[pd.Series, pd.Series]:
    slope = slope.abs()

    norm = mpl.colors.Normalize(vmin=0.0, vmax=12.0)
    slope_color_value = slope.copy()
    slope_color_value.loc[slope_color_value > 12.0] = 12.0
    slope_color_value = slope_color_value.apply(norm)

    return slope, slope_color_value


def build_slope_artifact(
    slope: gpd.GeoDataFrame, resources: ComputationResources, cmap_name: str = 'coolwarm'
) -> _Artifact:
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
        caption=Path('resources/info/slope/caption.md').read_text(),
        description=Path('resources/info/slope/description.md').read_text(),
        label=slope_values.to_list(),
        color=color.to_list(),
        legend_data=legend,
        resources=resources,
        filename='slope',
    )
