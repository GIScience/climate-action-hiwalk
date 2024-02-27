import geopandas as gpd
from climatoology.base.artifact import _Artifact, create_geojson_artifact
from climatoology.base.computation import ComputationResources


def build_sidewalk_artifact(sidewalks: gpd.GeoDataFrame, resources: ComputationResources) -> _Artifact:
    return create_geojson_artifact(
        features=sidewalks.geometry,
        layer_name='Sidewalks',
        caption='The layer highlights roads that have sidewalks or are explicitly dedicated to pedestrians.',
        description='The layer features all roads that are neither highways/motorways nor specifically exclude '
        'pedestrians, such as cycle ways.',
        color=sidewalks.color.to_list(),
        resources=resources,
        filename='sidewalks',
    )
