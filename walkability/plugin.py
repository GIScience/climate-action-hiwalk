import logging.config

from walkability.operator_worker import Operator
from climatoology.app.plugin import start_plugin

log = logging.getLogger(__name__)


def init_plugin() -> None:
    operator = Operator()

    log.info(f'Starting plugin: {operator.info().name}')
    return start_plugin(operator=operator)


if __name__ == '__main__':
    exit_code = init_plugin()
    log.info(f'Plugin exited with exit code {exit_code}')
