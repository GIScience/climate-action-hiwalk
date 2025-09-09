import logging

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from climatoology.base.artifact import _Artifact, create_geojson_artifact
from climatoology.base.computation import ComputationResources
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color

from walkability.components.utils.geometry import get_buffered_aoi
from walkability.components.utils.misc import generate_colors
from walkability.components.utils.ors_settings import ORSSettings
from walkability.components.wellness.benches_and_drinking_water import PointsOfInterest, get_pois

log = logging.getLogger(__name__)
N_BINS = 5


def compute_wellness_artifacts(
    paths: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    max_walking_distance_map: dict[PointsOfInterest, float],
    ohsome_client: OhsomeClient,
    ors_settings: ORSSettings,
    resources: ComputationResources,
) -> list[_Artifact]:
    artifacts = []
    for poi in [PointsOfInterest.DRINKING_WATER, PointsOfInterest.SEATING]:
        log.debug(f'Computing Wellness for {poi}')
        max_walking_distance = max_walking_distance_map[poi]
        step_size = int(max_walking_distance / N_BINS)
        bins = [x for x in range(step_size, int(max_walking_distance) + 1, step_size)]
        max_walking_distance = max(bins)

        buffered_aoi = get_buffered_aoi(aoi, max_walking_distance)
        enriched_paths = get_pois(
            paths=paths,
            aoi=buffered_aoi,
            poi=poi,
            bins=bins,
            ohsome_client=ohsome_client,
            ors_settings=ors_settings,
        )
        enriched_paths = enriched_paths.clip(aoi)

        isodistance_artifact = build_isodistance_artifact(
            resources=resources, data=enriched_paths, max_walking_distance=max_walking_distance, poi=poi, bins=bins
        )
        artifacts.append(isodistance_artifact)

    return artifacts


def build_isodistance_artifact(
    resources: ComputationResources,
    data: gpd.GeoDataFrame,
    poi: PointsOfInterest,
    bins: list[int],
    max_walking_distance: float,
) -> _Artifact:
    log.debug('Building isodistance artifact')
    cleaned_data = clean_data(data, max_walking_distance, min_value=min(bins), poi=poi)

    legend = {}
    unique_labels = cleaned_data.sort_values('value').label.unique()
    for label in unique_labels:
        legend_color = cleaned_data.loc[cleaned_data['label'] == label, 'color'].mode().loc[0]
        legend.update({label: legend_color})

    return create_geojson_artifact(
        features=data.geometry,
        layer_name=f'Distance to {poi.value.title()}',
        caption=f'How far is it to {poi.value.capitalize()}?',
        color=cleaned_data['color'].to_list(),
        label=cleaned_data['label'].to_list(),
        legend_data=legend,
        resources=resources,
        filename=f'isodistance_{poi.value.replace(" ", "_")}',
    )


def clean_data(
    data: gpd.GeoDataFrame, max_walking_distance: float, min_value: float, poi: PointsOfInterest
) -> gpd.GeoDataFrame:
    data['label'] = data.apply(assign_label, poi=poi, max_walking_distance=max_walking_distance, axis=1)

    data = assign_color(data, max_walking_distance=max_walking_distance, min_value=min_value, poi=poi)

    return data


def assign_color(
    data: gpd.GeoDataFrame, max_walking_distance: float, min_value: float, poi: PointsOfInterest
) -> gpd.GeoDataFrame:
    data['color'] = generate_colors(
        data.value, 'coolwarm', min_value, max_value=max_walking_distance, bad_color=Color('red').as_hex()
    )
    match poi:
        case PointsOfInterest.SEATING:
            point_color = Color('brown')
        case PointsOfInterest.DRINKING_WATER:
            point_color = Color('darkblue')
        case _:
            raise NotImplementedError('POI not supported by coloring function')
    data.loc[data.geom_type == 'Point', 'color'] = point_color

    return data


def assign_label(row: pd.Series, poi: PointsOfInterest, max_walking_distance: float) -> str:
    match row.geometry.geom_type:
        case 'Point':
            return poi.value
        case _:
            return f'> {int(max_walking_distance)}m' if np.isnan(row['value']) else f'< {int(row["value"])}m'
