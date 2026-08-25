import logging

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import shapely
from climatoology.base.artifact import Artifact
from climatoology.base.computation import ComputationResources
from climatoology.base.exception import ClimatoologyUserError
from geopandas import GeoDataFrame
from ohsome_py2.client import OhsomeClient

from walkability.components.tactile_paving.tactile_paving_artifact import (
    build_tactile_paving_artifact,
    build_tactile_paving_chart_artifact,
)
from walkability.components.utils.misc import (
    TACTILE_PAVING_CATEGORY_RATING_MAP,
    TactilePavingCategory,
    TactilePavingInfrastructureCategory,
    fetch_osm_data,
    generate_colors,
)

log = logging.getLogger(__name__)


def tactile_paving_analysis(
    aoi: shapely.MultiPolygon,
    ohsome: OhsomeClient,
    resources: ComputationResources,
) -> list[Artifact]:
    tactile_paths_all = get_tactile_paving_osm_data(aoi=aoi, ohsome=ohsome)
    tactile_paving_categorised = get_tactile_paving(tactile_paths_all=tactile_paths_all)
    tactile_paving_chart = plot_tactile_paving(tactile_paving_categorised)
    tactile_paving_artifact = build_tactile_paving_artifact(
        tactile_locations=tactile_paving_categorised, resources=resources
    )
    tactile_paving_summary_artifact = build_tactile_paving_chart_artifact(
        figure=tactile_paving_chart, resources=resources
    )
    return [tactile_paving_artifact, tactile_paving_summary_artifact]


def get_tactile_paving_osm_data(aoi: shapely.MultiPolygon, ohsome: OhsomeClient) -> gpd.GeoDataFrame:
    log.debug('Extracting OSM data for tactile paving analysis')
    tactile_line_paths = fetch_osm_data(aoi=aoi, osm_filter=tactile_paving_ohsome_filter('line'), ohsome=ohsome)
    tactile_polygon_paths = fetch_osm_data(aoi=aoi, osm_filter=tactile_paving_ohsome_filter('polygon'), ohsome=ohsome)
    crossings = fetch_osm_data(aoi=aoi, osm_filter='highway=crossing', ohsome=ohsome)

    log.debug('Finished extracting OSM data for tactile paving analysis')

    if tactile_line_paths.empty and tactile_polygon_paths.empty and crossings.empty:
        raise ClimatoologyUserError(
            'No accessible walking infrastructure that is relevant for tactile paving was found in your area. Please select a larger area'
        )
    tactile_paths_all = gpd.GeoDataFrame(pd.concat([tactile_line_paths, tactile_polygon_paths, crossings]))

    return tactile_paths_all


def tactile_paving_ohsome_filter(geometry_type: str) -> str:
    return str(
        f'geometry:{geometry_type} and '
        '(highway in (bus_stop, platform, steps) or public_transport=platform or railway=platform)'
    )


def get_tactile_paving(tactile_paths_all: gpd.GeoDataFrame) -> GeoDataFrame:
    """
    Filter relevant walking infrastructure, categorise infrastructure into crossings, platforms, and stairs, and categorise tactile paving

    :param tactile_paths_all: Walking infrastructure relevant for tactile paving in the computation area
    :return: gpd.GeoDataFrame with infrastructure categories and tactile paving categories
    """
    tactile_paths_all['infrastructure_category'] = tactile_paths_all.apply(
        tactile_paving_infrastructure_categorisation, axis=1
    )
    tactile_paving_categorised = tactile_paving_categorisation(tactile_paths_all)
    return tactile_paving_categorised


def tactile_paving_infrastructure_categorisation(row: pd.Series) -> TactilePavingInfrastructureCategory:
    """
    Categorise pedestrian infrastructure relevant for tactile paving into crossings, platforms, and stairs

    :param row: Row of the GeoDataframe containing crossings and paths relevant for tactile paving
    :return: Infrastructure category of the respective row
    """
    log.debug('Tactile paving infrastructure categorisation')
    d = row['osm_tags']

    if d.get('highway') == 'crossing':
        return TactilePavingInfrastructureCategory.CROSSINGS

    if (
        d.get('highway') in ['bus_stop', 'platform']
        or d.get('public_transport') == 'platform'
        or d.get('railway') == 'platform'
    ):
        return TactilePavingInfrastructureCategory.PLATFORMS

    if d.get('highway') == 'steps':
        return TactilePavingInfrastructureCategory.STAIRS

    return None


def tactile_paving_categorisation(
    geometries: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Categorise pedestrian infrastructure by presence and quality of tactile paving. Add tactile paving rating (a value between 0 and 1).

    :param geometries: GeoDataframe containing crossings and paths relevant for tactile paving
    :return: GeoDataframe with tactile paving category and tactile paving rating
    """
    log.debug('Tactile paving categorisation')
    geometries['tactile_paving'] = geometries.apply(apply_tactile_paving_filters, axis=1, result_type='reduce')

    geometries['tactile_paving_rating'] = geometries.tactile_paving.apply(
        lambda tactile_paving: TACTILE_PAVING_CATEGORY_RATING_MAP[tactile_paving]
    )
    return geometries


def apply_tactile_paving_filters(row: pd.Series) -> TactilePavingCategory:
    """
    Apply OSM filters to categorise geometry by presence and quality of tactile paving.

    :param row: Row of the GeoDataframe containing crossings and paths relevant for tactile paving
    :return: Tactile paving category of the respective row
    """

    match row['osm_tags'].get('tactile_paving'):
        case 'yes':
            return TactilePavingCategory.YES
        case 'primitive':
            return TactilePavingCategory.OTHER_SIGNS
        case 'partial':
            return TactilePavingCategory.PARTIAL
        case 'no':
            return TactilePavingCategory.NO
        case _:
            return TactilePavingCategory.UNKNOWN


def plot_tactile_paving(df: gpd.GeoDataFrame) -> go.Figure:
    """
    Build horizontal bar chart with distribution of Tactile Paving Categories for crossings, platforms, and stairs.

    :param df: gpd.GeoDataFrame with infrastructure categories and tactile paving categories
    :return: go.Figure
    """
    df = df.copy()
    df['color'] = [
        c.as_hex()
        for c in generate_colors(
            color_by=df['tactile_paving_rating'], min_value=0.0, max_value=1.0, cmap_name='coolwarm_r'
        )
    ]
    df['infrastructure_category'] = df['infrastructure_category'].apply(lambda x: x.value if x is not None else x)
    counts = df.groupby(['infrastructure_category', 'tactile_paving'], sort=False).size().reset_index(name='count')
    counts['percentage'] = counts.groupby('infrastructure_category', sort=False)['count'].transform(
        lambda x: 100 * x / x.sum()
    )
    categories = counts['infrastructure_category'].unique()
    rating_lookup = df.drop_duplicates(subset=['tactile_paving']).set_index('tactile_paving')['tactile_paving_rating']
    color_lookup = df.drop_duplicates(subset=['tactile_paving']).set_index('tactile_paving')['color']
    paving_values = rating_lookup.sort_values().index.tolist()
    fig = go.Figure()
    for i, paving_value in enumerate(paving_values):
        subset = counts[counts['tactile_paving'] == paving_value]
        subset = subset.set_index('infrastructure_category').reindex(categories)
        fig.add_trace(
            go.Bar(
                name=paving_value.value,
                y=categories,
                x=subset['percentage'].fillna(0),
                orientation='h',
                text=subset['percentage'].fillna(0).round(1).astype(str) + '%',
                textposition='inside',
                marker_color=color_lookup[paving_value],
                customdata=subset['count'].fillna(0).astype(int),
                hovertemplate=f'{paving_value.value}: ' + '%{customdata} %{y}<extra></extra>',
                legendrank=len(paving_values) - i,
            )
        )
    fig.update_layout(
        barmode='stack',
        xaxis_title='Percentage of rows (%)',
        legend_title='Tactile Paving',
        yaxis=dict(
            tickfont=dict(size=13),
            ticksuffix='  ',
        ),
    )
    return fig
