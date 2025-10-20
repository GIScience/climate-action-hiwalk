import logging
from enum import Enum

import geopandas as gpd
import numpy
import pandas as pd
import shapely
from mobility_tools.ors_settings import ORSSettings
from ohsome import OhsomeClient

log = logging.getLogger(__name__)


class PointsOfInterest(Enum):
    DRINKING_WATER = 'drinking water locations'
    SEATING = 'benches'
    REMAINDER = 'remainder'


def distance_enrich_paths(
    paths: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    poi_type: PointsOfInterest,
    bins: list[int],
    ohsome_client: OhsomeClient,
    ors_settings: ORSSettings,
) -> gpd.GeoDataFrame:
    log.debug(f'Requesting {poi_type} from ohsome')
    pois = request_pois(aoi, poi_type, ohsome_client)
    if pois.empty:
        paths = paths.copy(deep=True)
        paths['value'] = numpy.nan

        log.debug(f'No POIs of {poi_type} in this area, returning paths unchanged')
        return paths
    pois['value'] = 0.0

    isochrones = generate_isochrones(pois.geometry, bins, ors_settings)

    poi_enriched_paths = apply_isochrones_to_paths(isochrones, paths)

    result: gpd.GeoDataFrame = pd.concat([poi_enriched_paths, pois], ignore_index=True)

    return result


def request_pois(aoi: shapely.MultiPolygon, poi: PointsOfInterest, ohsome_client: OhsomeClient) -> gpd.GeoDataFrame:
    poi_request = ohsome_client.elements.centroid.post(
        bpolys=aoi,
        filter=get_ohsome_filter(poi),
    )
    pois = poi_request.as_dataframe(multi_index=False)
    pois = gpd.GeoDataFrame(
        data={'value': [0.0] * pois.shape[0]},
        geometry=pois.geometry,
        crs=4326,
    )
    return pois


def get_ohsome_filter(poi: PointsOfInterest):
    match poi:
        case PointsOfInterest.DRINKING_WATER:
            return '(amenity=drinking_water or drinking_water=yes) and (not access=* or not access in (private, no, customers))'
        case PointsOfInterest.SEATING:
            return str(
                'amenity=bench or ((amenity=shelter or public_transport=platform or highway=bus_stop) and bench=yes) '
                'and (not "bench:type"=stand_up) and (not access=* or not access in (private, no, customers))'
            )
        case _:
            raise NotImplementedError('POI type has no ohsome filter')


def generate_isochrones(pois: gpd.GeoSeries, bins: list[int], ors_settings: ORSSettings = None) -> gpd.GeoDataFrame:
    num_pois = len(pois)
    log.debug(f'Generating isochrones for {num_pois} POIs')

    if num_pois > ors_settings.ors_isochrone_max_request_number:
        iso_list = approximate_isochrones(pois, bins)
    else:
        iso_list = real_isochrones(pois, bins, ors_settings)

    iso: gpd.GeoDataFrame = pd.concat(iso_list)
    iso.to_crs(4326, inplace=True)

    log.debug('Isochrones generated')

    return iso


def approximate_isochrones(pois: gpd.GeoSeries, bins: list[int]) -> list[gpd.GeoDataFrame]:
    log.debug('Using naive buffers')
    iso_list = []
    local_pois = pois.copy(deep=True).to_crs(pois.estimate_utm_crs())
    for curr_bin in bins:
        iso = local_pois.buffer(curr_bin).to_frame(name='geometry')
        iso['value'] = curr_bin
        iso_list.append(iso)
    return iso_list


def real_isochrones(pois: gpd.GeoSeries, bins: list[int], ors_settings: ORSSettings | None) -> list[gpd.GeoDataFrame]:
    log.debug('Requesting isochrones from openrouteservice')

    iso_list = []
    locations = list(zip(pois.geometry.x, pois.geometry.y))
    for batch_start in range(0, len(locations), ors_settings.ors_isochrone_max_batch_size):
        batch_end = batch_start + ors_settings.ors_isochrone_max_batch_size
        log.debug(f'Requesting POIs {batch_start} to {batch_end} of {len(locations)}')
        batch = locations[batch_start:batch_end]

        isochrones = ors_settings.client.isochrones(
            locations=batch,
            profile='foot-walking',
            range_type='distance',
            range=bins,
        )
        iso = gpd.GeoDataFrame.from_features(isochrones, crs=4326)
        iso_list.append(iso)

    return iso_list


def apply_isochrones_to_paths(iso: gpd.GeoDataFrame, paths: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    log.debug('Applying isochrones to paths')

    grouped_iso = iso.dissolve(by=['value'])

    path_list = []
    remaining_paths = paths.geometry.copy(deep=True)
    for value, geometry in grouped_iso.geometry.items():
        value_paths = remaining_paths.clip(geometry, keep_geom_type=True).to_frame()
        value_paths['value'] = value
        path_list.append(value_paths)

        remaining_paths = remaining_paths.difference(geometry).rename('geometry')
        remaining_paths = remaining_paths[~remaining_paths.geometry.is_empty]

    path_list.append(remaining_paths.to_frame())
    paths: gpd.GeoDataFrame = pd.concat(path_list, ignore_index=True)
    paths = paths.explode()

    log.debug('Completed "Voronoi" computation')
    return paths[['value', 'geometry']]
