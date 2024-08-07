import logging
from pathlib import Path
from typing import List, Dict, Callable

import geopandas as gpd
import momepy
import networkx as nx
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
from pyproj import CRS
from semver import Version

from walkability.artifact import (
    build_paths_artifact,
    build_pavement_quality_artifact,
    build_areal_summary_artifacts,
    build_connectivity_artifact,
)
from walkability.input import ComputeInputWalkability
from walkability.utils import (
    construct_filters,
    fetch_osm_data,
    boost_route_members,
    get_color,
    PathCategory,
    PavementQuality,
    geodataframe_to_graph,
    read_pavement_quality_rankings,
    get_flat_key_combinations,
    get_first_match,
    euclidian_distance,
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

        line_paths, polygon_paths = self.get_paths(params.get_buffered_aoi(), params.get_path_rating_mapping())
        paths_artifact = build_paths_artifact(
            line_paths, polygon_paths, params.path_rating, params.get_aoi_geom(), resources
        )

        line_pavement_quality = self.get_pavement_quality(line_paths)
        pavement_quality_artifact = build_pavement_quality_artifact(line_pavement_quality, resources)

        connectivity = self.get_connectivity(
            line_paths,
            params.get_max_walking_distance(),
            params.get_utm_zone(),
            idw_function=params.get_distance_weighting_function(),
        )
        connectivity_artifact = build_connectivity_artifact(connectivity, params.get_aoi_geom(), resources)

        areal_summaries = self.summarise_by_area(
            line_paths, params.get_aoi_geom(), params.admin_level, params.get_utm_zone()
        )
        chart_artifacts = build_areal_summary_artifacts(areal_summaries, resources)

        return [paths_artifact, connectivity_artifact, pavement_quality_artifact] + chart_artifacts

    def get_paths(
        self, aoi: shapely.MultiPolygon, rating_map: Dict[PathCategory, float]
    ) -> (gpd.GeoDataFrame, gpd.GeoDataFrame):
        log.debug('Extracting paths')

        def get_osm_data(aoi: shapely.MultiPolygon, geom_type: str, category: PathCategory) -> gpd.GeoDataFrame:
            osm_data = fetch_osm_data(
                aoi,
                f'geometry:{geom_type} and ({osm_filter})',
                self.ohsome,
            )
            osm_data['category'] = category
            return osm_data

        lines_list = []
        polygons_list = []
        for category, osm_filter in construct_filters().items():
            lines_list.append(get_osm_data(aoi=aoi, geom_type='line', category=category))
            polygons_list.append(get_osm_data(aoi=aoi, geom_type='polygon', category=category))

        paths_line: gpd.GeoDataFrame = pd.concat(lines_list, ignore_index=True)
        paths_polygon = pd.concat(polygons_list, ignore_index=True)

        paths_line['category'] = boost_route_members(
            aoi=aoi,
            paths_line=paths_line,
            ohsome=self.ohsome,
        )

        paths_line['rating'] = paths_line.category.apply(lambda category: rating_map[category])
        paths_polygon['rating'] = paths_polygon.category.apply(lambda category: rating_map[category])

        return paths_line, paths_polygon

    def get_connectivity(
        self,
        paths: gpd.GeoDataFrame,
        walkable_distance: float,
        projected_crs: CRS,
        threshold: float = 0.5,
        idw_function: Callable[[float], float] = lambda _: 1,
    ) -> gpd.GeoDataFrame:
        """Get connectivity.

        Walkable distance is in meter.
        Category threshold.
        """
        paths = paths[paths['rating'] >= threshold]
        if paths.empty:
            return paths

        original_crs = paths.crs
        log.debug(f'Reproject geodataframe from {original_crs} to {projected_crs.name}')
        paths = paths.to_crs(projected_crs)

        G = geodataframe_to_graph(paths)
        node_attributes = {}
        for center in G.nodes:

            def within_max_distance(target):
                return euclidian_distance(center, target) <= walkable_distance

            subgraph = nx.subgraph_view(G, filter_node=within_max_distance)
            weighting = {
                target: idw_function(euclidian_distance(center, target))
                for target in subgraph.nodes
                if target != center
            }

            shortest_paths = nx.single_source_dijkstra_path_length(
                subgraph, center, cutoff=walkable_distance, weight='length'
            )
            shortest_paths = {key: weighting[key] for key, value in shortest_paths.items() if value > 0}

            node_attributes[center] = {
                'connectivity': (sum(shortest_paths.values())) / (sum(weighting.values()))
                if len(subgraph.nodes) > 1
                else 1.0
            }
        nx.set_node_attributes(G, node_attributes)

        edge_attributes = {}
        for s_node, e_node, edge_id in G.edges:
            edge_attributes[(s_node, e_node, edge_id)] = {
                'connectivity': (G.nodes[s_node]['connectivity'] + G.nodes[e_node]['connectivity']) / 2
            }
        nx.set_edge_attributes(G, edge_attributes)

        result = momepy.nx_to_gdf(G, points=False)
        return result.to_crs(original_crs)[['connectivity', 'geometry']]

    def get_pavement_quality(self, line_paths: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        log.debug('Evaluating pavement quality')

        def evaluate_quality(
            row: pd.Series, keys: List[str], evaluation_dict: Dict[str, Dict[str, PavementQuality]]
        ) -> PavementQuality:
            tags = row['@other_tags']

            match_key, match_value = get_first_match(keys, tags)

            match match_key:
                case 'sidewalk:both:smoothness' | 'sidewalk:left:smoothness' | 'sidewalk:right:smoothness':
                    match_key = 'smoothness'
                case 'sidewalk:both:surface' | 'sidewalk:left:surface' | 'sidewalk:right:surface':
                    match_key = 'surface'
                case 'smoothness':
                    if row.category != PathCategory.EXCLUSIVE:
                        return PavementQuality.UNKNOWN
                case 'surface':
                    if row.category != PathCategory.EXCLUSIVE:
                        return PavementQuality.UNKNOWN
                case 'tracktype':
                    pass
                case _:
                    return PavementQuality.UNKNOWN
            return evaluation_dict.get(match_key, {}).get(match_value, PavementQuality.UNKNOWN)

        rankings = read_pavement_quality_rankings()
        keys = get_flat_key_combinations()

        line_paths = line_paths[line_paths.category != PathCategory.INACCESSIBLE]

        line_paths['quality'] = line_paths.apply(lambda row: evaluate_quality(row, keys, rankings), axis=1)

        return line_paths[['quality', 'geometry']]

    def summarise_by_area(
        self,
        paths: gpd.GeoDataFrame,
        aoi: shapely.MultiPolygon,
        admin_level: int,
        projected_crs: CRS,
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

        stats = stats.overlay(boundaries, how='identity')
        stats = stats.to_crs(projected_crs)

        stats['length'] = stats.length / length_resolution_m
        stats['category'] = stats.category.apply(lambda cat: cat.value)

        stats = stats.groupby(['name', 'category', 'rating']).aggregate({'length': 'sum'})
        stats['length'] = round(stats['length'], 2)
        stats = stats.reset_index()
        stats = stats.groupby('name')

        data = {}
        for name, group in stats:
            group = group.sort_values(by=['category'], ascending=False)
            colors = get_color(group.rating).tolist()
            data[name] = Chart2dData(
                x=group.category.tolist(),
                y=group.length.tolist(),
                color=colors,
                chart_type=ChartType.PIE,
            )

        return data
