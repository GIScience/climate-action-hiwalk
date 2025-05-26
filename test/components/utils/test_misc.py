import geopandas as gpd
import geopandas.testing
import pandas as pd
import pytest
import shapely
from approvaltests import verify
from approvaltests.namer import NamerFactory
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color

from walkability.components.utils.misc import fetch_osm_data, generate_colors, ohsome_filter


def test_fetch_osm_data(expected_compute_input, default_aoi, responses_mock):
    with open('test/resources/ohsome_line_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_osm_data = gpd.GeoDataFrame(
        data={
            '@osmId': ['way/171574582'],
            '@other_tags': [{'highway': 'pedestrian'}],
        },
        geometry=[shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])],
        crs=4326,
    )
    computed_osm_data = fetch_osm_data(default_aoi, 'dummy=yes', OhsomeClient())
    geopandas.testing.assert_geodataframe_equal(computed_osm_data, expected_osm_data, check_like=True)


def test_generate_colors():
    expected_output = [Color('#3b4cc0'), Color('#dcdddd'), Color('#b40426')]

    expected_input = pd.Series([1.0, 0.5, 0.0])
    computed_output = generate_colors(expected_input, min_value=0, max_value=1, cmap_name='coolwarm_r')

    assert computed_output == expected_output


@pytest.mark.parametrize('geometry_type', ['line', 'polygon'])
def test_ohsome_filter(geometry_type):
    verify(ohsome_filter(geometry_type), options=NamerFactory.with_parameters(geometry_type))
