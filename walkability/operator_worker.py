import logging
from pathlib import Path
from typing import List

import geopandas as gpd
import pandas as pd
import shapely
from climatoology.base.operator import ComputationResources, Concern, Info, Operator, PluginAuthor, _Artifact
from ohsome import OhsomeClient
from semver import Version

from walkability.artifact import build_paths_artifact
from walkability.input import ComputeInputWalkability
from walkability.utils import construct_filter, fetch_osm_data, boost_route_members, get_color

log = logging.getLogger(__name__)


class OperatorWalkability(Operator[ComputeInputWalkability]):
    def __init__(self):
        self.ohsome = OhsomeClient(user_agent='CA Plugin Walkability')
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
            concerns=[Concern.MOBILITY_PEDESTRIAN],
            purpose=Path('resources/info/purpose.md').read_text(),
            methodology=Path('resources/info/methodology.md').read_text(),
            sources=Path('resources/info/sources.bib'),
        )
        log.info(f'Return info {info.model_dump()}')

        return info

    def compute(self, resources: ComputationResources, params: ComputeInputWalkability) -> List[_Artifact]:
        log.info(f'Handling compute request: {params.model_dump()} in context: {resources}')

        paths = self.get_paths(params.get_geom())
        paths_artifact = build_paths_artifact(paths, resources)
        return [paths_artifact]

    def get_paths(self, aoi: shapely.MultiPolygon) -> gpd.GeoDataFrame:
        log.debug('Requesting paths')

        lines_list = []
        polygon_list = []
        for rating, osm_filter in construct_filter().items():
            lines_list.append(fetch_osm_data(aoi, f'geometry:line and ({osm_filter})', rating, self.ohsome))
            polygon_list.append(fetch_osm_data(aoi, f'geometry:polygon and ({osm_filter})', rating, self.ohsome))

        paths_line = pd.concat(lines_list, ignore_index=True)
        paths_polygon = pd.concat(polygon_list, ignore_index=True)

        paths_line['category'] = boost_route_members(aoi, paths_line[['geometry', 'category']], self.ohsome)

        paths = pd.concat([paths_line, paths_polygon], ignore_index=True)

        paths['color'] = get_color(paths.category)

        return paths[['category', 'color', 'geometry']]
