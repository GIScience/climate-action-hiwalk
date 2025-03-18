from climatoology.base.baseoperator import _Artifact
from climatoology.base.info import _Info

from test.conftest import filter_start_matcher
from walkability.core.input import ComputeInputWalkability


def test_plugin_info_request(operator):
    assert isinstance(operator.info(), _Info)


def test_plugin_compute_request(
    operator, expected_compute_input, default_aoi, default_aoi_properties, compute_resources, ohsome_api, ors_api
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

    assert len(computed_artifacts) == 7
    for artifact in computed_artifacts:
        assert isinstance(artifact, _Artifact)


def test_plugin_compute_request_empty(operator, default_aoi, default_aoi_properties, compute_resources, ohsome_api):
    computed_artifacts = operator.compute(
        resources=compute_resources,
        aoi=default_aoi,
        aoi_properties=default_aoi_properties,
        params=ComputeInputWalkability(walkable_categories_selection=set()),
    )

    assert len(computed_artifacts) == 2
    for artifact in computed_artifacts:
        assert isinstance(artifact, _Artifact) or artifact is None
