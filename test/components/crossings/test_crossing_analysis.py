import pandas as pd
import pytest
from climatoology.base.artifact import Artifact
from ohsome_filter_to_sql.main import validate_filter

from walkability.components.crossings.crossing_analysis import (
    categorize_crossing,
    crossing_analysis,
    ohsome_filter,
)
from walkability.components.utils.misc import CrossingType


@pytest.mark.vcr
def test_crossing_analysis(default_aoi, parametrized_ohsome_client, compute_resources):
    result = crossing_analysis(default_aoi, parametrized_ohsome_client, resources=compute_resources)
    assert isinstance(result, Artifact)


@pytest.mark.parametrize(
    argnames=['tags', 'expected'],
    argvalues=[
        ({'crossing': 'marked'}, CrossingType.Marked),
        ({'crossing': 'uncontrolled'}, CrossingType.Marked),
        ({'crossing': 'unmarked'}, CrossingType.Unmarked),
        ({'crossing': 'traffic_signals'}, CrossingType.TrafficSignals),
        ({'crossing': ''}, CrossingType.Other),
        ({'crossing:signals': 'yes'}, CrossingType.TrafficSignals),
        ({'crossing:signals': 'no', 'crossing:markings': 'zebra'}, CrossingType.Marked),
        ({'crossing_ref': 'toucan'}, CrossingType.TrafficSignals),
    ],
)
def test_categorize_crossings(tags, expected):
    row = pd.Series({'osm_tags': tags})
    received = categorize_crossing(row)
    assert received == expected


def test_ohsome_filter_function():
    validate_filter(ohsome_filter())
