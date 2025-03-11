import geopandas as gpd
import pandas as pd
import shapely
from ohsome import OhsomeClient

from walkability.components.categorise_paths.path_categorisation import (
    evaluate_quality,
    get_flat_key_combinations,
    read_pavement_quality_rankings,
    boost_route_members,
)
from walkability.components.utils.misc import PathCategory, PavementQuality


def test_boost_route_members(expected_compute_input, default_aoi, default_path_geometry, responses_mock):
    with open('test/resources/ohsome_line_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_output = pd.Series(
        data=[
            PathCategory.DESIGNATED,
            PathCategory.DESIGNATED_SHARED_WITH_BIKES,
            PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED,
            PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
            PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED,
            PathCategory.NOT_WALKABLE,
            PathCategory.UNKNOWN,
            PathCategory.DESIGNATED,
            PathCategory.DESIGNATED,
        ]
    )

    paths_input = gpd.GeoDataFrame(
        data={
            'category': [
                PathCategory.DESIGNATED,
                PathCategory.DESIGNATED_SHARED_WITH_BIKES,
                PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED,
                PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
                PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED,
                PathCategory.NOT_WALKABLE,
                PathCategory.UNKNOWN,
                PathCategory.DESIGNATED,
                PathCategory.UNKNOWN,
            ]
        },
        geometry=[
            default_path_geometry,
            default_path_geometry,
            default_path_geometry,
            default_path_geometry,
            default_path_geometry,
            default_path_geometry,
            shapely.LineString([(0, 0), (1, 0), (1, 1)]),
            default_path_geometry,
            default_path_geometry,
        ],
        crs=4326,
    )
    computed_output = boost_route_members(default_aoi, paths_input, OhsomeClient())
    pd.testing.assert_series_equal(computed_output, expected_output)


def test_boost_route_members_overlapping_routes(expected_compute_input, default_aoi, responses_mock):
    with open('test/resources/ohsome_route_response.geojson', 'rb') as vector:
        responses_mock.post(
            'https://api.ohsome.org/v1/elements/geometry',
            body=vector.read(),
        )

    expected_output = pd.Series(data=[PathCategory.DESIGNATED])

    paths_input = gpd.GeoDataFrame(
        data={'category': [PathCategory.UNKNOWN]},
        geometry=[
            shapely.LineString([(0, 0), (1, 1)]),
        ],
        crs=4326,
    )
    computed_output = boost_route_members(default_aoi, paths_input, OhsomeClient())
    pd.testing.assert_series_equal(computed_output, expected_output)


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
            'category': PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
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
            'category': PathCategory.DESIGNATED_SHARED_WITH_BIKES,
        }
    )
    # TODO: the categorisation above fulfils the code but should be reviewed!

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
            'category': PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
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
            'category': PathCategory.DESIGNATED_SHARED_WITH_BIKES,
        }
    )
    # TODO: the categorisation above fulfils the code but should be reviewed!

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
            'category': PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
        }
    )

    predicted_quality = evaluate_quality(
        row=input_row, keys=get_flat_key_combinations(), evaluation_dict=read_pavement_quality_rankings()
    )

    assert predicted_quality == PavementQuality.UNKNOWN
