import logging
from pathlib import Path
from typing import List, Dict

import geopandas as gpd
import pandas as pd
import shapely
from climatoology.base.artifact import Chart2dData, ChartType
from climatoology.base.operator import (
    ComputationResources,
    Concern,
    Info,
    Operator,
    PluginAuthor,
    _Artifact,
)
from ohsome import OhsomeClient
from semver import Version

from walkability.artifact import build_paths_artifact, build_areal_summary_artifacts
from walkability.input import ComputeInputWalkability
from walkability.utils import (
    construct_filters,
    fetch_osm_data,
    boost_route_members,
    get_color,
    Rating,
)

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

        paths = self.get_paths(params.get_aoi_geom())
        paths_artifact = build_paths_artifact(paths, resources)

        areal_summaries = self.summarise_by_area(paths, params.get_aoi_geom(), params.admin_level)
        chart_artifacts = build_areal_summary_artifacts(areal_summaries, resources)

        return [paths_artifact] + chart_artifacts

    def get_paths(self, aoi: shapely.MultiPolygon) -> gpd.GeoDataFrame:
        log.debug('Requesting paths')

        lines_list = []
        polygon_list = []
        for rating, osm_filter in construct_filters().items():
            lines_list.append(fetch_osm_data(aoi, f'geometry:line and ({osm_filter})', rating, self.ohsome))
            polygon_list.append(fetch_osm_data(aoi, f'geometry:polygon and ({osm_filter})', rating, self.ohsome))

        paths_line = pd.concat(lines_list, ignore_index=True)
        paths_polygon = pd.concat(polygon_list, ignore_index=True)

        paths_line['category'] = boost_route_members(aoi, paths_line[['geometry', 'category']], self.ohsome)

        paths = pd.concat([paths_line, paths_polygon], ignore_index=True)

        paths['color'] = get_color(paths.category)

        return paths[['category', 'color', 'geometry']]

    def summarise_by_area(
        self,
        paths: gpd.GeoDataFrame,
        aoi: shapely.MultiPolygon,
        admin_level: int,
        length_resolution_m: int = 1000,
    ) -> Dict[str, Chart2dData]:
        stats = paths.copy()
        stats = stats.loc[stats.geometry.geom_type.isin(('MultiLineString', 'LineString'))]

        minimum_keys = ['admin_level', 'name']
        boundaries = self.ohsome.elements.geometry.post(
            properties='tags',
            bpolys=aoi,
            filter=f'geometry:polygon and boundary=administrative and admin_level={admin_level}',
            clipGeometry=True,
        ).as_dataframe(explode_tags=minimum_keys)
        boundaries = boundaries[boundaries.is_valid]
        boundaries = boundaries.reset_index(drop=True)

        # this is a hack due to https://github.com/GIScience/ohsome-py/issues/149
        reference_df = pd.DataFrame(columns=minimum_keys)
        missing_columns = reference_df[reference_df.columns.difference(boundaries.columns)]
        boundaries = pd.concat([boundaries, missing_columns], axis=1)

        stats = stats.overlay(boundaries, how='identity')
        stats = stats.to_crs(stats.geometry.estimate_utm_crs())

        stats['length'] = stats.length / length_resolution_m
        stats['category'] = stats.category.apply(lambda cat: cat.value)

        stats = stats.groupby(['name', 'category']).aggregate({'length': 'sum'})
        stats['length'] = round(stats['length'], 2)
        stats = stats.reset_index()
        stats = stats.groupby('name')

        data = {}
        for name, group in stats:
            group = group.sort_values(by=['category'], ascending=False)
            group.category = group.category.apply(lambda cat: Rating(cat))
            colors = get_color(group.category).tolist()
            data[name] = Chart2dData(
                x=group.category.apply(lambda cat: cat.name).tolist(),
                y=group.length.tolist(),
                color=colors,
                chart_type=ChartType.PIE,
            )

        return data
