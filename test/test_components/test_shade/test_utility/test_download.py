import geopandas as gpd

from walkability.components.shade.utility.download import download_shade_tile, download_tile_spec


def test_download_tile_spec(operator, compute_resources):
    tiles = download_tile_spec(
        shade_config=operator.shade_config,
        shade_client=operator.shade_client,
        download_dir=compute_resources.computation_dir,
    )

    assert isinstance(tiles, gpd.GeoSeries)


def test_download_shade_tile(default_shade_client, default_shade_config):
    tile_id = 'mock_tree_raster1'
    expected_result = default_shade_config.cache_dir / 'mock_tree_raster1.tif'

    result = download_shade_tile(tile_id=tile_id, shade_client=default_shade_client, shade_config=default_shade_config)

    assert result == expected_result
