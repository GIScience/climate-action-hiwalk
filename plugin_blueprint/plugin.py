import asyncio
import logging.config
import os

import yaml
from climatoology.app.plugin import PlatformPlugin
from climatoology.broker.message_broker import AsyncRabbitMQ
from climatoology.store.object_store import MinioStorage

from plugin_blueprint.operator_worker import OperatorBlueprint

log_level = os.getenv('LOG_LEVEL', 'INFO')
log_config = 'conf/logging.yaml'
log = logging.getLogger(__name__)


async def start_plugin() -> None:
    """ Function to start the plugin within the architecture.

    Please adjust the class reference to the class you created above. Apart from that **DO NOT TOUCH**.

    :return:
    """
    operator = OperatorBlueprint()
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
    log.debug(f'Configured broker: {os.environ.get("RABBITMQ_HOST")} and storage: {os.environ.get("MINIO_HOST")}')

    plugin = PlatformPlugin(operator=operator,
                            storage=storage,
                            broker=broker)
    log.info(f'Running plugin: {operator.info().name}')

    await plugin.run()


if __name__ == '__main__':
    logging.basicConfig(level=log_level.upper())
    with open(log_config) as file:
        logging.config.dictConfig(yaml.safe_load(file))
    log.info('Starting Plugin')

    asyncio.run(start_plugin())
