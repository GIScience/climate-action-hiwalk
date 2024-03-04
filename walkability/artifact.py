import geopandas as gpd
from climatoology.base.artifact import _Artifact, create_geojson_artifact
from climatoology.base.computation import ComputationResources


def build_paths_artifact(sidewalks: gpd.GeoDataFrame, resources: ComputationResources) -> _Artifact:
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
        color=sidewalks.color.to_list(),
        resources=resources,
        filename='walkable',
    )
