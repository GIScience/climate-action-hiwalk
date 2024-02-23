from walkability.operator_worker import OperatorWalkability


def test_plugin_info_request(settings, expected_info_output, lulc_utility):
    operator = OperatorWalkability(
        settings.lulc_host,
        settings.lulc_port,
        settings.lulc_path,
    )
    assert operator.info() == expected_info_output


def test_plugin_compute_request(settings, expected_compute_input, expected_compute_output, compute_resources, web_apis):
    operator = OperatorWalkability(
        settings.lulc_host,
        settings.lulc_port,
        settings.lulc_path,
    )
    assert (
        operator.compute(
            resources=compute_resources,
            params=expected_compute_input,
        )
        == expected_compute_output
    )
