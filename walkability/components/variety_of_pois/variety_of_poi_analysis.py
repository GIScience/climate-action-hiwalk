import logging
from pathlib import Path

import geopandas as gpd
import h3
import matplotlib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import shapely
from climatoology.base.artifact import Artifact, ArtifactMetadata, ContinuousLegendData, Legend
from climatoology.base.artifact_creators import create_plotly_chart_artifact, create_vector_artifact
from climatoology.base.computation import AoiProperties, ComputationResources
from climatoology.base.exception import ClimatoologyUserError
from ohsome_py2.client import OhsomeClient
from shapely.geometry import shape

from walkability.components.utils.misc import Topics, generate_colors
from walkability.components.variety_of_pois.variety_poi_filters import POI_CATEGORIES

log = logging.getLogger(__name__)


def variety_of_pois_analysis(
    aoi: shapely.MultiPolygon,
    aoi_properties: AoiProperties,
    ohsome_client: OhsomeClient,
    resources: ComputationResources,
) -> list[Artifact]:
    """
    Wrapper function for variety of POIs indicator

    :param aoi: Computation area
    :param aoi_properties: Name and unique identifier of the computation area
    :param ohsome_client: Client for querying OSM data via the ohsome API
    :param resources: Computation resources
    :return: List of variety of POIs artifacts
    """
    variety_of_pois = get_variety_of_pois(aoi=aoi, ohsome=ohsome_client)
    summary = summarise_hexgrid(hexgrid=variety_of_pois)
    number_of_pois_artifact = build_number_of_pois_artifact(data=variety_of_pois, resources=resources)
    number_of_categories_artifact = build_number_of_categories_artifact(data=variety_of_pois, resources=resources)

    number_of_pois_summary_chart = create_poi_summary_chart(summary=summary)
    evenness = calculate_evenness(summary=summary)
    variety_of_pois_summary_artifact = build_variety_of_pois_summary_artifact(
        fig=number_of_pois_summary_chart, evenness=evenness, aoi_properties=aoi_properties, resources=resources
    )

    return [number_of_pois_artifact, number_of_categories_artifact, variety_of_pois_summary_artifact]


def get_variety_of_pois(aoi: shapely.MultiPolygon, ohsome: OhsomeClient) -> gpd.GeoDataFrame:
    """
    Query POIs from ohsome, join them to the hexgrid, and calculate summary statistics

    :param aoi: computation area
    :param ohsome: client for querying OSM data via the ohsome API
    :return: Hexgrid with number of POIs per category, total number of POIs, and number of categories present
    """
    hexgrid = get_hex_grids(aoi=aoi)
    hexgrid_boundary = hexgrid.union_all()
    for poi_category in POI_CATEGORIES:
        column_name = f'number_of_pois_{poi_category.type}'
        pois = ohsome.features_extraction(aoi=hexgrid_boundary, osm_filter=poi_category.ohsome_filter, centroid=True)
        if pois.empty:
            hexgrid[column_name] = 0
            continue
        join_result = gpd.sjoin(hexgrid, pois, predicate='intersects', how='left')
        counts = join_result.groupby('hex_id')['osm_id'].count()
        hexgrid[column_name] = hexgrid['hex_id'].map(counts).fillna(0)

    poi_columns = [f'number_of_pois_{poi_category.type}' for poi_category in POI_CATEGORIES]
    hexgrid['total_number_of_pois'] = hexgrid[poi_columns].sum(axis=1)
    hexgrid['number_of_categories'] = (hexgrid[poi_columns] > 0).sum(axis=1)
    return hexgrid


def summarise_hexgrid(hexgrid: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Calculate total number of POIs per category in the entire AOI

    :param hexgrid: Hexgrid with number of POIs per category, total number of POIs, and number of categories present
    :return: pd.DataFrame with total number of POIs per category in the entire AOI
    """
    poi_columns = [f'number_of_pois_{poi_category.type}' for poi_category in POI_CATEGORIES]
    summary = pd.DataFrame(
        {'poi_category': (poi_type.type for poi_type in POI_CATEGORIES), 'poi_sum': hexgrid[poi_columns].sum().values}
    )
    return summary


def get_hex_grids(aoi: shapely.MultiPolygon, hex_resolution: int = 9) -> gpd.GeoDataFrame:
    """
    Get hexgrid in the AOI

    :param aoi: computation area
    :param hex_resolution: Resolution of the output cells of the hexgrid
    :return: Hexgrid as gpd.GeoDataFrame
    """
    city_polygon_h3 = h3.geo_to_h3shape(aoi)
    log.debug('Getting hexgrids')
    hexagons = h3.h3shape_to_cells(city_polygon_h3, res=hex_resolution)

    if len(hexagons) == 0:
        log.error(
            f'No hexagons generated for the city polygon at resolution {hex_resolution}. Consider using a lower resolution.'
        )
        raise ClimatoologyUserError('The area could not be segmented into smaller areas. Try a bigger area.')

    features = []
    for hex_id in hexagons:
        features.append(
            {
                'geometry': shape(h3.cells_to_geo([hex_id])),
                'hex_id': hex_id,
            }
        )

    hexagon_features = gpd.GeoDataFrame(features, geometry='geometry', crs=4326)

    return hexagon_features


def calculate_evenness(summary: pd.DataFrame) -> dict[str, float | int]:
    """
    Calculate evenness of POI distribution across the categories
    Evenness = H' / log(N)
    where H' is the Shannon diversity index and N is the number of categories.

    :param summary: pd.DataFrame with total number of POIs per category in the entire AOI
    :return: Dict with evenness, number of categories with 0 POIs, and total number of categories
    """
    num_zero_categories = len(summary[summary['poi_sum'] == 0])

    nonzero_summary = summary[summary['poi_sum'] > 0]
    num_nonzero_categories = len(nonzero_summary)

    if num_nonzero_categories <= 1:
        evenness = 0.0  # Evenness is undefined for 0 or 1 category, return 0
    else:
        proportions = nonzero_summary['poi_sum'] / nonzero_summary['poi_sum'].sum()
        h_shannon = -np.sum(proportions * np.log(proportions))
        evenness = h_shannon / np.log(num_nonzero_categories)

    return {
        'evenness': evenness,
        'num_zero_categories': num_zero_categories,
        'num_categories': num_nonzero_categories + num_zero_categories,
    }


def create_poi_summary_chart(summary: pd.DataFrame) -> go.Figure:
    """
    :param summary: pd.DataFrame with total number of POIs per category in the entire AOI
    :return: Bar chart showing total number of POIs per category in the entire AOI
    """
    fig = go.Figure(data=[go.Bar(x=summary['poi_category'], y=summary['poi_sum'], marker_color='#808080')])
    return fig


def build_number_of_pois_artifact(
    data: gpd.GeoDataFrame, resources: ComputationResources, cmap_name: str = 'coolwarm_r', min_val=0, max_val=50
) -> Artifact:
    """
    Build map artifact showing the total number of POIs per grid cell

    :param data: Hexgrid with number of POIs per category, total number of POIs, and number of categories present
    :param resources: Computation resources
    :param cmap_name: Colormap for the hexgrid, the default is red - light grey - blue
    :param min_val: Minimum number of POIs for the legend, the default is 0
    :param max_val: Maximum number of POIs for the legend, the default is 50
    :return: Map artifact showing the total number of POIs per grid cell
    """
    cmap = matplotlib.colormaps.get(cmap_name)
    cmap.set_under('#808080')
    data['color'] = generate_colors(
        color_by=data['total_number_of_pois'], cmap_name=cmap_name, min_value=min_val, max_value=max_val
    )
    legend = ContinuousLegendData(
        cmap_name=cmap_name,
        ticks={str(min_val): 0.0, f'>={max_val}': 1.0},
    )
    data['label'] = data['total_number_of_pois'].astype(str)
    return create_vector_artifact(
        data=data,
        metadata=ArtifactMetadata(
            name='Number of POIs',
            filename='hexgrid_number_of_pois',
            description=Path('resources/components/variety_of_pois/number_of_pois_description.md').read_text(),
            summary='How many points of interest are in my neighbourhood?',
            primary=False,
            tags={Topics.ATTRACTIVENESS},
        ),
        resources=resources,
        legend=Legend(legend_data=legend),
    )


def build_number_of_categories_artifact(
    data: gpd.GeoDataFrame, resources: ComputationResources, cmap_name: str = 'coolwarm_r'
) -> Artifact:
    """
    Build map artifact showing the number of POI categories present in each grid cell

    :param data: Hexgrid with number of POIs per category, total number of POIs, and number of categories present
    :param resources: Computation resources
    :param cmap_name: Colormap for the hexgrid, the default is red - light grey - blue
    :return: Map artifact showing the number of POI categories present in each grid cell
    """
    data['color'] = generate_colors(
        color_by=data['number_of_categories'], cmap_name=cmap_name, min_value=0, max_value=len(POI_CATEGORIES)
    )
    data['label'] = data['number_of_categories'].astype(str)
    return create_vector_artifact(
        data=data,
        metadata=ArtifactMetadata(
            name='Number of POI Categories',
            filename='hexgrid_number_of_categories',
            description=Path(
                'resources/components/variety_of_pois/number_of_poi_categories_description.md'
            ).read_text(),
            summary='Of how many categories are there points of interest in my neighbourhood?',
            primary=False,
            tags={Topics.ATTRACTIVENESS},
        ),
        resources=resources,
    )


def build_variety_of_pois_summary_artifact(
    fig: go.Figure, evenness: dict[str, float | int], aoi_properties: AoiProperties, resources: ComputationResources
) -> Artifact:
    """
    Build chart artifact showing the total number of POIs per category in the entire AOI

    :param fig: Bar chart showing total number of POIs per category in the entire AOI
    :param evenness: Dict with evenness, number of categories with 0 POIs, and total number of categories
    :param aoi_properties: Name and unique identifier of the computation area
    :param resources: Computation resources
    :return: Chart artifact showing the total number of POIs per category in the entire AOI
    """
    summary_chart_metadata = ArtifactMetadata(
        name='Number of POIs by Category',
        summary=f'How many POIs per category are in {aoi_properties.name}? '
        f'The relative diversity index for {aoi_properties.name} is {round(evenness["evenness"], 2)}. '
        'View the detailed description for details on the relative diversity index.',
        description=f'Relative diversity index for {aoi_properties.name} = {round(evenness["evenness"], 2)} '
        f'(with {evenness["num_zero_categories"]} / {evenness["num_categories"]} categories having 0 POIs).\n\nThe '
        'relative diversity index (Peet 1975) shows how evenly the POIs are distributed across the categories. It '
        'has a range from 0 to 1 with values close to 0 representing a very uneven distribution and values close to 1 '
        'representing a very even distribution (i.e. all POI categories have the same number of POIs). Categories with '
        '0 POIs are excluded from the calculation of the relative diversity index.',
        tags={Topics.ATTRACTIVENESS},
        primary=False,
    )
    return create_plotly_chart_artifact(
        figure=fig,
        metadata=summary_chart_metadata,
        resources=resources,
    )
