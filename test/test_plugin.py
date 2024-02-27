def test_plugin_info_request(operator, expected_info_output):
    assert operator.info() == expected_info_output


def test_plugin_compute_request(
    operator,
    expected_compute_input,
    expected_compute_output,
    compute_resources,
    ohsome_api,
):
    assert operator.compute(resources=compute_resources, params=expected_compute_input) == expected_compute_output
