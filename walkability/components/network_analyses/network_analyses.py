import time
from typing import Callable, Tuple
import geopandas as gpd
import momepy
import numpy as np
from networkx import set_node_attributes
from osmnx import simplify_graph
from pyproj import CRS
import shapely
from shapely import MultiLineString, LineString
from tqdm import tqdm
import networkx as nx
from climatoology.base.artifact import _Artifact
from climatoology.base.computation import ComputationResources

from walkability.components.network_analyses.network_artifacts import build_network_artifacts
from walkability.components.utils.geometry import euclidian_distance, get_utm_zone
import logging


log = logging.getLogger(__name__)


def connectivity_permeability_analyses(
    paths: gpd.GeoDataFrame,
    walkable_distance: float,
    aoi: shapely.MultiPolygon,
    resources: ComputationResources,
    idw_function: Callable[[float], float] = lambda _: 1,
) -> list[_Artifact]:
    log.info('Starting network analyses')
    connectivity_permeability = get_connectivity_permeability(
        paths=paths, walkable_distance=walkable_distance, projected_crs=get_utm_zone(aoi), idw_function=idw_function
    )

    connectivity_permeability = connectivity_permeability.clip(aoi, keep_geom_type=True)

    artifacts = build_network_artifacts(connectivity_permeability=connectivity_permeability, resources=resources)
    log.debug('Completed network analyses')
    return artifacts


def get_connectivity_permeability(
    paths: gpd.GeoDataFrame,
    walkable_distance: float,
    projected_crs: CRS,
    threshold: float = 0.5,
    idw_function: Callable[[float], float] = lambda _: 1,
) -> gpd.GeoDataFrame:
    begin = time.time()
    original_crs = paths.crs
    log.debug(f'Reprojecting geodataframe from {original_crs} to {projected_crs.name}')
    paths = paths.to_crs(projected_crs)

    G = geodataframe_to_graph(paths)
    node_attributes = {}

    def within_max_distance(target: Tuple[float, float]) -> bool:
        return euclidian_distance(center, target) <= walkable_distance

    def within_double_max_distance(target: Tuple[float, float]) -> bool:
        return euclidian_distance(center, target) <= walkable_distance * 2

    def is_walkable(start_node: Tuple[float, float], end_node: Tuple[float, float], target_edge_id: int) -> bool:
        edge_data = G.get_edge_data(start_node, end_node)
        return edge_data.get(target_edge_id).get('rating') > threshold

    for center in tqdm(G.nodes, desc='Computing connectivity for nodes', mininterval=2):
        # Skip node if all edge fails threshold check - premature optimisation, does it even help?
        a = G.edges(nbunch=center, data='rating', default=0)
        if all([k[2] < threshold for k in a]):
            continue

        subgraph = nx.subgraph_view(G, filter_node=within_max_distance, filter_edge=is_walkable)
        subgraph_big = nx.subgraph_view(G, filter_node=within_double_max_distance, filter_edge=is_walkable)
        weighting = {
            target: idw_function(euclidian_distance(center, target)) for target in subgraph.nodes if target != center
        }

        shortest_paths = nx.single_source_dijkstra_path_length(subgraph_big, center, weight='length')
        shortest_paths_connectivity = {
            key: weighting[key] for key, value in shortest_paths.items() if 0 < value < walkable_distance
        }

        straightness = 0.0
        for target in subgraph.nodes:
            if center != target:
                network_dist = shortest_paths.get(target, None)
                euclidean_dist = euclidian_distance(center, target)
                if network_dist is None:
                    straightness += 0.1
                else:
                    straightness += euclidean_dist / network_dist
                if straightness < 0.1:
                    straightness = 0.1

        node_attributes[center] = {
            'connectivity': (sum(shortest_paths_connectivity.values())) / (sum(weighting.values()))
            if len(subgraph.nodes) > 1
            else np.nan,
            'permeability': round(straightness / (len(subgraph.nodes) - 1), 2) if len(subgraph.nodes) > 1 else np.nan,
        }
    nx.set_node_attributes(G, node_attributes)
    log.debug('Finished evaluating connectivity for all nodes')

    edge_attributes = {}
    for s_node, e_node, edge_id in G.edges:
        if is_walkable(s_node, e_node, edge_id):
            connectivity = (G.nodes[s_node]['connectivity'] + G.nodes[e_node]['connectivity']) / 2
            permeability = (G.nodes[s_node]['permeability'] + G.nodes[e_node]['permeability']) / 2
        else:
            connectivity = 0.0
            permeability = 0.0
        edge_attributes[(s_node, e_node, edge_id)] = {'connectivity': connectivity, 'permeability': permeability}

    nx.set_edge_attributes(G, edge_attributes)

    result = momepy.nx_to_gdf(G, points=False)

    end = time.time()
    log.info(f'Finished Connectivity-Permeability Calculation. Took {end-begin}s')

    return result.to_crs(original_crs)[['connectivity', 'permeability', 'geometry']]


def geodataframe_to_graph(df: gpd.GeoDataFrame) -> nx.MultiGraph:
    log.debug('Splitting paths at intersections')
    df_ = split_paths_at_intersections(df)

    log.debug('Creating network graph from paths geodataframe')
    G = momepy.gdf_to_nx(df_, multigraph=True, directed=False, length='length')
    node_data = dict()
    for node in G.nodes():
        node_data[node] = {'x': node[0], 'y': node[1]}
    set_node_attributes(G, node_data)

    log.debug('Simplifying graph by removing intermediate nodes along edges')
    G_ = simplify_graph(G.to_directed(), remove_rings=False, edge_attrs_differ=['rating'])

    log.debug('Finished creating graph')
    return G_.to_undirected()


def split_paths_at_intersections(df):
    df = df.drop(errors='ignore', labels='@other_tags', axis=1)
    df.geometry = df.geometry.apply(lambda geom: MultiLineString([geom]) if isinstance(geom, LineString) else geom)
    df_ = (
        df.assign(
            geometry=df.geometry.apply(
                lambda geom: list(
                    list(map(LineString, zip(geom_part.coords[:-1], geom_part.coords[1:]))) for geom_part in geom.geoms
                )
            )
        )
        .explode('geometry')
        .explode('geometry')
    )
    # PERF: `unary_union` might lead to performance issues ...
    # ... since it creates a single geometry
    # `unary_union`: self-intersection geometries
    # NOTE: All properties of the geodataframe are lost
    # geom: MultiLineString = df.unary_union
    # df_ = gpd.GeoDataFrame(data={'geometry': [geom], 'foo': ["bar"]}, crs=df.crs).explode(index_parts=True)
    df_ = gpd.GeoDataFrame(df_).set_crs(df.crs)
    return df_
