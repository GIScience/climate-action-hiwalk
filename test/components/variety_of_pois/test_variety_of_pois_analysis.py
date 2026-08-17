import pandas as pd
import plotly.graph_objects as go
import pytest

from walkability.components.variety_of_pois.variety_of_poi_analysis import (
    calculate_evenness,
    create_poi_summary_chart,
    get_hex_grids,
    get_variety_of_pois,
)
from walkability.components.variety_of_pois.variety_poi_filters import POI_CATEGORIES


@pytest.mark.vcr
def test_variety_of_pois(parametrized_ohsome_client, small_aoi):
    expected_columns = (
        ['geometry', 'hex_id']
        + [f'number_of_pois_{category.type}' for category in POI_CATEGORIES]
        + ['total_number_of_pois', 'number_of_categories']
    )
    received = get_variety_of_pois(aoi=small_aoi, ohsome=parametrized_ohsome_client)
    assert list(received.columns) == expected_columns
    assert received['hex_id'][0] == '891faa9965bffff'


def test_get_hex_grids(small_aoi):
    expected_hexids = pd.Series(
        ['8a1fae6cb25ffff', '8a1faa9965a7fff', '8a1faa9965b7fff', '8a1faa996587fff'], name='hex_id'
    )
    hexagons = get_hex_grids(aoi=small_aoi, hex_resolution=10)
    pd.testing.assert_series_equal(expected_hexids, hexagons['hex_id'])


def test_create_poi_summary_chart():
    summary = pd.DataFrame(
        {
            'poi_category': ['education', 'childcare', 'healthcare'],
            'poi_sum': [2, 0, 8],
        }
    )
    bar_chart = create_poi_summary_chart(summary)
    assert isinstance(bar_chart, go.Figure)
    assert bar_chart['data'][0]['x'][0] == 'education'
    assert bar_chart['data'][0]['x'][1] == 'childcare'


def test_calculate_evenness():
    summary = pd.DataFrame(
        {
            'poi_category': ['education', 'childcare', 'healthcare'],
            'poi_sum': [2, 0, 8],
        }
    )

    expected_result = {
        'evenness': 0.721928,
        'num_zero_categories': 1,
        'num_categories': 3,
    }

    evenness_result = calculate_evenness(summary)

    assert pytest.approx(evenness_result, abs=0.00001) == expected_result
