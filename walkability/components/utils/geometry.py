import geopandas as gpd
import shapely
from pyproj import CRS, Transformer
from shapely.ops import transform

WGS84 = CRS('EPSG:4326')


def get_buffered_aoi(aoi: shapely.MultiPolygon, distance: float) -> shapely.MultiPolygon:
    utm = get_utm_zone(aoi)

    geographic_projection_function = Transformer.from_crs(WGS84, utm, always_xy=True).transform
    wgs84_projection_function = Transformer.from_crs(utm, WGS84, always_xy=True).transform
    projected_aoi = transform(geographic_projection_function, aoi)
    buffered_aoi: shapely.MultiPolygon = projected_aoi.buffer(distance)
    return transform(wgs84_projection_function, buffered_aoi)


def get_utm_zone(aoi: shapely.MultiPolygon) -> CRS:
    return gpd.GeoSeries(data=aoi, crs=WGS84).estimate_utm_crs()


def calculate_length(length_resolution_m, paths, projected_crs):
    stats = paths.copy()
    stats = stats.loc[stats.geometry.geom_type.isin(('MultiLineString', 'LineString'))]
    stats = stats.to_crs(projected_crs)
    stats['length'] = stats.length / length_resolution_m
    stats['length'] = round(stats['length'], 2)
    return stats
