import geopandas as gpd
import plotly.graph_objects as go
from geopandas.testing import assert_geodataframe_equal
from pyproj import CRS
from responses import matchers
from shapely.geometry.linestring import LineString
from shapely.geometry.multilinestring import MultiLineString

from walkability.components.slope.slope_analysis import get_slope, summarise_slope


def test_get_slope(global_aoi, responses_mock, default_ors_settings):
    responses_mock.post(
        'http://localhost:8080/ors/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by https://srtm.csi.cgiar.org',
            'geometry': [
                [0.0, 0.0, 1.0],
                [0.01, 0.01, 2.0],
            ],
            'timestamp': 1738238852,
            'version': '0.2.1',
        },
        match=[
            matchers.header_matcher({'Authorization': 'test-key'}),
            matchers.json_params_matcher(
                {
                    'dataset': 'srtm',
                    'format_in': 'polyline',
                    'format_out': 'polyline',
                    'geometry': [[0.0, 0.0], [0.01, 0.01]],
                }
            ),
        ],
    )

    paths = gpd.GeoDataFrame(
        index=[1],
        data={'@osmId': ['way/a']},
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
        ],
        crs='EPSG:4326',
    )
    computed_slope = get_slope(aoi=global_aoi, paths=paths, ors_settings=default_ors_settings)

    expected_naturalness = gpd.GeoDataFrame(
        index=[1],
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
        ],
        data={'slope': [0.06], '@osmId': ['way/a']},
        crs=CRS.from_epsg(4326),
    )

    assert_geodataframe_equal(computed_slope, expected_naturalness, check_like=True)


def test_get_negative_slope(global_aoi, responses_mock, default_ors_settings):
    responses_mock.post(
        'http://localhost:8080/ors/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by https://srtm.csi.cgiar.org',
            'geometry': [
                [0.0, 0.0, 1.0],
                [0.01, 0.01, 2.0],
                [0.02, 0.02, 2.0],
                [0.03, 0.03, 1.0],
            ],
            'timestamp': 1738238852,
            'version': '0.2.1',
        },
        match=[
            matchers.header_matcher({'Authorization': 'test-key'}),
            matchers.json_params_matcher(
                {
                    'dataset': 'srtm',
                    'format_in': 'polyline',
                    'format_out': 'polyline',
                    'geometry': [[0.0, 0.0], [0.01, 0.01], [0.02, 0.02], [0.03, 0.03]],
                }
            ),
        ],
    )

    paths = gpd.GeoDataFrame(
        index=[1, 2],
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
            LineString([[0.02, 0.02], [0.03, 0.03]]),
        ],
        data={'@osmId': ['way/a', 'way/b']},
        crs='EPSG:4326',
    )
    computed_slope = get_slope(aoi=global_aoi, paths=paths, ors_settings=default_ors_settings)

    expected_naturalness = gpd.GeoDataFrame(
        index=[1, 2],
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
            LineString([[0.02, 0.02], [0.03, 0.03]]),
        ],
        data={'slope': [0.06, -0.06], '@osmId': ['way/a', 'way/b']},
        crs=CRS.from_epsg(4326),
    )

    assert_geodataframe_equal(computed_slope, expected_naturalness, check_like=True)


def test_get_duplicate_slope(global_aoi, responses_mock, default_ors_settings):
    responses_mock.post(
        'http://localhost:8080/ors/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by https://srtm.csi.cgiar.org',
            'geometry': [
                [0.0, 0.0, 1.0],
                [0.01, 0.01, 2.0],
                [0.02, 0.02, 1.0],
            ],
            'timestamp': 1738238852,
            'version': '0.2.1',
        },
        match=[
            matchers.header_matcher({'Authorization': 'test-key'}),
            matchers.json_params_matcher(
                {
                    'dataset': 'srtm',
                    'format_in': 'polyline',
                    'format_out': 'polyline',
                    'geometry': [[0.0, 0.0], [0.01, 0.01], [0.02, 0.02]],
                }
            ),
        ],
    )

    paths = gpd.GeoDataFrame(
        index=[1, 2],
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
            LineString([[0.01, 0.01], [0.02, 0.02]]),
        ],
        data={'@osmId': ['way/a', 'way/b']},
        crs='EPSG:4326',
    )
    computed_slope = get_slope(aoi=global_aoi, paths=paths, ors_settings=default_ors_settings)

    expected_slope = gpd.GeoDataFrame(
        index=[1, 2],
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
            LineString([[0.01, 0.01], [0.02, 0.02]]),
        ],
        data={'slope': [0.06, -0.06], '@osmId': ['way/a', 'way/b']},
        crs=CRS.from_epsg(4326),
    )

    assert_geodataframe_equal(computed_slope, expected_slope, check_like=True)


def test_slope_matching_according_to_ors_precision(responses_mock, global_aoi, default_ors_settings):
    responses_mock.post(
        'http://localhost:8080/ors/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by https://srtm.csi.cgiar.org',
            'geometry': [
                [0.0000001, 0.0, 1.0],
                [0.01, 0.01, 2.0],
            ],
            'timestamp': 1738238852,
            'version': '0.2.1',
        },
        match=[
            matchers.header_matcher({'Authorization': 'test-key'}),
            matchers.json_params_matcher(
                {
                    'dataset': 'srtm',
                    'format_in': 'polyline',
                    'format_out': 'polyline',
                    'geometry': [[0.0, 0.0], [0.01, 0.01]],
                }
            ),
        ],
    )

    paths = gpd.GeoDataFrame(
        index=[1],
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
        ],
        data={'@osmId': ['way/a']},
        crs='EPSG:4326',
    )
    computed_slope = get_slope(aoi=global_aoi, paths=paths, ors_settings=default_ors_settings)

    expected_naturalness = gpd.GeoDataFrame(
        index=[1],
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
        ],
        data={'slope': [0.06], '@osmId': ['way/a']},
        crs=CRS.from_epsg(4326),
    )

    assert_geodataframe_equal(computed_slope, expected_naturalness, check_like=True)


def test_get_large_amount_of_slopes(global_aoi, responses_mock, default_ors_settings):
    responses_mock.post(
        'http://localhost:8080/ors/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by https://srtm.csi.cgiar.org',
            'geometry': [[0.0, 0.0, 1.0], [1.0, 1.0, 1.0]],
            'timestamp': 1738238852,
            'version': '0.2.1',
        },
        match=[
            matchers.header_matcher({'Authorization': 'test-key'}),
            matchers.json_params_matcher(
                {
                    'format_in': 'polyline',
                    'format_out': 'polyline',
                    'dataset': 'srtm',
                    'geometry': [[0.0, 0.0], [1.0, 1.0]],
                }
            ),
        ],
    )
    responses_mock.post(
        'http://localhost:8080/ors/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by https://srtm.csi.cgiar.org',
            'geometry': [[2.0, 2.0, 1.0]],
            'timestamp': 1738238852,
            'version': '0.2.1',
        },
        match=[
            matchers.header_matcher({'Authorization': 'test-key'}),
            matchers.json_params_matcher(
                {
                    'format_in': 'polyline',
                    'format_out': 'polyline',
                    'dataset': 'srtm',
                    'geometry': [[2.0, 2.0]],
                }
            ),
        ],
    )

    geoms = [LineString([[0.0, 0.0], [1.0, 1.0]]), LineString([[1.0, 1.0], [2.0, 2.0]])]
    paths = gpd.GeoDataFrame(geometry=geoms, crs='EPSG:4326', data={'@osmId': ['way/a', 'way/b']})
    computed_slope = get_slope(aoi=global_aoi, paths=paths, ors_settings=default_ors_settings, request_chunk_size=2)

    expected_slope = gpd.GeoDataFrame(
        geometry=geoms,
        data={'slope': [0.0, 0.0], '@osmId': ['way/a', 'way/b']},
        crs=CRS.from_epsg(4326),
    )

    assert_geodataframe_equal(computed_slope, expected_slope, check_like=True)


def test_slope_for_multipart_geom(responses_mock, global_aoi, default_ors_settings):
    responses_mock.post(
        'http://localhost:8080/ors/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by https://srtm.csi.cgiar.org',
            'geometry': [
                [0.0, 0.0, 1.0],
                [0.03, 0.03, 1.0],
            ],
            'timestamp': 1738238852,
            'version': '0.2.1',
        },
        match=[
            matchers.header_matcher({'Authorization': 'test-key'}),
            matchers.json_params_matcher(
                {
                    'dataset': 'srtm',
                    'format_in': 'polyline',
                    'format_out': 'polyline',
                    'geometry': [[0.0, 0.0], [0.03, 0.03]],
                }
            ),
        ],
    )

    paths = gpd.GeoDataFrame(
        index=[1],
        geometry=[
            MultiLineString([[[0.0, 0.0], [0.01, 0.01]], [[0.02, 0.02], [0.03, 0.03]]]),
        ],
        data={'@osmId': ['way/a']},
        crs='EPSG:4326',
    )
    computed_slope = get_slope(aoi=global_aoi, paths=paths, ors_settings=default_ors_settings)

    expected_naturalness = gpd.GeoDataFrame(
        index=[1],
        geometry=[
            MultiLineString([[[0.0, 0.0], [0.01, 0.01]], [[0.02, 0.02], [0.03, 0.03]]]),
        ],
        data={'slope': [0.0], '@osmId': ['way/a']},
        crs=CRS.from_epsg(4326),
    )

    assert_geodataframe_equal(computed_slope, expected_naturalness, check_like=True)


def test_summarise_slope(default_path_geometry, default_polygon_geometry):
    input_paths = gpd.GeoDataFrame(
        data={
            'slope': [0.4, 0.6],
            'geometry': [default_path_geometry] + [default_polygon_geometry],
        },
        crs='EPSG:4326',
    )
    bar_chart = summarise_slope(paths=input_paths, projected_crs=CRS.from_user_input(32632))

    assert isinstance(bar_chart, go.Figure)
    assert bar_chart['data'][0]['x'] == ('Gentle slope (0-4%)',)
    assert bar_chart['data'][0]['y'] == (0.12,)
