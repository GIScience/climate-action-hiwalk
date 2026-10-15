import geopandas as gpd
from climatoology.base.artifact import Artifact

from walkability.components.tactile_paving.tactile_paving_artifact import build_tactile_paving_artifact
from walkability.components.utils.geometry import CAN_DEFAULT_CRS
from walkability.components.utils.misc import TactilePavingCategory


def test_build_tactile_paving_artifact(default_path_geometry, default_polygon_geometry, compute_resources):
    tactile_locations = gpd.GeoDataFrame(
        index=[1, 2, 3],
        data={
            'osm_id': ['1', '2', '3'],
            'osm_type': ['way', 'way', 'way'],
            'osm_tags': [{'tactile_paving': 'yes'}, {'tactile_paving': 'unpaved'}, {}],
            'tactile_paving': [
                TactilePavingCategory.YES,
                TactilePavingCategory.OTHER_SIGNS,
                TactilePavingCategory.UNKNOWN,
            ],
            'tactile_paving_rating': [1, 0.5, None],
        },
        geometry=[
            default_path_geometry,
            default_path_geometry,
            default_polygon_geometry,
        ],
        crs=CAN_DEFAULT_CRS,
    )
    artifact = build_tactile_paving_artifact(tactile_locations=tactile_locations, resources=compute_resources)

    assert artifact.name == 'Tactile Paving'
    assert isinstance(artifact, Artifact)
