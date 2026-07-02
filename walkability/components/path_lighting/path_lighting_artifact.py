import logging
from pathlib import Path

import geopandas as gpd
from climatoology.base.artifact_creators import Artifact, ArtifactMetadata, Legend, create_vector_artifact
from climatoology.base.computation import ComputationResources

from walkability.components.utils.misc import Topics, generate_colors, get_path_lighting_legend

log = logging.getLogger(__name__)


def build_path_lighting_artifact(light_locations: gpd.GeoDataFrame, resources: ComputationResources) -> Artifact:
    log.debug('Building path lighting artifact')
    light_locations['color'] = generate_colors(
        color_by=light_locations.path_lighting_rating, cmap_name='coolwarm_r', min_value=0.0, max_value=1.0
    )
    light_locations['label'] = light_locations.path_lighting.apply(lambda r: r.value)
    return create_vector_artifact(
        data=light_locations[['@osmId', 'color', 'label', 'geometry']],
        metadata=ArtifactMetadata(
            name='Path Lighting',
            summary='How well lit is my path?',
            description=Path('resources/components/path_lighting/path_lighting_description.md').read_text(),
            filename='path_lighting',
            primary=False,
            tags={Topics.SAFETY},
        ),
        resources=resources,
        legend=Legend(legend_data=get_path_lighting_legend()),
    )
