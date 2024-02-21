import geopandas as gpd
import pandas as pd
import shapely
from climatoology.base.artifact import Chart2dData, ChartType
from geopandas import testing
from pydantic_extra_types.color import Color

from plugin_blueprint.operator_worker import OperatorBlueprint


def test_get_md_text(expected_compute_input):
    expected = """# Input Parameters

The Plugin Blueprint was run with the following parameters.
You can check if your input was received in the correct manner.
Be aware that if you did not specify a value, some of the optional parameters may use defaults.

```json
{
    "bool_blueprint": true,
    "int_blueprint": 3,
    "float_blueprint": 2.1,
    "string_blueprint": "John Doe",
    "date_blueprint": "2020-01-01",
    "select_blueprint": "Option 2",
    "select_multi_blueprint": [
        "Option 2"
    ]
}
```

In addition the following area of interest was sent:

```json
{
    "type": "Feature",
    "geometry": {
        "type": "MultiPolygon",
        "coordinates": [
            [
                [
                    [
                        12.3,
                        48.22
                    ],
                    [
                        12.3,
                        48.34
                    ],
                    [
                        12.48,
                        48.34
                    ],
                    [
                        12.48,
                        48.22
                    ],
                    [
                        12.3,
                        48.22
                    ]
                ]
            ]
        ]
    },
    "properties": null
}
```
"""
    received = OperatorBlueprint.get_md_text(expected_compute_input)
    assert received == expected


def test_create_table(expected_compute_input):
    data = [
        {'character': 'o', 'count': 2},
        {'character': ' ', 'count': 1},
        {'character': 'd', 'count': 1},
        {'character': 'e', 'count': 1},
        {'character': 'h', 'count': 1},
        {'character': 'j', 'count': 1},
        {'character': 'n', 'count': 1},
    ]
    expected = pd.DataFrame.from_records(data, index='character')
    received = OperatorBlueprint.create_table(expected_compute_input.string_blueprint)

    pd.testing.assert_frame_equal(received, expected)


def test_chart_creator():
    expected = (
        Chart2dData(
            x=[0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0],
            y=[0.0, -10.0, -20.0, -30.0, -40.0, -50.0, -60.0, -70.0, -80.0, -90.0],
            chart_type=ChartType.SCATTER,
            color=Color('#590d08'),
        ),
        Chart2dData(
            x=[0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0],
            y=[0.0, -10.0, -20.0, -30.0, -40.0, -50.0, -60.0, -70.0, -80.0, -90.0],
            chart_type=ChartType.LINE,
            color=Color('#590d08'),
        ),
        Chart2dData(
            x=['0', '10', '20', '30', '40', '50', '60', '70', '80', '90'],
            y=[0.0, -10.0, -20.0, -30.0, -40.0, -50.0, -60.0, -70.0, -80.0, -90.0],
            chart_type=ChartType.BAR,
            color=Color('#590d08'),
        ),
        Chart2dData(
            x=[0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0],
            y=[
                0.0,
                0.022222222222222223,
                0.044444444444444446,
                0.06666666666666667,
                0.08888888888888889,
                0.1111111111111111,
                0.13333333333333333,
                0.15555555555555556,
                0.17777777777777778,
                0.2,
            ],
            chart_type=ChartType.PIE,
            color=[
                Color('#a6cee3'),
                Color('#1f78b4'),
                Color('#b2df8a'),
                Color('#33a02c'),
                Color('#fb9a99'),
                Color('#e31a1c'),
                Color('#fdbf6f'),
                Color('#ff7f00'),
                Color('#cab2d6'),
                Color('#6a3d9a'),
            ],
        ),
    )
    received = OperatorBlueprint.chart_creator(1)
    assert received == expected


def test_vector_creator(settings, expected_compute_input, ohsome_api):
    line_blue = shapely.LineString(
        [
            [8.698543628011903, 49.39500732240416],
            [8.698421796496781, 49.3930214907138],
            [8.695924392376607, 49.3930214907138],
            [8.69604618891268, 49.39500732240416],
            [8.698543628011903, 49.39500732240416],
        ]
    )
    line_red = shapely.LineString(
        [
            [12.391322017203764, 48.280978625572004],
            [12.391156159366846, 48.27902138662579],
            [12.388678003226348, 48.27902138662579],
            [12.388843827892703, 48.280978625572004],
            [12.391322017203764, 48.280978625572004],
        ]
    )
    expected = (
        gpd.GeoDataFrame(
            data={
                'color': [Color('blue'), Color('red')],
                'geometry': [shapely.Point(8.697234, 49.3940144), shapely.Point(12.39, 48.279999999999994)],
            },
            crs='EPSG:4326',
        ),
        gpd.GeoDataFrame(
            data={'color': [Color('blue'), Color('red')], 'geometry': [line_blue, line_red]},
            crs='EPSG:4326',
        ),
        gpd.GeoDataFrame(
            data={
                'color': [Color('blue'), Color('red')],
                'geometry': [shapely.Polygon(line_blue), shapely.Polygon(line_red)],
            },
            crs='EPSG:4326',
        ),
    )
    bp = OperatorBlueprint(
        settings.lulc_host,
        settings.lulc_port,
        settings.lulc_path,
    )
    received = bp.vector_creator(expected_compute_input.get_geom(), expected_compute_input.date_blueprint)
    for expected_gdf, received_gdf in zip(expected, received):
        testing.assert_geodataframe_equal(
            received_gdf,
            expected_gdf,
            check_like=True,
            check_geom_type=True,
            check_less_precise=True,
        )
