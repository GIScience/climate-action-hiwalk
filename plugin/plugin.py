import os
from pathlib import Path
from typing import List

from climatoology.app.plugin import PlatformPlugin
from climatoology.base.operator import Operator, Info, Artifact, Concern, ArtifactModality
from climatoology.broker.message_broker import RabbitMQ
from climatoology.store.object_store import MinioStorage
from pydantic import BaseModel
from semver import Version


class BlueprintComputeInput(BaseModel):
    blueprint_attribute: str


class BlueprintOperator(Operator[BlueprintComputeInput]):

    def info(self) -> Info:
        return Info(name='BlueprintOperator',
                    icon=Path('resources/icon.jpeg'),
                    version=Version(0, 0, 1),
                    concerns=[Concern.GHG_EMISSION],
                    purpose='This Operator serves no purpose besides being a blueprint for real operators.',
                    methodology='This Operator uses no methodology because it does nothing.')

    def compute(self, params: BlueprintComputeInput) -> List[Artifact]:
        out_path = Path('/tmp/blueprint.txt')
        with open(out_path, 'w') as out_file:
            out_file.write(params.model_dump_json())

        first_artifact = Artifact(name="Blueprint",
                                  modality=ArtifactModality.TEXT,
                                  file_path=out_path,
                                  summary='The input parameter.',
                                  description='Raw return of the input parameter')

        return [first_artifact]


def start_plugin() -> None:
    """ Function to start the plugin within the architecture.

    Please adjust the class reference to the class you created above. Apart from that **DO NOT TOUCH**.

    :return:
    """
    storage = MinioStorage(host=os.environ.get('MINIO_HOST'),
                           port=int(os.environ.get('MINIO_PORT')),
                           access_key=os.environ.get('MINIO_ACCESS_KEY'),
                           secret_key=os.environ.get('MINIO_SECRET_KEY'),
                           bucket=os.environ.get('MINIO_BUCKET'),
                           secure=os.environ.get('MINIO_SECURE') == 'True')
    broker = RabbitMQ(host=os.environ.get('RABBITMQ_HOST'),
                      port=int(os.environ.get('RABBITMQ_PORT')))

    plugin = PlatformPlugin(operator=BlueprintOperator(),
                            storage=storage,
                            broker=broker)
    plugin.run()


if __name__ == '__main__':
    start_plugin()
