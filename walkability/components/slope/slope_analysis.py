import logging
import math


import geopandas as gpd

from climatoology.base.baseoperator import _Artifact
from climatoology.base.computation import ComputationResources
import numpy as np
import openrouteservice
import pandas as pd
import shapely

from walkability.components.slope.slope_artifacts import build_slope_artifact
from walkability.components.utils.geometry import ORS_COORDINATE_PRECISION, get_utm_zone


log = logging.getLogger(__name__)


def slope_analysis(
    line_paths: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    ors_client: openrouteservice.Client,
    resources: ComputationResources,
) -> _Artifact:
    log.info('Computing slope')
    slope = get_slope(paths=line_paths, aoi=aoi, ors_client=ors_client)
    slope_artifact = build_slope_artifact(slope=slope, resources=resources)
    log.info('Finished computing slope')

    return slope_artifact


def get_slope(
    paths: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    ors_client: openrouteservice.Client,
    request_chunk_size: int = 2000,
) -> gpd.GeoDataFrame:
    """Retrieve the slope of paths.

    :param ors_client:
    :param paths:
    :param aoi:
    :param request_chunk_size: Maximum number of elevation to be requested from the server. The server has a limit set that must be respected.
    :return:
    """
    utm = get_utm_zone(aoi)

    paths['start_ele'] = pd.Series(dtype='float64')
    paths['end_ele'] = pd.Series(dtype='float64')
    paths['start_point'] = shapely.get_point(shapely.get_geometry(paths.geometry, 0), 0)
    paths['end_point'] = shapely.get_point(shapely.get_geometry(paths.geometry, -1), -1)
    points: pd.Series = pd.concat([paths['start_point'], paths['end_point']])
    points = points.drop_duplicates().sort_values()

    num_chunks = math.ceil(len(points) / request_chunk_size)

    # PERF: do parallel calls (using async?)
    for chunk in np.array_split(points, num_chunks):
        polyline = list(zip(chunk.x, chunk.y))
        response = ors_client.elevation_line(
            format_in='polyline', format_out='polyline', dataset='srtm', geometry=polyline
        )

        coords = response['geometry']
        for coord in coords:
            point = shapely.Point(coord[0:2])
            ele = coord[2]

            start_point_match = paths['start_point'].geom_equals_exact(point, tolerance=ORS_COORDINATE_PRECISION)
            end_point_match = paths['end_point'].geom_equals_exact(point, tolerance=ORS_COORDINATE_PRECISION)

            paths.loc[start_point_match, 'start_ele'] = ele
            paths.loc[end_point_match, 'end_ele'] = ele

    paths['slope'] = (paths.end_ele - paths.start_ele) / (paths.geometry.to_crs(utm).length / 100.0)
    paths.slope = paths.slope.round(2)

    return paths[['slope', 'geometry']]
