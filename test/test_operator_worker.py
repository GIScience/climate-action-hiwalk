import geopandas as gpd
import shapely
from geopandas import testing
from pydantic_extra_types.color import Color

from walkability.utils import Rating


def test_get_paths(operator, expected_compute_input, ohsome_api):
    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])
    polygon_geom = shapely.Polygon(((12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22), (12.3, 48.22)))

    expected_gdf = gpd.GeoDataFrame(
        data={
            'category': 2 * [Rating.EXCLUSIVE, Rating.EXPLICIT, Rating.PROBABLE, Rating.INACCESSIBLE],
            'color': 2 * [Color('#006837'), Color('#84ca66'), Color('#feffbe'), Color('#a50026')],
            'geometry': 4 * [line_geom] + 4 * [polygon_geom],
        },
        crs='EPSG:4326',
    )
    computed_gdf = operator.get_paths(expected_compute_input.get_geom())

    testing.assert_geodataframe_equal(
        computed_gdf,
        expected_gdf,
        check_like=True,
        check_geom_type=True,
        check_less_precise=True,
    )
