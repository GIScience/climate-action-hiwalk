import geopandas as gpd
import shapely
from pydantic_extra_types.color import Color

from walkability.components.wellness.benches_and_drinking_water import PointsOfInterest
from walkability.components.wellness.wellness_artifacts import assign_color, assign_label


def test_assign_color(default_max_walking_distance_map):
    poi = PointsOfInterest.SEATING
    max_walking_distance = default_max_walking_distance_map[poi]

    string = shapely.LineString([(1.0, 1.0), (1.0, 1.0)])
    data = gpd.GeoDataFrame(
        data={
            'value': [0.0, 200, None],
        },
        geometry=[shapely.Point(0.0, 0.0), string, string],
    )
    received = assign_color(data, poi_type=poi, max_walking_distance=max_walking_distance, min_value=0.0)

    assert received['color'].to_list() == [Color('brown'), Color('#f2cbb7'), Color('red')]


def test_assign_label(default_max_walking_distance_map):
    poi_type = PointsOfInterest.SEATING
    max_walking_distance = default_max_walking_distance_map[poi_type]

    path = shapely.LineString([(0.0, 0.0), (1.0, 1.0)])
    paths = gpd.GeoDataFrame(data={'value': [0.0, 200, None]}, geometry=[shapely.Point(1.0, 1.0), path, path])

    computed_labels = paths.apply(assign_label, poi_type=poi_type, max_walking_distance=max_walking_distance, axis=1)
    assert computed_labels.to_list() == ['benches', '< 200m', '> 333m']
