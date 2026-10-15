import geopandas as gpd
import shapely
from numpy.testing import assert_almost_equal

from walkability.components.utils.geometry import CAN_DEFAULT_CRS, length_weighted_mean


def test_length_weighted_mean():
    col = 'column'
    input_data = gpd.GeoDataFrame(
        data={col: [1, 4]},
        geometry=[shapely.LineString([(0.0, 0.0), (0.0, 0.2)]), shapely.LineString([(0.0, 0.0), (0.0, 0.1)])],
        crs=CAN_DEFAULT_CRS,
    )

    expected = 2

    received = length_weighted_mean(input_data, col=col)

    assert_almost_equal(received, expected)
