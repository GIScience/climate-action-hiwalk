from functools import partial

import geopandas as gpd
import geopandas.testing
import pandas as pd
import pytest
import shapely
from approvaltests.approvals import verify
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color
from shapely.testing import assert_geometries_equal

from walkability.utils import (
    construct_filters,
    PathCategory,
    fetch_osm_data,
    boost_route_members,
    fix_geometry_collection,
    get_color,
)


@pytest.fixture(scope='module')
def bpolys():
    """Small bounding box"""
    return gpd.GeoSeries(
        data=[
            shapely.box(8.674922287, 49.4158635794, 8.677604496, 49.417915596),
            shapely.box(8.6284769976, 49.4267943445, 8.6344636881, 49.4296553394),
        ],
        crs='EPSG:4326',
    )


@pytest.fixture(scope='module')
def request_ohsome(bpolys):
    return partial(
        OhsomeClient(user_agent='HeiGIT Climate Action Walkability Tester').elements.geometry.post,
        bpolys=bpolys,
        time='2024-01-01',
    )


@pytest.fixture
def id_filter() -> str:
    # way/98453212 is part of exclusive
    # way/25263180 is part of ignored
    # way/148612595 is part of explicit
    # way/25149880 is part of probable_yes
    # way/156202491 is part of potential_but_unknown
    # way/400711541 is part of inaccessible
    return 'id:(way/98453212,way/25263180,way/148612595,way/25149880,way/156202491,way/400711541)'


def test_construct_filter_verify_exlusive():
    filters = construct_filters()
    exclusive_filter = filters[PathCategory.EXCLUSIVE]
    verify(exclusive_filter)


def test_construct_filter_validate_exclusive(request_ohsome, id_filter):
    filters = construct_filters()
    ohsome_filter = filters[PathCategory.EXCLUSIVE]
    ohsome_filter = f'({ohsome_filter}) and ({id_filter})'
    elements = request_ohsome(filter=ohsome_filter).as_dataframe(multi_index=False)
    assert set(elements['@osmId']) == {'way/98453212'}


def test_construct_filter_verify_explicit():
    filters = construct_filters()
    explicit_filter = filters[PathCategory.EXPLICIT]
    verify(explicit_filter)


def test_construct_filter_validate_explicit(request_ohsome, id_filter):
    filters = construct_filters()
    ohsome_filter = filters[PathCategory.EXPLICIT]
    ohsome_filter = f'({ohsome_filter}) and ({id_filter})'
    elements = request_ohsome(filter=ohsome_filter).as_dataframe(multi_index=False)

    assert set(elements['@osmId']) == {'way/148612595'}


def test_construct_filter_verify_probable_yes():
    filters = construct_filters()
    probable_filter = filters[PathCategory.PROBABLE_YES]
    verify(probable_filter)


def test_construct_filter_validate_probable_yes(request_ohsome, id_filter):
    filters = construct_filters()
    ohsome_filter = filters[PathCategory.PROBABLE_YES]
    ohsome_filter = f'({ohsome_filter}) and ({id_filter})'
    elements = request_ohsome(filter=ohsome_filter).as_dataframe(multi_index=False)

    assert set(elements['@osmId']) == {'way/25149880'}


def test_construct_filter_verify_potential_but_unknown():
    filters = construct_filters()
    probable_filter = filters[PathCategory.POTENTIAL_BUT_UNKNOWN]
    verify(probable_filter)


def test_construct_filter_validate_potential_but_unknown(request_ohsome, id_filter):
    filters = construct_filters()
    ohsome_filter = filters[PathCategory.POTENTIAL_BUT_UNKNOWN]
    ohsome_filter = f'({ohsome_filter}) and ({id_filter})'
    elements = request_ohsome(filter=ohsome_filter).as_dataframe(multi_index=False)

    assert set(elements['@osmId']) == {'way/156202491'}


def test_construct_filter_verify_inaccessible():
    filters = construct_filters()
    probable_filter = filters[PathCategory.INACCESSIBLE]
    verify(probable_filter)


def test_construct_filter_validate_inaccessible(request_ohsome, id_filter):
    filters = construct_filters()
    ohsome_filter = filters[PathCategory.INACCESSIBLE]
    ohsome_filter = f'({ohsome_filter}) and ({id_filter})'

    elements = request_ohsome(filter=ohsome_filter).as_dataframe(multi_index=False)

    assert set(elements['@osmId']) == {'way/400711541'}


def test_fetch_osm_data(expected_compute_input, responses_mock):
    with open('resources/test/ohsome_line_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_osm_data = gpd.GeoDataFrame(
        geometry=[shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])],
        crs=4326,
    )
    computed_osm_data = fetch_osm_data(expected_compute_input.get_aoi_geom(), 'dummy=yes', OhsomeClient())
    geopandas.testing.assert_geodataframe_equal(computed_osm_data, expected_osm_data)


def test_boost_route_members(expected_compute_input, responses_mock):
    with open('resources/test/ohsome_line_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_output = pd.Series(
        data=[
            PathCategory.INACCESSIBLE,
            PathCategory.EXPLICIT,
            PathCategory.EXCLUSIVE,
            PathCategory.POTENTIAL_BUT_UNKNOWN,
        ]
    )

    paths_input = gpd.GeoDataFrame(
        data={
            'category': [
                PathCategory.INACCESSIBLE,
                PathCategory.POTENTIAL_BUT_UNKNOWN,
                PathCategory.EXCLUSIVE,
                PathCategory.POTENTIAL_BUT_UNKNOWN,
            ]
        },
        geometry=[
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
            shapely.LineString([(0, 0), (1, 0), (1, 1)]),
        ],
        crs=4326,
    )
    computed_output = boost_route_members(expected_compute_input.get_aoi_geom(), paths_input, OhsomeClient())
    pd.testing.assert_series_equal(computed_output, expected_output)


def test_boost_route_members_overlapping_routes(expected_compute_input, responses_mock):
    with open('resources/test/ohsome_route_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_output = pd.Series(data=[PathCategory.EXPLICIT])

    paths_input = gpd.GeoDataFrame(
        data={'category': [PathCategory.POTENTIAL_BUT_UNKNOWN]},
        geometry=[
            shapely.LineString([(0, 0), (1, 1)]),
        ],
        crs=4326,
    )
    computed_output = boost_route_members(expected_compute_input.get_aoi_geom(), paths_input, OhsomeClient())
    pd.testing.assert_series_equal(computed_output, expected_output)


def test_fix_geometry_collection():
    expected_geom = shapely.LineString([(0, 0), (1, 0), (1, 1)])

    geometry_collection_input = shapely.GeometryCollection(
        [
            shapely.Point(-1, -1),
            expected_geom,
        ]
    )
    point_input = shapely.Point(-1, -1)

    input_output_map = {
        'unchanged': {'input': expected_geom, 'output': expected_geom},
        'extracted': {'input': geometry_collection_input, 'output': expected_geom},
        'ignored': {'input': point_input, 'output': shapely.LineString()},
    }
    for _, map in input_output_map.items():
        computed_geom = fix_geometry_collection(map['input'])
        assert_geometries_equal(computed_geom, map['output'])


def test_get_color():
    expected_output = pd.Series([Color('#006837'), Color('#feffbe'), Color('#a50026')])

    expected_input = pd.Series([1.0, 0.5, 0.0])
    computed_output = get_color(expected_input)

    pd.testing.assert_series_equal(computed_output, expected_output)
