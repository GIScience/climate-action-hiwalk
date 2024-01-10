import pytest
import responses
import uuid
from pathlib import Path
from semver import Version
from typing import List

from climatoology.base.artifact import ArtifactModality
from climatoology.base.computation import ComputationScope
from climatoology.base.operator import Info, Artifact, Concern
from plugin_blueprint.input import ComputeInputBlueprint
from plugin_blueprint.plugin import Settings


@pytest.fixture
def expected_info_output() -> Info:
    # noinspection PyTypeChecker
    return Info(name='Plugin Blueprint',
                icon=Path('resources/icon.jpeg'),
                version=Version(0, 0, 1),
                concerns=[Concern.CLIMATE_ACTION__GHG_EMISSION],
                purpose='This Plugin serves no purpose besides being a blueprint for real plugins.',
                methodology='This Plugin uses no methodology because it does nothing.',
                sources=Path('resources/example.bib'))


@pytest.fixture
def expected_compute_input() -> ComputeInputBlueprint:
    # noinspection PyTypeChecker
    return ComputeInputBlueprint(bool_blueprint=True,
                                 aoi_blueprint={
                                     'type': 'Feature',
                                     'properties': None,
                                     'geometry': {
                                         'type': 'MultiPolygon',
                                         'coordinates': [
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
    markdown_artifact = Artifact(name='A Text',
                                 modality=ArtifactModality.MARKDOWN,
                                 file_path=Path(compute_resources.computation_dir / 'markdown_blueprint.md'),
                                 summary='A JSON-block of the input parameters')
    table_artifact = Artifact(name='Character Count',
                              modality=ArtifactModality.TABLE,
                              file_path=Path(compute_resources.computation_dir / 'table_blueprint.csv'),
                              summary='The table lists the number of occurrences for each character in the input '
                                      'parameters.',
                              description='A table with two columns.')
    image_artifact = Artifact(name='Image',
                              modality=ArtifactModality.IMAGE,
                              file_path=Path(compute_resources.computation_dir / 'image_blueprint.png'),
                              summary='A nice image.',
                              description='The image is under CC0 license taken from [pexels](https://www.pexels.com/'
                                          'photo/person-holding-a-green-plant-1072824/).')
    scatter_chart_artifact = Artifact(name='The Points',
                                      modality=ArtifactModality.CHART,
                                      file_path=Path(
                                          compute_resources.computation_dir / 'scatter_chart_blueprint.json'),
                                      summary='A simple scatter plot.',
                                      description='Beautiful points.')
    line_chart_artifact = Artifact(name='The Line',
                                   modality=ArtifactModality.CHART,
                                   file_path=Path(compute_resources.computation_dir / 'line_chart_blueprint.json'),
                                   summary='A simple line of negative incline.')
    bar_chart_artifact = Artifact(name='The Bars',
                                  modality=ArtifactModality.CHART,
                                  file_path=Path(compute_resources.computation_dir / 'bar_chart_blueprint.json'),
                                  summary='A simple bar chart.')
    pie_chart_artifact = Artifact(name='The Pie',
                                  modality=ArtifactModality.CHART,
                                  file_path=Path(compute_resources.computation_dir / 'pie_chart_blueprint.json'),
                                  summary='A simple pie.')
    point_artifact = Artifact(name='Points',
                              modality=ArtifactModality.MAP_LAYER_GEOJSON,
                              file_path=Path(compute_resources.computation_dir / 'points_blueprint.geojson'),
                              summary='Schools in the area of interest including a dummy school in the center.',
                              description='The schools are taken from OSM at the date given in the input form.')
    line_artifact = Artifact(name='Lines',
                             modality=ArtifactModality.MAP_LAYER_GEOJSON,
                             file_path=Path(compute_resources.computation_dir / 'lines_blueprint.geojson'),
                             summary='Buffers around schools in the area of interest including a dummy school in the '
                                     'center.',
                             description='The schools are taken from OSM at the date given in the input form.')
    polygon_artifact = Artifact(name='Polygons',
                                modality=ArtifactModality.MAP_LAYER_GEOJSON,
                                file_path=Path(compute_resources.computation_dir / 'polygons_blueprint.geojson'),
                                summary='Schools in the area of interest including a dummy school in the center, '
                                        'buffered by ca. 100m.',
                                description='The schools are taken from OSM at the date given in the input form.')
    raster_artifact = Artifact(name='LULC Classification',
                               modality=ArtifactModality.MAP_LAYER_GEOTIFF,
                               file_path=Path(compute_resources.computation_dir / 'raster_blueprint.tiff'),
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


# The following fixtures can be ignored on plugin setup
@pytest.fixture
def compute_resources():
    with ComputationScope(uuid.uuid4()) as resources:
        yield resources


@pytest.fixture
def settings():
    return Settings(minio_host='localhost',
                    minio_port=80,
                    minio_access_key='access_key',
                    minio_secret_key='secret_key',
                    minio_bucket='bucket',
                    rabbitmq_host='localhost',
                    rabbitmq_port=80,
                    rabbitmq_user='user',
                    rabbitmq_password='password',
                    lulc_host='localhost',
                    lulc_port=80,
                    lulc_root_url='/api/lulc/')


@pytest.fixture
def web_apis():
    with (responses.RequestsMock() as rsps,
          open('resources/test_segmentation.tiff', 'rb') as raster,
          open('resources/ohsome.geojson', 'rb') as vector):
        rsps.post('http://localhost:80/api/lulc/segment/',
                  body=raster.read())
        rsps.post('https://api.ohsome.org/v1/elements/centroid',
                  body=vector.read())
        yield rsps


@pytest.fixture
def ohsome_api():
    with (responses.RequestsMock() as rsps,
          open('resources/ohsome.geojson', 'rb') as vector):
        rsps.post('https://api.ohsome.org/v1/elements/centroid',
                  body=vector.read())
        yield rsps
