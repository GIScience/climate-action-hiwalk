import uuid
from unittest.mock import MagicMock

import pytest
import rasterio
from climatoology.base.computation import ComputationScope
from climatoology.utility.api import LulcUtilityUtility


@pytest.fixture
def compute_resources():
    with ComputationScope(uuid.uuid4()) as resources:
        yield resources


@pytest.fixture
def lulc_utility():
    LulcUtilityUtility.compute_raster = MagicMock()
    LulcUtilityUtility.compute_raster.return_value.__enter__.return_value = rasterio.open(fp='resources/test_segmentation.tiff')
