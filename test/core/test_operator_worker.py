from unittest.mock import Mock, patch

import geopandas as gpd
import pytest
import shapely
from climatoology.base.exception import ClimatoologyUserError


@pytest.mark.vcr
def test_get_paths(operator, small_aoi, parametrized_ohsome_client):
    operator.ohsome = parametrized_ohsome_client
    required_columns = {
        'osm_id',
        'osm_type',
        'osm_tags',
        'category',
        'rating',
        'quality',
        'quality_rating',
        'smoothness',
        'smoothness_rating',
        'surface',
        'surface_rating',
        'geometry',
    }
    computed_lines, computed_polygons = operator._get_paths(aoi=small_aoi)

    assert set(computed_lines.columns) >= required_columns
    assert set(computed_polygons.columns) >= required_columns


def test_get_paths_with_erroneous_clipping(operator):
    # No difference between ohsome v1 and v2
    mocked_paths_response = gpd.read_file('test/resources/ohsome_erroneous_clipping.geojson').rename_geometry('geom')
    operator.ohsome.features_extraction = Mock(return_value=mocked_paths_response)

    with pytest.raises(
        ClimatoologyUserError,
        match=r'No accessible paths for walking were found in your area. Please select a larger area',
    ):
        operator._get_paths(
            aoi=shapely.MultiPolygon(
                polygons=[
                    [
                        [
                            [8.676042, 49.418866],
                            [8.676042, 49.4190311],
                            [8.6765357, 49.4190311],
                            [8.6765357, 49.418866],
                            [8.676042, 49.418866],
                        ]
                    ]
                ]
            )
        )


def test_get_paths_empty_ohsome_response(operator, default_aoi):
    # No difference between ohsome v1 and v2
    with patch('walkability.core.operator_worker.fetch_osm_data') as mock:
        mock.return_value = gpd.GeoDataFrame(columns=['osm_id', 'osm_type', 'geometry', 'osm_tags'])
        with pytest.raises(
            ClimatoologyUserError,
            match=r'No accessible paths for walking were found in your area. Please select a larger area',
        ):
            operator._get_paths(aoi=default_aoi)


# There are paths in the AOI, but they are removed by path_categorisation because they are in PathCategory.INACCESSIBLE
def test_get_paths_inaccessible_ohsome_response(default_path_geometry, operator, default_aoi):
    # No difference between ohsome v1 and v2
    with patch('walkability.core.operator_worker.fetch_osm_data') as mock:
        mock.return_value = gpd.GeoDataFrame(
            data={
                'osm_id': ['1'],
                'osm_type': ['way'],
                'geometry': [default_path_geometry],
                'osm_tags': [{'highway': 'motorway'}],
            },
        )
        with pytest.raises(
            ClimatoologyUserError,
            match=r'No accessible paths for walking were found in your area. Please select a larger area',
        ):
            operator._get_paths(aoi=default_aoi)


def test_clean_geometries_tiny_remnants(operator):
    aoi = shapely.box(xmin=-0.1, xmax=1, ymin=-0.1, ymax=1.1)

    big_path = shapely.LineString([(0.0, 1.0), (0.0, 0.0)])
    path_that_should_collapse = shapely.LineString([(0.00000004, 0.0), (0.0, 0.0)])

    paths = gpd.GeoDataFrame(data={'expected': [True, False]}, geometry=[big_path, path_that_should_collapse])

    received = operator.clean_geometries(aoi=aoi, geometries=paths, geom_name='String')

    assert received[~received['expected']].empty
