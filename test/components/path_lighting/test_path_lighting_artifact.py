import geopandas as gpd
from climatoology.base.artifact import Artifact

from walkability.components.path_lighting.path_lighting_artifact import build_path_lighting_artifact
from walkability.components.utils.geometry import CAN_DEFAULT_CRS
from walkability.components.utils.misc import PathLightingCategory


def test_build_path_lighting_artifact(default_path_geometry, default_polygon_geometry, compute_resources):
    light_locations = gpd.GeoDataFrame(
        index=[1, 2, 3],
        data={
            '@osmId': ['way/1', 'way/2', 'way/3'],
            '@other_tags': [{'lit': 'yes'}, {'lit': 'automatic'}, {}],
            'path_lighting': [PathLightingCategory.YES, PathLightingCategory.AUTOMATIC, PathLightingCategory.UNKNOWN],
            'path_lighting_rating': [1, 0.8, None],
        },
        geometry=[
            default_path_geometry,
            default_path_geometry,
            default_polygon_geometry,
        ],
        crs=CAN_DEFAULT_CRS,
    )
    artifact = build_path_lighting_artifact(light_locations=light_locations, resources=compute_resources)

    assert artifact.name == 'Path Lighting'
    assert isinstance(artifact, Artifact)
