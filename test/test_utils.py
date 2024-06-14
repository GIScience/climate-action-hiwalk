import geopandas as gpd
import geopandas.testing
import pandas as pd
import shapely
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color
from shapely.testing import assert_geometries_equal

from walkability.utils import (
    construct_filter,
    Rating,
    fetch_osm_data,
    boost_route_members,
    fix_geometry_collection,
    get_color,
)


def test_filter():
    expected_filter = {
        Rating.EXCLUSIVE: 'highway in (pedestrian,steps,corridor) or '
        '( highway=footway and ( ( foot in (designated,official) or foot!=* ) or ( footway in (access_aisle,alley,residential,link,path) or footway!=* ) ) ) or '
        '( highway=path and ( ( foot in (designated,official) or foot!=* ) or ( footway in (access_aisle,alley,residential,link,path) or footway!=* ) ) )',
        Rating.EXPLICIT: '( highway=living_street or '
        '( highway=footway and ( foot in (yes,permissive) or footway in (sidewalk,crossing,traffic_island) ) ) or '
        '( highway=path and ( foot in (yes,permissive) or footway in (sidewalk,crossing,traffic_island) ) ) or '
        '( highway in (primary,secondary,tertiary,unclassified,residential,service,track,road) and '
        '( sidewalk in (both,left,right) or foot in (yes,permissive) ) ) ) and not '
        '( footway in (separate,no) or '
        'sidewalk=separate or '
        'sidewalk:left=separate or '
        'sidewalk:right=separate or '
        'access in (no,private,permit,military,delivery,customers) or '
        'foot in (no,private,use_sidepath,discouraged) )',
        Rating.PROBABLE: (
            'highway in (track,service) and not '
            '(footway in (separate,no) or '
            'sidewalk=separate or '
            'sidewalk:left=separate or '
            'sidewalk:right=separate or '
            'access in (no,private,permit,military,delivery,customers) or '
            'foot in (no,private,use_sidepath,discouraged))'
        ),
        Rating.INACCESSIBLE: 'highway in (primary,secondary,tertiary,unclassified,residential,service,track,road) and not '
        '( ( highway=living_street or ( highway=footway and ( foot in (yes,permissive) or footway in (sidewalk,crossing,traffic_island) ) ) or '
        '( highway=path and ( foot in (yes,permissive) or footway in (sidewalk,crossing,traffic_island) ) ) or '
        '( highway in (primary,secondary,tertiary,unclassified,residential,service,track,road) and '
        '( sidewalk in (both,left,right) or foot in (yes,permissive) ) ) ) and not '
        '( footway in (separate,no) or '
        'sidewalk=separate or '
        'sidewalk:left=separate or '
        'sidewalk:right=separate or '
        'access in (no,private,permit,military,delivery,customers) or '
        'foot in (no,private,use_sidepath,discouraged) ) ) and not '
        '(highway in (track,service) and not '
        '(footway in (separate,no) or '
        'sidewalk=separate or '
        'sidewalk:left=separate or '
        'sidewalk:right=separate or '
        'access in (no,private,permit,military,delivery,customers) or '
        'foot in (no,private,use_sidepath,discouraged))) and not '
        '(footway in (separate,no) or '
        'sidewalk=separate or '
        'sidewalk:left=separate or '
        'sidewalk:right=separate or '
        'access in (no,private,permit,military,delivery,customers) or '
        'foot in (no,private,use_sidepath,discouraged))',
    }
    computed_filter = construct_filter()

    for rating, osm_filter in computed_filter.items():
        assert ' '.join(osm_filter.replace('\n', '').split()) == expected_filter.get(rating)


def test_get_osm_data(expected_compute_input, responses_mock):
    with open('resources/test/ohsome_line_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_osm_data = gpd.GeoDataFrame(
        data={'category': [Rating.EXCLUSIVE]},
        geometry=[shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])],
        crs=4326,
    )
    computed_osm_data = fetch_osm_data(
        expected_compute_input.get_aoi_geom(), 'dummy=yes', Rating.EXCLUSIVE, OhsomeClient()
    )
    geopandas.testing.assert_geodataframe_equal(computed_osm_data, expected_osm_data)


def test_boost_route_members(expected_compute_input, responses_mock):
    with open('resources/test/ohsome_line_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_output = pd.Series(data=[Rating.EXPLICIT, Rating.INACCESSIBLE, Rating.EXCLUSIVE])

    paths_input = gpd.GeoDataFrame(
        data={'category': [Rating.INACCESSIBLE, Rating.INACCESSIBLE, Rating.EXCLUSIVE]},
        geometry=[
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
            shapely.LineString([(0, 0), (1, 0), (1, 1)]),
            shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)]),
        ],
        crs=4326,
    )
    computed_output = boost_route_members(expected_compute_input.get_aoi_geom(), paths_input, OhsomeClient())
    pd.testing.assert_series_equal(computed_output, expected_output)


def test_boost_route_members_overlapping_routes(expected_compute_input, responses_mock):
    with open('resources/test/ohsome_route_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_output = pd.Series(data=[Rating.EXPLICIT])

    paths_input = gpd.GeoDataFrame(
        data={'category': [Rating.INACCESSIBLE]},
        geometry=[
            shapely.LineString([(0, 0), (1, 1)]),
        ],
        crs=4326,
    )
    computed_output = boost_route_members(expected_compute_input.get_aoi_geom(), paths_input, OhsomeClient())
    pd.testing.assert_series_equal(computed_output, expected_output)


def test_fix_geometry_collection():
    expected_geom = shapely.LineString([(0, 0), (1, 0), (1, 1)])

    geometry_collection_input = shapely.GeometryCollection(
        [
            shapely.Point(-1, -1),
            expected_geom,
        ]
    )
    point_input = shapely.Point(-1, -1)

    input_output_map = {
        'unchanged': {'input': expected_geom, 'output': expected_geom},
        'extracted': {'input': geometry_collection_input, 'output': expected_geom},
        'ignored': {'input': point_input, 'output': shapely.LineString()},
    }
    for _, map in input_output_map.items():
        computed_geom = fix_geometry_collection(map['input'])
        assert_geometries_equal(computed_geom, map['output'])


def test_get_color():
    expected_output = pd.Series([Color('#006837'), Color('#feffbe'), Color('#a50026')])

    expected_input = pd.Series([Rating.EXCLUSIVE, Rating.PROBABLE, Rating.INACCESSIBLE])
    computed_output = get_color(expected_input)

    pd.testing.assert_series_equal(computed_output, expected_output)
