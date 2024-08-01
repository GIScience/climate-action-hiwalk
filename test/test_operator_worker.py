from itertools import product
from typing import Tuple, List

import geopandas as gpd
import pytest
import shapely
from climatoology.base.artifact import Chart2dData, ChartType
from geopandas import testing
from geopandas.testing import assert_geodataframe_equal
from pydantic_extra_types.color import Color
from pyproj import CRS

from walkability.utils import (
    PathCategory,
    filter_start_matcher,
    PavementQuality,
    read_pavement_quality_rankings,
    get_sidewalk_key_combinations,
)


def test_get_paths(operator, expected_compute_input, ohsome_api):
    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])
    polygon_geom = shapely.Polygon(((12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22), (12.3, 48.22)))

    expected_lines = gpd.GeoDataFrame(
        data={
            'category': [
                PathCategory.EXCLUSIVE,
                PathCategory.EXPLICIT,
                PathCategory.PROBABLE_YES,
                PathCategory.POTENTIAL_BUT_UNKNOWN,
                PathCategory.INACCESSIBLE,
            ],
            'rating': [
                1.0,
                0.8,
                0.6,
                0.5,
                0.0,
            ],
            'geometry': 5 * [line_geom],
            '@other_tags': 5 * [{}],
        },
        crs='EPSG:4326',
    )
    expected_polygons = gpd.GeoDataFrame(
        data={
            'category': [
                PathCategory.EXCLUSIVE,
                PathCategory.EXPLICIT,
                PathCategory.PROBABLE_YES,
                PathCategory.POTENTIAL_BUT_UNKNOWN,
                PathCategory.INACCESSIBLE,
            ],
            'rating': [
                1.0,
                0.8,
                0.6,
                0.5,
                0.0,
            ],
            'geometry': 5 * [polygon_geom],
            '@other_tags': 5 * [{}],
        },
        crs='EPSG:4326',
    )
    computed_lines, computed_polygons = operator.get_paths(
        expected_compute_input.get_aoi_geom(), expected_compute_input.get_path_rating_mapping()
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

    connectivity = operator.get_connectivity(
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

    connectivity = operator.get_connectivity(
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
            'connectivity': [1.0],
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

    connectivity = operator.get_connectivity(paths=paths, walkable_distance=1, projected_crs=CRS.from_user_input(32632))

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_within_but_long(operator):
    expected_connectivity = gpd.GeoDataFrame(
        data={
            'connectivity': [0.0],
            'geometry': [
                #                                      2m                      1m
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

    connectivity = operator.get_connectivity(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_one_in_one_out(operator):
    # WGS84 representation of two paths: one 1m one 2m
    path_geoms = [
        shapely.LineString([(9, 49), (9, 49.0000088)]),
        shapely.LineString([(9, 49), (9.0000137, 49.000018)]),
    ]
    expected_connectivity = gpd.GeoDataFrame(
        data={
            'connectivity': [0.75, 0.5],
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

    connectivity = operator.get_connectivity(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_filter_out_probably_no(operator):
    paths = gpd.GeoDataFrame(
        data={
            'geometry': [shapely.LineString([(9, 49), (9, 49.0000088)])],
            'rating': [0.25],
        },
        crs='EPSG:4326',
    )
    connectivity = operator.get_connectivity(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )
    assert connectivity.empty


def test_connectivity_filter_out_probably_yes(operator):
    paths = gpd.GeoDataFrame(
        data={
            'geometry': [shapely.LineString([(9, 49), (9, 49.0000088)])],
            'rating': [0.5],
        },
        crs='EPSG:4326',
    )
    connectivity = operator.get_connectivity(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )
    assert not connectivity.empty


@pytest.mark.skip(reason='Topology is not preseverd for overlapping geometries with shared node.')
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
            'connectivity': [0.75, 0.5],
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
    connectivity = operator.get_connectivity(
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

    connectivity = operator.get_connectivity(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_multipart(operator):
    expected_connectivity = gpd.GeoDataFrame(
        data={
            'connectivity': [0.75, 0.75],
            'geometry': [
                shapely.LineString([(9, 49), (9, 49.0000088)]),
                shapely.LineString([(9, 49.0000088), (9.0000137, 49.0000088)]),
            ],
        },
        crs='EPSG:4326',
    )

    paths = gpd.GeoDataFrame(
        data={
            'geometry': [
                shapely.MultiLineString([[(9, 49), (9, 49.0000088)], [(9, 49.0000088), (9.0000137, 49.0000088)]])
            ],
            'rating': [1.0],
        },
        crs='EPSG:4326',
    )

    connectivity = operator.get_connectivity(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_aggregate(operator, expected_compute_input, responses_mock):
    with open('resources/test/ohsome_admin_response.geojson', 'r') as admin_file:
        admin_body = admin_file.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=admin_body,
        match=[filter_start_matcher('geometry:polygon and boundary')],
    )
    expected_charts = {
        'Bergheim': Chart2dData(
            x=['exclusive'],
            y=[0.12],
            color=[Color('#006837')],
            chart_type=ChartType.PIE,
        ),
        'Südstadt': Chart2dData(
            x=['exclusive'],
            y=[0.12],
            color=[Color('#006837')],
            chart_type=ChartType.PIE,
        ),
    }

    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])
    polygon_geom = shapely.Polygon(((12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22), (12.3, 48.22)))

    input_paths = gpd.GeoDataFrame(
        data={
            'category': 2 * [PathCategory.EXCLUSIVE],
            'rating': 2 * [1.0],
            'geometry': [line_geom] + [polygon_geom],
        },
        crs='EPSG:4326',
    )
    computed_charts = operator.summarise_by_area(
        input_paths, expected_compute_input.get_aoi_geom(), 9, CRS.from_user_input(32632)
    )

    assert computed_charts == expected_charts


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
            'category': [PathCategory.EXCLUSIVE],
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
            'category': [PathCategory.EXCLUSIVE],
            'geometry': [line_geom],
            '@other_tags': [{primary_key: primary_value, secondary_key: 'wrong'}],
        },
        crs='EPSG:4326',
    )

    result_line = operator.get_pavement_quality(line_paths)

    assert result_line['quality'].to_list() == [quality]
