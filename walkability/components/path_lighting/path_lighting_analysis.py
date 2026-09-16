import logging

import geopandas as gpd
import pandas as pd
import plotly.graph_objs as go
from climatoology.base.artifact import Artifact
from climatoology.base.computation import ComputationResources
from geopandas import GeoDataFrame

from walkability.components.path_lighting.path_lighting_artifact import (
    build_path_lighting_artifact,
    build_path_lighting_chart_artifact,
)
from walkability.components.utils.geometry import calculate_length
from walkability.components.utils.misc import PATH_LIGHTING_CATEGORY_RATING_MAP, PathLightingCategory, generate_colors

log = logging.getLogger(__name__)


def path_lighting_analysis(
    line_paths: gpd.GeoDataFrame,
    polygon_paths: gpd.GeoDataFrame,
    resources: ComputationResources,
) -> list[Artifact]:
    light_paths_all = get_path_lighting(line_paths=line_paths, polygon_paths=polygon_paths)
    light_path_artifact = build_path_lighting_artifact(light_locations=light_paths_all, resources=resources)

    light_chart = summarise_path_lighting(light_paths_all)
    light_chart_artifact = build_path_lighting_chart_artifact(figure=light_chart, resources=resources)

    return [light_path_artifact, light_chart_artifact]


def get_path_lighting(line_paths: GeoDataFrame, polygon_paths: GeoDataFrame) -> GeoDataFrame:
    light_path = []
    if not line_paths.empty:
        paths_light = path_lighting_categorisation(geometries=line_paths)
        light_path.append(paths_light)
    if not polygon_paths.empty:
        polygons_light = path_lighting_categorisation(geometries=polygon_paths)
        light_path.append(polygons_light)
    light_paths_all: gpd.GeoDataFrame = pd.concat(light_path)
    return light_paths_all


def path_lighting_categorisation(
    geometries: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    log.debug('Path Lighting categorisation')
    geometries['path_lighting'] = geometries.apply(apply_path_lighting_filters, axis=1, result_type='reduce')

    geometries['path_lighting_rating'] = geometries.path_lighting.apply(
        lambda path_lighting: PATH_LIGHTING_CATEGORY_RATING_MAP[path_lighting]
    )
    return geometries


def apply_path_lighting_filters(row: pd.Series) -> PathLightingCategory:
    path_lighting_tag = row['osm_tags'].get('lit')

    if path_lighting_tag is None:
        if row['osm_tags'].get('lit_by_led') == 'yes' or row['osm_tags'].get('lit_by_gaslight') == 'yes':
            path_lighting_tag = 'yes'

    match path_lighting_tag:
        case 'yes' | '24/7':
            return PathLightingCategory.YES
        case 'automatic':
            return PathLightingCategory.AUTOMATIC
        case 'limited':
            return PathLightingCategory.LIMITED
        case 'no' | 'disused':
            return PathLightingCategory.NO
        case _:
            return PathLightingCategory.UNKNOWN


def summarise_path_lighting(light_paths_all: gpd.GeoDataFrame, length_resolution_m: int = 1000) -> go.Figure:
    paths = light_paths_all[light_paths_all.geometry.geom_type.isin(('LineString', 'MultiLineString'))]
    stats = calculate_length(length_resolution_m, paths, paths.estimate_utm_crs())

    stats['path_lighting_label'] = stats['path_lighting'].apply(lambda category: category.value.capitalize())
    stats = stats.sort_values(by=['path_lighting_rating'], ascending=False)

    summary = (
        stats.groupby(['path_lighting_rating', 'path_lighting_label'], sort=True, dropna=False)['length']
        .sum()
        .reset_index()
    )
    summary['percent'] = summary['length'] / summary['length'].sum() * 100
    summary = summary.set_index('path_lighting_label').rename(columns={'path_lighting_rating': 'rating'})

    return create_path_lighting_chart_plot(summary)


def create_path_lighting_chart_plot(summary: pd.DataFrame) -> go.Figure:
    colors = generate_colors(color_by=summary['rating'], cmap_name='coolwarm_r', min_value=0.0, max_value=1.0)

    data = go.Figure()
    for i, (category, row) in enumerate(summary.iterrows()):
        data.add_trace(
            go.Bar(
                y=['Lighting'],  # placeholder for y axis label (which is hidden anyway)
                x=[row['percent']],
                name=category,
                orientation='h',
                marker_color=colors.iloc[i].as_hex(),
                hovertemplate=f'{category}: {row["length"]:.0f} km ({row["percent"]:.1f}%)<extra></extra>',
                showlegend=True,
                legendrank=len(summary) - i,
            )
        )
        data.update_layout(
            barmode='stack',
            height=300,
            margin=dict(t=30, b=80, l=30, r=30),
            xaxis_title=f'Percentage of the {summary["length"].sum():.0f} km of paths that are lit.',
            yaxis=dict(showticklabels=False),
            legend=dict(
                orientation='h',
                yanchor='top',
                y=-1,
                xanchor='center',
                x=0.5,
                font=dict(size=12),
            ),
        )

    return data
