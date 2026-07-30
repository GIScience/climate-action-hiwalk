from unittest.mock import patch

import geopandas as gpd
import numpy as np
import pytest
import responses
import shapely
from approvaltests import verify
from geopandas.testing import assert_geodataframe_equal
from responses.registries import OrderedRegistry
from shapely import Point

from walkability.components.comfort.comfort_poi_filters import (
    PointsOfInterest,
    apply_isochrones_to_paths,
    distance_enrich_paths,
    real_isochrones,
)
from walkability.components.utils.geometry import CAN_DEFAULT_CRS


@pytest.mark.vcr
def test_distance_enrich_paths(default_aoi_paths, default_aoi, operator):
    """Test distance_enrich_paths with several POIs and with proper isochrones."""
    bins = [100, 200, 300, 400, 500]
    received = distance_enrich_paths(
        paths=default_aoi_paths,
        aoi=default_aoi,
        poi_type=PointsOfInterest.DRINKING_WATER,
        ohsome_client=operator.ohsome,
        ors_settings=operator.ors_settings,
        bins=bins,
    )

    valid_values = bins + [0, np.nan]
    assert all(received['value'].isin(valid_values))


def test_distance_enrich_paths_one_poi(default_aoi_paths, default_aoi, operator):
    """Test distance_enrich_paths with just one POI returned, and approximate isochrones (i.e. with buffer)."""
    single_poi = gpd.GeoDataFrame(data={'value': [0]}, geometry=[Point(8.70026, 49.40951)], crs=CAN_DEFAULT_CRS)

    with patch('walkability.components.comfort.comfort_poi_filters.request_pois', return_value=single_poi):
        operator.ors_settings.ors_isochrone_max_request_number = 0  # approximate isochrones with a buffer
        received = distance_enrich_paths(
            paths=default_aoi_paths,
            aoi=default_aoi,
            poi_type=PointsOfInterest.DRINKING_WATER,
            ohsome_client=operator.ohsome,
            ors_settings=operator.ors_settings,
            bins=[50],
        )

    valid_values = [0, 50, np.nan]
    assert all(received['value'].isin(valid_values))


def test_distance_enrich_paths_empty_request(default_aoi_paths, default_aoi, operator, default_ohsome_client_v1):
    with patch('walkability.components.comfort.comfort_poi_filters.request_pois', return_value=gpd.GeoDataFrame()):
        received = distance_enrich_paths(
            default_aoi_paths,
            default_aoi,
            poi_type=PointsOfInterest.DRINKING_WATER,
            ohsome_client=default_ohsome_client_v1,
            ors_settings=operator.ors_settings,
            bins=[100, 200, 300, 400, 500],
        )
    assert all(received['value'].isna())


def test_apply_isochrones_to_paths():
    paths = gpd.GeoDataFrame(geometry=[shapely.LineString([(0, 0), (0, 3)])])

    isos = gpd.GeoDataFrame(
        data={'value': [100.0, 200.0]},
        geometry=[shapely.Point(0.0, 0.0).buffer(1), shapely.Point(0.0, 0.0).buffer(2)],
    )

    expected_result = gpd.GeoDataFrame(
        data={'value': [100.0, 200.0, None]},
        geometry=[
            shapely.LineString([(0, 0), (0, 1)]),
            shapely.LineString([(0, 1), (0, 2)]),
            shapely.LineString([(0, 2), (0, 3)]),
        ],
    )
    received = apply_isochrones_to_paths(isos, paths=paths)

    assert_geodataframe_equal(received, expected_result)


def test_real_isochrones_one_bin_failure(default_ors_settings):
    ors_settings_low_batch = default_ors_settings.copy()
    ors_settings_low_batch.ors_isochrone_max_batch_size = 1

    pois = gpd.GeoSeries.from_xy(x=list(range(3)), y=list(range(3)), crs=CAN_DEFAULT_CRS)

    with open('test/resources/test_real_isochrones.json') as file:
        working_isochrones = file.read()

    with responses.RequestsMock(registry=OrderedRegistry) as mock:
        mock.post(
            'http://vcr-secret-url/v2/isochrones/foot-walking/geojson',
            json={
                'error': {'code': 3099, 'message': 'Unable to build an isochrone map.'},
            },
            status=500,
        )

        mock.post(
            'http://vcr-secret-url/v2/isochrones/foot-walking/geojson',
            body=working_isochrones,
        )
        mock.post('http://vcr-secret-url/v2/isochrones/foot-walking/geojson', body=working_isochrones)

        received = real_isochrones(pois=pois, bins=[0, 1, 2], ors_settings=ors_settings_low_batch)

        verify(received.to_json(indent=2))
