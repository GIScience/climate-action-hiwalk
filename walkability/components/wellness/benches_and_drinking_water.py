import logging
from enum import Enum

import geopandas as gpd
import pandas as pd
import shapely
from ohsome import OhsomeClient

from walkability.components.utils.ors_settings import ORSSettings

log = logging.getLogger(__name__)


class PointsOfInterest(Enum):
    DRINKING_WATER = 'drinking water sources'
    SEATING = 'benches'
    REMAINDER = 'remainder'


def get_pois(
    paths: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    poi: PointsOfInterest,
    bins: list[int],
    ohsome_client: OhsomeClient,
    ors_settings: ORSSettings,
) -> gpd.GeoDataFrame:
    log.debug(f'Requesting {poi} from ohsome')
    pois = request_pois(aoi, poi, ohsome_client)
    if pois.empty:
        paths = paths.copy(deep=True)
        paths['value'] = None
        return paths
    pois['value'] = 0.0

    log.debug('Requesting isochrones from openrouteservice')
    ors_client = ors_settings.client
    locations = list(zip(pois.geometry.x, pois.geometry.y))
    iso_list = []
    for i in range(0, len(locations), ors_settings.isochrone_max_batch_size):
        log.debug(f'Requesting batch {i} of {len(locations)}')
        batch = locations[i : i + ors_settings.isochrone_max_batch_size]

        isochrones = ors_client.isochrones(
            locations=batch,
            profile='foot-walking',
            range_type='distance',
            range=bins,
        )
        iso = gpd.GeoDataFrame.from_features(isochrones, crs=4326)
        iso_list.append(iso)
    iso: gpd.GeoDataFrame = pd.concat(iso_list)

    poi_enriched_paths = isochrone_polys_to_isochrone_paths(iso, paths, precision=ors_settings.coordinate_precision)

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


def isochrone_polys_to_isochrone_paths(
    iso: gpd.GeoDataFrame, paths: gpd.GeoDataFrame, precision: float
) -> gpd.GeoDataFrame:
    log.debug('Creating linear Voronoi isochrones')
    # The following would better be implemented on ORS side, https://github.com/GIScience/openrouteservice/issues/2122
    # and https://github.com/GIScience/openrouteservice/issues/2123 were raised
    unique_areas = gpd.GeoDataFrame(geometry=iso.boundary.polygonize())

    iso.geometry = iso.set_precision(precision)
    unique_areas.geometry = unique_areas.set_precision(precision)
    enriched_areas = gpd.sjoin(unique_areas, iso, predicate='covered_by')
    enriched_areas = enriched_areas.reset_index(names=['unique_area_id'])

    iso_locations = enriched_areas.sort_values('value', ascending=True).drop_duplicates(
        subset=['unique_area_id'], keep='first'
    )
    poi_enriched_paths = paths.overlay(iso_locations, how='union').explode()

    log.debug('Completed Voronoi computation')
    return poi_enriched_paths[['value', 'geometry']]
