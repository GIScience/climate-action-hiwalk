from typing import Callable, Any, Tuple
from urllib.parse import parse_qsl

import geopandas as gpd
import geopandas.testing
import pandas as pd
import pytest
import shapely
from approvaltests import verify
from approvaltests.namer import NamerFactory
from ohsome import OhsomeClient
from pandas import DataFrame
from pydantic_extra_types.color import Color
from requests import PreparedRequest

from walkability.components.categorise_paths.path_categorisation import apply_path_category_filters
from walkability.components.utils.misc import PathCategory, ohsome_filter, fetch_osm_data, get_color

validation_objects = {
    PathCategory.DESIGNATED: {
        'way/84908668',  # https://www.openstreetmap.org/way/84908668 highway=pedestrian
        'way/243233105',  # https://www.openstreetmap.org/way/243233105 highway=footway
        'way/27797959',  # https://www.openstreetmap.org/way/27797959 railway=platform
        'way/98453212',  # https://www.openstreetmap.org/way/98453212 foot=designated
        'way/184725322',  # https://www.openstreetmap.org/way/184725322 sidewalk:right=right and sidewalk:left=separate
        'way/118975501',  # https://www.openstreetmap.org/way/118975501 foot=designated and bicycle=designated and segregated=yes
    },
    PathCategory.DESIGNATED_SHARED_WITH_BIKES: {
        'way/25806383',  # https://www.openstreetmap.org/way/25806383 bicycle=designated & foot=designated
        'way/148612595',  # https://www.openstreetmap.org/way/148612595/history/16 bicycle=yes & highway=residential
        'way/715905259',  # https://www.openstreetmap.org/way/715905259 highway=track
    },
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED: {
        'way/25149880',  # https://www.openstreetmap.org/way/25149880 highway=service
        'way/14193661',  # https://www.openstreetmap.org/way/14193661 highway=living_street
    },
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED: {
        'way/28890081',  # https://www.openstreetmap.org/way/28890081 highway=residential and sidewalk=no and maxspeed=30
        'way/109096915',  # https://www.openstreetmap.org/way/109096915 highway=residential and sidewalk=no and maxspeed=20
    },
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED: {
        'way/25340617',  # https://www.openstreetmap.org/way/25340617 highway=residential and sidewalk=no and maxspeed=50
        'way/258562284',  # https://www.openstreetmap.org/way/258562284 highway=tertiary and sidewalk=no and maxspeed=50
        'way/152645928',  # https://www.openstreetmap.org/way/152645928 highway=residential and sidewalk!=* and maxspeed!=*
    },
    PathCategory.NOT_WALKABLE: {
        'way/400711541',  # https://www.openstreetmap.org/way/400711541 sidewalk=no and maxspeed:backward=70
        'way/24635973',  # https://www.openstreetmap.org/way/24635973 foot=no
        'way/25238623',  # https://www.openstreetmap.org/way/25238623 access=private
        'way/87956068',  # https://www.openstreetmap.org/way/87956068 highway=track and ford=yes
        'way/225895739',  # https://www.openstreetmap.org/way/225895739 service=yes and bus=yes
    },
}


@pytest.fixture(scope='module')
def ohsome_test_data_categorisation(global_aoi, responses_mock) -> pd.DataFrame:
    with open('test/resources/ohsome_categorisation_response.geojson', 'r') as categorisation_examples:
        categorisation_examples = categorisation_examples.read()

    responses_mock.post('https://api.ohsome.org/v1/elements/geometry', body=categorisation_examples)
    osm_data = fetch_osm_data(aoi=global_aoi, osm_filter='', ohsome=OhsomeClient())
    osm_data['category'] = osm_data.apply(apply_path_category_filters, axis=1)

    return osm_data


@pytest.mark.parametrize('category', validation_objects)
def test_construct_filter_validate(ohsome_test_data_categorisation: DataFrame, category: PathCategory):
    ohsome_test_data_categorisation = ohsome_test_data_categorisation[
        ohsome_test_data_categorisation['category'] == category
    ]

    assert set(ohsome_test_data_categorisation['@osmId']) == validation_objects[category]


def test_fetch_osm_data(expected_compute_input, default_aoi, responses_mock):
    with open('test/resources/ohsome_line_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_osm_data = gpd.GeoDataFrame(
        data={
            '@osmId': ['way/171574582'],
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
