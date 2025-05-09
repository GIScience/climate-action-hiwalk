import logging
from typing import Dict, Tuple

import geopandas as gpd
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import numpy as np
import plotly.graph_objects as go
import shapely
from ohsome import OhsomeClient
from plotly.graph_objects import Figure
from pyproj import CRS

from walkability.components.utils.misc import (
    PATH_RATING_MAP,
    PathCategory,
    generate_colors,
    PAVEMENT_QUALITY_RATING_MAP,
    PavementQuality,
)

log = logging.getLogger(__name__)


def summarise_by_area(
    paths: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    admin_level: int,
    projected_crs: CRS,
    ohsome_client: OhsomeClient,
    length_resolution_m: int = 1000,
) -> Dict[str, Figure]:
    log.info('Summarising walkability stats by area')

    stats = paths.copy()
    stats = stats.loc[stats.geometry.geom_type.isin(('MultiLineString', 'LineString'))]

    minimum_keys = ['admin_level', 'name']
    boundaries = ohsome_client.elements.geometry.post(
        properties='tags',
        bpolys=aoi,
        filter=f'geometry:polygon and boundary=administrative and admin_level={admin_level}',
        clipGeometry=True,
    ).as_dataframe(explode_tags=minimum_keys)
    boundaries = boundaries.loc[boundaries.geometry.geom_type.isin(('MultiPolygon', 'Polygon'))]
    boundaries = boundaries[boundaries.is_valid]
    boundaries = boundaries.reset_index(drop=True)
    if boundaries.shape[0] == 1:
        data = {}
    else:
        log.debug(f'Summarising paths into {boundaries.shape[0]} boundaries')

        stats = stats.overlay(boundaries, how='identity')
        stats = stats.to_crs(projected_crs)
        stats['length'] = stats.length / length_resolution_m

        stats['category'] = stats.category.apply(lambda cat: cat.value)
        stats = stats.groupby(['name', 'category']).aggregate({'length': 'sum'})

        stats['length'] = round(stats['length'], 2)
        stats = stats.reset_index()
        stats_group = stats.groupby('name')

        data = {}
        for name, group in stats_group:
            group['rating'] = group.category.apply(lambda category: PATH_RATING_MAP[PathCategory(category)])
            group = group.sort_values(
                by=['rating'],
                ascending=False,
            )

            summary = group.groupby(['rating', 'category'], sort=True, dropna=False)['length'].sum().reset_index()
            total_length = summary['length'].sum()
            summary['percent'] = summary['length'] / total_length * 100
            stacked_bar_colors = [
                c.as_hex()
                for c in generate_colors(color_by=summary['rating'], min=0.0, max=1.0, cmap_name='coolwarm_r')
            ]

            data[name] = go.Figure()

            for i, (_, row) in enumerate(summary.iterrows()):
                data[name].add_trace(
                    go.Bar(
                        y=['Path Types'],
                        x=[row['percent']],
                        name=row['category'],
                        orientation='h',
                        marker_color=stacked_bar_colors[i],
                        hovertemplate=f"{row['category']}: {row['length']:.2f} km ({row['percent']:.1f}%)<extra></extra>",
                        showlegend=True,
                    )
                )

            data[name].update_layout(
                barmode='stack',
                height=300,
                margin=dict(t=30, b=80, l=30, r=30),
                xaxis_title=f'Percentage of the {round(sum(summary["length"]), 2)} km of paths in each category',
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


def summarise_aoi(
    paths: gpd.GeoDataFrame,
    projected_crs: CRS,
    length_resolution_m: int = 1000,
) -> Tuple[Figure, Figure]:
    log.info('Summarising walkability stats (Walkable Path Categories and Surface Quality)')

    stats = calculate_length(length_resolution_m, paths, projected_crs)

    stats['category'] = stats.category.apply(lambda cat: cat.value)
    stats['quality'] = stats.quality.apply(lambda cat: cat.value)

    stats = stats.reset_index()
    stats['path_rating'] = stats.category.apply(lambda category: PATH_RATING_MAP[PathCategory(category)])
    stats['pavement_quality_rating'] = stats.quality.apply(
        lambda quality: PAVEMENT_QUALITY_RATING_MAP[PavementQuality(quality)]
    )
    stats = stats.sort_values(
        by=['path_rating'],
        ascending=False,
    )

    # Path category stacked bar chart
    summary = stats.groupby(['path_rating', 'category'], sort=True, dropna=False)['length'].sum().reset_index()
    total_length = summary['length'].sum()
    summary['percent'] = summary['length'] / total_length * 100
    stacked_bar_colors = [
        c.as_hex() for c in generate_colors(color_by=summary['path_rating'], min=0.0, max=1.0, cmap_name='coolwarm_r')
    ]

    category_fig_stacked_bar = go.Figure()

    for i, (_, row) in enumerate(summary.iterrows()):
        category_fig_stacked_bar.add_trace(
            go.Bar(
                y=['Path Types'],
                x=[row['percent']],
                name=row['category'],
                orientation='h',
                marker_color=stacked_bar_colors[i],
                hovertemplate=f"{row['category']}: {row['length']:.2f} km ({row['percent']:.1f}%)<extra></extra>",
                showlegend=True,
            )
        )

    category_fig_stacked_bar.update_layout(
        barmode='stack',
        height=300,
        margin=dict(t=30, b=80, l=30, r=30),
        xaxis_title=f'Percentage of the {round(sum(summary["length"]), 2)} km of paths in each category',
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

    stats = stats.sort_values(
        by=['pavement_quality_rating'],
        ascending=False,
    )

    # Pavement quality stacked bar chart
    summary = (
        stats.groupby(['pavement_quality_rating', 'quality'], sort=True, dropna=False)['length'].sum().reset_index()
    )
    total_length = summary['length'].sum()
    summary['percent'] = summary['length'] / total_length * 100
    stacked_bar_colors = [
        c.as_hex()
        for c in generate_colors(color_by=summary['pavement_quality_rating'], min=0.0, max=1.0, cmap_name='coolwarm_r')
    ]

    quality_fig_stacked_bar = go.Figure()

    for i, (_, row) in enumerate(summary.iterrows()):
        quality_fig_stacked_bar.add_trace(
            go.Bar(
                y=['Surface Quality Types'],
                x=[row['percent']],
                name=row['quality'].replace('_', ' '),
                orientation='h',
                marker_color=stacked_bar_colors[i],
                hovertemplate=f"{row['quality'].replace('_', ' ')}: {row['length']:.2f} km ({row['percent']:.1f}%)<extra></extra>",
                showlegend=True,
            )
        )

    quality_fig_stacked_bar.update_layout(
        barmode='stack',
        height=300,
        margin=dict(t=30, b=80, l=30, r=30),
        xaxis_title=f'Percentage of the {round(sum(summary["length"]), 2)} km of paths in each surface quality '
        f'category',
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

    return category_fig_stacked_bar, quality_fig_stacked_bar


def summarise_naturalness(
    paths: gpd.GeoDataFrame,
    projected_crs: CRS,
    length_resolution_m: int = 1000,
) -> Figure:
    log.info('Summarising naturalness stats')
    stats = calculate_length(length_resolution_m, paths, projected_crs)

    # Categorize naturalness values and set negative values (e.g. water) to 0
    stats['naturalness_rating'] = stats['naturalness'].apply(lambda x: 0 if x < 0.3 else (0.5 if x < 0.6 else 1))

    # Add naturalness categories for labels
    naturalness_map = {
        0: 'Low (< 0.3) ',
        0.5: 'Medium (0.3 to 0.6)',
        1: 'High (> 0.6)',
        -999: 'Unknown naturalness',
    }
    stats['naturalness_category'] = stats['naturalness_rating'].map(naturalness_map)

    stats = stats.sort_values(
        by=['naturalness_rating'],
        ascending=False,
    )
    summary = stats.groupby(['naturalness_rating', 'naturalness_category'], sort=True)['length'].sum().reset_index()

    bar_colors = generate_colors(color_by=summary.naturalness_rating, min=0.0, max=1.0, cmap_name='YlGn')

    bar_fig = Figure(
        data=go.Bar(
            x=summary['naturalness_category'],
            y=summary['length'],
            marker_color=[c.as_hex() for c in bar_colors],
            hovertemplate='%{x}: %{y} km <extra></extra>',
        )
    )
    bar_fig.update_layout(
        title=dict(
            subtitle=dict(text='Length (km)', font=dict(size=14)),
        ),
        xaxis_title='Length of paths with different naturalness levels',
        yaxis_title=None,
        margin=dict(t=30, b=60, l=80, r=30),
    )
    return bar_fig


def summarise_slope(
    paths: gpd.GeoDataFrame,
    projected_crs: CRS,
    length_resolution_m: int = 1000,
) -> Figure:
    log.info('Summarising slope stats')
    stats = calculate_length(length_resolution_m, paths, projected_crs)

    # Categorize slope values
    slope_categories = [
        stats['slope'] == 0,
        (stats['slope'] > 0) & (stats['slope'] <= 4),
        (stats['slope'] > 4) & (stats['slope'] <= 8),
        (stats['slope'] > 8) & (stats['slope'] <= 12),
        stats['slope'] > 12,
    ]
    slope_ratings = [0, 0.25, 0.5, 0.75, 1]
    stats['slope_rating'] = np.select(slope_categories, slope_ratings)

    # Add slope categories for labels
    slope_map = {
        0: 'Flat (0%)',
        0.25: 'Gentle slope (0-4%)',
        0.5: 'Moderate slope (4-8%)',
        0.75: 'Considerable slope (8-12%)',
        1: 'Steep (>12%)',
    }
    stats['slope_category'] = stats['slope_rating'].map(slope_map)

    stats = stats.sort_values(by=['slope_rating'])

    summary = stats.groupby(['slope_rating', 'slope_category'], sort=True)['length'].sum().reset_index()

    bar_colors = generate_colors(color_by=summary.slope_rating, min=0.0, max=1.0, cmap_name='coolwarm')

    bar_fig = Figure(
        data=go.Bar(
            x=summary['slope_category'],
            y=summary['length'],
            marker_color=[c.as_hex() for c in bar_colors],
            hovertemplate='%{x}: %{y} km <extra></extra>',
        )
    )
    bar_fig.update_layout(
        title=dict(
            subtitle=dict(text='Length (km)', font=dict(size=14)),
        ),
        xaxis_title=f'Proportionate length of the {round(sum(summary["length"]), 2)} km of paths in each slope category',
        yaxis_title=None,
        margin=dict(t=30, b=60, l=80, r=30),
    )
    return bar_fig


def summarise_detour(
    hexgrid: gpd.GeoDataFrame,
    projected_crs: CRS,
) -> Figure:
    log.info('Summarising detour factor stats')
    stats = hexgrid.dropna(how='any')
    stats = stats.to_crs(projected_crs)

    counts, bin_edges = np.histogram(stats['detour_factor'], bins=30)
    cmap = cm.get_cmap('YlOrRd', len(counts))
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


def calculate_length(length_resolution_m, paths, projected_crs):
    stats = paths.copy()
    stats = stats.loc[stats.geometry.geom_type.isin(('MultiLineString', 'LineString'))]
    stats = stats.to_crs(projected_crs)
    stats['length'] = stats.length / length_resolution_m
    stats['length'] = round(stats['length'], 2)
    return stats
