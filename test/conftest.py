import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Tuple
from unittest.mock import patch
from urllib.parse import parse_qsl

import boto3
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from approvaltests import DiffReporter, set_default_reporter
from botocore import UNSIGNED
from botocore.config import Config
from climatoology.base.baseoperator import AoiProperties
from climatoology.base.computation import ComputationScope
from dotenv import load_dotenv
from mobility_tools.settings import ORSSettings
from moto import mock_aws
from ohsome_py2.client import OhsomeClient
from rasterio import Affine
from requests import PreparedRequest
from shapely.geometry import LineString

from walkability.components.comfort.comfort_poi_filters import PointsOfInterest
from walkability.components.shade.utility.config import S3ShadeConfig
from walkability.components.shade.utility.download import download_tile_spec
from walkability.components.utils.geometry import CAN_DEFAULT_CRS
from walkability.components.utils.misc import PathCategory
from walkability.core.input import ComputeInputWalkability
from walkability.core.operator_worker import OperatorWalkability
from walkability.core.settings import Settings

TEST_RESOURCES_DIR = Path('test/resources')

load_dotenv()  # To load the `OHSOME_BASE_URL` environment variable, for recording new cassettes
pytest_plugins = ('ohsome_py2.test.fixtures',)


@pytest.fixture(scope='session')
def vcr_config(vcr_config_ohsomepy2):
    vcr_config_ohsomepy2.update(
        {
            'filter_headers': ['authorization'],
            'cassette_library_dir': 'test/resources/vcr_cassettes',
        }
    )

    return vcr_config_ohsomepy2


@pytest.fixture
def expected_compute_input() -> ComputeInputWalkability:
    return ComputeInputWalkability()


@pytest.fixture
def default_aoi() -> shapely.MultiPolygon:
    return shapely.MultiPolygon(polygons=[shapely.box(8.6983273, 49.4079880, 8.7108559, 49.4136026)])


@pytest.fixture
def small_aoi() -> shapely.Polygon:
    return shapely.MultiPolygon([shapely.box(8.6742192, 49.4046213, 8.6774288, 49.4064122)])


@pytest.fixture
def default_aoi_properties() -> AoiProperties:
    return AoiProperties(name='Heidelberg', id='heidelberg')


# The following fixtures can be ignored on plugin setup
@pytest.fixture
def compute_resources():
    with ComputationScope(uuid.uuid4()) as resources:
        yield resources


@pytest.fixture
def default_shade_config():
    with TemporaryDirectory() as tmpdir:
        yield S3ShadeConfig(bucket='test-bucket', cache_dir=tmpdir)


@pytest.fixture
def default_canopy_tiles(default_shade_client, default_shade_config):
    canopy_tiles = download_tile_spec(
        shade_client=default_shade_client,
        shade_config=default_shade_config,
        download_dir=default_shade_config.cache_dir,
    )
    yield canopy_tiles


@pytest.fixture
def default_shade_client(default_shade_config):
    with mock_aws():
        shade_client = boto3.client('s3', config=Config(user_agent='test', signature_version=UNSIGNED))
        shade_client.create_bucket(Bucket=default_shade_config.bucket, ACL='public-read-write')

        shade_client.upload_file(
            Bucket=default_shade_config.bucket,
            Key=str(default_shade_config.base_path / default_shade_config.tiles_object),
            Filename=TEST_RESOURCES_DIR / 'shade/mock_shade_tiles.geojson',
        )

        upload_tiles = ['mock_tree_raster1.tif', 'mock_tree_raster2.tif', 'mock_tree_raster2.tif.msk']
        for tile in upload_tiles:
            if tile.endswith('.msk'):
                path = default_shade_config.cloud_mask_path
            else:
                path = default_shade_config.canopy_heights_path
            shade_client.upload_file(
                Bucket=default_shade_config.bucket,
                Key=str(path / tile),
                Filename=TEST_RESOURCES_DIR / 'shade' / tile,
            )

        yield shade_client


@pytest.fixture
def operator(
    naturalness_utility_mock, default_shade_config, default_settings, default_ors_settings, default_shade_client
) -> OperatorWalkability:
    with patch('walkability.core.operator_worker.boto3.client', return_value=default_shade_client):
        return OperatorWalkability(
            naturalness_utility=naturalness_utility_mock,
            hiwalk_settings=default_settings,
            ors_settings=default_ors_settings,
            s3_settings=None,
            shade_config=default_shade_config,
            max_path_limit=100000,
            feature_flag_experimental=True,
        )  # type: ignore


@pytest.fixture
def default_settings() -> Settings:
    settings = Settings(
        naturalness_host='mock-naturalness-host',
        naturalness_port=1234,
        naturalness_path='mock-naturalness-path',
        feature_flag_ohsome2=False,
    )
    return settings


@pytest.fixture
def default_ohsome_client_v1():
    return OhsomeClient(user_agent='can-walkability-test', v2=False)


@pytest.fixture
def default_ohsome_client_v2():
    return OhsomeClient(user_agent='can-walkability-test', v2=True)


@pytest.fixture(params=['default_ohsome_client_v2', 'default_ohsome_client_v1'])
def parametrized_ohsome_client(request):
    return request.getfixturevalue(request.param)


@pytest.fixture
def default_ors_settings() -> ORSSettings:
    # This secret url comes from the vcr_config fixture
    return ORSSettings(ors_base_url='http://vcr-secret-url', ors_api_key='test-key')


@pytest.fixture
def expected_detour_factors() -> pd.DataFrame:
    detour_factors = pd.DataFrame(
        data={
            'detour_factor': [
                1.3995538900828162,
                1.219719961221372,
                1.454343083874761,
                1.7969363677141994,
                1.4832090368368422,
                1.8521635465676833,
                1.3880294081510607,
            ],
            'id': [
                '8a1faa996847fff',
                '8a1faa99684ffff',
                '8a1faa996857fff',
                '8a1faa99685ffff',
                '8a1faa9968c7fff',
                '8a1faa9968effff',
                '8a1faa996bb7fff',
            ],
        }
    ).set_index('id')
    return detour_factors.h3.h3_to_geo_boundary()


@pytest.fixture
def naturalness_utility_mock():
    with patch('climatoology.utility.naturalness.NaturalnessUtility') as naturalness_utility:
        vectors = gpd.GeoSeries(
            index=[1, 2],
            data=[
                LineString([[12.4, 48.25], [12.4, 48.30]]),
                LineString([[12.41, 48.25], [12.41, 48.30]]),
            ],
            crs=CAN_DEFAULT_CRS,
        )
        return_gdf = gpd.GeoDataFrame(index=[1, 2], data={'median': [0.5, 0.6]}, geometry=vectors, crs=CAN_DEFAULT_CRS)

        naturalness_utility.compute_vector.return_value = return_gdf
        yield naturalness_utility


@pytest.fixture
def default_path_geometry() -> shapely.LineString:
    return shapely.LineString([(12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22)])


@pytest.fixture
def default_polygon_geometry() -> shapely.Polygon:
    return shapely.Polygon(((12.3, 48.22), (12.3, 48.2205), (12.3005, 48.22), (12.3, 48.22)))


@pytest.fixture
def default_path(default_path_geometry) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        data={
            'osm_id': ['test'],
            'osm_type': ['way'],
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'osm_tags': [{}],
            'length': [122.5],
            'length_shaded': [49],
            'geometry': [default_path_geometry],
        },
        crs=CAN_DEFAULT_CRS,
    )


@pytest.fixture
def default_aoi_paths() -> gpd.GeoDataFrame:
    """Several paths that cross the space of the default_aoi"""
    xs = list(np.arange(8.70, 8.71, step=0.002))
    ys = list(np.arange(49.407, 49.412, step=0.002))

    lines = []
    for i in range(len(xs)):
        lines.append(LineString([(xs[i], ys[0]), (xs[i], ys[-1])]))

    for i in range(len(ys)):
        lines.append(LineString([(xs[0], ys[i]), (xs[-1], ys[i])]))

    gdf = gpd.GeoDataFrame(geometry=lines, crs=CAN_DEFAULT_CRS)
    gdf = gdf.assign(
        osm_type='way',
        rating=1.0,
        length=100,  # TODO: fix?
        length_shaded=50,  # TODO: fix
    )
    gdf = gdf.reset_index(names='osm_id')

    return gdf


@pytest.fixture
def small_aoi_paths(small_aoi) -> shapely.Polygon:
    xmin, ymin, xmax, ymax = small_aoi.bounds
    return gpd.GeoDataFrame(
        data={
            'osm_id': ['small1', 'small2'],
            'osm_type': ['way', 'way'],
            'category': [PathCategory.DESIGNATED, PathCategory.DESIGNATED],
            'rating': [1.0, 1.0],
            'osm_tags': [{}, {}],
            'length': [122.5, 122.5],
            'length_shaded': [49, 49],
            'geometry': [
                LineString([(xmin, ymin), (xmax, ymax)]),
                shapely.Polygon([(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymin)]),
            ],
        },
        crs=CAN_DEFAULT_CRS,
    )


def filter_start_matcher(filter_start: str) -> Callable[..., Any]:
    def match(request: PreparedRequest) -> Tuple[bool, str]:
        request_body = request.body
        qsl_body = dict(parse_qsl(request_body, keep_blank_values=False)) if request_body else {}

        if request_body is None:
            return False, 'The given request has no body'
        elif qsl_body.get('filter') is None:
            return False, 'Filter parameter not set'
        else:
            valid = qsl_body.get('filter', '').startswith(filter_start)
            return (True, '') if valid else (False, f'The filter parameter does not start with {filter_start}')

    return match


@pytest.fixture
def default_max_walking_distance_map() -> dict[PointsOfInterest, float]:
    m_per_minute = 66.666
    return {
        PointsOfInterest.DRINKING_WATER: m_per_minute * 10,
        PointsOfInterest.SEATING: m_per_minute * 5,
        PointsOfInterest.REMAINDER: m_per_minute * 15,
    }


@pytest.fixture(autouse=True)
def configure_approvaltests():
    set_default_reporter(DiffReporter())


@pytest.fixture
def default_slopes_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        data={
            'osm_id': ['1', '1', '2', '3'],
            'osm_type': ['way', 'way', 'way', 'way'],
            'segment_id': [0, 1, 0, 0],
            'segment_length': [10, 10, 10, 10],
            'slope': [1.0, 2.0, 3.0, 10.0],
        },
        geometry=[
            LineString([(-1.0, -1.0), (-0.5, -0.5)]),  # way/1 seg0 — fully OUTSIDE
            LineString([(0.2, 0.2), (0.5, 0.5)]),  # way/1 seg1 — fully INSIDE
            LineString([(0.5, 0.0), (0.5, 1.0)]),  # way/2 seg0 — fully INSIDE (on boundary)
            LineString([(0.8, 0.8), (1.5, 1.5)]),  # way/3 seg0 — CROSSES boundary (partial)
        ],
        crs=CAN_DEFAULT_CRS,
    )


@pytest.fixture
def slopes_mock(default_slopes_gdf):
    with patch('walkability.components.slope.slope_analysis.get_paths_slopes') as get_slopes:
        get_slopes.return_value = default_slopes_gdf
        yield default_slopes_gdf


@pytest.fixture
def default_shade_path() -> gpd.GeoDataFrame:
    """A default shade path which overlaps with both `mock_tree_raster1.tif` and `mock_tree_raster2.tif`."""
    # This LineString transforms to clean coordinates in EPSG:3857, which makes for nice testing with the raster files.
    return gpd.GeoDataFrame(
        data={
            'osm_id': ['test'],
            'osm_type': ['way'],
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'osm_tags': [{}],
            'geometry': [LineString([[12.29973287, 48.22], [12.31051265, 48.22]])],
        },
        crs=CAN_DEFAULT_CRS,
    )


@pytest.fixture
def default_shade_path_small() -> gpd.GeoDataFrame:
    """A default shade path which is covered by only `mock_tree_raster1.tif` and can be used with
    `default_canopy_raster_profile` for unit testing.
    """
    return gpd.GeoDataFrame(
        data={
            'osm_id': ['test'],
            'osm_type': ['way'],
            'category': [PathCategory.DESIGNATED],
            'rating': [1.0],
            'osm_tags': [{}],
            'geometry': [LineString([[12.30, 48.22], [12.305, 48.22]])],
        },
        crs=CAN_DEFAULT_CRS,
    )


@pytest.fixture
def default_canopy_raster_profile():
    """This is a default raster profile for an array of shape (4, 20), which covers all of `default_shade_path_small`."""
    return {
        'driver': 'GTiff',
        'dtype': 'float32',
        'nodata': 255,
        'width': 20,
        'height': 4,
        'count': 1,
        'crs': CAN_DEFAULT_CRS,
        'transform': Affine(0.00024999999999995024, 0.0, 12.3, 0.0, -0.00024999999999995024, 48.2205),
    }
