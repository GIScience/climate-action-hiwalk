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


def test_plugin_compute_request(
    operator,
    expected_compute_input,
    default_aoi,
    default_aoi_properties,
    compute_resources,
    ohsome_api,
):
    with open('test/resources/ohsome_admin_response.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    ohsome_api.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )

    computed_artifacts = operator.compute(
        resources=compute_resources,
        aoi=default_aoi,
        aoi_properties=default_aoi_properties,
        params=expected_compute_input,
    )

    assert len(computed_artifacts) == 8
    for artifact in computed_artifacts:
        assert isinstance(artifact, _Artifact)


def test_plugin_compute_request_empty(operator, default_aoi, default_aoi_properties, compute_resources, ohsome_api):
    computed_artifacts = operator.compute(
        resources=compute_resources,
        aoi=default_aoi,
        aoi_properties=default_aoi_properties,
        params=ComputeInputWalkability(walkable_categories_selection=set()),
    )

    assert len(computed_artifacts) == 6
    for artifact in computed_artifacts:
        assert isinstance(artifact, _Artifact) or artifact is None


def test_plugin_compute_request_with_only_one_optional_indicator(
    operator,
    default_aoi,
    default_aoi_properties,
    compute_resources,
    ohsome_api,
    ors_elevation_api,
    mock_detour_factor_calculation,
):
    computed_artifacts = operator.compute(
        resources=compute_resources,
        aoi=default_aoi,
        aoi_properties=default_aoi_properties,
        params=ComputeInputWalkability(
            optional_indicators={WalkabilityIndicators.SLOPE, WalkabilityIndicators.DETOURS}
        ),
    )

    assert len(computed_artifacts) == 10
    for artifact in computed_artifacts:
        assert isinstance(artifact, _Artifact) or artifact is None
