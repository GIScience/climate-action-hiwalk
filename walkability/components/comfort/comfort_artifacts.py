import logging

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import shapely
from climatoology.base.artifact_creators import (
    Artifact,
    ArtifactMetadata,
    Legend,
    create_plotly_chart_artifact,
    create_vector_artifact,
)
from climatoology.base.computation import ComputationResources
from mobility_tools.settings import ORSSettings
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color

from walkability.components.comfort.comfort_poi_filters import PointsOfInterest, distance_enrich_paths, request_pois
from walkability.components.utils.geometry import CAN_DEFAULT_CRS, get_buffered_aoi, get_utm_zone
from walkability.components.utils.misc import Topics, generate_colors

log = logging.getLogger(__name__)
N_BINS = 5


def compute_comfort_artifacts(
    paths: gpd.GeoDataFrame,
    aoi: shapely.MultiPolygon,
    max_walking_distance_map: dict[PointsOfInterest, float],
    ohsome_client: OhsomeClient,
    ors_settings: ORSSettings,
    resources: ComputationResources,
) -> list[Artifact]:
    artifacts = []
    comfort_summary = pd.DataFrame()
    for poi_type in [
        PointsOfInterest.DRINKING_WATER,
        PointsOfInterest.SEATING,
        PointsOfInterest.PUBLIC_TOILET,
    ]:
        log.debug(f'Computing Comfort for {poi_type}')
        max_walking_distance = max_walking_distance_map[poi_type]
        bin_size = int(max_walking_distance / N_BINS)
        bins = [x for x in range(bin_size, int(max_walking_distance) + 1, bin_size)]
        max_walking_distance = max(bins)

        buffered_aoi = get_buffered_aoi(aoi, max_walking_distance)
        enriched_paths = distance_enrich_paths(
            paths=paths,
            aoi=buffered_aoi,
            poi_type=poi_type,
            bins=bins,
            ohsome_client=ohsome_client,
            ors_settings=ors_settings,
        )
        enriched_paths = enriched_paths.clip(aoi)

        cleaned_data = clean_data(
            data=enriched_paths,
            max_walking_distance=max_walking_distance,
            min_value=min(bins),
            poi_type=poi_type,
        )

        if poi_type == PointsOfInterest.SEATING:
            sheltered_benches = request_pois(
                aoi=buffered_aoi,
                poi=PointsOfInterest.SHELTERED_BENCH,
                ohsome_client=ohsome_client,
            )

            sheltered_benches = sheltered_benches.clip(aoi)
            sheltered_benches['value'] = 0
            sheltered_benches['poi_type'] = PointsOfInterest.SHELTERED_BENCH.value
            sheltered_benches['label'] = PointsOfInterest.SHELTERED_BENCH.value
            sheltered_benches['color'] = Color('brown')

            bench_intersections = gpd.sjoin(cleaned_data, sheltered_benches, how='left', predicate='intersects')
            cleaned_data = cleaned_data.loc[bench_intersections['index_right'].isna()].copy()

            cleaned_data = pd.concat(
                [cleaned_data, sheltered_benches],
                ignore_index=True,
            )
            cleaned_data['label'] = cleaned_data['label'].replace({'benches': 'unsheltered benches'})

            bench_chart_artifact = build_benches_chart_artifact(benches_data=cleaned_data, resources=resources)
            artifacts.append(bench_chart_artifact)

        isodistance_artifact = build_isodistance_artifact(
            resources=resources,
            cleaned_data=cleaned_data,
            poi_type=poi_type,
            max_isochrone_request=ors_settings.ors_isochrone_max_request_number,
        )
        artifacts.append(isodistance_artifact)
        comfort_summary = pd.concat(
            [comfort_summary, cleaned_data],
            ignore_index=True,
        )
        comfort_summary = comfort_summary[comfort_summary.geom_type.isin(['Point'])]
    comfort_chart_artifact = build_comfort_chart_artifact(
        aoi=aoi,
        comfort_summary=comfort_summary,
        resources=resources,
    )
    artifacts.append(comfort_chart_artifact)
    return artifacts


def build_isodistance_artifact(
    # TODO write test for this function
    resources: ComputationResources,
    cleaned_data: gpd.GeoDataFrame,
    poi_type: PointsOfInterest,
    max_isochrone_request: int,
) -> Artifact:
    log.debug('Building isodistance artifact')

    legend = {}
    unique_labels = cleaned_data.sort_values('value').label.unique()
    for label in unique_labels:
        legend_color = cleaned_data.loc[cleaned_data['label'] == label, 'color'].mode().loc[0]
        legend.update({label: legend_color})

    if poi_type == PointsOfInterest.SEATING:
        isodistance_artifact = create_vector_artifact(
            data=cleaned_data,
            metadata=ArtifactMetadata(
                name=f'Distance to {poi_type.value.title()}',
                summary=f'How far is it to {poi_type.value.capitalize()}?',
                description=f'If there are fewer than {max_isochrone_request} {poi_type.value.title()} in the area of interest, '
                f'actual walking distances are computed. Otherwise, straight line distances are used.\n\n'
                f'This map includes both sheltered and unsheltered benches.\n\n'
                f'Benches: We define benches as seating locations explicitly tagged as benches, '
                f'as well as public facilities such as transport platforms, picnic tables, and picnic sites '
                f'that do not explicitly exclude the presence of benches.\n\n'
                f'Sheltered benches: Sheltered benches are benches from the categories defined above '
                f'that also provide some form of overhead shelter or cover. A bench is considered sheltered '
                f'when it includes either the tag covered=yes or shelter=yes, or when it is located inside '
                f'a shelter facility tagged with amenity=shelter.\n\n'
                f'Unsheltered benches: All benches that do not meet the sheltered-bench criteria '
                f'are classified as unsheltered benches.\n\n',
                filename=f'isodistance_{poi_type.value.replace(" ", "_")}',
                tags={Topics.COMFORT},
            ),
            resources=resources,
            legend=Legend(
                legend_data=legend,
            ),
        )
    else:
        isodistance_artifact = create_vector_artifact(
            data=cleaned_data,
            metadata=ArtifactMetadata(
                name=f'Distance to {poi_type.value.title()}',
                summary=f'How far is it to {poi_type.value.capitalize()}?',
                description=f'If there are fewer than {max_isochrone_request} {poi_type.value.title()} in the area of interest, '
                f'actual walking distances are computed. Otherwise, straight line distances are used.',
                filename=f'isodistance_{poi_type.value.replace(" ", "_")}',
                tags={Topics.COMFORT},
            ),
            resources=resources,
            legend=Legend(
                legend_data=legend,
            ),
        )
    return isodistance_artifact


def build_comfort_chart_artifact(
    aoi: shapely.MultiPolygon,
    comfort_summary: gpd.GeoDataFrame,
    resources: ComputationResources,
) -> Artifact:
    summary = pd.DataFrame(
        {
            'poi_type': ['sheltered benches', 'drinking water locations', 'public toilets'],
            'count': [
                len(comfort_summary[comfort_summary['label'] == 'sheltered benches']),
                len(comfort_summary[comfort_summary['label'] == 'drinking water locations']),
                len(comfort_summary[comfort_summary['label'] == 'public toilets']),
            ],
        }
    )
    aoi_crs = get_utm_zone(aoi)
    aoi_projected = gpd.GeoSeries(data=aoi, crs=CAN_DEFAULT_CRS).to_crs(aoi_crs)
    summary['density'] = summary['count'] / (aoi_projected[0].area / 1000000)
    comfort_chart = create_comfort_chart_plot(summary=summary)

    comfort_chart_metadata = ArtifactMetadata(
        name='Density of Public Comfort Infrastructure',
        summary='How well-equipped is my area with public comfort infrastructure?',
        tags={Topics.COMFORT},
        primary=False,
    )
    comfort_chart = create_plotly_chart_artifact(
        figure=comfort_chart,
        metadata=comfort_chart_metadata,
        resources=resources,
    )
    return comfort_chart


def build_benches_chart_artifact(benches_data: gpd.GeoDataFrame, resources: ComputationResources) -> Artifact:
    unsheltered_count = len(benches_data[benches_data['label'] == 'unsheltered benches'])
    sheltered_count = len(benches_data[benches_data['label'] == 'sheltered benches'])

    summary = pd.DataFrame(
        {
            'bench_type': [
                'Unsheltered',
                'Sheltered',
            ],
            'count': [
                unsheltered_count,
                sheltered_count,
            ],
        }
    )
    summary['percent'] = summary['count'] / summary['count'].sum() * 100
    summary = summary.set_index('bench_type')
    bench_chart = create_bench_chart_plot(summary=summary)

    bench_chart_metadata = ArtifactMetadata(
        name='Share of Sheltered Benches',
        summary='How many benches are sheltered?',
        tags={Topics.COMFORT},
        primary=False,
    )
    bench_chart = create_plotly_chart_artifact(
        figure=bench_chart,
        metadata=bench_chart_metadata,
        resources=resources,
    )
    return bench_chart


def clean_data(
    data: gpd.GeoDataFrame, max_walking_distance: float, min_value: float, poi_type: PointsOfInterest
) -> gpd.GeoDataFrame:
    data = data[['value', 'geometry']]
    data['label'] = data.apply(assign_label, poi_type=poi_type, max_walking_distance=max_walking_distance, axis=1)

    data = assign_color(data, max_walking_distance=max_walking_distance, min_value=min_value, poi_type=poi_type)

    return data


def assign_color(
    data: gpd.GeoDataFrame, max_walking_distance: float, min_value: float, poi_type: PointsOfInterest
) -> gpd.GeoDataFrame:
    data['color'] = generate_colors(
        data.value, 'coolwarm', min_value, max_value=max_walking_distance, bad_color=Color('red').as_hex()
    )
    match poi_type:
        case PointsOfInterest.SEATING:
            point_color = Color('grey')
        case PointsOfInterest.DRINKING_WATER:
            point_color = Color('darkblue')
        case PointsOfInterest.PUBLIC_TOILET:
            point_color = Color('purple')
        case _:
            raise NotImplementedError('POI not supported by coloring function')
    data.loc[data.geom_type == 'Point', 'color'] = point_color

    return data


def assign_label(row: pd.Series, poi_type: PointsOfInterest, max_walking_distance: float) -> str:
    match row.geometry.geom_type:
        case 'Point':
            return poi_type.value
        case _:
            return f'> {int(max_walking_distance)}m' if np.isnan(row['value']) else f'< {int(row["value"])}m'


def create_bench_chart_plot(summary: pd.DataFrame) -> go.Figure:
    colors = ['grey', 'brown']

    data = go.Figure()
    for i, (category, row) in enumerate(summary.iterrows()):
        data.add_trace(
            go.Bar(
                x=[row['percent']],
                name=category,
                orientation='h',
                marker_color=colors[i],
                hovertemplate=f'{category}: {int(row["count"])} ({row["percent"]:.1f}%)<extra></extra>',
                showlegend=True,
                legendrank=len(summary) - i,
            )
        )
        data.update_layout(
            barmode='stack',
            height=300,
            margin=dict(t=30, b=80, l=30, r=30),
            xaxis_title=f'Percentage of unsheltered and sheltered benches. {summary["count"].iloc[1]} out of {summary["count"].sum()} benches are sheltered.',
            yaxis=dict(showticklabels=False),
            legend=dict(
                orientation='h',
                yanchor='top',
                y=-1,
                xanchor='center',
                x=0.45,
                font=dict(size=12),
            ),
        )

    return data


def create_comfort_chart_plot(summary: pd.DataFrame) -> go.Figure:
    colors = ['brown', 'darkblue', 'purple']
    data = go.Figure()
    for i, row in summary.iterrows():
        data.add_trace(
            go.Bar(
                x=[row['poi_type'].capitalize()],
                y=[row['density']],
                name=row['poi_type'],
                marker_color=colors[i],
                hovertemplate=f'Number of {row["poi_type"]}: {int(row["count"])} ({row["density"]:.2f} {row["poi_type"]} per km²)<extra></extra>',
            )
        )
        data.update_layout(
            margin=dict(t=30, b=80, l=30, r=30),
            yaxis_title='Facilities per km²',
            xaxis_title=f'In this area, there are {summary["count"].iloc[0]} sheltered benches, {summary["count"].iloc[1]} drinking water locations, and '
            f'{summary["count"].iloc[2]} public toilets.',
            yaxis=dict(),
            showlegend=False,
        )
    return data
