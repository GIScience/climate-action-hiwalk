from itertools import product
from typing import Tuple, List

import geopandas
import geopandas as gpd
import numpy as np
import pytest
import shapely
from climatoology.base.artifact import Chart2dData, ChartType
from climatoology.utility.Naturalness import NaturalnessIndex
from geopandas import testing
from geopandas.testing import assert_geodataframe_equal
from pydantic_extra_types.color import Color
from pyproj import CRS
from responses import matchers
from shapely.geometry.linestring import LineString
from shapely.geometry.multilinestring import MultiLineString

from walkability.utils import (
    PathCategory,
    filter_start_matcher,
    PavementQuality,
    read_pavement_quality_rankings,
    get_sidewalk_key_combinations,
)


def test_get_paths(operator, expected_compute_input, default_aoi, ohsome_api):
    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])
    polygon_geom = shapely.Polygon(((12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22), (12.3, 48.22)))

    expected_lines = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [line_geom],
            '@other_tags': [{'highway': 'pedestrian'}],
        },
        crs='EPSG:4326',
    )
    expected_polygons = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [polygon_geom],
            '@other_tags': [{'highway': 'platform', 'area': 'yes'}],
        },
        crs='EPSG:4326',
    )

    computed_lines, computed_polygons = operator.get_paths(
        aoi=default_aoi, rating_map=expected_compute_input.get_path_rating_mapping()
    )

    testing.assert_geodataframe_equal(
        computed_lines,
        expected_lines,
        check_like=True,
        check_geom_type=True,
        check_less_precise=True,
    )
    testing.assert_geodataframe_equal(
        computed_polygons,
        expected_polygons,
        check_like=True,
        check_geom_type=True,
        check_less_precise=True,
    )


def test_connectivity(operator):
    # WGS84 representation of two ca. 1m long adjacent orthogonal paths in UTM 31N
    path_geoms = [
        shapely.LineString([(9, 49), (9, 49.0000088)]),
        shapely.LineString([(9, 49.0000088), (9.0000137, 49.0000088)]),
    ]
    expected_connectivity = gpd.GeoDataFrame(
        data={
            'connectivity': [0.75, 0.75],
            'permeability': [0.925, 0.925],
            'geometry': path_geoms,
        },
        crs='EPSG:4326',
    )

    paths = gpd.GeoDataFrame(
        data={
            'geometry': path_geoms,
            'rating': [1.0, 0.75],
        },
        crs='EPSG:4326',
    )

    connectivity = operator.get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_fully_inside_buffer(operator):
    path_geoms = [
        # ca 1m long path
        shapely.LineString([(9, 49), (9, 49.0000088)]),
    ]
    expected_connectivity = gpd.GeoDataFrame(
        data={
            'connectivity': [1.0],
            'permeability': [1.0],
            'geometry': path_geoms,
        },
        crs='EPSG:4326',
    )

    paths = gpd.GeoDataFrame(
        data={
            'geometry': path_geoms,
            'rating': [1.0],
        },
        crs='EPSG:4326',
    )

    connectivity = operator.get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_exceeds_buffer(operator):
    path_geoms = [
        # ca 2m long path
        shapely.LineString([(9, 49), (9, 49.000018)]),
    ]
    expected_connectivity = gpd.GeoDataFrame(
        data={
            'connectivity': [np.nan],
            'permeability': [np.nan],
            'geometry': path_geoms,
        },
        crs='EPSG:4326',
    )

    paths = gpd.GeoDataFrame(
        data={
            'geometry': path_geoms,
            'rating': [1.0],
        },
        crs='EPSG:4326',
    )

    connectivity = operator.get_connectivity_permeability(
        paths=paths, walkable_distance=1, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_within_but_long(operator):
    expected_connectivity = gpd.GeoDataFrame(
        data={
            'connectivity': [0.0],
            'permeability': [0.41],
            'geometry': [
                # 3m long path with end nodes 1m apart                                     2m                      1m
                shapely.LineString([(9.0, 49.0), (9.0, 49.000018), (9.0000137, 49.0000088)]),
            ],
        },
        crs='EPSG:4326',
    )

    paths = gpd.GeoDataFrame(
        data={
            'geometry': [
                # 3m long path with end nodes 1m apart
                shapely.LineString([(9.0, 49.0), (9.0, 49.000018), (9.0000137, 49.0000088)]),
            ],
            'rating': [1.0],
        },
        crs='EPSG:4326',
    )

    connectivity = operator.get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True, normalize=True)


def test_connectivity_one_in_one_out(operator):
    # WGS84 representation of two paths: one 1m one 2m
    path_geoms = [
        shapely.LineString([(9, 49), (9, 49.0000088)]),
        shapely.LineString([(9, 49), (9.0000137, 49.000018)]),
    ]
    expected_connectivity = gpd.GeoDataFrame(
        data={
            'connectivity': [0.75, 0.5],
            'permeability': [0.86, 0.725],
            'geometry': path_geoms,
        },
        crs='EPSG:4326',
    )

    paths = gpd.GeoDataFrame(
        data={
            'geometry': path_geoms,
            'rating': [1.0, 0.75],
        },
        crs='EPSG:4326',
    )

    connectivity = operator.get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_walkable(operator):
    paths = gpd.GeoDataFrame(
        data={
            'geometry': [shapely.LineString([(9, 49), (9, 49.0000088)])],
            'rating': [0.5],
        },
        crs='EPSG:4326',
    )
    connectivity = operator.get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )
    assert not connectivity.empty


def test_connectivity_overlapping_paths(operator):
    # WGS84 representation of two paths: one 1m one 2m
    geom = [
        #                                2m
        shapely.LineString([(9, 49), (9, 49.000018)]),
        #                       2m              1m
        shapely.LineString([(9, 49.000018), (9, 49.0000088)]),
    ]
    expected_connectivity = gpd.GeoDataFrame(
        data={
            'connectivity': [0.5, 0.75],
            'permeability': [0.66, 0.83],
            'geometry': geom,
        },
        crs='EPSG:4326',
    )
    paths = gpd.GeoDataFrame(
        data={
            'geometry': geom,
            'rating': [1.0, 0.75],
        },
        crs='EPSG:4326',
    )
    connectivity = operator.get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )
    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_intersected_line(operator):
    # WGS84 representation of two paths: one 1m one 2m meeting orthogonal in the middle of line 2m
    path_geoms = [
        shapely.LineString([(9, 49), (9, 49.0000088), (9, 49.000018)]),
        shapely.LineString([(9, 49.0000088), (9.0000137, 49.0000088)]),
    ]
    expected_connectivity = gpd.GeoDataFrame(
        data={
            'connectivity': [0.75, 0.75, 0.66666666666],
            'permeability': [0.925, 0.925, 0.9],
            'geometry': [
                shapely.LineString([(9, 49), (9, 49.0000088)]),
                shapely.LineString([(9, 49.0000088), (9, 49.000018)]),
                shapely.LineString([(9, 49.0000088), (9.0000137, 49.0000088)]),
            ],
        },
        crs='EPSG:4326',
    )

    paths = gpd.GeoDataFrame(
        data={
            'geometry': path_geoms,
            'rating': [1.0, 0.75],
        },
        crs='EPSG:4326',
    )

    connectivity = operator.get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_decay(operator):
    # WGS84 representation of two ca. 1m long adjacent orthogonal paths in UTM 31N
    path_geoms = [
        shapely.LineString([(9, 49), (9, 49.0000088)]),
        shapely.LineString([(9, 49.0000088), (9.0000137, 49.0000088)]),
    ]
    expected_connectivity = gpd.GeoDataFrame(
        data={
            'connectivity': [1.0, 1.0],
            'permeability': [0.925, 0.925],
            'geometry': path_geoms,
        },
        crs='EPSG:4326',
    )

    paths = gpd.GeoDataFrame(
        data={
            'geometry': path_geoms,
            'rating': [1.0, 0.75],
        },
        crs='EPSG:4326',
    )

    connectivity = operator.get_connectivity_permeability(
        paths=paths,
        walkable_distance=1.5,
        projected_crs=CRS.from_user_input(32632),
        idw_function=lambda distance: 1 if distance < 1.1 else 0,
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_unwalkable(operator):
    # WGS84 representation of 1 m up, another m up, and one meter down right
    path_geoms = [
        shapely.LineString([(9.0, 49.0), (9.0, 49.0000088)]),
        shapely.LineString([(9.0, 49.0000088), (9.0, 49.000018)]),
        shapely.LineString([(9.0, 49.000018), (9.0000137, 49.0000088)]),
    ]
    expected_connectivity = gpd.GeoDataFrame(
        data={
            'connectivity': [1 / 3, 0.0, 1 / 3],
            'permeability': [0.4, 0.0, 0.4],
            'geometry': path_geoms,
        },
        crs='EPSG:4326',
    )

    paths = gpd.GeoDataFrame(
        data={
            'geometry': path_geoms,
            'rating': [1.0, 0.0, 1.0],
        },
        crs='EPSG:4326',
    )

    connectivity = operator.get_connectivity_permeability(
        paths=paths,
        walkable_distance=100,
        projected_crs=CRS.from_user_input(32632),
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_summarise_by_area(operator, default_aoi, expected_compute_input, responses_mock):
    with open('resources/test/ohsome_admin_response.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )
    expected_charts = {
        'Bergheim': Chart2dData(
            x=['designated'],
            y=[0.12],
            color=[Color('#313695')],
            chart_type=ChartType.PIE,
        ),
        'Südstadt': Chart2dData(
            x=['designated'],
            y=[0.12],
            color=[Color('#313695')],
            chart_type=ChartType.PIE,
        ),
    }

    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])
    polygon_geom = shapely.Polygon(((12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22), (12.3, 48.22)))

    input_paths = gpd.GeoDataFrame(
        data={
            'category': 2 * [PathCategory.DESIGNATED],
            'rating': 2 * [1.0],
            'geometry': [line_geom] + [polygon_geom],
        },
        crs='EPSG:4326',
    )
    computed_charts = operator.summarise_by_area(input_paths, default_aoi, 9, CRS.from_user_input(32632))

    assert computed_charts == expected_charts


def test_summarise_by_area_no_boundaries(operator, default_aoi, expected_compute_input, responses_mock):
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body="""{
  "attribution" : {
    "url" : "https://ohsome.org/copyrights",
    "text" : "© OpenStreetMap contributors"
  },
  "apiVersion" : "1.10.4",
  "type" : "FeatureCollection",
  "features" : []
}""",
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )

    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [line_geom],
        },
        crs='EPSG:4326',
    )
    computed_charts = operator.summarise_by_area(input_paths, default_aoi, 9, CRS.from_user_input(32632))

    assert computed_charts == dict()


def test_summarise_by_area_mixed_geometry_boundaries(operator, default_aoi, expected_compute_input, responses_mock):
    with open('resources/test/ohsome_boundaries_mixed_geometries.geojson', 'r') as response_file:
        response_body = response_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=response_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )
    expected_charts = {
        'Innenstadt West': Chart2dData(
            x=['designated'],
            y=[0.69],
            color=[Color('#313695')],
            chart_type=ChartType.PIE,
        )
    }

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [shapely.LineString([[7.42, 51.51], [7.43, 51.51]])],
        },
        crs='EPSG:4326',
    )
    computed_charts = operator.summarise_by_area(input_paths, default_aoi, 9, CRS.from_user_input(32632))

    assert computed_charts == expected_charts


def test_summarise_by_area_boundaries_no_name(operator, default_aoi, expected_compute_input, responses_mock):
    with open('resources/test/ohsome_admin_response_no_name.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )

    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])

    input_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'geometry': [line_geom],
        },
        crs='EPSG:4326',
    )
    computed_charts = operator.summarise_by_area(input_paths, default_aoi, 9, CRS.from_user_input(32632))

    assert computed_charts == dict()


def get_key_value_combinations() -> List[Tuple[str, Tuple[str, PavementQuality]]]:
    rankings = read_pavement_quality_rankings()
    combinations = get_sidewalk_key_combinations()

    smoothness = combinations['smoothness'] + ['smoothness']
    surface = combinations['surface'] + ['surface']
    tracktype = ['tracktype']

    pairs = [
        *product(smoothness, rankings['smoothness'].items()),
        *product(smoothness, [('invalid', PavementQuality.UNKNOWN)]),
        *product(surface, rankings['surface'].items()),
        *product(surface, [('invalid', PavementQuality.UNKNOWN)]),
        *product(tracktype, rankings['tracktype'].items()),
        *product(tracktype, [('invalid', PavementQuality.UNKNOWN)]),
        ('other', ('invalid', PavementQuality.UNKNOWN)),
    ]
    return pairs


key_value_combinations = get_key_value_combinations()


@pytest.mark.parametrize('combination', key_value_combinations)
def test_pavement_quality_return_values(operator, combination: Tuple[str, Tuple[str, PavementQuality]]):
    key = combination[0]
    value, quality = combination[1]

    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])
    line_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'geometry': [line_geom],
            '@other_tags': [{key: value}],
        },
        crs='EPSG:4326',
    )

    result_line = operator.get_pavement_quality(line_paths)

    assert result_line['quality'].to_list() == [quality]


def get_key_combinations() -> List[Tuple[str, str, str, PavementQuality]]:
    combinations = get_sidewalk_key_combinations()

    ssm = combinations['smoothness']
    ssu = combinations['surface']
    sm = ['smoothness']
    su = ['surface']
    tr = ['tracktype']

    pairs = []
    for combi in product([*ssu, *sm, *su, *tr], ssm):
        pairs.append((*combi, 'good', PavementQuality.GOOD))
    for combi in product([*sm, *su, *tr], ssu):
        pairs.append((*combi, 'asphalt', PavementQuality.POTENTIALLY_GOOD))
    for combi in product([*su, *tr], sm):
        pairs.append((*combi, 'good', PavementQuality.GOOD))
    for combi in product(tr, su):
        pairs.append((*combi, 'asphalt', PavementQuality.POTENTIALLY_GOOD))
    return pairs


key_combinations = get_key_combinations()


@pytest.mark.parametrize('combination', key_combinations)
def test_pavement_quality_hierarchy(operator, combination):
    secondary_key, primary_key, primary_value, quality = combination

    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])
    line_paths = gpd.GeoDataFrame(
        data={
            'category': [PathCategory.DESIGNATED],
            'geometry': [line_geom],
            '@other_tags': [{primary_key: primary_value, secondary_key: 'wrong'}],
        },
        crs='EPSG:4326',
    )

    result_line = operator.get_pavement_quality(line_paths)

    assert result_line['quality'].to_list() == [quality]


def test_get_naturalness(default_aoi, operator, naturalness_utility_mock):
    paths = gpd.GeoDataFrame(
        index=[1, 2],
        geometry=[
            LineString([[12.4, 48.25], [12.4, 48.30]]),
            LineString([[12.41, 48.25], [12.41, 48.30]]),
        ],
        crs='EPSG:4326',
    )
    computed_naturalness = operator.get_naturalness(aoi=default_aoi, paths=paths, index=NaturalnessIndex.NDVI)

    expected_naturalness = gpd.GeoDataFrame(
        index=[1, 2],
        geometry=[
            LineString([[12.4, 48.25], [12.4, 48.30]]),
            LineString([[12.41, 48.25], [12.41, 48.30]]),
        ],
        data={'naturalness': [0.5, 0.6]},
        crs=CRS.from_epsg(4326),
    )

    geopandas.testing.assert_geodataframe_equal(computed_naturalness, expected_naturalness, check_like=True)


def test_get_slope(global_aoi, operator, responses_mock):
    responses_mock.post(
        'https://api.openrouteservice.org/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by http://srtm.csi.cgiar.org',
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
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
        ],
        crs='EPSG:4326',
    )
    computed_slope = operator.get_slope(aoi=global_aoi, paths=paths)

    expected_naturalness = gpd.GeoDataFrame(
        index=[1],
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
        ],
        data={'slope': [0.06]},
        crs=CRS.from_epsg(4326),
    )

    geopandas.testing.assert_geodataframe_equal(computed_slope, expected_naturalness, check_like=True)


def test_get_negative_slope(global_aoi, operator, responses_mock):
    responses_mock.post(
        'https://api.openrouteservice.org/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by http://srtm.csi.cgiar.org',
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
        crs='EPSG:4326',
    )
    computed_slope = operator.get_slope(aoi=global_aoi, paths=paths)

    expected_naturalness = gpd.GeoDataFrame(
        index=[1, 2],
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
            LineString([[0.02, 0.02], [0.03, 0.03]]),
        ],
        data={'slope': [0.06, -0.06]},
        crs=CRS.from_epsg(4326),
    )

    geopandas.testing.assert_geodataframe_equal(computed_slope, expected_naturalness, check_like=True)


def test_get_duplicate_slope(global_aoi, operator, responses_mock):
    responses_mock.post(
        'https://api.openrouteservice.org/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by http://srtm.csi.cgiar.org',
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
        crs='EPSG:4326',
    )
    computed_slope = operator.get_slope(aoi=global_aoi, paths=paths)

    expected_slope = gpd.GeoDataFrame(
        index=[1, 2],
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
            LineString([[0.01, 0.01], [0.02, 0.02]]),
        ],
        data={'slope': [0.06, -0.06]},
        crs=CRS.from_epsg(4326),
    )

    geopandas.testing.assert_geodataframe_equal(computed_slope, expected_slope, check_like=True)


def test_slope_matching_according_to_ORS_precision(operator, responses_mock, global_aoi):
    responses_mock.post(
        'https://api.openrouteservice.org/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by http://srtm.csi.cgiar.org',
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
        crs='EPSG:4326',
    )
    computed_slope = operator.get_slope(aoi=global_aoi, paths=paths)

    expected_naturalness = gpd.GeoDataFrame(
        index=[1],
        geometry=[
            LineString([[0.0, 0.0], [0.01, 0.01]]),
        ],
        data={'slope': [0.06]},
        crs=CRS.from_epsg(4326),
    )

    geopandas.testing.assert_geodataframe_equal(computed_slope, expected_naturalness, check_like=True)


def test_get_large_amount_of_slopes(global_aoi, operator, responses_mock):
    responses_mock.post(
        'https://api.openrouteservice.org/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by http://srtm.csi.cgiar.org',
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
        'https://api.openrouteservice.org/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by http://srtm.csi.cgiar.org',
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
    paths = gpd.GeoDataFrame(
        geometry=geoms,
        crs='EPSG:4326',
    )
    computed_slope = operator.get_slope(
        aoi=global_aoi,
        paths=paths,
        request_chunk_size=2,
    )

    expected_slope = gpd.GeoDataFrame(
        geometry=geoms,
        data={'slope': [0.0, 0.0]},
        crs=CRS.from_epsg(4326),
    )

    geopandas.testing.assert_geodataframe_equal(computed_slope, expected_slope, check_like=True)


def test_slope_for_multipart_geom(operator, responses_mock, global_aoi):
    responses_mock.post(
        'https://api.openrouteservice.org/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by http://srtm.csi.cgiar.org',
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
        crs='EPSG:4326',
    )
    computed_slope = operator.get_slope(aoi=global_aoi, paths=paths)

    expected_naturalness = gpd.GeoDataFrame(
        index=[1],
        geometry=[
            MultiLineString([[[0.0, 0.0], [0.01, 0.01]], [[0.02, 0.02], [0.03, 0.03]]]),
        ],
        data={'slope': [0.0]},
        crs=CRS.from_epsg(4326),
    )

    geopandas.testing.assert_geodataframe_equal(computed_slope, expected_naturalness, check_like=True)
