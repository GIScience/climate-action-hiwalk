import geopandas as gpd
import shapely
from climatoology.base.artifact import _Artifact
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color

from walkability.components.wellness.benches_and_drinking_water import PointsOfInterest
from walkability.components.wellness.wellness_artifacts import assign_color, assign_label, compute_wellness_artifacts


def test_compute_wellness_artifact(
    default_aoi,
    default_path,
    operator,
    compute_resources,
    responses_mock,
    ors_isochrone_api,
    default_max_walking_distance_map,
):
    with (
        open('test/resources/ohsome_drinking_water.geojson', 'r') as drinking_water,
        open('test/resources/ohsome_benches.geojson', 'r') as benches,
    ):
        drinking_water_body = drinking_water.read()
        benches_body = benches.read()
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/centroid',
        body=drinking_water_body,
    )
    responses_mock.post(
        'https://api.ohsome.org/v1/elements/centroid',
        body=benches_body,
    )

    recieved = compute_wellness_artifacts(
        paths=default_path,
        aoi=default_aoi,
        max_walking_distance_map=default_max_walking_distance_map,
        ohsome_client=OhsomeClient(),
        ors_settings=operator.ors_settings,
        resources=compute_resources,
    )

    assert len(recieved) == 2
    for artifact in recieved:
        assert isinstance(artifact, _Artifact)


def test_assign_color(default_max_walking_distance_map):
    poi = PointsOfInterest.SEATING
    max_walking_distance = default_max_walking_distance_map[poi]

    string = shapely.LineString([(1.0, 1.0), (1.0, 1.0)])
    data = gpd.GeoDataFrame(
        data={
            'value': [0.0, 200, None],
        },
        geometry=[shapely.Point(0.0, 0.0), string, string],
    )
    received = assign_color(data, poi=poi, max_walking_distance=max_walking_distance, min_value=0.0)

    assert received['color'].to_list() == [Color('brown'), Color('#f2cbb7'), Color('red')]


def test_assign_label(default_max_walking_distance_map):
    poi = PointsOfInterest.SEATING
    max_walking_distance = default_max_walking_distance_map[poi]

    string = shapely.LineString([(0.0, 0.0), (1.0, 1.0)])
    paths = gpd.GeoDataFrame(data={'value': [0.0, 200, None]}, geometry=[shapely.Point(1.0, 1.0), string, string])

    computed_labels = paths.apply(assign_label, poi=poi, max_walking_distance=max_walking_distance, axis=1)
    assert computed_labels.to_list() == ['benches', '< 200m', '> 333m']
