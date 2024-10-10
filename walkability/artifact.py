from typing import List, Dict

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
        layer_name='Walkable',
        caption='Categories of the pedestrian paths based on the share with other road users.',
        description='Explanation of the different categories (from good to bad):\n'
        '* Dedicated exclusive: dedicated footways without other traffic close by.\n'
        '* Dedicated separated: dedicated footways with other traffic close by. This means for example sidewalks or segregated bike and footways (VZ 241, in Germany).\n'
        '* Designated shared with bikes: Footways shared with bikes, typically either a common foot and bikeway (VZ 240, in Germany) or footways where bikes are allowed to ride on (zVZ 1022-10, in Germany).\n'
        '* Shared with motorized traffic low speed: Streets without a sidewalk, with low speed limits, such as living streets or service ways.\n'
        '* Shared with motorized traffic medium speed: Streets without a sidewalk, with medium speed limits up to 30 km/h.\n'
        '* Shared with motorized traffic high speed: Streets without a sidewalk, with higher speed limits up to 50 km/h.\n'
        '* Not Walkable: Paths where walking is forbidden (e.g. tunnels, private or military streets) or streets without a sidewalk and with speed limits higher than 50 km/h.\n'
        '* Unknown: Paths that could not be fit in any of the above categories because of missing information.\n\n'
        'The data source is OpenStreetMap.',
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
        cmap_name=cmap_name, ticks={'Low Connectivity': 1, 'Medium Connectivity': 0.5, 'High Connectivity': 0}
    )

    return create_geojson_artifact(
        features=connectivity.geometry,
        layer_name='Connectivity',
        primary=False,
        filename='connectivity',
        caption='Map of connectivity scores.',
        description='Each path is evaluated based on the reachability of other paths within the area of interest. '
        'Reachability or connectivity is defined as the share of locations that can be reached by foot in '
        'reference to an optimum where all locations are directly connected "as the crow flies".',
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
        layer_name='Pavement Quality',
        caption='The layer displays the pavement quality for the accessible paths of the walkable layer.',
        description='Based on the values of the `smoothness`, `surface` and `tracktype` tags of OpenStreetMap (in order of importance). '
        'If there is no specification for the pavement of non-exlusive footways, the quality of accompanying roads is adopted if available and labelled as *potential*. '
        'Some surface types, such as gravel, are also labelled *potential* as they can exhibit a wide variation in their maintenance status (see table below).\n\n'
        'Full list of tag-value-ranking combinations:\n\n'
        '' + generate_detailed_pavement_quality_mapping_info(),
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
            title=region,
            caption='The distribution of paths categories for this administrative area. '
            f'The total length of paths in this area is {sum(data.y)} km',
            resources=resources,
            filename=f'aggregation_{region}',
            primary=False,
        )
        chart_artifacts.append(chart_artifact)
    return chart_artifacts
