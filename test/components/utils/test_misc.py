import logging
import urllib.parse
from functools import partial
from typing import Callable, Any, Tuple
from urllib.parse import parse_qsl

import geopandas as gpd
import geopandas.testing
import pandas as pd
import pytest
import shapely
from approvaltests import verify
from approvaltests.namer import NamerFactory
from ohsome import OhsomeClient, OhsomeResponse
from pydantic_extra_types.color import Color
from requests import PreparedRequest
from urllib3 import Retry

from walkability.components.categorise_paths.path_categorisation import apply_path_category_filters
from walkability.components.utils.misc import PathCategory, ohsome_filter, fetch_osm_data, get_color

validation_objects = {
    PathCategory.DESIGNATED: {
        'way/84908668',
        'way/243233105',
        'way/27797959',
        'way/98453212',
        'way/184725322',
        'way/118975501',
    },
    # https://www.openstreetmap.org/way/98453212 foot=designated
    # https://www.openstreetmap.org/way/84908668 highway=pedestrian
    # https://www.openstreetmap.org/way/27797959 railway=platform
    # https://www.openstreetmap.org/way/184725322 sidewalk:right=right and sidewalk:left=separate
    # https://www.openstreetmap.org/way/243233105 highway=footway
    # https://www.openstreetmap.org/way/118975501 foot=designated and bicycle=designated and segregated=yes
    PathCategory.DESIGNATED_SHARED_WITH_BIKES: {'way/25806383', 'way/148612595', 'way/715905259'},
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
    PathCategory.NOT_WALKABLE: {'way/400711541', 'way/24635973', 'way/25238623', 'way/87956068'},
    # https://www.openstreetmap.org/way/400711541 sidewalk=no and maxspeed:backward=70
    # https://www.openstreetmap.org/way/24635973 foot=no
    # https://www.openstreetmap.org/way/25238623 access=private
    # https://www.openstreetmap.org/way/225895739 service=yes and bus=yes
    # https://www.openstreetmap.org/way/87956068 highway=track and ford=yes
}


@pytest.fixture(scope='module')
def bpolys():
    """Small bounding boxes."""
    bpolys = gpd.GeoSeries(
        data=[
            # Heidelberg (large box but not full city area)
            shapely.box(8.61920, 49.36622, 8.71928, 49.44017),
            # Bammental (small box for way/87956068)
            shapely.box(8.7868406, 49.3701598, 8.7868428, 49.3701902),
            # Lagos (small box for way/152645928)
            shapely.box(3.354680, 6.444900, 3.369928, 6.455165),
        ],
        crs='EPSG:4326',
    )
    # NOTE: used to generate geojson.io link
    base_url = 'https://geojson.io/#data=data:application/json,'
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
        timeout=120,
    )


@pytest.fixture(scope='module')
def id_filter() -> str:
    """Optimization to make the ohsome API request time faster."""
    full_ids = set().union(*validation_objects.values())
    return f'id:({",".join(full_ids)})'


@pytest.fixture(scope='module')
def osm_return_data(request_ohsome: partial[OhsomeResponse], id_filter: str) -> pd.DataFrame:
    osm_line_data = request_ohsome(filter=f'({ohsome_filter("line")})  and ({id_filter})').as_dataframe(
        multi_index=False
    )
    osm_line_data['category'] = osm_line_data.apply(apply_path_category_filters, axis=1)

    osm_polygon_data = request_ohsome(filter=f'({ohsome_filter("polygon")})  and ({id_filter})').as_dataframe(
        multi_index=False
    )
    osm_polygon_data['category'] = osm_polygon_data.apply(apply_path_category_filters, axis=1)

    return pd.concat([osm_line_data, osm_polygon_data])


@pytest.mark.slow
@pytest.mark.parametrize('category', validation_objects)
def test_construct_filter_validate(osm_return_data: pd.DataFrame, category: PathCategory):
    osm_return_data = osm_return_data[osm_return_data['category'] == category]

    assert set(osm_return_data['@osmId']) == validation_objects[category]


def test_fetch_osm_data(expected_compute_input, default_aoi, responses_mock):
    with open('test/resources/ohsome_line_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_osm_data = gpd.GeoDataFrame(
        data={
            '@other_tags': [{'highway': 'pedestrian'}],
        },
        geometry=[shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])],
        crs=4326,
    )
    computed_osm_data = fetch_osm_data(default_aoi, 'dummy=yes', OhsomeClient())
    geopandas.testing.assert_geodataframe_equal(computed_osm_data, expected_osm_data, check_like=True)


def test_get_color():
    expected_output = pd.Series([Color('#3b4cc0'), Color('#dcdddd'), Color('#b40426')])

    expected_input = pd.Series([1.0, 0.5, 0.0])
    computed_output = get_color(expected_input)

    pd.testing.assert_series_equal(computed_output, expected_output)


@pytest.mark.parametrize('geometry_type', ['line', 'polygon'])
def test_ohsome_filter(geometry_type):
    verify(ohsome_filter(geometry_type), options=NamerFactory.with_parameters(geometry_type))


def filter_start_matcher(filter_start: str) -> Callable[..., Any]:
    def match(request: PreparedRequest) -> Tuple[bool, str]:
        request_body = request.body
        qsl_body = dict(parse_qsl(request_body, keep_blank_values=False)) if request_body else {}

        if request_body is None:
            return False, 'The given request has no body'
        elif qsl_body.get('filter') is None:
            return False, 'Filter parameter not set'
        else:
            valid = qsl_body.get('filter', '').startswith(filter_start)
            return (True, '') if valid else (False, f'The filter parameter does not start with {filter_start}')

    return match
