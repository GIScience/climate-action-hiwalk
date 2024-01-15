import asyncio
import logging.config
import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from climatoology.app.plugin import PlatformPlugin
from climatoology.broker.message_broker import AsyncRabbitMQ
from climatoology.store.object_store import MinioStorage
from plugin_blueprint.operator_worker import OperatorBlueprint

log_config = 'conf/logging.yaml'
log = logging.getLogger(__name__)


class Settings(BaseSettings):
    log_level: str = 'INFO'

    minio_host: str
    minio_port: int
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool = False

    rabbitmq_host: str
    rabbitmq_port: int
    rabbitmq_user: str
    rabbitmq_password: str

    lulc_host: str
    lulc_port: int
    lulc_root_url: str

    model_config = SettingsConfigDict(env_file='.env')


async def start_plugin(settings: Settings) -> None:
    """ Function to start the plugin within the architecture.

    Please adjust the class reference to the class you created above. Apart from that **DO NOT TOUCH**.

    :return:
    """
    operator = OperatorBlueprint(settings.lulc_host,
                                 settings.lulc_port,
                                 settings.lulc_root_url)
    log.info(f'Configuring plugin: {operator.info().name}')

    storage = MinioStorage(host=settings.minio_host,
                           port=settings.minio_port,
                           access_key=settings.minio_access_key,
                           secret_key=settings.minio_secret_key,
                           bucket=settings.minio_bucket,
                           secure=settings.minio_secure)
    broker = AsyncRabbitMQ(host=settings.rabbitmq_host,
                           port=settings.rabbitmq_port,
                           user=settings.rabbitmq_user,
                           password=settings.rabbitmq_password)
    await broker.async_init()
    log.debug(f'Configured broker: {settings.rabbitmq_host} and storage: {settings.minio_host}')

    plugin = PlatformPlugin(operator=operator,
                            storage=storage,
                            broker=broker)
    log.info(f'Running plugin: {operator.info().name}')

    await plugin.run()


if __name__ == '__main__':
    settings = Settings()

    logging.basicConfig(level=settings.log_level.upper())
    with open(log_config) as file:
        logging.config.dictConfig(yaml.safe_load(file))
    log.info('Starting Plugin')

    asyncio.run(start_plugin(settings))
