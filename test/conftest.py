import json
import uuid
from typing import Any, Callable, Tuple
from unittest.mock import patch
from urllib.parse import parse_qsl

import geopandas as gpd
import pandas as pd
import pytest
import responses
import shapely
from climatoology.base.baseoperator import AoiProperties
from climatoology.base.computation import ComputationScope
from pyproj import CRS
from requests import PreparedRequest
from responses import matchers
from shapely.geometry import LineString

from walkability.components.comfort.benches_and_drinking_water import PointsOfInterest
from walkability.components.utils.misc import PathCategory
from walkability.core.input import ComputeInputWalkability
from walkability.core.operator_worker import OperatorWalkability
from walkability.core.settings import ORSSettings


@pytest.fixture
def expected_compute_input() -> ComputeInputWalkability:
    return ComputeInputWalkability()


@pytest.fixture(scope='module')
def global_aoi() -> shapely.MultiPolygon:
    return shapely.MultiPolygon([[[[-90, -180], [90, -180], [90, 180], [-90, 180], [-90, -180]]]])


@pytest.fixture
def default_aoi() -> shapely.MultiPolygon:
    return shapely.MultiPolygon(
        polygons=[
            [
                [
                    [12.29, 48.20],
                    [12.29, 48.34],
                    [12.48, 48.34],
                    [12.48, 48.20],
                    [12.29, 48.20],
                ]
            ]  # type: ignore
        ]
    )


@pytest.fixture
def small_aoi() -> shapely.Polygon:
    return shapely.box(8.689282, 49.416193, 8.693186, 49.419123)


@pytest.fixture
def default_aoi_properties() -> AoiProperties:
    return AoiProperties(name='Heidelberg', id='heidelberg')


# The following fixtures can be ignored on plugin setup
@pytest.fixture
def compute_resources():
    with ComputationScope(uuid.uuid4()) as resources:
        yield resources


@pytest.fixture(scope='module')
def responses_mock():
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def ordered_responses_mock():
    with responses.RequestsMock(registry=responses.registries.OrderedRegistry) as rsps:
        yield rsps


@pytest.fixture
def operator(naturalness_utility_mock, default_ors_settings) -> OperatorWalkability:
    return OperatorWalkability(naturalness_utility_mock, default_ors_settings)


@pytest.fixture
def default_ors_settings() -> ORSSettings:
    return ORSSettings(ors_base_url='http://localhost:8080/ors', ors_api_key='test-key')


@pytest.fixture
def expected_detour_factors() -> pd.DataFrame:
    detour_factors = pd.DataFrame(
        data={
            'detour_factor': [
                1.3995538900828162,
                1.219719961221372,
                1.454343083874761,
                1.7969363677141994,
                1.4832090368368422,
                1.8521635465676833,
                1.3880294081510607,
            ],
            'id': [
                '8a1faa996847fff',
                '8a1faa99684ffff',
                '8a1faa996857fff',
                '8a1faa99685ffff',
                '8a1faa9968c7fff',
                '8a1faa9968effff',
                '8a1faa996bb7fff',
            ],
        }
    ).set_index('id')
    return detour_factors.h3.h3_to_geo_boundary()


@pytest.fixture
def ohsome_api(responses_mock):
    with (
        open('test/resources/ohsome_line_response.geojson', 'r') as line_file,
        open('test/resources/ohsome_polygon_response.geojson', 'r') as polygon_file,
    ):
        line_body = line_file.read()
        polygon_body = polygon_file.read()

    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=line_body,
        match=[filter_start_matcher('geometry:line')],
    )

    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=polygon_body,
        match=[filter_start_matcher('geometry:polygon')],
    )
    return responses_mock


@pytest.fixture
def naturalness_utility_mock():
    with patch('climatoology.utility.Naturalness.NaturalnessUtility') as naturalness_utility:
        vectors = gpd.GeoSeries(
            index=[1, 2],
            data=[
                LineString([[12.4, 48.25], [12.4, 48.30]]),
                LineString([[12.41, 48.25], [12.41, 48.30]]),
            ],
            crs=CRS.from_epsg(4326),
        )
        return_gdf = gpd.GeoDataFrame(
            index=[1, 2], data={'median': [0.5, 0.6]}, geometry=vectors, crs=CRS.from_epsg(4326)
        )

        naturalness_utility.compute_vector.return_value = return_gdf
        yield naturalness_utility


@pytest.fixture
def ors_elevation_api(responses_mock):
    responses_mock.post(
        'https://api.openrouteservice.org/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by https://srtm.csi.cgiar.org',
            'geometry': [[12.3, 48.22, 1.0], [12.3005, 48.22, 2.0]],
            'timestamp': 1738238852,
            'version': '0.2.1',
        },
        match=[
            matchers.header_matcher({'Authorization': 'test-key'}),
            matchers.json_params_matcher(
                {
                    'format_in': 'polyline',
                    'format_out': 'polyline',
                    'dataset': 'srtm',
                    'geometry': [[12.3, 48.22], [12.3005, 48.22]],
                }
            ),
        ],
    )
    return responses_mock


@pytest.fixture
def ors_isochrone_api(responses_mock):
    with open('test/resources/ors_isochrones.geojson', 'r') as isochrones:
        isochrones_body = isochrones.read()

    responses_mock.post('http://localhost:8080/ors/v2/isochrones/foot-walking/geojson', body=isochrones_body)


@pytest.fixture
def large_mock_ors_snapping_api(ordered_responses_mock, snapping_response):
    ordered_responses_mock.add(
        method='POST', url='http://localhost:8080/ors/v2/snap/foot-walking', json=snapping_response
    )


@pytest.fixture
def snapping_response():
    return {
        'locations': [
            {'location': [8.690396, 49.418228], 'snapped_distance': 19.2},
            {'location': [8.690353, 49.417188], 'snapped_distance': 18.76},
            {'location': [8.689776, 49.416313], 'snapped_distance': 29.88},
            {'location': [8.692346, 49.416992], 'snapped_distance': 0.43},
            {'location': [8.693091, 49.418907], 'snapped_distance': 1.28},
            {'location': [8.692439, 49.418159], 'snapped_distance': 43.83},
            {'location': [8.691352, 49.419144], 'snapped_distance': 6.04},
        ]
    }


@pytest.fixture
def large_mock_ors_directions_api(ordered_responses_mock, ors_directions_responses):
    for response in ors_directions_responses['responses']:
        ordered_responses_mock.add(
            method='POST', url='https://api.openrouteservice.org/v2/directions/foot-walking', json=response
        )


@pytest.fixture
def ors_directions_responses() -> dict:
    with open('test/resources/ors_directions_responses.json', 'r') as file:
        return json.load(file)


@pytest.fixture
def default_path_geometry() -> shapely.LineString:
    return shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])


@pytest.fixture
def default_polygon_geometry() -> shapely.Polygon:
    return shapely.Polygon(((12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22), (12.3, 48.22)))


@pytest.fixture
def default_path(default_path_geometry) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            '@other_tags': [{}],
            'geometry': [default_path_geometry],
        },
        crs='EPSG:4326',
    )


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


@pytest.fixture
def empty_pois(default_path):
    with patch('walkability.components.comfort.benches_and_drinking_water.request_pois') as mock:
        mock.return_value = gpd.GeoDataFrame()
        yield mock


@pytest.fixture
def default_max_walking_distance_map() -> dict[PointsOfInterest, float]:
    m_per_minute = 66.666
    return {
        PointsOfInterest.DRINKING_WATER: m_per_minute * 10,
        PointsOfInterest.SEATING: m_per_minute * 5,
        PointsOfInterest.REMAINDER: m_per_minute * 15,
    }
