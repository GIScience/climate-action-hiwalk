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
    get_single_color,
    PavementQualityRating,
    generate_detailed_pavement_quality_mapping_info,
)


def build_paths_artifact(
    paths_line: gpd.GeoDataFrame,
    paths_polygon: gpd.GeoDataFrame,
    ratings: PathRating,
    clip_aoi: shapely.MultiPolygon,
    resources: ComputationResources,
    cmap_name: str = 'RdYlGn',
) -> _Artifact:
    paths_line = paths_line.clip(clip_aoi, keep_geom_type=True)
    paths_polygon = paths_polygon.clip(clip_aoi, keep_geom_type=True)
    sidewalks = pd.concat([paths_line, paths_polygon], ignore_index=True)

    sidewalks['color'] = get_color(sidewalks.rating, cmap_name)
    return create_geojson_artifact(
        features=sidewalks.geometry,
        layer_name='Walkable',
        caption='The layer displays paths in four categories: '
        'a) paths dedicated to pedestrians exclusively '
        'b) paths that are explicitly meant for pedestrians but may be shared with other traffic (e.g. a '
        'road with a sidewalk) '
        'c) paths that probably are walkable but the true status is unknown (e.g. a dirt road) '
        'd) paths that are not walkable but could be (e.g. a residential road without sidewalk).',
        description='The layer excludes paths that are not walkable by definition such as motorways or cycle ways. '
        'The data source is OpenStreetMap.',
        label=sidewalks.category.apply(lambda r: r.name).to_list(),
        color=sidewalks.color.to_list(),
        legend_data={rating[0]: get_single_color(rating[1]) for rating in ratings},
        resources=resources,
        filename='walkable',
    )


def build_connectivity_artifact(
    connectivity: gpd.GeoDataFrame,
    clip_aoi: shapely.MultiPolygon,
    resources: ComputationResources,
    cmap_name: str = 'RdYlGn',
) -> _Artifact:
    connectivity = connectivity.clip(clip_aoi, keep_geom_type=True)
    color = get_color(connectivity.connectivity, cmap_name).to_list()
    legend = ContinuousLegendData(
        cmap_name=cmap_name, ticks={'Low Connectivity': 0, 'Medium Connectivity': 0.5, 'High Connectivity': 1}
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
    resources: ComputationResources,
    cmap_name: str = 'RdYlGn',
) -> _Artifact:
    paths_line['color'] = get_color(paths_line.quality.map(PavementQualityRating), cmap_name)
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
        legend_data={rating: get_single_color(PavementQualityRating[rating]) for rating in PavementQualityRating},
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
            f'The total length of paths in this area is {sum(data.y)}km',
            resources=resources,
            filename=f'aggregation_{region}',
            primary=False,
        )
        chart_artifacts.append(chart_artifact)
    return chart_artifacts
