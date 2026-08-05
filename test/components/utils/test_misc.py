from unittest.mock import patch

import geopandas as gpd
import geopandas.testing
import pandas as pd
import pytest
from approvaltests import verify
from approvaltests.namer import NamerFactory
from climatoology.base.exception import ClimatoologyUserError, InputValidationError
from ohsome.exceptions import OhsomeException
from ohsome_py2.client import OhsomeClient
from pandas.testing import assert_series_equal
from pydantic_extra_types.color import Color
from shapely import box

from walkability.components.utils.misc import (
    check_paths_count_limit,
    fetch_osm_data,
    generate_colors,
    ohsome_filter,
    sanitize_filenames,
)


@pytest.mark.vcr
def test_fetch_osm_data(small_aoi, parametrized_ohsome_client):
    # Basic test that could probably be deleted (it is a very short function that just calls external code)

    computed_osm_data = fetch_osm_data(
        aoi=small_aoi,
        osm_filter='geometry:polygon and highway=*',
        ohsome=parametrized_ohsome_client,
    )

    assert isinstance(computed_osm_data, gpd.GeoDataFrame)
    assert not computed_osm_data.empty
    assert all([col in computed_osm_data for col in ['osm_id', 'osm_type', 'osm_tags', 'geometry']])


class MockPostClient:
    def post(self, **kwags):
        raise OhsomeException('test: Broken Response', error_code=500)


class MockElements:
    @property
    def geometry(self):
        return MockPostClient()


@patch.object(OhsomeClient, attribute='features_extraction', new=MockElements())
def test_fetch_osm_data_ohsome_error(default_aoi, default_ohsome_client_v1):
    # We won't test this with V2 because it doesn't need the API, just the mocks defined above
    with pytest.raises(ClimatoologyUserError):
        fetch_osm_data(
            aoi=default_aoi,
            osm_filter='dummy=yes',
            ohsome=default_ohsome_client_v1,
        )


def test_generate_colors():
    expected_output = pd.Series(data=[Color('#3b4cc0'), Color('#dcdddd'), Color('#b40426')])

    expected_input = pd.Series([1.0, 0.5, 0.0])
    computed_output = generate_colors(expected_input, min_value=0, max_value=1, cmap_name='coolwarm_r')

    assert_series_equal(computed_output, expected_output)


@pytest.mark.parametrize('geometry_type', ['line', 'polygon'])
def test_ohsome_filter(geometry_type):
    verify(ohsome_filter(geometry_type), options=NamerFactory.with_parameters(geometry_type))


@pytest.mark.vcr
def test_check_paths_count_limit(parametrized_ohsome_client):
    big_aoi = box(8.5, 49.0, 9.0, 49.5)
    with pytest.raises(InputValidationError):
        check_paths_count_limit(
            aoi=big_aoi,
            count_limit=5000,
            ohsome=parametrized_ohsome_client,
        )


def test_sanitize_filenames():
    unsanitized_filename = 'West/Südost-Stadt'
    expected = 'WestSdost-Stadt'
    recieved = sanitize_filenames(unsanitized_filename)

    assert recieved == expected
