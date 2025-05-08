import logging
import time
from requests import HTTPError

from climatoology.base.artifact import (
    _Artifact,
    ContinuousLegendData,
    create_geojson_artifact,
    create_plotly_chart_artifact,
)
from climatoology.base.computation import ComputationResources
from pathlib import Path
from plotly.graph_objects import Figure


import geopandas as gpd
import openrouteservice
import openrouteservice.directions
import pandas as pd
import h3pandas
import h3
import numpy as np
from requests_ratelimiter import LimiterSession
import shapely
import math

from walkability.components.utils.misc import generate_colors
from walkability.components.utils.ORSSettings import ORSSettings

log = logging.getLogger(__name__)


def detour_factor_analysis(
    aoi: shapely.MultiPolygon,
    ors_settings: ORSSettings,
    resources: ComputationResources,
) -> tuple[_Artifact, gpd.GeoDataFrame]:
    detour_factors = get_detour_factors(aoi=aoi, ors_settings=ors_settings)

    artifact = build_detour_factor_artifact(detour_factor_data=detour_factors, resources=resources)
    return artifact, detour_factors


def get_detour_factors(aoi: shapely.MultiPolygon, ors_settings: ORSSettings) -> gpd.GeoDataFrame:
    log.info('Computing detour factors')

    destinations = create_destinations(aoi, max_waypoint_number=ors_settings.directions_waypoint_limit)
    distance_between_cells = get_cell_distance(destinations)

    # This following calculation gives the distance from the cell center point to one of the corners.
    # It's based on the normal distance from the center point of the cell to one of its sides,
    # which is half the distance to its neighbouring cell.
    distance_center_corner = int(np.ceil((distance_between_cells / 2) * math.cos(math.pi / 6)))

    snapped_destinations = snap_destinations(
        destinations,
        ors_settings=ors_settings,
        snapping_radius=distance_center_corner,
    )

    destinations_with_snapping = pd.merge(
        left=destinations, right=snapped_destinations, how='left', left_on='id', right_on='id'
    )

    mean_walking_distances = get_ors_walking_distances(ors_settings, distance_between_cells, destinations_with_snapping)
    return mean_walking_distances.h3.h3_to_geo_boundary().drop(columns='distance')


def create_destinations(aoi: shapely.MultiPolygon, resolution: int = 10, max_waypoint_number: int = 50) -> pd.DataFrame:
    """
    This function creates a set of spurs (straight lines) through the hexgrid covering the aoi.
    These spurs cover all three directions in a hexagonal grid,
    and are the basis for routing to get the distances between all adjacent cells in the hexgrid.
    ## Parameters
    - :param:`aoi`: the `shapely.MultiPolygon` to be covered with spurs.
    - :param:`resolution`: h3 grid resolution to use. Default: `10`.
    - :param:`max_waypoint_number`: length of the admissible ors_directions request.
    Defines how long each resulting spur can be. Default: `50`.
    ## Return
    - :return:`batched_spurs`: `gpd.GeoDataFrame` containing `'id'` with h3 cell ids, and `'spur_id'` in order of adjacency
    """
    log.debug(f'Using h3pandas v{h3pandas.version} to get hexgrid for aoi.')  # need to use h3pandas import
    hexgrid = gpd.GeoDataFrame(geometry=[aoi], crs='EPSG:4326').h3.polyfill_resample(resolution).reset_index()

    log.debug('Creating Destinations')
    origin_id = hexgrid.loc[0, 'h3_polyfill']
    hexgrid['local_ij'] = hexgrid['h3_polyfill'].apply(lambda cell_id: h3.cell_to_local_ij(origin=origin_id, h=cell_id))
    hexgrid['local_i'] = hexgrid['local_ij'].apply(lambda ij: ij[0])
    hexgrid['local_j'] = hexgrid['local_ij'].apply(lambda ij: ij[1])

    # all i and j spurs start and end here
    min_ij = (hexgrid.local_i.min(), hexgrid.local_j.min())
    max_ij = (hexgrid.local_i.max(), hexgrid.local_j.max())

    current_ij_starting_point = min_ij
    # i_and_j_spurs = pd.DataFrame(data={'id': [], 'spur_id': [], 'ordinal': []})
    i_and_j_spurs: list[pd.DataFrame] = []
    while current_ij_starting_point[0] <= max_ij[0] or current_ij_starting_point[1] <= max_ij[1]:
        # all i spurs
        current_j = current_ij_starting_point[1]
        i_spurs = get_i_or_j_spurs(aoi, origin_id, min_ij, max_ij, current_value=current_j, current_direction='i')

        current_j += 1
        i_and_j_spurs.append(i_spurs)

        # all j spurs
        current_i = current_ij_starting_point[0]
        j_spurs = get_i_or_j_spurs(aoi, origin_id, min_ij, max_ij, current_value=current_i, current_direction='j')

        current_i += 1
        i_and_j_spurs.append(j_spurs)

        current_ij_starting_point = (current_i, current_j)

    ij_spurs = get_ij_spurs(aoi, hexgrid, origin_id, min_ij, max_ij)

    i_and_j_spurs.append(ij_spurs)
    all_spurs = pd.concat(i_and_j_spurs).reset_index(drop=True)

    filtered_spurs = batch_and_filter_spurs(all_spurs, max_waypoint_number=max_waypoint_number)

    log.debug(f'Created {filtered_spurs.shape[0]} batches of destinations')
    return filtered_spurs


def get_i_or_j_spurs(
    aoi: shapely.MultiPolygon,
    origin_id: str,
    min_ij: tuple[int, int],
    max_ij: tuple[int, int],
    current_value: int,
    current_direction: str,
) -> pd.DataFrame:
    """
    Gets an ordered line of cells in `i` or `j` direction, from the current coordinate value.
    ## Parameters
    - :param:`aoi`: area of interest for which the spur is created.
    - :param:`origin_id`: reference id for a common origin hexcell to reference the local coordinate system.
    - :param:`min_ij`: the minimum i and j values of hexcells in the aoi, with the origin of :param:`origin_id`.
    - :param:`max_ij`: the maximum i and j values of hexcells in the aoi, with the origin of :param:`origin_id`.
    - :param:`current_value` the current i or j value starting point. Either i or j, inverse of :param:`current_direction`.
    - :param:`current_direction`: either `'i'` or `'j'`. Gives the direction of spur to return.
    ## Returns
    - :return:`spur`: a pandas Dataframe with an ordered and numbered list of cells in the line.
    """
    match current_direction:
        case 'i':
            working_index = 0
            static_index = 1
        case 'j':
            working_index = 1
            static_index = 0
        case _:
            raise ValueError()

    ordered_line_of_cells: list[dict] = []

    current_cell_ij: list[int] = [0, 0]
    current_cell_ij[static_index] = current_value
    spur_number = 0
    ordinal = 0

    for i in range(min_ij[working_index], max_ij[working_index] + 1):
        current_cell_ij[working_index] = i
        current_cell_id: str = h3.local_ij_to_cell(origin=origin_id, i=current_cell_ij[0], j=current_cell_ij[1])

        if check_contains_cell(aoi, current_cell_id):
            current_cell = {
                'id': current_cell_id,
                'spur_id': f'{current_direction}:{current_value}:{spur_number}',
                'ordinal': ordinal,
            }
            ordered_line_of_cells.append(current_cell)
            ordinal += 1
        else:
            spur_number += 1
            ordinal = 0

    spur = pd.DataFrame.from_records(ordered_line_of_cells)
    return spur


def get_ij_spurs(
    aoi: shapely.MultiPolygon,
    hexgrid: gpd.GeoDataFrame,
    origin_id: str,
    min_ij: tuple[int, int],
    max_ij: tuple[int, int],
) -> pd.DataFrame:
    """
    Gets ordered lines of cells in `ij` direction, for the aoi.
    ## Parameters
    - :param:`aoi`: area of interest for which the spur is created.
    - :param:`hexgrid`: the `gpd.GeoDataFrame` containing the hexcells for the aoi
    - :param:`origin_id`: reference id for a common origin hexcell to reference the local coordinate system.
    - :param:`min_ij`: the minimum i and j values of hexcells in the aoi, with the origin of :param:`origin_id`.
    - :param:`max_ij`: the maximum i and j values of hexcells in the aoi, with the origin of :param:`origin_id`.
    ## Returns
    - :return:`ij_spurs`: a pandas.Dataframe with an ordered and numbered list of cells in line in ij direction.
    """

    min_i = min_ij[0]
    max_i = max_ij[0]
    max_j = max_ij[1]
    # starting_ij = h3.cell_to_local_ij(origin=origin_id, h=origin_id)

    tried_j_values: set[int] = set()
    spur_number = 0
    ordered_line_of_cells: list[dict] = []

    for i in range(min_i, max_i + 1):
        matching_js = hexgrid.loc[hexgrid['local_i'] == i, 'local_j'].sort_values()
        # This loop iterates through all available js at current i
        for matching_j in matching_js:
            if matching_j in tried_j_values:
                continue
            tried_j_values.add(matching_j)
            current_ij = np.array([i, matching_j])
            ordinal = 0
            # The following loop goes throug one spur
            while current_ij[0] <= max_i or current_ij[1] <= max_j:
                current_cell_id = h3.local_ij_to_cell(origin=origin_id, i=current_ij[0], j=current_ij[1])
                if check_contains_cell(aoi, current_cell_id):
                    current_cell = {'id': current_cell_id, 'spur_id': f'ij:{spur_number}', 'ordinal': ordinal}
                    ordered_line_of_cells.append(current_cell)
                    ordinal += 1
                else:
                    spur_number += 1
                    ordinal = 0

                current_ij += np.array([1, 1])
            spur_number += 1

    ij_spurs = pd.DataFrame.from_records(ordered_line_of_cells)
    return ij_spurs


def check_contains_cell(aoi: shapely.MultiPolygon, cell_id: str) -> bool:
    lat, lon = h3.cell_to_latlng(h=cell_id)
    return aoi.contains(shapely.Point(lon, lat))


def batch_and_filter_spurs(spurs: pd.DataFrame, max_waypoint_number: int = 50) -> pd.DataFrame:
    """
    Removes spurs with less than 2 members. And splits up spurs above length 50, packing them into batches.
    ## Parameters
    - :param:`spurs`: `pd.DataFrame` containing spurs with columns `'id'` containing hexcell ids,
    `'spur_id'` containing the id of a spur, and `'ordinal'` describing the order in the spur.
    - :param:`max_waypoint_number`: the maximum batch size for a single ors directions request.
    Determines the batch size for longer spurs.
    ## Returns
    - :return:`filtered_spurs`: `pd.DataFrame` with updated spurs
    """

    spur_lengths = spurs.groupby('spur_id').count()

    # Filter out short spurs
    short_spurs = spur_lengths[spur_lengths['id'] < 2]
    short_spur_ids: list[str] = short_spurs.index.to_list()
    sufficiently_long_spurs = spurs[~spurs['spur_id'].isin(short_spur_ids)]

    long_spurs = spur_lengths[spur_lengths['id'] > max_waypoint_number]

    if long_spurs.empty:
        return sufficiently_long_spurs.reset_index(drop=True)

    long_spur_ids: list[str] = long_spurs.index.to_list()
    sufficiently_short_spurs = sufficiently_long_spurs[~sufficiently_long_spurs['spur_id'].isin(long_spur_ids)]
    overlength_spurs = sufficiently_long_spurs[sufficiently_long_spurs['spur_id'].isin(long_spur_ids)]

    split_spurs: list[pd.DataFrame] = []
    for spur_id in long_spur_ids:
        old_spur = overlength_spurs[overlength_spurs['spur_id'] == spur_id]
        number_of_batches = int(np.ceil(len(old_spur) / (max_waypoint_number)))
        spur_segment_start = 0
        for i in range(number_of_batches):
            spur_segment_end = spur_segment_start + max_waypoint_number
            batch = old_spur[(spur_segment_start <= old_spur['ordinal']) & (old_spur['ordinal'] < spur_segment_end)]
            batch['spur_id'] = f'{batch["spur_id"].iloc[0]}:{i}'

            split_spurs.append(batch)
            spur_segment_start = spur_segment_end - 1

    modified_spurs = pd.concat(split_spurs)

    filtered_spurs = pd.concat([sufficiently_short_spurs, modified_spurs]).reset_index(drop=True)
    return filtered_spurs


def get_cell_distance(destinations: pd.DataFrame) -> float:
    """Return distance in meter between the center points of two adjacent cells."""
    first_spur_id = destinations.loc[0, 'spur_id']
    first_spur = destinations[destinations['spur_id'] == first_spur_id].set_index('id')
    first_spur_gdf = first_spur.h3.h3_to_geo().set_index('ordinal')
    first_spur_locations = first_spur_gdf.to_crs(first_spur_gdf.estimate_utm_crs())
    location_a: shapely.Point = first_spur_locations.loc[0, 'geometry']
    location_b: shapely.Point = first_spur_locations.loc[1, 'geometry']

    return location_a.distance(location_b)


def snap_destinations(
    destinations: pd.DataFrame, ors_settings: ORSSettings, snapping_radius: int = 150
) -> pd.DataFrame:
    """Snap to closest path in radius from center of cell."""
    log.debug('Setting up unique destinations')
    # sorted here serves no purpose other than to preserve the order for testing
    # TODO maybe fix mocking for the snapping response to keep order of set irrelevant here
    unique_destinations: pd.DataFrame = destinations.groupby('id').count()
    unique_destinations_gdf = unique_destinations.h3.h3_to_geo().drop(columns=['spur_id', 'ordinal'])

    batched_destinations = batching(
        series=unique_destinations_gdf.geometry, batch_size=ors_settings.snapping_request_size_limit
    )

    snapped_records = snap_batched_records(ors_settings, batched_destinations, snapping_radius=snapping_radius)
    log.debug(f'Snapped {len(snapped_records)} unique destinations')
    return snapped_records


def snap_batched_records(
    ors_settings: ORSSettings,
    batched_locations: list[gpd.GeoSeries],
    snapping_radius: int = 150,
) -> pd.DataFrame:
    log.debug('Snapping Destinations')
    # snapping unfortunately does not have a wrapper in openrouteservice-py
    headers = {
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Authorization': ors_settings.client._key,
        'Content-Type': 'application/json; charset=utf-8',
    }

    request_session = LimiterSession(per_minute=ors_settings.snapping_rate_limit)

    snapped_df_list = []
    for i, batch in enumerate(batched_locations):
        locations = [(x, y) for x, y in zip(batch.x, batch.y)]
        body = {'locations': locations, 'radius': snapping_radius}

        call = request_session.post(f'{ors_settings.client._base_url}/v2/snap/foot-walking', json=body, headers=headers)
        if call.status_code == 200:
            json_result = call.json()
        else:
            raise HTTPError(
                f'{ors_settings.client._base_url}/v2/snap/foot-walking responded wih error code {call.status_code}:{call.json}',
                response=call,
            )

        snapping_response = pd.Series(index=batch.index, data=json_result['locations'])
        snapped_response_extracted = snapping_response.apply(extract_ors_snapping_results)
        snapped_df = pd.DataFrame()
        snapped_df['snapping_results'] = snapped_response_extracted
        snapped_df['snapped_location'], snapped_df['snapped_distance'] = zip(*snapped_df.snapping_results)

        snapped_df_list.append(snapped_df)

    return pd.concat(snapped_df_list).drop(columns=['snapping_results'])


def extract_ors_snapping_results(result: None | dict) -> tuple[None, None] | tuple[list[float], float]:
    if result is None:
        return None, None
    else:
        return result['location'], result['snapped_distance']


def batching(series: gpd.GeoSeries, batch_size: int) -> list[gpd.GeoSeries]:
    num_batches = int(np.ceil(len(series) / batch_size))

    batches = []
    for i in range(num_batches):
        start = batch_size * i
        end = start + batch_size
        batches.append(series.iloc[start:end])
    return batches


def get_ors_walking_distances(
    ors_settings: ORSSettings, cell_distance: float, destinations_with_snapping: pd.DataFrame
) -> pd.DataFrame:
    """Route between destinations of adjacent cells using ORS."""
    log.debug('Requesting direction from the ors')
    sleep_time = 60 / ors_settings.directions_rate_limit
    spur_ids: set[str] = set(destinations_with_snapping['spur_id'].to_list())

    list_of_df: list[pd.DataFrame] = []
    for spur_id in spur_ids:
        spur = (
            destinations_with_snapping[destinations_with_snapping['spur_id'] == spur_id]
            .set_index('ordinal')
            .sort_index()
            .reset_index()
        )
        coordinates: list[float] = list(filter(lambda x: x is not None, spur['snapped_location'].to_list()))
        if len(coordinates) < 2:
            continue

        json_result = openrouteservice.directions.directions(
            client=ors_settings.client, coordinates=coordinates, profile='foot-walking', geometry=False
        )
        start = time.time()
        distances = [segment['distance'] for segment in json_result['routes'][0]['segments']]

        # TODO this matching actually breaks, whoopsie
        walking_distances = match_ors_distance_to_cells(spur, distances)

        list_of_df.append(walking_distances)

        time_remaining = sleep_time - (time.time() - start)
        if time_remaining > 0:
            time.sleep(time_remaining)

    cell_walking_distances = pd.concat(list_of_df)
    mean_walking_distances = cell_walking_distances.groupby('id').mean()
    mean_walking_distances['detour_factor'] = mean_walking_distances['distance'].apply(
        lambda distance: distance / cell_distance
    )
    log.debug('Calculated Detour Factors')
    return mean_walking_distances


def match_ors_distance_to_cells(spur: pd.DataFrame, distances: list[float]) -> pd.DataFrame:
    walking_distances = pd.DataFrame(columns=['id', 'distance'])
    waypoint_pairs = generate_waypoint_pairs(spur)
    spur_by_ordinal = spur.set_index('ordinal', drop=True)

    for index, distance in enumerate(distances):
        origin_ordinal = waypoint_pairs[index][0]
        destination_ordinal = waypoint_pairs[index][1]
        if origin_ordinal + 1 != destination_ordinal:
            # cells are not adjacent
            continue
        cell_id_origin = spur_by_ordinal.loc[origin_ordinal, 'id']
        cell_id_destination = spur_by_ordinal.loc[destination_ordinal, 'id']

        actual_distance = (
            distance
            + spur_by_ordinal.loc[origin_ordinal, 'snapped_distance']  # type: ignore
            + spur_by_ordinal.loc[destination_ordinal, 'snapped_distance']
        )  # type: ignore

        walking_distances.loc[len(walking_distances)] = [cell_id_origin, actual_distance]
        walking_distances.loc[len(walking_distances)] = [cell_id_destination, actual_distance]
    return walking_distances


def generate_waypoint_pairs(spur: pd.DataFrame) -> list[tuple[int, int]]:
    spur_without_na = spur[~spur['snapped_distance'].isna()]
    last_valid_ordinal: int = spur_without_na['ordinal'].min()

    waypoint_pairs: list[tuple[int, int]] = []

    for index, row in spur.iterrows():
        if row['ordinal'] <= last_valid_ordinal:
            continue
        if np.isnan(row.loc['snapped_distance']):
            continue

        waypoint_pairs.append((last_valid_ordinal, row.loc['ordinal']))
        last_valid_ordinal = row.loc['ordinal']

    return waypoint_pairs


def build_detour_factor_artifact(
    detour_factor_data: gpd.GeoDataFrame, resources: ComputationResources, cmap_name: str = 'YlOrRd'
) -> _Artifact:
    """Artifact containing a GeoJSON with hex-grid cells and the Detour Factor."""
    detour_factor_data_no_na = detour_factor_data.dropna()
    detour = detour_factor_data_no_na.detour_factor
    color = generate_colors(color_by=detour, cmap_name=cmap_name)
    legend = ContinuousLegendData(
        cmap_name=cmap_name, ticks={f'{round(detour.min(), ndigits=2)}': 0, f'{round(detour.max(), ndigits=2)}': 1}
    )

    return create_geojson_artifact(
        features=detour_factor_data_no_na.geometry,
        layer_name='Detour Factor',
        filename='hexgrid_detours',
        caption=Path('resources/components/network_analyses/detour_factor/caption.md').read_text(),
        description=Path('resources/components/network_analyses/detour_factor/description.md').read_text(),
        label=detour_factor_data_no_na.detour_factor.round(2).to_list(),
        color=color,
        legend_data=legend,
        resources=resources,
    )


def build_detour_summary_artifact(aoi_aggregate: Figure, resources: ComputationResources) -> _Artifact:
    return create_plotly_chart_artifact(
        figure=aoi_aggregate,
        title='Histogram of Detour Factors',
        caption='How are detour factor values distributed?',
        resources=resources,
        filename='aggregation_aoi_detour',
        primary=True,
    )
