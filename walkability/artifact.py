from typing import List, Dict
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely
from climatoology.base.artifact import (
    _Artifact,
    create_geojson_artifact,
    create_chart_artifact,
    Chart2dData,
    ContinuousLegendData,
)
from climatoology.base.computation import ComputationResources

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
    cmap_name: str = 'seismic',
) -> _Artifact:
    connectivity = connectivity.clip(clip_aoi, keep_geom_type=True)
    color = get_color(connectivity.connectivity, cmap_name).to_list()
    legend = ContinuousLegendData(
        cmap_name=cmap_name, ticks={'High Connectivity': 0, 'Medium Connectivity': 0.5, 'Low Connectivity': 1}
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
