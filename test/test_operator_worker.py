import geopandas as gpd
import shapely
from geopandas import testing
from pydantic_extra_types.color import Color


def test_sidewalk_classifier(operator, expected_compute_input, ohsome_api):
    sidewalk_geom = shapely.LineString([[8.7, 49.4], [8.7, 49.5], [8.8, 49.4]])

    expected_gdf = gpd.GeoDataFrame(
        data={'highway': ['path'], '@other_tags': [{}], 'color': [Color('blue')], 'geometry': [sidewalk_geom]},
        crs='EPSG:4326',
    )
    computed_gdf = operator.get_sidewalks(expected_compute_input.get_geom())

    testing.assert_geodataframe_equal(
        computed_gdf,
        expected_gdf,
        check_like=True,
        check_geom_type=True,
        check_less_precise=True,
    )
