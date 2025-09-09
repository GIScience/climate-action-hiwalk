import geopandas as gpd
import shapely
from approvaltests import verify
from geopandas.testing import assert_geodataframe_equal
from ohsome import OhsomeClient
from shapely import LineString, Point

from walkability.components.wellness.benches_and_drinking_water import (
    PointsOfInterest,
    get_ohsome_filter,
    get_pois,
    isochrone_polys_to_isochrone_paths,
    request_pois,
)


def test_get_drinking_water(default_path, default_aoi, responses_mock, operator, ors_isochrone_api):
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
            Point(12.3, 4.22),
        ],
        crs=4326,
    )
    received = get_pois(
        paths=default_path,
        aoi=default_aoi,
        poi=PointsOfInterest.DRINKING_WATER,
        ohsome_client=operator.ohsome,
        ors_settings=operator.ors_settings,
        bins=[100, 200, 300, 400, 500],
    )
    assert_geodataframe_equal(received, expected_drinking_water, check_like=True)


def test_get_pois_empty_request(empty_pois, default_path, default_aoi, operator):
    received = get_pois(
        default_path,
        default_aoi,
        poi=PointsOfInterest.DRINKING_WATER,
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


def test_get_ohsome_filter():
    expected_drinking_water_filter = (
        '(amenity=drinking_water or drinking_water=yes) and (not access=* or not access in (private, no, customers))'
    )
    expected_bench_filter = str(
        'amenity=bench or ((amenity=shelter or public_transport=platform or highway=bus_stop) and bench=yes) '
        'and (not "bench:type"=stand_up) and (not access=* or not access in (private, no, customers))'
    )

    recieved_drinking_water_filter = get_ohsome_filter(PointsOfInterest.DRINKING_WATER)
    recieved_bench_filter = get_ohsome_filter(PointsOfInterest.SEATING)

    assert expected_drinking_water_filter == recieved_drinking_water_filter
    assert expected_bench_filter == recieved_bench_filter


def test_isochrone_polys_to_isochrone_paths(default_ors_settings):
    paths = gpd.GeoDataFrame(geometry=[shapely.LineString([(0, 0), (0, 3)])])

    isos = gpd.GeoDataFrame(
        data={'value': [100.0, 200.0]},
        geometry=[shapely.Point(0.0, 0.0).buffer(1), shapely.Point(0.0, 1.0).buffer(1)],
    )

    expected_result = gpd.GeoDataFrame(
        data={'value': [100.0, 200.0, None]},
        geometry=[
            shapely.LineString([(0, 0), (0, 1)]),
            shapely.LineString([(0, 1), (0, 2)]),
            shapely.LineString([(0, 2), (0, 3)]),
        ],
    )
    received = isochrone_polys_to_isochrone_paths(
        isos, paths=paths, precision=default_ors_settings.coordinate_precision
    )

    assert_geodataframe_equal(received, expected_result)
