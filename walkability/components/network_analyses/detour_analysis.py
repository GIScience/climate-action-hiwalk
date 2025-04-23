import time
import logging
from typing import Tuple

from climatoology.base.artifact import (
    _Artifact,
    ContinuousLegendData,
    create_geojson_artifact,
    create_plotly_chart_artifact,
)
from climatoology.base.computation import ComputationResources
from pathlib import Path

from networkx import set_node_attributes
import numpy as np
from osmnx import simplify_graph
from plotly.graph_objects import Figure
from pyproj import CRS
from shapely import LineString, MultiLineString

from walkability.components.utils.geometry import get_buffered_aoi
from walkability.components.utils.misc import PathCategory


import geopandas as gpd
import h3pandas
import networkx as nx
import pandas as pd
import shapely
import momepy


from operator import itemgetter
from statistics import fmean

from walkability.components.utils.misc import generate_colors

log = logging.getLogger(__name__)


def detour_factor_analysis(
    paths: gpd.GeoDataFrame, aoi: shapely.MultiPolygon, max_walking_distance: float, resources: ComputationResources
) -> Tuple[_Artifact, gpd.GeoDataFrame]:
    detour_factors = get_detour_factors(paths=paths, aoi=aoi, max_walking_distance=max_walking_distance)

    artifact = build_detour_factor_artifact(detour_factor_data=detour_factors, resources=resources)
    return artifact, detour_factors


def get_detour_factors(
    paths: gpd.GeoDataFrame, aoi: shapely.MultiPolygon, max_walking_distance: float
) -> gpd.GeoDataFrame:
    begin = time.time()
    log.info('Computing detour factors')

    buffered_aoi = get_buffered_aoi(aoi, distance=max_walking_distance)
    local_crs = paths.estimate_utm_crs()

    projected_paths = paths.to_crs(local_crs)

    destinations = create_destinations(buffered_aoi, local_crs, projected_paths)

    split_paths, snapped_destinations = snap(points=destinations, paths=projected_paths, crs=local_crs)

    graph = geodataframe_to_graph(df=split_paths)

    origins = snapped_destinations[snapped_destinations.to_crs('EPSG:4326').intersects(aoi)]

    detours = []
    index = []
    for cell_index, cell in origins.iterrows():
        destinations_per_cell = snapped_destinations.clip(cell['buffer'])
        origin = cell['centroids']
        cell_detours = []
        for _i, destination in destinations_per_cell.iterrows():
            try:
                network_distance = nx.dijkstra_path_length(
                    graph,
                    (origin.x, origin.y),
                    (destination['centroids'].x, destination['centroids'].y),
                    weight='length',
                )
                euclidian_distance = origin.distance(destination['centroids'])

                if euclidian_distance == 0:
                    continue
                else:
                    cell_detours.append(network_distance / euclidian_distance)
            except nx.exception.NetworkXNoPath:
                # TODO pass here with no value (watch fmean exceptions if list is empty)
                pass
        index.append(cell_index)
        if len(cell_detours) == 0:
            detours.append(np.nan)
        else:
            detours.append(fmean(cell_detours))

    detour_factors = pd.DataFrame(data={'detour_factor': detours}, index=index)
    hexgrid_detour_factors = detour_factors.h3.h3_to_geo_boundary()

    end = time.time()
    log.info(f'Finished calculating Detour Factors. Took {end - begin}s')
    return hexgrid_detour_factors


def create_destinations(
    aoi: shapely.MultiPolygon, local_crs: CRS, paths: gpd.GeoDataFrame, resolution: int = 10
) -> gpd.GeoDataFrame:
    """
    Creates a h3 hexgrid for the aoi and drops all cells that do not contain any paths
    ## Params
    :param:`aoi`: `shapely.Multipolygon` to be polyfilled as a hexgrid in `EPSG:4326`
    :param:`local_crs`: `pyproject.CRS` local UTM CRS of the `aoi` and `paths`
    :param:`paths`: `geopandas.GeoDataFrame` of local paths. CRS must match `local_crs`
    ## Returns
    :return:`destinations`: `geopandas.GeoDataFrame` hexgrid of the `aoi` in `local_crs` with added centroids and 200 m buffer
    """
    log.debug(f'Using h3pandas v{h3pandas.version} to get hexgrid for aoi.')  # need to use h3pandas import

    hexgrid = gpd.GeoDataFrame(geometry=[aoi], crs='EPSG:4326').h3.polyfill_resample(resolution)
    local_hexgrid = hexgrid.to_crs(crs=local_crs)

    log.debug('Creating Destinations')
    local_hexgrid['buffer'] = local_hexgrid.buffer(distance=200)
    local_hexgrid['centroids'] = local_hexgrid.centroid
    destinations = local_hexgrid[local_hexgrid.intersects(paths.union_all())]

    return destinations


def snap(points: gpd.GeoDataFrame, paths: gpd.GeoDataFrame, crs: CRS) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    log.debug('Snapping points to path network.')

    points['nearest_point'] = points.apply(find_nearest_point, lines=paths, axis=1)
    points['nearest_point'].set_crs(crs)
    points['snapping_distance'] = points.apply(lambda row: row['nearest_point'].distance(row['centroids']), axis=1)

    snapping_edges = points.apply(lambda row: shapely.LineString([row['centroids'], row['nearest_point']]), axis=1)

    nearest_points = points['nearest_point'].union_all()
    paths['geometry'] = paths.snap(other=nearest_points, tolerance=1)

    paths['geometry'] = paths.apply(lambda row: shapely.ops.split(row['geometry'], splitter=nearest_points), axis=1)
    split_paths = paths.explode().reset_index(drop=True).set_crs(crs)

    log.debug('Adding edges to hexcell centroids to paths')
    for edge in snapping_edges:
        last_row = split_paths.shape[0]
        split_paths.loc[last_row, 'category'] = PathCategory.DESIGNATED
        split_paths.loc[last_row, 'rating'] = 1.0
        split_paths.loc[last_row, 'geometry'] = edge

    return split_paths, points


def find_nearest_point(row: pd.Series, lines: gpd.GeoDataFrame) -> shapely.Point:
    paths_in_cell = lines.clip(row['geometry'])
    point_candidates = []
    for geometry in paths_in_cell['geometry']:
        centroid, point_on_path = shapely.ops.nearest_points(row['centroids'], geometry)
        distance = centroid.distance(point_on_path)
        candidate = {'point': point_on_path, 'distance': distance}
        point_candidates.append(candidate)

    if len(point_candidates) == 0:
        return shapely.Point()

    sorted_candidates = sorted(point_candidates, key=itemgetter('distance'))
    closest_candidate = sorted_candidates[0]
    return closest_candidate['point']


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


def build_detour_factor_artifact(
    detour_factor_data: gpd.GeoDataFrame, resources: ComputationResources, cmap_name: str = 'YlOrRd'
) -> _Artifact:
    detour = detour_factor_data.detour_factor
    color = generate_colors(color_by=detour, cmap_name=cmap_name)
    legend = ContinuousLegendData(
        cmap_name=cmap_name, ticks={f'{round(detour.min(), ndigits=2)}': 0, f'{round(detour.max(), ndigits=2)}': 1}
    )

    return create_geojson_artifact(
        features=detour_factor_data.geometry,
        layer_name='Detour Factor',
        filename='hexgrid_detours',
        caption=Path('resources/components/network_analyses/detour_factor/caption.md').read_text(),
        description=Path('resources/components/network_analyses/detour_factor/description.md').read_text(),
        label=detour_factor_data.detour_factor.round(2).to_list(),
        color=color,
        legend_data=legend,
        resources=resources,
    )


def build_detour_summary_artifact(aoi_aggregate: Figure, resources: ComputationResources) -> _Artifact:
    return create_plotly_chart_artifact(
        figure=aoi_aggregate,
        title='Histogram of Detour Factors',
        caption='How are detour factor values distributed?',
        resources=resources,
        filename='aggregation_aoi_detour',
        primary=True,
    )
