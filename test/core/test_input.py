from walkability.core.input import ComputeInputWalkability, IDW


def test_get_distance_weighting_function_step_func():
    test_input = ComputeInputWalkability(idw_method=IDW.STEP_FUNCTION)
    received_func = ComputeInputWalkability.get_distance_weighting_function(test_input)
    assert received_func.__name__ == 'step_func'
    assert callable(received_func)
    assert received_func(100) == 1
    assert received_func(500) == 0.6
    assert received_func(1000) == 0.25
    assert received_func(1500) == 0.08
    assert received_func(2000) == 0


def test_get_distance_weighting_function_polynomial():
    test_input = ComputeInputWalkability(idw_method=IDW.POLYNOMIAL)
    received_func = ComputeInputWalkability.get_distance_weighting_function(test_input)
    assert received_func.__name__ == 'scaled_polynom'
    assert callable(received_func)
    assert round(received_func(1000), 2) == 0.37
    assert received_func(2000) == 0


def test_get_distance_weighting_function_none():
    test_input = ComputeInputWalkability(idw_method=IDW.NONE)
    received_func = ComputeInputWalkability.get_distance_weighting_function(test_input)
    assert callable(received_func)
    assert received_func(10) == 1.0
    assert received_func(100) == 1.0
