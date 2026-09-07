import geopandas as gpd
import pandas as pd
from climatoology.base.artifact_creators import Artifact, ArtifactMetadata, Legend, create_vector_artifact
from climatoology.base.computation import ComputationResources
from ohsome_filter_to_sql import OhsomeFilter
from ohsome_py2.client import OhsomeClient
from pydantic_extra_types.color import Color
from shapely import MultiPolygon

from walkability.components.utils.misc import CrossingType, Topics, fetch_osm_data

CROSSING_COLORS: dict[CrossingType, Color] = {
    CrossingType.TrafficSignals: Color('#a32cf2'),
    CrossingType.Marked: Color('#dd0dda'),
    CrossingType.Unmarked: Color('#b00b69'),
    CrossingType.Other: Color('#808080'),
}


def crossing_analysis(aoi: MultiPolygon, ohsome_client: OhsomeClient, resources: ComputationResources) -> Artifact:
    crossings = get_crossings(aoi, ohsome_client)
    map_artifact = build_crossing_artifact(data=crossings, resources=resources)
    return map_artifact


def build_crossing_artifact(data: gpd.GeoDataFrame, resources: ComputationResources) -> Artifact:
    data['color'] = data['crossing_type'].apply(lambda x: CROSSING_COLORS.get(x))
    data['crossing_type'] = data['crossing_type'].apply(lambda crossing_type: crossing_type.value)

    metadata = ArtifactMetadata(
        name='Pedestrian Crossings',
        summary='Map of pedestrian crossings by type',
        primary=False,
        tags=set(Topics.SAFETY),
    )
    legend = Legend(legend_data={key.value: value for key, value in CROSSING_COLORS.items()})
    return create_vector_artifact(
        data=data, metadata=metadata, resources=resources, label='crossing_type', legend=legend
    )


def get_crossings(aoi, ohsome) -> gpd.GeoDataFrame:
    crossings = fetch_osm_data(aoi=aoi, osm_filter=ohsome_filter(), ohsome_client=ohsome)
    crossings['crossing_type'] = crossings.apply(categorize_crossing, axis=1)
    return crossings


def categorize_crossing(row: pd.Series) -> CrossingType:
    tags = row['osm_tags']
    match tags:
        case x if identify_traffic_signals(x):
            return CrossingType.TrafficSignals
        case x if identify_marked(x):
            return CrossingType.Marked
        case x if identify_unmarked(x):
            return CrossingType.Unmarked
        case _:
            return CrossingType.Other


def identify_traffic_signals(d: dict) -> bool:
    return (
        d.get('crossing') == 'traffic_signals'
        or d.get('crossing:signals') == 'yes'
        or d.get('crossing_ref') in ['pelican', 'toucan']
    )


def identify_marked(d: dict) -> bool:
    return (
        d.get('crossing') in ['uncontrolled', 'marked']
        or d.get('crossing:markings') in ['yes', 'zebra']
        or d.get('crossing_ref') == 'zebra'
    )


def identify_unmarked(d: dict) -> bool:
    return d.get('crossing') == 'unmarked' or d.get('crossing:markings') == 'no'


def ohsome_filter() -> OhsomeFilter:
    return 'highway=crossing'
