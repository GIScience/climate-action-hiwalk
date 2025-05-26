import logging.config

from climatoology.app.plugin import start_plugin
from climatoology.utility.Naturalness import NaturalnessUtility

from walkability.core.operator_worker import OperatorWalkability
from walkability.core.settings import Settings

log = logging.getLogger(__name__)


def init_plugin(initialised_settings: Settings) -> int | None:
    naturalness_utility = NaturalnessUtility(
        host=initialised_settings.naturalness_host,
        port=initialised_settings.naturalness_port,
        path=initialised_settings.naturalness_path,
    )
    operator = OperatorWalkability(
        naturalness_utility=naturalness_utility,
        ors_api_key=initialised_settings.ors_api_key,
        ors_snapping_rate_limit=initialised_settings.ors_snapping_rate_limit,
        ors_snapping_request_size_limit=initialised_settings.ors_snapping_request_size_limit,
        ors_directions_rate_limit=initialised_settings.ors_directions_rate_limit,
        ors_directions_waypoint_limit=initialised_settings.ors_directions_waypoint_limit,
        ors_base_url=initialised_settings.ors_base_url,
    )

    log.info(f'Starting plugin: {operator.info().name}')
    return start_plugin(operator=operator)


if __name__ == '__main__':
    # We require the user to provide the settings as environment variables or in the .env file
    # noinspection PyArgumentList
    settings = Settings()

    exit_code = init_plugin(settings)
    log.info(f'Plugin exited with exit code {exit_code}')
