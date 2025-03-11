import shapely
from walkability.components.network_analyses.hexgrid_analysis import (
    create_destinations,
    find_nearest_point,
    get_hexgrid_permeability,
    snap,
)


import geopandas as gpd
import h3pandas
import pandas as pd
from geopandas.testing import assert_geodataframe_equal

from walkability.components.utils.misc import PathCategory


def test_hexgrid_permeability(default_path, default_aoi):
    assert h3pandas.version is not None

    permeabilities = pd.DataFrame(
        data={'permeability': [1.5547923713301433, 1.253117941712255, 1.518730573232965]},
        index=['8a1f8d289187fff', '8a1f8d2891a7fff', '8a1f8d2891b7fff'],
    )

    expected = permeabilities.h3.h3_to_geo_boundary()

    result = get_hexgrid_permeability(paths=default_path, aoi=default_aoi, max_walking_distance=1000)

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

    assert type(result['geometry'].iloc[0]) == shapely.Polygon

    assert 'buffer' in result.columns.to_list()
    assert result['buffer'].dtype == gpd.array.GeometryDtype()
    assert type(result['buffer'].iloc[0]) == shapely.Polygon

    assert 'centroids' in result.columns.to_list()
    assert result['centroids'].dtype == gpd.array.GeometryDtype()
    assert type(result['centroids'].iloc[0]) == shapely.Point
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
        assert type(result_paths.loc[index, 'geometry']) == shapely.LineString


def test_find_nearest_point(default_path):
    point_geom = shapely.Point(299459.197, 5344278.607)
    area = point_geom.buffer(10)
    row = pd.Series(data=[point_geom, area], index=['centroids', 'geometry'])

    crs = default_path.estimate_utm_crs()
    lines = default_path.to_crs(crs)

    result = find_nearest_point(row, lines)

    assert result == shapely.from_wkt('POINT (299458.2337885652 5344278.6408732245)')
