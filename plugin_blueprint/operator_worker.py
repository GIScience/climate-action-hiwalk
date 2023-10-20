# You may ask yourself why this file has such a strange name.
# Well ... python imports: https://discuss.python.org/t/warning-when-importing-a-local-module-with-the-same-name-as-a-2nd-or-3rd-party-module/27799

import datetime
import logging
import os
import sys
from pathlib import Path
from typing import List

import rasterio
import shapely
from climatoology.base.operator import Operator, Info, Concern, ComputationResources, Artifact, ArtifactModality
from climatoology.utility.api import LulcUtilityUtility, LULCWorkUnit
from semver import Version

from plugin_blueprint.input import BlueprintComputeInput

log = logging.getLogger(__name__)
log.addHandler(logging.StreamHandler(sys.stdout))
log.setLevel(logging.INFO)


class BlueprintOperator(Operator[BlueprintComputeInput]):
    # This is your working-class hero.
    # See all the details below.

    def __init__(self):
        # Create a base connection for the LULC classification utility.
        # Remove it, if you don't plan on using that utility.
        self.lulc_generator = LulcUtilityUtility(host=os.environ.get('LULC_HOST'),
                                                 port=int(os.environ.get('LULC_PORT')),
                                                 root_url=os.environ.get('LULC_ROOT_URL'))

    def info(self) -> Info:
        return Info(name='BlueprintPlugin',
                    icon=Path('resources/icon.jpeg'),
                    version=Version(0, 0, 1),
                    concerns=[Concern.CLIMATE_ACTION__GHG_EMISSION],
                    purpose='This Plugin serves no purpose besides being a blueprint for real plugins.',
                    methodology='This Plugin uses no methodology because it does nothing.',
                    sources=Path('resources/example.bib'))

    def compute(self, resources: ComputationResources, params: BlueprintComputeInput) -> List[Artifact]:
        log.info(f'Handling compute request: {params} in context: {resources}')

        # The code is split into several functions from here.
        # Each one describes the functionality of a specific artifact type or utility.
        # Feel free to copy, adapt and delete them at will.

        # ## Artifact types ##
        # This function creates an example text artifact
        text_artifact = BlueprintOperator.text_artifact_creator(resources.computation_dir, params)

        # ## Utilities ##
        # This function provides an example for the LULC utility usage.
        raster_artifact = self.lulc_utility_usage(resources.computation_dir,
                                                  params.get_geom(),
                                                  params.blueprint_date)

        return [text_artifact, raster_artifact]

    @staticmethod
    def text_artifact_creator(computation_dir: Path, params: BlueprintComputeInput) -> Artifact:
        """This method creates a simple text artifact.

        It stores the input parameters as JSON.

        :param computation_dir: The plugin working directory
        :param params: The input parameters
        :return: The input parameters, but as JSON wrapped in an artifact
        """
        out_path = computation_dir / 'blueprint.txt'
        with open(out_path, 'w') as out_file:
            out_file.write(params.model_dump_json())

        return Artifact(name="Input Parameters",
                        modality=ArtifactModality.TEXT,
                        file_path=out_path,
                        summary='The input parameters.',
                        description='Raw return of the input parameter')

    def lulc_utility_usage(self,
                           computation_dir: Path,
                           aoi: shapely.MultiPolygon,
                           target_date: datetime.date) -> Artifact:
        """LULC Utility example usage.

        This is a very simplified example of usage for the LULC utility.
        It requests a user-defined area from the services for a fixed date and returns the result.

        :param computation_dir: The plugin working directory
        :param aoi: The area of interest
        :param target_date: The date for which the classification will be requested
        :return: A LULC classification raster layer
        """
        # Be aware that there are more parameters to the LULCWorkUnit which affect the configuration of the service.
        # These can be handed to the user for adaption via the input parameters.
        aoi = LULCWorkUnit(area_coords=aoi.bounds,
                           end_date=target_date.isoformat())

        out_map = computation_dir / 'raster.tiff'
        with self.lulc_generator.compute_raster([aoi]) as lulc_classification:
            with rasterio.open(out_map, 'w', **lulc_classification.profile.data) as out_map_file:
                out_map_file.write(lulc_classification.read())
                out_map_file.write_colormap(1, lulc_classification.colormap(1))

        artifact = Artifact(name="LULC Classification",
                            modality=ArtifactModality.MAP_LAYER,
                            file_path=out_map,
                            summary='The raw map data.',
                            description='A GeoTIFF.')

        return artifact
