import pytest

from walkability.components.categorise_paths.path_category_filters import PathCategoryFilters


def test_get_max_speed():
    tags = {'highway': 'residential', 'maxspeed': '60'}
    pcf = PathCategoryFilters(tags=tags)
    assert pcf.max_speed == 60


def test_get_max_speed_empty():
    tags = {'highway': 'residential'}
    pcf = PathCategoryFilters(tags=tags)
    assert pcf.max_speed == -1


def test_get_max_speed_not_number():
    tags = {'highway': 'residential', 'maxspeed': 'foo'}
    pcf = PathCategoryFilters(tags=tags)
    assert pcf.max_speed == -1


def test_get_max_speed_zone():
    tags = {'highway': 'residential', 'zone:maxspeed': 'DE:30'}
    pcf = PathCategoryFilters(tags=tags)
    assert pcf.max_speed == 30


def test_get_max_speed_zone_any_country():
    tags = {'highway': 'residential', 'zone:maxspeed': 'FR:30'}
    pcf = PathCategoryFilters(tags=tags)
    assert pcf.max_speed == 30


@pytest.mark.parametrize(
    'tags, max_speed',
    [
        ({'highway': 'residential', 'zone:maxspeed': 'RS:urban'}, 50.0),
        ({'highway': 'residential', 'zone:maxspeed': 'RS:school'}, 50.0),
        ({'highway': 'residential', 'zone:traffic': 'AW:rural'}, 80.0),
        ({'highway': 'residential', 'zone:traffic': 'BE-WAL:rural'}, 90.0),
        ({'highway': 'residential', 'zone:traffic': 'DE:rural'}, 100.0),
        ({'highway': 'residential', 'zone:traffic': 'FR:urban'}, 50.0),
        ({'highway': 'residential', 'zone:traffic': 'BQ-BO:urban'}, 40.0),
        ({'highway': 'residential', 'zone:traffic': 'SX:urban'}, 30.0),
        ({'highway': 'residential', 'zone:traffic': 'LU:motorway'}, 120.0),
    ],
)
def test_get_max_speed_zone_land_use_any_country(tags, max_speed):
    """The expected values for these tests come from -- and should be regularly updated against -- the information
    in the OSM Wiki:
    https://wiki.openstreetmap.org/wiki/Key:zone:maxspeed
    https://wiki.openstreetmap.org/wiki/Key:zone:traffic
    """
    pcf = PathCategoryFilters(tags=tags)
    assert pcf.max_speed == max_speed


def test_get_max_speed_multiple_given():
    tags = {'highway': 'residential', 'maxspeed:forward': '10', 'maxspeed:backward': '20'}
    pcf = PathCategoryFilters(tags=tags)
    assert pcf.max_speed == 20.0


def test_get_max_speed_zone_only_number():
    tags = {'highway': 'residential', 'zone:maxspeed': '10'}
    pcf = PathCategoryFilters(tags=tags)
    assert pcf.max_speed == 10.0
