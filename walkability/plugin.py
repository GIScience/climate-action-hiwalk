import logging.config

from climatoology.app.plugin import start_plugin
from climatoology.utility.naturalness import NaturalnessUtility
from mobility_tools.settings import ORSSettings, S3Settings

from walkability.components.shade.utility import S3ShadeConfig
from walkability.core.operator_worker import OperatorWalkability
from walkability.core.settings import Settings

log = logging.getLogger(__name__)


def init_plugin(
    initialised_settings: Settings,
    initialised_ors_settings: ORSSettings,
    s3_settings: S3Settings,
    shade_config: S3ShadeConfig,
) -> int | None:
    naturalness_utility = NaturalnessUtility(
        base_url=f'http://{initialised_settings.naturalness_host}:{initialised_settings.naturalness_port}{initialised_settings.naturalness_path}',
    )

    operator = OperatorWalkability(
        naturalness_utility=naturalness_utility,
        ors_settings=initialised_ors_settings,
        s3_settings=s3_settings,
        shade_config=shade_config,
        max_path_limit=initialised_settings.max_path_limit,
    )

    log.info(f'Starting plugin: {operator.info().name}')
    return start_plugin(operator=operator)


if __name__ == '__main__':
    # We require the user to provide the settings as environment variables or in the .env file
    # noinspection PyArgumentList
    settings = Settings()  # type: ignore
    shade_config = S3ShadeConfig(cache_dir='cache/tree_canopies')
    ors_settings = ORSSettings()
    s3_settings = S3Settings()  # type: ignore

    exit_code = init_plugin(
        initialised_settings=settings,
        initialised_ors_settings=ors_settings,
        s3_settings=s3_settings,
        shade_config=shade_config,
    )
    log.info(f'Plugin exited with exit code {exit_code}')
