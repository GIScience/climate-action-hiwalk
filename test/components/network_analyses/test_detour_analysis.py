import shapely
import pytest
from walkability.components.network_analyses.detour_analysis import (
    create_destinations,
    find_nearest_point,
    geodataframe_to_graph,
    get_detour_factors,
    snap,
    split_paths_at_intersections,
)


import geopandas as gpd
import h3pandas
import pandas as pd
from geopandas.testing import assert_geodataframe_equal

from walkability.components.utils.misc import PathCategory


def test_get_detour_factors(default_path, default_aoi):
    assert h3pandas.version is not None

    permeabilities = pd.DataFrame(
        data={'detour_factor': [1.5547923713301433, 1.253117941712255, 1.518730573232965]},
        index=['8a1f8d289187fff', '8a1f8d2891a7fff', '8a1f8d2891b7fff'],
    )

    expected = permeabilities.h3.h3_to_geo_boundary()

    result = get_detour_factors(paths=default_path, aoi=default_aoi, max_walking_distance=1000)

    assert_geodataframe_equal(result.sort_index(), expected.sort_index())


def test_create_destinations(default_aoi, default_path):
    crs = default_path.estimate_utm_crs()
    paths = default_path.to_crs(crs)
    result = create_destinations(aoi=default_aoi, local_crs=crs, paths=paths)

    expected_index = ['8a1f8d289187fff', '8a1f8d2891a7fff', '8a1f8d2891b7fff']
    expected_centroid = shapely.from_wkt('POINT (299526.3228283426 5344230.417665939)')

    assert result.crs == crs
    assert result.shape[0] == 3
    assert sorted(result.index.to_list()) == sorted(expected_index)

    assert isinstance(result['geometry'].iloc[0], shapely.Polygon)

    assert 'buffer' in result.columns.to_list()
    assert result['buffer'].dtype == gpd.array.GeometryDtype()
    assert isinstance(result['buffer'].iloc[0], shapely.Polygon)

    assert 'centroids' in result.columns.to_list()
    assert result['centroids'].dtype == gpd.array.GeometryDtype()
    assert isinstance(result['centroids'].iloc[0], shapely.Point)
    assert result.loc[expected_index[0], 'centroids'] == expected_centroid


def test_snap(default_path):
    crs = default_path.estimate_utm_crs()
    paths = default_path.to_crs(crs)

    point_geom = shapely.Point(299459.197, 5344278.607)
    area = point_geom.buffer(10)
    points = gpd.GeoDataFrame(data={'geometry': [area], 'centroids': [point_geom]}, crs=crs)

    result_paths, result_points = snap(points, paths=paths, crs=crs)

    assert result_points.shape[0] == 1
    assert result_points.loc[0, 'snapping_distance'] == 0.963806860025318
    assert result_points.loc[0, 'nearest_point'] == shapely.from_wkt('POINT (299458.2337885652 5344278.6408732245)')

    assert result_paths.shape[0] == 3
    for index in range(0, 3):
        assert result_paths.loc[index, 'category'] == PathCategory.DESIGNATED
        assert isinstance(result_paths.loc[index, 'geometry'], shapely.LineString)


def test_find_nearest_point(default_path):
    point_geom = shapely.Point(299459.197, 5344278.607)
    area = point_geom.buffer(10)
    row = pd.Series(data=[point_geom, area], index=['centroids', 'geometry'])

    crs = default_path.estimate_utm_crs()
    lines = default_path.to_crs(crs)

    result = find_nearest_point(row, lines)

    assert result == shapely.from_wkt('POINT (299458.2337885652 5344278.6408732245)')


@pytest.fixture
def intersecting_path_geoms():
    return [
        shapely.LineString([(9, 49.0000088), (9.0, 49.000018)]),
        shapely.LineString([(9.0, 49.0), (9.0, 49.000018), (9.0000137, 49.0000088)]),
    ]


def test_split_paths_at_intersections(intersecting_path_geoms):
    expected_path_geoms = [
        shapely.LineString([(9, 49.0000088), (9.0, 49.000018)]),
        shapely.LineString([(9.0, 49.0), (9.0, 49.000018)]),
        shapely.LineString([(9.0, 49.000018), (9.0000137, 49.0000088)]),
    ]
    paths = gpd.GeoDataFrame(
        data={
            'geometry': intersecting_path_geoms,
            'rating': [1.0, 0.75],
        },
        crs='EPSG:4326',
    )
    expected = gpd.GeoDataFrame(
        data={
            'geometry': expected_path_geoms,
            'rating': [1.0, 0.75, 0.75],
        },
        crs='EPSG:4326',
        index=[0, 1, 1],
    )
    received = split_paths_at_intersections(paths)
    assert_geodataframe_equal(received, expected)


def test_geodataframe_to_graph(intersecting_path_geoms):
    paths = gpd.GeoDataFrame(
        data={
            'geometry': intersecting_path_geoms,
            'rating': [1.0, 0.75],
        },
        crs='EPSG:4326',
    )
    expected_edges = {
        ((9, 49.0000088), (9.0, 49.000018), 0): 1.0,
        ((9.0, 49.0), (9.0, 49.000018), 1): 0.75,
        ((9.0, 49.000018), (9.0000137, 49.0000088), 2): 0.75,
    }
    received = geodataframe_to_graph(paths)
    for (u, v, k), rating in expected_edges.items():
        assert received.has_edge(u, v, key=k)
    for (u, v, k), expected_rating in expected_edges.items():
        assert 'rating' in received[u][v][k]
        assert received[u][v][k]['rating'] == expected_rating
