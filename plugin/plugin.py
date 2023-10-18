import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List, Tuple

import rasterio
from climatoology.app.plugin import PlatformPlugin
from climatoology.base.operator import Operator, Info, Artifact, Concern, ArtifactModality, ComputationResources
from climatoology.broker.message_broker import AsyncRabbitMQ
from climatoology.store.object_store import MinioStorage
from climatoology.utility.api import LulcUtilityUtility, LULCWorkUnit
from pydantic import BaseModel, Field
from semver import Version

log = logging.getLogger(__name__)
log.addHandler(logging.StreamHandler(sys.stdout))
log.setLevel(logging.INFO)


class BlueprintComputeInput(BaseModel):
    # This class defines all the input parameters of your plugin.
    # It uses pydantic to announce the parameters and validate them from the user realm (i.e. the front-end).
    # These parameters will later be available in the computation method.
    # Make sure you document them well using pydantic Fields.
    # The title, description and example parameters as well as marking them as optional (if applicable) are required!
    # Additional constraints can be set.
    # Examples for the different data types are given below.
    # In case you need custom data types, please contact the CA team.

    blueprint_string: str = Field(title='Blueprint Attribute Title',
                                  description='A string that should be forwarded to the output.',
                                  examples=['Some Text'])

    blueprint_bbox: Tuple[float, float, float, float] = Field(title='Blueprint Bounding Box',
                                                              description='The geographic area of interest as a '
                                                                          'bounding box in WGS84 in the form of '
                                                                          '(minx, miny, maxx, maxy).',
                                                              examples=[(12.304687500000002,
                                                                         48.2246726495652,
                                                                         12.480468750000002,
                                                                         48.3416461723746)],
                                                              default=(12.304687500000002,
                                                                       48.2246726495652,
                                                                       12.480468750000002,
                                                                       48.3416461723746)
                                                              )


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
                    methodology='This Plugin uses no methodology because it does nothing.')

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
        raster_artifact = self.lulc_utility_usage(resources.computation_dir, params.blueprint_bbox)

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
                           bbox: Tuple[float, float, float, float] = None) -> Artifact:
        """LULC Utility example usage.

        This is a very simplified example of usage for the LULC utility.
        It requests a user-defined area from the services for a fixed date and returns the result.

        :param computation_dir: The plugin working directory
        :param bbox: The area of interest
        :return: A LULC classification raster layer
        """
        # Be aware that there are more parameters to the LULCWorkUnit which affect the configuration of the service access
        # ability to the user via the input parameters
        aoi = LULCWorkUnit(area_coords=bbox,
                           end_date="2023-01-01")

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


async def start_plugin() -> None:
    """ Function to start the plugin within the architecture.

    Please adjust the class reference to the class you created above. Apart from that **DO NOT TOUCH**.

    :return:
    """
    operator = BlueprintOperator()
    log.info(f'Configuring plugin: {operator.info().name}')

    storage = MinioStorage(host=os.environ.get('MINIO_HOST'),
                           port=int(os.environ.get('MINIO_PORT')),
                           access_key=os.environ.get('MINIO_ACCESS_KEY'),
                           secret_key=os.environ.get('MINIO_SECRET_KEY'),
                           bucket=os.environ.get('MINIO_BUCKET'),
                           secure=os.environ.get('MINIO_SECURE') == 'True')
    broker = AsyncRabbitMQ(host=os.environ.get('RABBITMQ_HOST'),
                           port=int(os.environ.get('RABBITMQ_PORT')),
                           user=os.environ.get('RABBITMQ_USER'),
                           password=os.environ.get('RABBITMQ_PASSWORD'))
    await broker.async_init()
    log.info(f'Configuring async broker: {os.environ.get("RABBITMQ_HOST")}')

    plugin = PlatformPlugin(operator=operator,
                            storage=storage,
                            broker=broker)
    log.info(f'Running plugin: {operator.info().name}')
    await plugin.run()


if __name__ == '__main__':
    asyncio.run(start_plugin())
