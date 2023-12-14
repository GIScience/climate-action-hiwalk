from unittest import mock

import os
from plugin_blueprint.operator_worker import OperatorBlueprint


@mock.patch.dict(os.environ, {'LULC_HOST': 'localhost', 'LULC_PORT': '80', 'LULC_ROOT_URL': '/api/lulc/'}, clear=True)
def test_plugin_info_request(expected_info_output):
    operator = OperatorBlueprint()
    assert operator.info() == expected_info_output


@mock.patch.dict(os.environ, {'LULC_HOST': 'localhost', 'LULC_PORT': '80', 'LULC_ROOT_URL': '/api/lulc/'}, clear=True)
def test_plugin_compute_request(expected_compute_input, expected_compute_output, compute_resources, web_apis):
    operator = OperatorBlueprint()
    assert operator.compute(resources=compute_resources,
                            params=expected_compute_input) == expected_compute_output
