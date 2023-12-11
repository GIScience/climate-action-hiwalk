from unittest import mock

import os
import pytest
from pathlib import Path
from semver import Version
from typing import List

from climatoology.base.artifact import ArtifactModality
from climatoology.base.operator import Info, Artifact, Concern
from plugin_blueprint.input import BlueprintComputeInput
from plugin_blueprint.operator_worker import BlueprintOperator


@pytest.fixture
def expected_info_output() -> Info:
    # noinspection PyTypeChecker
    return Info(name='Blueprint Plugin',
                icon=Path('resources/icon.jpeg'),
                version=Version(0, 0, 1),
                concerns=[Concern.CLIMATE_ACTION__GHG_EMISSION],
                purpose='This Plugin serves no purpose besides being a blueprint for real plugins.',
                methodology='This Plugin uses no methodology because it does nothing.',
                sources=Path('resources/example.bib'))


@pytest.fixture
def expected_compute_input() -> BlueprintComputeInput:
    # noinspection PyTypeChecker
    return BlueprintComputeInput(blueprint_bool=True,
                                 blueprint_aoi={
                                     "type": "Feature",
                                     "properties": None,
                                     "geometry": {
                                         "type": "MultiPolygon",
                                         "coordinates": [
                                             [
                                                 [
                                                     [12.3, 48.22],
                                                     [12.3, 48.34],
                                                     [12.48, 48.34],
                                                     [12.48, 48.22],
                                                     [12.3, 48.22]
                                                 ]
                                             ]
                                         ]
                                     }
                                 })


@pytest.fixture
def expected_compute_output(compute_resources) -> List[Artifact]:
    markdown_artifact = Artifact(name="A Text",
                                 modality=ArtifactModality.MARKDOWN,
                                 file_path=Path(compute_resources.computation_dir / 'blueprint_markdown.md'),
                                 summary='A JSON-block of the input parameters')
    table_artifact = Artifact(name="Character Count",
                              modality=ArtifactModality.TABLE,
                              file_path=Path(compute_resources.computation_dir / 'blueprint_table.csv'),
                              summary='The table lists the number of occurrences for each character in the input '
                                      'parameters.',
                              description='A table with two columns.')
    image_artifact = Artifact(name="Image",
                              modality=ArtifactModality.IMAGE,
                              file_path=Path(compute_resources.computation_dir / 'blueprint_image.png'),
                              summary='A nice image.',
                              description='The image is under CC0 license taken from [pexels](https://www.pexels.com/'
                                          'photo/person-holding-a-green-plant-1072824/).')
    scatter_chart_artifact = Artifact(name="The Points",
                                      modality=ArtifactModality.CHART,
                                      file_path=Path(
                                          compute_resources.computation_dir / 'blueprint_scatter_chart.json'),
                                      summary='A simple scatter plot.',
                                      description='Beautiful points.')
    line_chart_artifact = Artifact(name="The Line",
                                   modality=ArtifactModality.CHART,
                                   file_path=Path(compute_resources.computation_dir / 'blueprint_line_chart.json'),
                                   summary='A simple line of negative incline.')
    bar_chart_artifact = Artifact(name="The Bars",
                                  modality=ArtifactModality.CHART,
                                  file_path=Path(compute_resources.computation_dir / 'blueprint_bar_chart.json'),
                                  summary='A simple bar chart.')
    pie_chart_artifact = Artifact(name="The Pie",
                                  modality=ArtifactModality.CHART,
                                  file_path=Path(compute_resources.computation_dir / 'blueprint_pie_chart.json'),
                                  summary='A simple pie.')
    point_artifact = Artifact(name="Points",
                              modality=ArtifactModality.MAP_LAYER_GEOJSON,
                              file_path=Path(compute_resources.computation_dir / 'blueprint_points.geojson'),
                              summary='Schools in the area of interest including a dummy school in the center.',
                              description='The schools are taken from OSM at the date given in the input form.')
    line_artifact = Artifact(name="Lines",
                             modality=ArtifactModality.MAP_LAYER_GEOJSON,
                             file_path=Path(compute_resources.computation_dir / 'blueprint_lines.geojson'),
                             summary='Buffers around schools in the area of interest including a dummy school in the '
                                     'center.',
                             description='The schools are taken from OSM at the date given in the input form.')
    polygon_artifact = Artifact(name="Polygons",
                                modality=ArtifactModality.MAP_LAYER_GEOJSON,
                                file_path=Path(compute_resources.computation_dir / 'blueprint_polygons.geojson'),
                                summary='Schools in the area of interest including a dummy school in the center, '
                                        'buffered by ca. 100m.',
                                description='The schools are taken from OSM at the date given in the input form.')
    raster_artifact = Artifact(name="LULC Classification",
                               modality=ArtifactModality.MAP_LAYER_GEOTIFF,
                               file_path=Path(compute_resources.computation_dir / 'blueprint_raster.tiff'),
                               summary='A land-use and land-cover classification of a user defined area.',
                               description='The classification is created using a deep learning model.')
    return [markdown_artifact,
            table_artifact,
            image_artifact,
            scatter_chart_artifact,
            line_chart_artifact,
            bar_chart_artifact,
            pie_chart_artifact,
            point_artifact,
            line_artifact,
            polygon_artifact,
            raster_artifact]


@mock.patch.dict(os.environ, {'LULC_HOST': 'localhost', 'LULC_PORT': '80', 'LULC_ROOT_URL': '/api/lulc/'}, clear=True)
def test_plugin_info_request(expected_info_output):
    operator = BlueprintOperator()
    assert operator.info() == expected_info_output


@mock.patch.dict(os.environ, {'LULC_HOST': 'localhost', 'LULC_PORT': '80', 'LULC_ROOT_URL': '/api/lulc/'}, clear=True)
def test_plugin_compute_request(expected_compute_input, expected_compute_output, compute_resources, web_apis):
    operator = BlueprintOperator()
    assert operator.compute(resources=compute_resources,
                            params=expected_compute_input) == expected_compute_output
