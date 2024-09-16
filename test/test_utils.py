from functools import partial
import logging
import urllib.parse

import geopandas as gpd
import geopandas.testing
import pandas as pd
import pytest
import shapely
from approvaltests.approvals import verify
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color
from shapely.testing import assert_geometries_equal
from urllib3 import Retry

from walkability.utils import (
    boost_route_members,
    construct_filters,
    PathCategory,
    fetch_osm_data,
    fix_geometry_collection,
    get_color,
    generate_detailed_pavement_quality_mapping_info,
    apply_path_category_filters,
)


validation_objects = {
    PathCategory.DEDICATED_EXCLUSIVE: {'way/84908668', 'way/243233105', 'way/27797959'},
    # https://www.openstreetmap.org/way/98453212 foot=designated
    # https://www.openstreetmap.org/way/84908668 highway=pedestrian
    # https://www.openstreetmap.org/way/27797959 railway=platform
    PathCategory.DEDICATED_SEPARATED: {'way/98453212', 'way/184725322', 'way/118975501'},
    # https://www.openstreetmap.org/way/184725322 sidewalk:right=right and sidewalk:left=separate
    # https://www.openstreetmap.org/way/243233105 highway=footway,
    # https://www.openstreetmap.org/way/118975501 foot=designated and bicycle=designated and segregated=yes
    PathCategory.SHARED_WITH_BIKES: {'way/25806383', 'way/148612595', 'way/715905259'},
    # https://www.openstreetmap.org/way/25806383 bicycle=designated & foot=designated
    # https://www.openstreetmap.org/way/148612595/history/16 bicycle=yes & highway=residential
    # https://www.openstreetmap.org/way/715905259 highway=track
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED: {'way/25149880', 'way/14193661'},
    # https://www.openstreetmap.org/way/25149880 highway=service
    # https://www.openstreetmap.org/way/14193661 highway=living_street
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED: {'way/28890081', 'way/109096915'},
    # https://www.openstreetmap.org/way/28890081 highway=residential and sidewalk=no and maxspeed=30
    # https://www.openstreetmap.org/way/109096915 highway=residential and sidewalk=no and maxspeed=20
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED: {'way/25340617', 'way/258562284', 'way/152645928'},
    # https://www.openstreetmap.org/way/25340617 highway=residential and sidewalk=no and maxspeed=50
    # https://www.openstreetmap.org/way/258562284 highway=tertiary and sidewalk=no and maxspeed=50
    # https://www.openstreetmap.org/way/152645928 highway=residential and sidewalk!=* and maxspeed!=*
    PathCategory.INACCESSIBLE: {'way/400711541', 'way/24635973', 'way/25238623', 'way/225895739'},
    # https://www.openstreetmap.org/way/400711541 sidewalk=no and maxspeed:backward=70
    # https://www.openstreetmap.org/way/24635973 foot=no
    # https://www.openstreetmap.org/way/25238623 access=private
    # https://www.openstreetmap.org/way/225895739 service=yes and bus=yes
}


@pytest.fixture(scope='module')
def bpolys():
    """Small bounding boxes."""
    bpolys = gpd.GeoSeries(
        data=[
            shapely.box(8.670396, 49.415353, 8.678818, 49.419778),
            shapely.box(8.693997, 49.414259, 8.697602, 49.415491),
            shapely.box(8.673989, 49.394600, 8.676486, 49.395344),
            shapely.box(8.665670, 49.418945, 8.667255, 49.419226),
            shapely.box(8.695955, 49.394446, 8.703445, 49.396585),
            shapely.box(8.695094, 49.406642, 8.699428, 49.408387),
            shapely.box(8.687238, 49.410277, 8.690776, 49.411319),
            shapely.box(8.6284769976, 49.4267943445, 8.6344636881, 49.4296553394),
            shapely.box(8.693717586876431, 49.41201247400707, 8.70768102673378, 49.408582680835906),
            shapely.box(8.690887, 49.406495, 8.694642, 49.409326),
            shapely.box(8.671805, 49.402299, 8.677725, 49.404730),
            shapely.box(3.354680, 6.444900, 3.369928, 6.455165),
        ],
        crs='EPSG:4326',
    )
    # NOTE: used to generate geojson.io link
    base_url = 'http://geojson.io/#data=data:application/json,'
    encoded = urllib.parse.quote(bpolys.to_json())
    url = base_url + encoded
    logging.debug(url)
    return bpolys


@pytest.fixture(scope='module')
def request_ohsome(bpolys):
    return partial(
        OhsomeClient(
            user_agent='HeiGIT Climate Action Walkability Tester', retry=Retry(total=1)
        ).elements.geometry.post,
        bpolys=bpolys,
        properties='tags',
        time='2024-01-01',
        timeout=60,
    )


@pytest.fixture(scope='module')
def id_filter() -> str:
    """Optimization to make the ohsome API request time faster."""
    full_ids = {''}
    for ids in validation_objects.values():
        full_ids.update(ids)
    full_ids.remove('')
    return f'id:({",".join(full_ids)})'


@pytest.fixture(scope='module')
def osm_return_data(request_ohsome, id_filter) -> gpd.GeoDataFrame:
    ohsome_filter = str(
        '(geometry:line or geometry:polygon) and '
        '(highway=* or route=ferry or railway=platform) and not '
        '(footway=separate or sidewalk=separate or sidewalk:both=separate or '
        '(sidewalk:right=separate and sidewalk:left=separate) or '
        '(sidewalk:right=separate and sidewalk:left=no) or (sidewalk:right=no and sidewalk:left=separate))'
    )
    osm_data = request_ohsome(filter=f'({ohsome_filter})  and ({id_filter})').as_dataframe(multi_index=False)
    osm_data['category'] = osm_data.apply(apply_path_category_filters, axis=1, filters=construct_filters().items())
    return osm_data


@pytest.mark.parametrize('category', validation_objects)
def test_construct_filter_validate(osm_return_data, category):
    osm_return_data = osm_return_data.query('category == @category')

    assert set(osm_return_data['@osmId']) == validation_objects[category]


def test_fetch_osm_data(expected_compute_input, responses_mock):
    with open('resources/test/ohsome_line_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_osm_data = gpd.GeoDataFrame(
        data={
            '@other_tags': [{}],
        },
        geometry=[shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])],
        crs=4326,
    )
    computed_osm_data = fetch_osm_data(expected_compute_input.get_aoi_geom(), 'dummy=yes', OhsomeClient())
    geopandas.testing.assert_geodataframe_equal(computed_osm_data, expected_osm_data, check_like=True)


def test_boost_route_members(expected_compute_input, responses_mock):
    with open('resources/test/ohsome_line_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_output = pd.Series(
        data=[
            PathCategory.DEDICATED_EXCLUSIVE,
            PathCategory.DEDICATED_SEPARATED,
            PathCategory.SHARED_WITH_BIKES,
            PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED,
            PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
            PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED,
            PathCategory.INACCESSIBLE,
            PathCategory.MISSING_DATA,
            PathCategory.SHARED_WITH_BIKES,
            PathCategory.SHARED_WITH_BIKES,
        ]
    )

    paths_input = gpd.GeoDataFrame(
        data={
            'category': [
                PathCategory.DEDICATED_EXCLUSIVE,
                PathCategory.DEDICATED_SEPARATED,
                PathCategory.SHARED_WITH_BIKES,
                PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED,
                PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
                PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED,
                PathCategory.INACCESSIBLE,
                PathCategory.MISSING_DATA,
                PathCategory.SHARED_WITH_BIKES,
                PathCategory.MISSING_DATA,
            ]
        },
        geometry=[
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
            shapely.LineString([(0, 0), (1, 0), (1, 1)]),
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
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

    expected_output = pd.Series(data=[PathCategory.SHARED_WITH_BIKES])

    paths_input = gpd.GeoDataFrame(
        data={'category': [PathCategory.MISSING_DATA]},
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


def test_pavement_quality_info_generator():
    verify(generate_detailed_pavement_quality_mapping_info())
