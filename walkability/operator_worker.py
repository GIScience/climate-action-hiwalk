import importlib
import logging
import math
from pathlib import Path
from typing import List, Dict, Callable, Tuple

import geopandas as gpd
import momepy
import networkx as nx
import numpy as np
import openrouteservice
import pandas as pd
import shapely
from climatoology.base.artifact import Chart2dData, ChartType
from climatoology.base.baseoperator import BaseOperator, AoiProperties, _Artifact
from climatoology.base.computation import ComputationResources
from climatoology.base.info import generate_plugin_info, _Info, PluginAuthor, Concern
from climatoology.utility.Naturalness import NaturalnessUtility, NaturalnessIndex
from climatoology.utility.api import TimeRange
from ohsome import OhsomeClient
from pyproj import CRS
from semver import Version
from shapely.geometry.point import Point

from walkability.artifact import (
    build_slope_artifact,
    build_paths_artifact,
    build_pavement_quality_artifact,
    build_connectivity_artifact,
    build_areal_summary_artifacts,
    build_naturalness_artifact,
)
from walkability.input import ComputeInputWalkability
from walkability.utils import (
    fetch_osm_data,
    fetch_naturalness_by_vector,
    boost_route_members,
    get_buffered_aoi,
    PathCategory,
    PavementQuality,
    geodataframe_to_graph,
    get_utm_zone,
    read_pavement_quality_rankings,
    get_flat_key_combinations,
    get_first_match,
    apply_path_category_filters,
    euclidian_distance,
    ohsome_filter,
    get_qualitative_color,
    ORS_COORDINATE_PRECISION,
)

log = logging.getLogger(__name__)


class OperatorWalkability(BaseOperator[ComputeInputWalkability]):
    def __init__(self, naturalness_utility: NaturalnessUtility, ors_api_key: str):
        super().__init__()
        self.naturalness_utility = naturalness_utility
        self.ohsome = OhsomeClient(user_agent='CA Plugin Walkability')
        self.ors_client = openrouteservice.Client(key=ors_api_key)
        log.debug('Initialised walkability operator with ohsome client and Naturalness Utility')

    def info(self) -> _Info:
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

    def compute(
        self,
        resources: ComputationResources,
        aoi: shapely.MultiPolygon,
        aoi_properties: AoiProperties,
        params: ComputeInputWalkability,
    ) -> List[_Artifact]:
        log.info(f'Handling compute request: {params.model_dump()} in context: {resources}')

        line_paths, polygon_paths = self.get_paths(
            get_buffered_aoi(aoi, params.get_max_walking_distance()), params.get_path_rating_mapping()
        )
        paths_artifact = build_paths_artifact(line_paths, polygon_paths, params.path_rating, aoi, resources)

        line_pavement_quality = self.get_pavement_quality(line_paths)
        pavement_quality_artifact = build_pavement_quality_artifact(line_pavement_quality, aoi, resources)

        connectivity = self.get_connectivity(
            line_paths,
            params.get_max_walking_distance(),
            get_utm_zone(aoi),
            idw_function=params.get_distance_weighting_function(),
        )
        connectivity_artifact = build_connectivity_artifact(connectivity, aoi, resources)

        areal_summaries = self.summarise_by_area(line_paths, aoi, params.admin_level, get_utm_zone(aoi))
        chart_artifacts = build_areal_summary_artifacts(areal_summaries, resources)

        naturalness_of_paths = self.get_naturalness(paths=line_paths, aoi=aoi, index=params.naturalness_index)
        naturalness_artifact = build_naturalness_artifact(naturalness_of_paths, resources)

        slope = self.get_slope(paths=line_paths, aoi=aoi)
        slope_artifact = build_slope_artifact(slope, resources)

        return [
            paths_artifact,
            connectivity_artifact,
            pavement_quality_artifact,
            naturalness_artifact,
            slope_artifact,
        ] + chart_artifacts

    def get_paths(
        self, aoi: shapely.MultiPolygon, rating_map: Dict[PathCategory, float]
    ) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        log.debug('Extracting paths')

        paths_line = fetch_osm_data(aoi, ohsome_filter('line'), self.ohsome)
        paths_line['category'] = paths_line.apply(apply_path_category_filters, axis=1)
        paths_line['category'] = boost_route_members(aoi=aoi, paths_line=paths_line, ohsome=self.ohsome)

        paths_polygon = fetch_osm_data(aoi, ohsome_filter('polygon'), self.ohsome)
        paths_polygon['category'] = paths_polygon.apply(apply_path_category_filters, axis=1)

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

        original_crs = paths.crs
        log.debug(f'Reproject geodataframe from {original_crs} to {projected_crs.name}')
        paths = paths.to_crs(projected_crs)

        G = geodataframe_to_graph(paths)
        node_attributes = {}

        def within_max_distance(target: Tuple[float, float]) -> bool:
            return euclidian_distance(center, target) <= walkable_distance

        def is_walkable(start_node: Tuple[float, float], end_node: Tuple[float, float], edge_id: int) -> bool:
            edge_data = G.get_edge_data(start_node, end_node)
            return edge_data.get(edge_id).get('rating') > threshold

        log.debug('Evaluating connectivity for nodes')
        for center in G.nodes:
            # premature optimisation, does it even help?
            a = G.edges(nbunch=center, data='rating', default=0)
            if all([k[2] < threshold for k in a]):
                continue

            subgraph = nx.subgraph_view(G, filter_node=within_max_distance, filter_edge=is_walkable)
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
            if is_walkable(s_node, e_node, edge_id):
                connectivity = (G.nodes[s_node]['connectivity'] + G.nodes[e_node]['connectivity']) / 2
            else:
                connectivity = 0.0
            edge_attributes[(s_node, e_node, edge_id)] = {'connectivity': connectivity}

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
                case (
                    'sidewalk:both:smoothness'
                    | 'sidewalk:left:smoothness'
                    | 'sidewalk:right:smoothness'
                    | 'footway:smoothness'
                ):
                    match_key = 'smoothness'
                case 'sidewalk:both:surface' | 'sidewalk:left:surface' | 'sidewalk:right:surface' | 'footway:surface':
                    match_key = 'surface'
                case 'smoothness':
                    if row.category not in [
                        PathCategory.DESIGNATED,
                        PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED,
                        PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
                        PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED,
                    ] and tags.get('highway') not in ['path', 'footway', 'cycleway', 'track']:
                        return PavementQuality.UNKNOWN
                case 'surface':
                    if row.category not in [
                        PathCategory.DESIGNATED,
                        PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED,
                        PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
                        PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED,
                    ] and tags.get('highway') not in ['path', 'footway', 'cycleway', 'track']:
                        return PavementQuality.UNKNOWN
                case 'tracktype':
                    pass
                case _:
                    return PavementQuality.UNKNOWN
            return evaluation_dict.get(match_key, {}).get(match_value, PavementQuality.UNKNOWN)

        rankings = read_pavement_quality_rankings()
        keys = get_flat_key_combinations()

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
        log.debug(f'Summarising paths into {boundaries.shape[0]} boundaries')

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
            colors = [
                get_qualitative_color(category=PathCategory(category), cmap_name='RdYlBu_r', class_name=PathCategory)
                for category in group.category
            ]
            data[name] = Chart2dData(
                x=group.category.tolist(),
                y=group.length.tolist(),
                color=colors,
                chart_type=ChartType.PIE,
            )
        return data

    def get_naturalness(
        self, aoi: shapely.MultiPolygon, paths: gpd.GeoDataFrame, index: NaturalnessIndex
    ) -> gpd.GeoDataFrame:
        """
        Get NDVI along street within the AOI.

        :param index:
        :param paths:
        :param aoi:
        :return: RasterInfo objects with NDVI values along streets and places
        """
        # Clip paths to aoi, then buffer as input to naturalness calculation
        # Clipping is temporary, pending: https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/154
        paths_clipped = gpd.clip(paths, aoi, keep_geom_type=True)

        paths_ndvi = fetch_naturalness_by_vector(
            naturalness_utility=self.naturalness_utility,
            time_range=TimeRange(),
            vectors=[paths_clipped.geometry],
            index=index,
        )

        return paths_ndvi

    def get_slope(
        self, paths: gpd.GeoDataFrame, aoi: shapely.MultiPolygon, request_chunk_size: int = 2000
    ) -> gpd.GeoDataFrame:
        """Retrieve the slope of paths.

        :param paths:
        :param aoi:
        :param request_chunk_size: Maximum number of elevation to be requested from the server. The server has a limit set that must be respected.
        :return:
        """
        # Clipping is temporary, pending: https://gitlab.heigit.org/climate-action/plugins/walkability/-/issues/154
        paths_clipped = gpd.clip(paths, aoi, keep_geom_type=True)
        utm = get_utm_zone(aoi)

        paths_clipped['start_ele'] = pd.Series(dtype='float64')
        paths_clipped['end_ele'] = pd.Series(dtype='float64')
        paths_clipped['start_point'] = shapely.get_point(shapely.get_geometry(paths_clipped.geometry, 0), 0)
        paths_clipped['end_point'] = shapely.get_point(shapely.get_geometry(paths_clipped.geometry, -1), -1)
        points = pd.concat([paths_clipped['start_point'], paths_clipped['end_point']]).drop_duplicates().sort_values()

        num_chunks = math.ceil(len(points) / request_chunk_size)

        # PERF: do parallel calls
        for chunk in np.array_split(points, num_chunks):
            polyline = list(zip(chunk.x, chunk.y))
            response = self.ors_client.elevation_line(
                format_in='polyline', format_out='polyline', dataset='srtm', geometry=polyline
            )

            coords = response['geometry']
            for coord in coords:
                point = Point(coord[0:2])
                ele = coord[2]

                start_point_match = paths_clipped['start_point'].geom_equals_exact(
                    point, tolerance=ORS_COORDINATE_PRECISION
                )
                end_point_match = paths_clipped['end_point'].geom_equals_exact(
                    point, tolerance=ORS_COORDINATE_PRECISION
                )

                paths_clipped.loc[start_point_match, 'start_ele'] = ele
                paths_clipped.loc[end_point_match, 'end_ele'] = ele

        paths_clipped['slope'] = (paths_clipped.end_ele - paths_clipped.start_ele) / (
            paths_clipped.geometry.to_crs(utm).length / 100.0
        )
        paths_clipped.slope = paths_clipped.slope.round(2)

        return paths_clipped[['slope', 'geometry']]
