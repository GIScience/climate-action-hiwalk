import logging
from pathlib import Path
from typing import List

import geopandas as gpd
import shapely
from climatoology.base.operator import ComputationResources, Concern, Info, Operator, PluginAuthor, _Artifact
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color
from semver import Version

from walkability.artifact import build_sidewalk_artifact
from walkability.input import ComputeInputWalkability

log = logging.getLogger(__name__)


class OperatorWalkability(Operator[ComputeInputWalkability]):
    def __init__(self):
        self.ohsome = OhsomeClient(user_agent='CA Plugin Blueprint')
        log.debug('Initialised walkability operator with ohsome client')

    def info(self) -> Info:
        # noinspection PyTypeChecker
        info = Info(
            name='Walkability',
            icon=Path('resources/info/icon.jpeg'),
            authors=[
                PluginAuthor(
                    name='Moritz Schott',
                    affiliation='HeiGIT gGmbH',
                    website='https://heigit.org/heigit-team/',
                )
            ],
            version=Version(0, 0, 1),
            concerns=[Concern.CLIMATE_ACTION__GHG_EMISSION],
            purpose=Path('resources/info/purpose.md').read_text(),
            methodology=Path('resources/info/methodology.md').read_text(),
            sources=Path('resources/info/sources.bib'),
        )
        log.info(f'Return info {info.model_dump()}')

        return info

    def compute(self, resources: ComputationResources, params: ComputeInputWalkability) -> List[_Artifact]:
        log.info(f'Handling compute request: {params.model_dump()} in context: {resources}')

        sidewalks = self.get_sidewalks(params.get_geom())
        return [build_sidewalk_artifact(sidewalks, resources)]

    def get_sidewalks(self, aoi: shapely.MultiPolygon) -> gpd.GeoDataFrame:
        log.debug('Requesting sidewalks')
        ohsome_response = self.ohsome.elements.geometry.post(bpolys=aoi, filter='highway=path')
        elements = ohsome_response.as_dataframe(explode_tags='highway')
        elements = elements.reset_index(drop=True)
        elements['color'] = Color('blue')
        return elements
