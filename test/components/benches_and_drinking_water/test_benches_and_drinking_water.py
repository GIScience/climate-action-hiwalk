import geopandas as gpd
import shapely
from approvaltests import verify
from geopandas.testing import assert_geodataframe_equal
from ohsome import OhsomeClient
from shapely import LineString, Point

from walkability.components.wellness.benches_and_drinking_water import (
    PointsOfInterest,
    apply_isochrones_to_paths,
    distance_enrich_paths,
    request_pois,
)


def test_distance_enrich_paths(default_path, default_aoi, responses_mock, operator, ors_isochrone_api):
    with open('test/resources/ohsome_drinking_water.geojson', 'r') as drinking_water:
        drinking_water_body = drinking_water.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/centroid',
        body=drinking_water_body,
    )

    expected_drinking_water = gpd.GeoDataFrame(
        data={
            'value': [
                300.0,
                300.0,
                400.0,
                400.0,
                500.0,
                0.0,
            ]
        },
        geometry=[
            LineString([[12.3, 48.22], [12.3, 48.22008508979592]]),
            LineString([[12.300434414529912, 48.22006558547009], [12.3005, 48.22]]),
            LineString([[12.3, 48.22008508979592], [12.3, 48.22030903641037]]),
            LineString([[12.300180707134169, 48.22031929286583], [12.300434414529912, 48.22006558547009]]),
            LineString([[12.3, 48.22030903641037], [12.3, 48.2205], [12.300180707134169, 48.22031929286583]]),
            Point(12.3, 48.22),
        ],
        crs=4326,
    )
    received = distance_enrich_paths(
        paths=default_path,
        aoi=default_aoi,
        poi_type=PointsOfInterest.DRINKING_WATER,
        ohsome_client=operator.ohsome,
        ors_settings=operator.ors_settings,
        bins=[100, 200, 300, 400, 500],
    )
    assert_geodataframe_equal(received, expected_drinking_water, check_like=True)


def test_distance_enrich_paths_many_pois(default_path, default_aoi, operator, responses_mock):
    with open('test/resources/ohsome_drinking_water.geojson', 'r') as drinking_water:
        drinking_water_body = drinking_water.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/centroid',
        body=drinking_water_body,
    )

    operator.ors_settings.ors_isochrone_max_request_number = 0
    received = distance_enrich_paths(
        paths=default_path,
        aoi=default_aoi,
        poi_type=PointsOfInterest.DRINKING_WATER,
        ohsome_client=operator.ohsome,
        ors_settings=operator.ors_settings,
        bins=[50],
    )
    expected_drinking_water = gpd.GeoDataFrame(
        data={
            'value': [
                50.0,
                50.0,
                None,
                0.0,
            ]
        },
        geometry=[
            LineString([[12.3, 48.22], [12.3, 48.2204491]]),
            LineString([[12.300052, 48.220448], [12.3005, 48.22]]),
            LineString([[12.3, 48.2204491], [12.3, 48.2205], [12.300052, 48.220448]]),
            Point(12.3, 48.22),
        ],
        crs=4326,
    )

    received.geometry = received.set_precision(0.0000001)
    assert_geodataframe_equal(received, expected_drinking_water, check_like=True)


def test_distance_enrich_paths_empty_request(empty_pois, default_path, default_aoi, operator):
    received = distance_enrich_paths(
        default_path,
        default_aoi,
        poi_type=PointsOfInterest.DRINKING_WATER,
        ohsome_client=OhsomeClient(),
        ors_settings=operator.ors_settings,
        bins=[100, 200, 300, 400, 500],
    )
    verify(received.to_csv())


def test_request_drinking_water(responses_mock, small_aoi):
    with open('test/resources/ohsome_drinking_water.geojson', 'r') as drinking_water:
        drinking_water_body = drinking_water.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/centroid',
        body=drinking_water_body,
    )
    verify(request_pois(aoi=small_aoi, poi=PointsOfInterest.DRINKING_WATER, ohsome_client=OhsomeClient()).to_json())


def test_request_benches(responses_mock, small_aoi):
    with open('test/resources/ohsome_benches.geojson', 'r') as benches:
        benches_body = benches.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/centroid',
        body=benches_body,
    )
    verify(request_pois(aoi=small_aoi, poi=PointsOfInterest.SEATING, ohsome_client=OhsomeClient()).to_json())


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
