from plugin_blueprint.operator_worker import OperatorBlueprint


def test_plugin_info_request(settings, expected_info_output):
    operator = OperatorBlueprint(settings.lulc_host,
                                 settings.lulc_port,
                                 settings.lulc_root_url)
    assert operator.info() == expected_info_output


def test_plugin_compute_request(settings, expected_compute_input, expected_compute_output, compute_resources, web_apis):
    operator = OperatorBlueprint(settings.lulc_host,
                                 settings.lulc_port,
                                 settings.lulc_root_url)
    assert operator.compute(resources=compute_resources,
                            params=expected_compute_input) == expected_compute_output
