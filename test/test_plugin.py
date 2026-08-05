from unittest.mock import patch

import pytest
import responses
import shapely
from climatoology.base.baseoperator import Artifact
from climatoology.base.plugin_info import PluginInfo

from test.conftest import filter_start_matcher
from walkability.core.input import ComputeInputWalkability, WalkabilityIndicators


def test_plugin_info_request(operator):
    assert isinstance(operator.info(), PluginInfo)


@pytest.fixture
def mock_detour_factor_calculation(expected_detour_factors):
    # This higher level mock exists because mocking a response for the api calls required for all hexcells of the entired default_aoi, is massive
    # The functionality is already covered by smaller tests in test/components/network_analyses/test_detour_analysis.py
    with patch('walkability.components.network_analyses.detour_analysis.get_detour_factors') as detour_factors:
        detour_factors.return_value = expected_detour_factors
        yield detour_factors


@pytest.mark.vcr
def test_plugin_compute_request_minimal(
    operator,
    small_aoi,
    default_aoi_properties,
    compute_resources,
    parametrized_ohsome_client,
):
    operator.ohsome = parametrized_ohsome_client
    computed_artifacts = operator.compute(
        resources=compute_resources,
        aoi=small_aoi,
        aoi_properties=default_aoi_properties,
        params=ComputeInputWalkability(),
    )

    assert len(computed_artifacts) == 6
    for artifact in computed_artifacts:
        assert isinstance(artifact, Artifact)


# The test below is the only one requiring responses mocks, so the fixtures are all defined here


@pytest.fixture
def responses_mock():
    with responses.RequestsMock() as rsps:
        yield rsps


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
def ohsome_api_count(responses_mock):
    with open('test/resources/ohsome_count_response.json', 'rb') as paths_count_file:
        paths_count_body = paths_count_file.read()

    responses_mock.post(
        'https://api.ohsome.org/v1/elements/count',
        body=paths_count_body,
    )

    return responses_mock


@pytest.fixture
def ors_isochrone_api(responses_mock):
    with open('test/resources/ors_isochrones.geojson', 'r') as isochrones:
        isochrones_body = isochrones.read()

    responses_mock.post('http://vcr-secret-url/v2/isochrones/foot-walking/geojson', body=isochrones_body)


def test_plugin_compute_request_all_optionals(
    operator,
    expected_compute_input,
    default_aoi_properties,
    compute_resources,
    ohsome_api,
    ohsome_api_count,
    ors_isochrone_api,
    slopes_mock,
):
    # Too complex to test ohsome v2 with mocks
    with (
        open('test/resources/ohsome_admin_response.geojson', 'r') as admin_file,
        open('test/resources/ohsome_drinking_water.geojson', 'r') as drinking_water,
    ):
        admin_body = admin_file.read()
        drinking_water_body = drinking_water.read()
    ohsome_api.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )
    ohsome_api.post(
        'https://api.ohsome.org/v1/elements/centroid',
        body=drinking_water_body,
    )

    expected_compute_input = expected_compute_input.model_copy(deep=True)
    expected_compute_input.optional_indicators = {e for e in WalkabilityIndicators}

    aoi = shapely.MultiPolygon(
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

    computed_artifacts = operator.compute(
        resources=compute_resources,
        aoi=aoi,
        aoi_properties=default_aoi_properties,
        params=expected_compute_input,
    )

    assert compute_resources.artifact_errors == {'Detour Factors': ''}

    assert len(computed_artifacts) == 20
    for artifact in computed_artifacts:
        assert isinstance(artifact, Artifact)
