import logging.config

from climatoology.app.plugin import start_plugin
from climatoology.utility.naturalness import NaturalnessUtility
from mobility_tools.ors_settings import ORSSettings

from walkability.core.operator_worker import OperatorWalkability
from walkability.core.settings import Settings

log = logging.getLogger(__name__)


def init_plugin(initialised_settings: Settings, initialised_ors_settings: ORSSettings) -> int | None:
    naturalness_utility = NaturalnessUtility(
        base_url=f'http://{initialised_settings.naturalness_host}{initialised_settings.naturalness_path}',
    )

    operator = OperatorWalkability(naturalness_utility=naturalness_utility, ors_settings=initialised_ors_settings)

    log.info(f'Starting plugin: {operator.info().name}')
    return start_plugin(operator=operator)


if __name__ == '__main__':
    # We require the user to provide the settings as environment variables or in the .env file
    # noinspection PyArgumentList
    settings = Settings()
    ors_settings = ORSSettings()

    exit_code = init_plugin(settings, ors_settings)
    log.info(f'Plugin exited with exit code {exit_code}')
