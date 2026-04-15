import numpy as np
import plotly.graph_objects as go
from climatoology.base.artifact import Artifact

from walkability.components.slope.slope_analysis import compute_slope_analysis, summarise_slope


def test_compute_slope_analysis(default_path, compute_resources, slopes_mock):
    artifacts = compute_slope_analysis(default_path, None, compute_resources)

    for artifact in artifacts:
        assert isinstance(artifact, Artifact)


def test_summarise_slope(default_slopes_gdf):
    histogram_chart = summarise_slope(path_slopes_data=default_slopes_gdf)

    assert isinstance(histogram_chart, go.Figure)
    print(histogram_chart.data[0].x)
    np.testing.assert_array_equal(histogram_chart.data[0].x, [1, 2, 3, 10])
