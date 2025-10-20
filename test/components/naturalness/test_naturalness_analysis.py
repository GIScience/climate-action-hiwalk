import geopandas as gpd
import plotly.graph_objects as go
import shapely
from climatoology.utility.api import TimeRange
from climatoology.utility.Naturalness import NaturalnessIndex
from pyproj import CRS
from shapely import LineString, MultiLineString

from walkability.components.naturalness.naturalness_analysis import (
    fetch_naturalness_by_vector,
    get_naturalness,
    summarise_naturalness,
)


def test_get_naturalness(operator, naturalness_utility_mock):
    polygon_geom = shapely.Polygon(((12.3, 48.2), (12.3, 48.25), (12.35, 48.25), (12.3, 48.25)))
    paths = gpd.GeoDataFrame(
        index=[1, 2],
        geometry=[
            LineString([[12.4, 48.25], [12.4, 48.30]]),
            LineString([[12.41, 48.25], [12.41, 48.30]]),
        ],
        crs='EPSG:4326',
    )
    polygons = gpd.GeoDataFrame(
        index=[1, 2],
        geometry=[polygon_geom, polygon_geom],
        crs='EPSG:4326',
    )
    computed_naturalness = get_naturalness(
        paths=paths, polygons=polygons, index=NaturalnessIndex.NDVI, naturalness_utility=operator.naturalness_utility
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

    gpd.testing.assert_geodataframe_equal(computed_naturalness[0], expected_naturalness, check_like=True)


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


def test_fetch_naturalness_polygon(naturalness_utility_mock):
    vectors = gpd.GeoSeries(
        [
            shapely.Polygon(((12.3, 48.2), (12.3, 48.25), (12.35, 48.25), (12.35, 48.2))),
            shapely.Polygon(((12.3, 48.2), (12.3, 48.25), (12.35, 48.25), (12.35, 48.2))),
        ]
    )
    greenness_gdf = fetch_naturalness_by_vector(
        naturalness_utility=naturalness_utility_mock, time_range=TimeRange(), vectors=[vectors]
    )
    assert isinstance(greenness_gdf, gpd.GeoDataFrame)
    assert 'naturalness' in greenness_gdf.columns


def test_summarise_naturalness(default_path_geometry, default_polygon_geometry):
    input_paths = gpd.GeoDataFrame(
        data={
            'naturalness': [0.4, 0.6],
            'geometry': [default_path_geometry] + [default_polygon_geometry],
        },
        crs='EPSG:4326',
    )
    bar_chart = summarise_naturalness(paths=input_paths)

    assert isinstance(bar_chart, go.Figure)
    assert bar_chart['data'][0]['x'] == ('Medium (0.3 to 0.6)',)
    assert bar_chart['data'][0]['y'] == (0.12,)
