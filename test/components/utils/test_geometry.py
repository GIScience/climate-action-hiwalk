import shapely
from shapely.testing import assert_geometries_equal

from walkability.components.utils.geometry import fix_geometry_collection


def test_fix_geometry_collection():
    expected_geom = shapely.LineString([(0, 0), (1, 0), (1, 1)])

    geometry_collection_input = shapely.GeometryCollection(
        [
            shapely.Point(-1, -1),
            expected_geom,
        ]
    )
    point_input = shapely.Point(-1, -1)

    input_output_map = {
        'unchanged': {'input': expected_geom, 'output': expected_geom},
        'extracted': {'input': geometry_collection_input, 'output': expected_geom},
        'ignored': {'input': point_input, 'output': shapely.LineString()},
    }
    for _, map_input_output_types in input_output_map.items():
        computed_geom = fix_geometry_collection(map_input_output_types['input'])
        assert_geometries_equal(computed_geom, map_input_output_types['output'])
