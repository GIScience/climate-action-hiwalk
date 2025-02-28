import logging.config

from climatoology.app.plugin import start_plugin
from climatoology.utility.Naturalness import NaturalnessUtility

from walkability.core.settings import Settings
from walkability.core.operator_worker import OperatorWalkability

log = logging.getLogger(__name__)


def init_plugin(initialised_settings: Settings) -> int:
    naturalness_utility = NaturalnessUtility(
        host=initialised_settings.naturalness_host,
        port=initialised_settings.naturalness_port,
        path=initialised_settings.naturalness_path,
    )
    operator = OperatorWalkability(naturalness_utility, initialised_settings.ors_api_key)

    log.info(f'Starting plugin: {operator.info().name}')
    return start_plugin(operator=operator)


if __name__ == '__main__':
    # We require the user to provide the settings as environment variables or in the .env file
    # noinspection PyArgumentList
    settings = Settings()

    exit_code = init_plugin(settings)
    log.info(f'Plugin exited with exit code {exit_code}')
