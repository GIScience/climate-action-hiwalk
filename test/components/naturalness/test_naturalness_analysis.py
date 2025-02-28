from climatoology.utility.Naturalness import NaturalnessIndex
import geopandas as gpd
from climatoology.utility.api import TimeRange
from pyproj import CRS
from shapely import LineString, MultiLineString

from walkability.components.naturalness.naturalness_analysis import get_naturalness, fetch_naturalness_by_vector


def test_get_naturalness(default_aoi, operator, naturalness_utility_mock):
    paths = gpd.GeoDataFrame(
        index=[1, 2],
        geometry=[
            LineString([[12.4, 48.25], [12.4, 48.30]]),
            LineString([[12.41, 48.25], [12.41, 48.30]]),
        ],
        crs='EPSG:4326',
    )
    computed_naturalness = get_naturalness(
        aoi=default_aoi, paths=paths, index=NaturalnessIndex.NDVI, naturalness_utility=operator.naturalness_utility
    )

    expected_naturalness = gpd.GeoDataFrame(
        index=[1, 2],
        geometry=[
            LineString([[12.4, 48.25], [12.4, 48.30]]),
            LineString([[12.41, 48.25], [12.41, 48.30]]),
        ],
        data={'naturalness': [0.5, 0.6]},
        crs=CRS.from_epsg(4326),
    )

    gpd.testing.assert_geodataframe_equal(computed_naturalness, expected_naturalness, check_like=True)


def test_fetch_naturalness_vectordata(naturalness_utility_mock):
    vectors = gpd.GeoSeries(
        [
            LineString([[7.381, 47.51], [7.385, 47.51], [7.385, 47.511], [7.381, 47.511], [7.381, 47.51]]),
            MultiLineString(
                [
                    [[7.381, 47.51], [7.385, 47.51], [7.385, 47.511]],
                    [[7.381, 47.511], [7.381, 47.51]],
                ]
            ),
        ]
    )

    greenness_gdf = fetch_naturalness_by_vector(
        naturalness_utility=naturalness_utility_mock, time_range=TimeRange(), vectors=[vectors]
    )
    assert isinstance(greenness_gdf, gpd.GeoDataFrame)
    assert 'naturalness' in greenness_gdf.columns
