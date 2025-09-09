from unittest.mock import patch

import pytest
from climatoology.base.baseoperator import _Artifact
from climatoology.base.info import _Info

from test.conftest import filter_start_matcher
from walkability.core.input import ComputeInputWalkability, WalkabilityIndicators


def test_plugin_info_request(operator):
    assert isinstance(operator.info(), _Info)


@pytest.fixture
def mock_detour_factor_calculation(expected_detour_factors):
    # This higher level mock exists because mocking a response for the api calls required for all hexcells of the entired default_aoi, is massive
    # The functionality is already covered by smaller tests in test/components/network_analyses/test_detour_analysis.py
    with patch('walkability.components.network_analyses.detour_analysis.get_detour_factors') as detour_factors:
        detour_factors.return_value = expected_detour_factors
        yield detour_factors


def test_plugin_compute_request_minimal(operator, default_aoi, default_aoi_properties, compute_resources, ohsome_api):
    computed_artifacts = operator.compute(
        resources=compute_resources,
        aoi=default_aoi,
        aoi_properties=default_aoi_properties,
        params=ComputeInputWalkability(),
    )

    assert len(computed_artifacts) == 6
    for artifact in computed_artifacts:
        assert isinstance(artifact, _Artifact)


def test_plugin_compute_request_all_optionals(
    operator,
    expected_compute_input,
    default_aoi,
    default_aoi_properties,
    compute_resources,
    ohsome_api,
    ors_isochrone_api,
):
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
    computed_artifacts = operator.compute(
        resources=compute_resources,
        aoi=default_aoi,
        aoi_properties=default_aoi_properties,
        params=expected_compute_input,
    )

    assert len(computed_artifacts) == 12
    for artifact in computed_artifacts:
        assert isinstance(artifact, _Artifact)
