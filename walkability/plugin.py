import logging.config

from climatoology.app.plugin import start_plugin
from pydantic_settings import BaseSettings, SettingsConfigDict

from walkability.operator_worker import OperatorWalkability
from climatoology.utility.Naturalness import NaturalnessUtility

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    naturalness_host: str
    naturalness_port: int
    naturalness_path: str

    model_config = SettingsConfigDict(env_file='.env')


def init_plugin(settings: Settings) -> int:
    naturalness_utility = NaturalnessUtility(
        host=settings.naturalness_host,
        port=settings.naturalness_port,
        path=settings.naturalness_path,
    )
    operator = OperatorWalkability(naturalness_utility)

    log.info(f'Starting plugin: {operator.info().name}')
    return start_plugin(operator=operator)


if __name__ == '__main__':
    settings = Settings()

    exit_code = init_plugin(settings)
    log.info(f'Plugin exited with exit code {exit_code}')
