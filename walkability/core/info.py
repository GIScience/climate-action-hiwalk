import importlib
import importlib.metadata
import logging
from pathlib import Path

from climatoology.base.info import _Info, generate_plugin_info, PluginAuthor, Concern
from semver import Version


log = logging.getLogger(__name__)


def get_info() -> _Info:
    info = generate_plugin_info(
        name='Walkability',
        icon=Path('resources/info/icon.jpeg'),
        authors=[
            PluginAuthor(
                name='Moritz Schott',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
            PluginAuthor(
                name='Matthias Schaub',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
            PluginAuthor(
                name='Levi Szamek',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
            PluginAuthor(
                name='Jonas Kemmer',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
            PluginAuthor(
                name='Anna Buch',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
            PluginAuthor(
                name='Danielle Gatland',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
        ],
        version=Version.parse(importlib.metadata.version('walkability')),
        concerns={Concern.MOBILITY_PEDESTRIAN},
        purpose=Path('resources/info/purpose.md'),
        methodology=Path('resources/info/methodology.md'),
        sources=Path('resources/info/sources.bib'),
    )
    log.info(f'Return info {info.model_dump()}')

    return info
