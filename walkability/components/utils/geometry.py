import math
from typing import Union, Tuple

import geopandas as gpd
import shapely
from pyproj import Transformer, CRS
from shapely import LineString
from shapely.ops import transform

WGS84 = CRS('EPSG:4326')
ORS_COORDINATE_PRECISION = 0.000001


def get_buffered_aoi(aoi: shapely.MultiPolygon, distance: float) -> shapely.MultiPolygon:
    utm = get_utm_zone(aoi)

    geographic_projection_function = Transformer.from_crs(WGS84, utm, always_xy=True).transform
    wgs84_projection_function = Transformer.from_crs(utm, WGS84, always_xy=True).transform
    projected_aoi = transform(geographic_projection_function, aoi)
    buffered_aoi: shapely.MultiPolygon = projected_aoi.buffer(distance)
    return transform(wgs84_projection_function, buffered_aoi)


def fix_geometry_collection(
    geom: shapely.Geometry,
) -> Union[shapely.LineString, shapely.MultiLineString]:
    # Hack due to https://github.com/GIScience/oshdb/issues/463
    if geom.geom_type == 'GeometryCollection':
        inner_geoms = []
        for inner_geom in geom.geoms:
            if inner_geom.geom_type in ('LineString', 'MultiLineString'):
                inner_geoms.append(inner_geom)
        geom = shapely.union_all(inner_geoms)

    if geom.geom_type in ('LineString', 'MultiLineString'):
        return geom
    else:
        return LineString()


def euclidian_distance(point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
    return math.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)


def get_utm_zone(aoi: shapely.MultiPolygon) -> CRS:
    return gpd.GeoSeries(data=aoi, crs=WGS84).estimate_utm_crs()
