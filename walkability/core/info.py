import logging
from datetime import timedelta
from pathlib import Path

from climatoology.base.plugin_info import Concern, CustomAOI, PluginAuthor, PluginInfo, generate_plugin_info

from walkability.core.input import EXPERIMENTAL_INDICATORS, ComputeInputWalkability, WalkabilityIndicators

log = logging.getLogger(__name__)


def get_info(*, feature_flag_experimental: bool) -> PluginInfo:
    exclude_indicators = {WalkabilityIndicators.SLOPE}
    if not feature_flag_experimental:
        exclude_indicators = exclude_indicators.union(EXPERIMENTAL_INDICATORS)

    demo_optional_indicators = set(WalkabilityIndicators).difference(exclude_indicators)

    info = generate_plugin_info(
        name='hiWalk',
        icon=Path('resources/info/walk.jpeg'),
        authors=[
            PluginAuthor(
                name='Moritz Schott',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
            PluginAuthor(
                name='Emily Wilke',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
            PluginAuthor(
                name='Jonas Kemmer',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
            PluginAuthor(
                name='Veit Ulrich',
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
                name='Anna Buch',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
            PluginAuthor(
                name='Danielle Gatland',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
            PluginAuthor(
                name='Sebastian Block',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
        ],
        concerns={Concern.MOBILITY_PEDESTRIAN},
        purpose=Path('resources/info/purpose.md'),
        teaser='Assess the safety, comfort, and quality of walkable infrastructure in an area of interest.',
        methodology=Path('resources/info/methodology.md'),
        demo_input_parameters=ComputeInputWalkability(optional_indicators=demo_optional_indicators),
        demo_aoi=CustomAOI(name='Heidelberg', path='resources/info/heidelberg_aoi.geojson'),
        computation_shelf_life=timedelta(weeks=24),
    )
    log.info(f'Return info {info.model_dump()}')

    return info
