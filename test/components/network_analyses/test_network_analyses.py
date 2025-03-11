import numpy as np
from pyproj import CRS
import shapely
import geopandas as gpd
from geopandas.testing import assert_geodataframe_equal

from walkability.components.network_analyses.network_analyses import (
    get_connectivity_permeability,
)


def test_connectivity():
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

    connectivity = get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_fully_inside_buffer():
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

    connectivity = get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_exceeds_buffer():
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

    connectivity = get_connectivity_permeability(
        paths=paths, walkable_distance=1, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_within_but_long():
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

    connectivity = get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True, normalize=True)


def test_connectivity_one_in_one_out():
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

    connectivity = get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_walkable():
    paths = gpd.GeoDataFrame(
        data={
            'geometry': [shapely.LineString([(9, 49), (9, 49.0000088)])],
            'rating': [0.5],
        },
        crs='EPSG:4326',
    )
    connectivity = get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )
    assert not connectivity.empty


def test_connectivity_overlapping_paths():
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
    connectivity = get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )
    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_intersected_line():
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

    connectivity = get_connectivity_permeability(
        paths=paths, walkable_distance=1.5, projected_crs=CRS.from_user_input(32632)
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_decay():
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

    connectivity = get_connectivity_permeability(
        paths=paths,
        walkable_distance=1.5,
        projected_crs=CRS.from_user_input(32632),
        idw_function=lambda distance: 1 if distance < 1.1 else 0,
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)


def test_connectivity_unwalkable():
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

    connectivity = get_connectivity_permeability(
        paths=paths,
        walkable_distance=100,
        projected_crs=CRS.from_user_input(32632),
    )

    assert_geodataframe_equal(connectivity, expected_connectivity, check_less_precise=True)
