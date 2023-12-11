import pytest
import responses
import uuid

from climatoology.base.computation import ComputationScope


@pytest.fixture
def compute_resources():
    with ComputationScope(uuid.uuid4()) as resources:
        yield resources


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
