import uuid
from unittest.mock import MagicMock

import pytest
import rasterio
from climatoology.base.operator import ComputationScope
from climatoology.utility.api import LulcUtilityUtility


@pytest.fixture
def compute_resources():
    with ComputationScope(uuid.uuid4()) as resources:
        yield resources


@pytest.fixture
def lulc_utility():
    with rasterio.open(fp='resources/test_segmentation.tiff') as dataset:
        LulcUtilityUtility.compute_raster = MagicMock(return_value=dataset)
        yield dataset
