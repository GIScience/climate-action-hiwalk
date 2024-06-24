from walkability.utils import filter_start_matcher


def test_plugin_info_request(operator, expected_info_output):
    assert operator.info() == expected_info_output


def test_plugin_compute_request(
    operator,
    expected_compute_input,
    expected_compute_output,
    compute_resources,
    ohsome_api,
):
    with open('resources/test/ohsome_admin_response.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    ohsome_api.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )
    assert operator.compute(resources=compute_resources, params=expected_compute_input) == expected_compute_output
