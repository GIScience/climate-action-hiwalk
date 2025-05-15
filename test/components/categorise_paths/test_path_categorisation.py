import geopandas as gpd
import pandas as pd
import pytest
import shapely
from ohsome import OhsomeClient
from pandas import DataFrame

from walkability.components.categorise_paths.path_categorisation import (
    evaluate_quality,
    get_flat_key_combinations,
    read_pavement_quality_rankings,
    subset_walkable_paths,
    apply_path_category_filters,
    path_categorisation,
)
from walkability.components.utils.misc import (
    PathCategory,
    PavementQuality,
    fetch_osm_data,
    SmoothnessCategory,
    SurfaceType,
)

validation_objects = {
    PathCategory.DESIGNATED: {
        'way/84908668',  # https://www.openstreetmap.org/way/84908668 highway=pedestrian
        'way/243233105',  # https://www.openstreetmap.org/way/243233105 highway=footway
        'way/27797959',  # https://www.openstreetmap.org/way/27797959 railway=platform
        'way/98453212',  # https://www.openstreetmap.org/way/98453212 foot=designated
        'way/184725322',  # https://www.openstreetmap.org/way/184725322 sidewalk:right=right and sidewalk:left=separate
        'way/118975501',  # https://www.openstreetmap.org/way/118975501 foot=designated and bicycle=designated and segregated=yes
        'way/148612595',  # https://www.openstreetmap.org/way/148612595/history/16 highway=residential & sidewalk=both and bicycle=yes (which refers to the street not the sidewalk)
    },
    PathCategory.DESIGNATED_SHARED_WITH_BIKES: {
        'way/25806383',  # https://www.openstreetmap.org/way/25806383 bicycle=designated & foot=designated
        'way/25806384',  # faked: only highway=path
        'way/1216700677',  # https://www.openstreetmap.org/way/1216700677 bicycle=permissive & foot=yes
        'way/57774238',  # https://www.openstreetmap.org/way/57774238 bicycle=official & foot=official
        'way/171794750',  # https://www.openstreetmap.org/way/171794750 bicycle=designated & foot=None
    },
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED: {
        'way/25149880',  # https://www.openstreetmap.org/way/25149880 highway=service
        'way/14193661',  # https://www.openstreetmap.org/way/14193661 highway=living_street
        'way/257385208',  # faked: highway=residential with a maxspeed=10
    },
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED: {
        'way/715905259',  # https://www.openstreetmap.org/way/715905259 highway=track
        'way/28890081',  # https://www.openstreetmap.org/way/28890081 highway=residential and sidewalk=no and maxspeed=30
        'way/109096915',  # faked: highway=residential and sidewalk=no and maxspeed=20
        'way/64390823',  # semi-faked https://www.openstreetmap.org/way/64390823 highway=service & maxspeed = 30
    },
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED: {
        'way/25340617',  # https://www.openstreetmap.org/way/25340617 highway=residential and sidewalk=no and maxspeed=50
        'way/258562284',  # https://www.openstreetmap.org/way/258562284 highway=tertiary and sidewalk=no and maxspeed=50
        'way/721931269',  # semi-faked: highway=residential and sidewalk=no and zone:maxspeed=DE:urban
    },
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED: {
        'way/152645929',
        # fake https://www.openstreetmap.org/way/152645928 highway=residential and sidewalk=no and maxspeed not given
    },
    PathCategory.INACCESSIBLE: {
        'way/24635973',  # https://www.openstreetmap.org/way/24635973 foot=no
        'way/25238623',  # https://www.openstreetmap.org/way/25238623 access=private
        'way/87956068',  # https://www.openstreetmap.org/way/87956068 highway=track and ford=yes
        'way/225895739',  # https://www.openstreetmap.org/way/225895739 service=yes and bus=yes
        'way/1031915576',  # reduced https://www.openstreetmap.org/way/1031915576 sidewalk=separate
    },
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_VERY_HIGH_SPEED: {
        'way/400711541',  # https://www.openstreetmap.org/way/400711541 sidewalk=no and maxspeed:backward=70
    },
    PathCategory.UNKNOWN: {
        'way/152645928',  # https://www.openstreetmap.org/way/152645928 highway=residential and sidewalk not given
    },
}


@pytest.fixture(scope='module')
def ohsome_test_data_categorisation(global_aoi, responses_mock) -> pd.DataFrame:
    with open('test/resources/ohsome_categorisation_response.geojson', 'r') as categorisation_examples:
        categorisation_examples = categorisation_examples.read()

    responses_mock.post('https://api.ohsome.org/v1/elements/geometry', body=categorisation_examples)
    osm_data = fetch_osm_data(aoi=global_aoi, osm_filter='', ohsome=OhsomeClient())

    return osm_data


def test_path_categorisation_only_line_paths():
    line_geom = shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])
    line_paths = gpd.GeoDataFrame(
        data={'@osmId': ['way/171574582'], 'geometry': [line_geom], '@other_tags': [{'highway': 'pedestrian'}]},
        crs='EPSG:4326',
    )
    polygon_paths = gpd.GeoDataFrame(
        data={'@osmId': [], 'geometry': [], '@other_tags': []},
        crs='EPSG:4326',
    )
    expected_paths_line = gpd.GeoDataFrame(
        data={
            '@osmId': ['way/171574582'],
            'geometry': [line_geom],
            '@other_tags': [{'highway': 'pedestrian'}],
            'category': [PathCategory.DESIGNATED],
            'quality': [PavementQuality.UNKNOWN],
            'smoothness': [SmoothnessCategory.UNKNOWN],
            'surface': [SurfaceType.UNKNOWN],
            'rating': [1.0],
            'quality_rating': [None],
            'smoothness_rating': [None],
            'surface_rating': [None],
        },
        crs='EPSG:4326',
    )
    expected_polygon_paths = gpd.GeoDataFrame(
        data={
            '@osmId': [],
            'geometry': [],
            '@other_tags': [],
            'category': [],
            'quality': [],
            'smoothness': [],
            'surface': [],
            'rating': [],
            'quality_rating': [],
            'smoothness_rating': [],
            'surface_rating': [],
        },
        crs='EPSG:4326',
    )
    line_paths_categorised, polygon_paths_categorised = path_categorisation(line_paths, polygon_paths)
    pd.testing.assert_frame_equal(expected_paths_line, line_paths_categorised)
    pd.testing.assert_frame_equal(expected_polygon_paths, polygon_paths_categorised, check_dtype=False)


@pytest.mark.parametrize('category', validation_objects)
def test_apply_path_category_filters(ohsome_test_data_categorisation: DataFrame, category: PathCategory):
    ohsome_test_data_categorisation['category'] = ohsome_test_data_categorisation.apply(
        apply_path_category_filters, axis=1
    )

    ohsome_test_data_categorisation = ohsome_test_data_categorisation[
        ohsome_test_data_categorisation['category'] == category
    ]

    assert set(ohsome_test_data_categorisation['@osmId']) == validation_objects[category]


def test_evaluate_quality_dedicated_smoothness():
    """A residential road with a smooth sidewalk made of paving stones."""
    input_row = pd.Series(
        data={
            '@other_tags': {
                'highway': 'residential',
                'sidewalk:both': 'yes',
                'sidewalk:both:smoothness': 'good',
                'sidewalk:both:surface': 'paving_stones',
            },
            'category': PathCategory.DESIGNATED,
        }
    )

    predicted_quality = evaluate_quality(
        row=input_row, keys=get_flat_key_combinations(), evaluation_dict=read_pavement_quality_rankings()
    )

    assert predicted_quality == PavementQuality.GOOD


def test_evaluate_quality_dedicated_surface():
    """A residential road with a sidewalk made of asphalt but no information on the smoothness of that asphalt."""
    input_row = pd.Series(
        data={
            '@other_tags': {
                'highway': 'residential',
                'sidewalk:both': 'yes',
                'sidewalk:both:surface': 'asphalt',
            },
            'category': PathCategory.DESIGNATED,
        }
    )

    predicted_quality = evaluate_quality(
        row=input_row, keys=get_flat_key_combinations(), evaluation_dict=read_pavement_quality_rankings()
    )

    assert predicted_quality == PavementQuality.POTENTIALLY_GOOD


def test_evaluate_quality_generic_smoothness_and_no_sidewalk():
    """A smooth residential road made of paving_stones with no sidewalk.
    Assumption: we walk on the highway and therefore the generic smoothness tag of the highway applies to us."""
    input_row = pd.Series(
        data={
            '@other_tags': {
                'highway': 'residential',
                'smoothness': 'good',
                'surface': 'paving_stones',
                'sidewalk': 'no',
            },
            'category': PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED,
        }
    )

    predicted_quality = evaluate_quality(
        row=input_row, keys=get_flat_key_combinations(), evaluation_dict=read_pavement_quality_rankings()
    )

    assert predicted_quality == PavementQuality.GOOD


def test_evaluate_quality_generic_smoothness_and_sidewalk():
    """A smooth residential road made of paving_stones with a sidewalk.
    Assumption: The generic smoothness tag only applies to the highway and not to the sidewalk."""
    input_row = pd.Series(
        data={
            '@other_tags': {
                'highway': 'residential',
                'surface': 'paving_stones',
                'smoothness': 'good',
                'sidewalk:both': 'yes',
            },
            'category': PathCategory.DESIGNATED,
        }
    )

    predicted_quality = evaluate_quality(
        row=input_row, keys=get_flat_key_combinations(), evaluation_dict=read_pavement_quality_rankings()
    )

    assert predicted_quality == PavementQuality.UNKNOWN


def test_evaluate_quality_generic_surface_and_no_sidewalk():
    """A residential road made of asphalt with no sidewalk.
    Assumption: we walk on the highway and therefore the generic surface tag of the highway applies to us."""
    input_row = pd.Series(
        data={
            '@other_tags': {
                'highway': 'residential',
                'surface': 'asphalt',
                'sidewalk': 'no',
            },
            'category': PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED,
        }
    )

    predicted_quality = evaluate_quality(
        row=input_row, keys=get_flat_key_combinations(), evaluation_dict=read_pavement_quality_rankings()
    )

    assert predicted_quality == PavementQuality.POTENTIALLY_GOOD


def test_evaluate_quality_generic_surface_and_sidewalk():
    """A residential road made of asphalt with a sidewalk.
    Assumption: The generic surface tag only applies to the highway and not to the sidewalk."""
    input_row = pd.Series(
        data={
            '@other_tags': {'highway': 'residential', 'surface': 'asphalt', 'sidewalk:both': 'yes'},
            'category': PathCategory.DESIGNATED,
        }
    )

    predicted_quality = evaluate_quality(
        row=input_row, keys=get_flat_key_combinations(), evaluation_dict=read_pavement_quality_rankings()
    )

    assert predicted_quality == PavementQuality.UNKNOWN


def test_evaluate_quality_track_with_no_sidewalk():
    """Assumption: It's a track, and it has no sidewalk i.e. the tracktype applies"""
    input_row = pd.Series(
        data={
            '@other_tags': {
                'highway': 'track',
                'tracktype': 'grade1',
            },
            'category': PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
        }
    )

    predicted_quality = evaluate_quality(
        row=input_row, keys=get_flat_key_combinations(), evaluation_dict=read_pavement_quality_rankings()
    )

    assert predicted_quality == PavementQuality.POTENTIALLY_GOOD


def test_evaluate_quality_no_information():
    """Assumption: There is no information on the surface"""
    input_row = pd.Series(
        data={
            '@other_tags': {'highway': 'residential'},
            'category': PathCategory.UNKNOWN,
        }
    )

    predicted_quality = evaluate_quality(
        row=input_row, keys=get_flat_key_combinations(), evaluation_dict=read_pavement_quality_rankings()
    )

    assert predicted_quality == PavementQuality.UNKNOWN


def test_evaluate_quality_we_dont_know_where_we_walk():
    """Assumption: There is no information on the surface"""
    input_row = pd.Series(
        data={
            '@other_tags': {'highway': 'residential', 'smoothness': 'good'},
            'category': PathCategory.UNKNOWN,
        }
    )

    predicted_quality = evaluate_quality(
        row=input_row, keys=get_flat_key_combinations(), evaluation_dict=read_pavement_quality_rankings()
    )

    assert predicted_quality == PavementQuality.UNKNOWN


def test_filter_walkable_paths():
    to_be_kept = gpd.GeoDataFrame(
        data={'category': [PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED]}, geometry=[shapely.Point()]
    )
    to_be_emptied = gpd.GeoDataFrame(data={'category': [PathCategory.DESIGNATED]}, geometry=[shapely.Point()])
    should_be_same, should_be_empty = subset_walkable_paths(
        to_be_kept,
        to_be_emptied,
        walkable_categories={PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED},
    )

    gpd.testing.assert_geodataframe_equal(should_be_same, to_be_kept)
    assert should_be_empty.empty
