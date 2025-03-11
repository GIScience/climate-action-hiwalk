import time
import logging
from climatoology.base.artifact import _Artifact, ContinuousLegendData, create_geojson_artifact
from climatoology.base.computation import ComputationResources
from pathlib import Path

import numpy as np
from pyproj import CRS

from walkability.components.network_analyses.network_analyses import geodataframe_to_graph
from walkability.components.utils.geometry import get_buffered_aoi
from walkability.components.utils.misc import PathCategory


import geopandas as gpd
import h3pandas
import networkx as nx
import pandas as pd
import shapely


from operator import itemgetter
from statistics import fmean

from walkability.components.utils.misc import generate_colors

log = logging.getLogger(__name__)


def hexgrid_permeability_analysis(
    paths: gpd.GeoDataFrame, aoi: shapely.MultiPolygon, max_walking_distance: float, resources: ComputationResources
) -> _Artifact:
    hexgrid_permeability = get_hexgrid_permeability(paths=paths, aoi=aoi, max_walking_distance=max_walking_distance)

    artifact = build_hexgrid_permeability_artifact(hexgrid_permeability=hexgrid_permeability, resources=resources)
    return artifact


def get_hexgrid_permeability(
    paths: gpd.GeoDataFrame, aoi: shapely.MultiPolygon, max_walking_distance: float
) -> gpd.GeoDataFrame:
    begin = time.time()
    log.info('Computing hexgrid permeability')

    buffered_aoi = get_buffered_aoi(aoi, distance=max_walking_distance)
    local_crs = paths.estimate_utm_crs()

    projected_paths = paths.to_crs(local_crs)
    projected_paths = projected_paths[projected_paths['category'] != PathCategory.NOT_WALKABLE]

    destinations = create_destinations(buffered_aoi, local_crs, projected_paths)

    split_paths, snapped_destinations = snap(points=destinations, paths=projected_paths, crs=local_crs)

    graph = geodataframe_to_graph(df=split_paths)

    origins = snapped_destinations[snapped_destinations.to_crs('EPSG:4326').intersects(aoi)]

    detours = []
    index = []
    for cell in origins.iterrows():
        destinations_per_cell = snapped_destinations.clip(cell[1]['buffer'])
        origin = cell[1]['centroids']
        cell_detours = []
        for destination in destinations_per_cell.iterrows():
            try:
                network_distance = nx.dijkstra_path_length(
                    graph,
                    (origin.x, origin.y),
                    (destination[1]['centroids'].x, destination[1]['centroids'].y),
                    weight='length',
                )
                euclidian_distance = origin.distance(destination[1]['centroids'])

                if euclidian_distance == 0:
                    continue
                else:
                    cell_detours.append(network_distance / euclidian_distance)
            except nx.exception.NetworkXNoPath:
                # TODO pass here with no value (watch fmean exceptions if list is empty)
                pass
        if len(cell_detours) == 0:
            detours.append(np.nan)
            index.append(cell[0])
        else:
            detours.append(fmean(cell_detours))
            index.append(cell[0])

    permeability = pd.DataFrame(data={'permeability': detours}, index=index)
    hexgrid_permeability = permeability.h3.h3_to_geo_boundary()

    end = time.time()
    log.info(f'Finished calculating Hexgrid Detour Factor. Took {end-begin}s')
    return hexgrid_permeability


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


def build_hexgrid_permeability_artifact(
    hexgrid_permeability: gpd.GeoDataFrame, resources: ComputationResources, cmap_name: str = 'YlOrRd'
) -> _Artifact:
    detour = hexgrid_permeability.permeability
    color = generate_colors(color_by=detour, cmap_name=cmap_name)
    legend = ContinuousLegendData(
        cmap_name=cmap_name, ticks={f'{round(detour.min(), ndigits=2)}': 0, f'{round(detour.max(), ndigits=2)}': 1}
    )

    return create_geojson_artifact(
        features=hexgrid_permeability.geometry,
        layer_name='Hexgrid Detours',
        filename='hexgrid_permeability',
        caption=Path('resources/components/network_analyses/hexgrid_permeability/caption.md').read_text(),
        description=Path('resources/components/network_analyses/hexgrid_permeability/description.md').read_text(),
        label=hexgrid_permeability.permeability.round(2).to_list(),
        color=color,
        legend_data=legend,
        resources=resources,
    )
