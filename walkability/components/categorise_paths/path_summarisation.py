import logging
from typing import Dict, Tuple

import geopandas as gpd
import plotly.graph_objects as go
import shapely
from ohsome import OhsomeClient
from pyproj import CRS

from walkability.components.utils.geometry import calculate_length
from walkability.components.utils.misc import (
    PATH_RATING_MAP,
    PAVEMENT_QUALITY_RATING_MAP,
    PathCategory,
    PavementQuality,
    generate_colors,
)

log = logging.getLogger(__name__)


def summarise_by_area(
    paths: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    admin_level: int,
    projected_crs: CRS,
    ohsome_client: OhsomeClient,
    length_resolution_m: int = 1000,
) -> Dict[str, go.Figure]:
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
                for c in generate_colors(
                    color_by=summary['rating'], min_value=0.0, max_value=1.0, cmap_name='coolwarm_r'
                )
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
                        hovertemplate=f'{row["category"]}: {row["length"]:.2f} km ({row["percent"]:.1f}%)<extra></extra>',
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
) -> Tuple[go.Figure, go.Figure]:
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
        c.as_hex()
        for c in generate_colors(color_by=summary['path_rating'], min_value=0.0, max_value=1.0, cmap_name='coolwarm_r')
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
                hovertemplate=f'{row["category"]}: {row["length"]:.2f} km ({row["percent"]:.1f}%)<extra></extra>',
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
        for c in generate_colors(
            color_by=summary['pavement_quality_rating'], min_value=0.0, max_value=1.0, cmap_name='coolwarm_r'
        )
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
                hovertemplate=f'{row["quality"].replace("_", " ")}: {row["length"]:.2f} km ({row["percent"]:.1f}%)<extra></extra>',
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
