import logging
import uuid
from enum import Enum, StrEnum
from typing import Dict, List, Optional, Set, Tuple

import geopandas as gpd
import matplotlib as mpl
import pandas as pd
import shapely
from climatoology.base.artifact import Attachments, ContinuousLegendData, Legend
from climatoology.base.baseoperator import ArtifactModality, _Artifact
from climatoology.base.computation import ComputationResources
from climatoology.utility.exception import ClimatoologyUserError
from numpy import number
from ohsome import OhsomeClient
from pydantic_extra_types.color import Color

log = logging.getLogger(__name__)


class PathCategory(Enum):
    DESIGNATED = 'Designated'
    DESIGNATED_SHARED_WITH_BIKES = 'Shared with bikes'
    SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED = 'Shared with cars up to 15 km/h'
    SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED = 'Shared with cars up to 30 km/h'
    SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED = 'Shared with cars up to 50 km/h'
    SHARED_WITH_MOTORIZED_TRAFFIC_VERY_HIGH_SPEED = 'Shared with cars above 50 km/h'
    SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED = 'Shared with cars of unknown speed'
    INACCESSIBLE = 'No access'
    UNKNOWN = 'Unknown'

    @classmethod
    def get_hidden(cls):
        return [cls.INACCESSIBLE]

    @classmethod
    def get_visible(cls):
        return [category for category in cls if category not in cls.get_hidden()]


PATH_RATING_MAP = {
    PathCategory.DESIGNATED: 1.0,
    PathCategory.DESIGNATED_SHARED_WITH_BIKES: 0.8,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED: 0.6,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED: 0.4,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED: 0.2,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_VERY_HIGH_SPEED: 0.0,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED: 0.0,
    PathCategory.UNKNOWN: None,
}


WALKABLE_CATEGORIES = {
    PathCategory.DESIGNATED,
    PathCategory.DESIGNATED_SHARED_WITH_BIKES,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED,
    PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED,
    PathCategory.UNKNOWN,
}


class PavementQuality(Enum):
    GOOD = 'good'
    POTENTIALLY_GOOD = 'potentially_good'
    MEDIOCRE = 'mediocre'
    POTENTIALLY_MEDIOCRE = 'potentially_mediocre'
    POOR = 'poor'
    UNKNOWN = 'unknown'


PAVEMENT_QUALITY_RATING_MAP = {
    PavementQuality.GOOD: 1.0,
    PavementQuality.POTENTIALLY_GOOD: 0.8,
    PavementQuality.MEDIOCRE: 0.5,
    PavementQuality.POTENTIALLY_MEDIOCRE: 0.3,
    PavementQuality.POOR: 0.0,
    PavementQuality.UNKNOWN: None,
}


class SmoothnessCategory(Enum):
    GOOD = 'good'
    MEDIOCRE = 'mediocre'
    POOR = 'poor'
    VERY_POOR = 'very_poor'
    UNKNOWN = 'unknown'


SMOOTHNESS_CATEGORY_RATING_MAP = {
    SmoothnessCategory.GOOD: 1.0,
    SmoothnessCategory.MEDIOCRE: 0.5,
    SmoothnessCategory.POOR: 0.2,
    SmoothnessCategory.VERY_POOR: 0.0,
    SmoothnessCategory.UNKNOWN: None,
}


class SurfaceType(Enum):
    CONTINUOUS_PAVEMENT = 'continuous_pavement'
    MODULAR_PAVEMENT = 'modular_pavement'
    COBBLESTONE = 'cobblestone'
    OTHER_PAVED = 'other_paved_surfaces'
    GRAVEL = 'gravel'
    GROUND = 'ground'
    OTHER_UNPAVED = 'other_unpaved_surfaces'
    UNKNOWN = 'unknown'


SURFACE_TYPE_RATING_MAP = {
    SurfaceType.CONTINUOUS_PAVEMENT: 1.0,
    SurfaceType.MODULAR_PAVEMENT: 0.85,
    SurfaceType.COBBLESTONE: 0.6,
    SurfaceType.OTHER_PAVED: 0.5,
    SurfaceType.GRAVEL: 0.4,
    SurfaceType.GROUND: 0.2,
    SurfaceType.OTHER_UNPAVED: 0.0,
    SurfaceType.UNKNOWN: None,
}


def fetch_osm_data(aoi: shapely.MultiPolygon, osm_filter: str, ohsome: OhsomeClient) -> gpd.GeoDataFrame:
    elements = ohsome.elements.geometry.post(
        bpolys=aoi, clipGeometry=True, properties='tags', filter=osm_filter
    ).as_dataframe()
    elements = elements.reset_index(drop=False)
    return elements[['@osmId', 'geometry', '@other_tags']]


def _dict_to_legend(d: dict, cmap_name: str = 'coolwarm_r') -> Dict[str, Color]:
    data = pd.DataFrame.from_records(data=list(d.items()), columns=['category', 'rating'])
    data['color'] = generate_colors(color_by=data.rating, cmap_name=cmap_name, min_value=0.0, max_value=1.0)
    data['category'] = data.category.apply(lambda cat: cat.value)
    return dict(zip(data['category'], data['color']))


def get_path_rating_legend() -> Dict[str, Color]:
    return _dict_to_legend(PATH_RATING_MAP, cmap_name='coolwarm_r')


def get_surface_quality_legend() -> Dict[str, Color]:
    return _dict_to_legend(PAVEMENT_QUALITY_RATING_MAP, cmap_name='coolwarm_r')


def get_smoothness_legend() -> Dict[str, Color]:
    return _dict_to_legend(SMOOTHNESS_CATEGORY_RATING_MAP, cmap_name='coolwarm_r')


def get_surface_type_legend() -> Dict[str, Color]:
    return _dict_to_legend(SURFACE_TYPE_RATING_MAP, cmap_name='tab10')


def generate_colors(
    color_by: pd.Series,
    cmap_name: str,
    min_value: number | None = None,
    max_value: number | None = None,
    bad_color='#808080',
) -> list[Color]:
    """
    Function to generate a list of colors based on a linear normalization for each element in `color_by`.
    ## Params
    :param:`color_by`: `pandas.Series` with numerical values to map colors to.
    :param:`cmap_name`: name of matplotlib colormap approved in climatoology.
    :param:`min`: optional minimal value of the normalization, numerical or `None`. If `None` minimum value of `color_by` is used.
    :param:`max`: optional maxmial value of the normalization, numerical or `None`. If `None` maximum value of `color_by` is used.
    ## Returns
    :return:`mapped_colors`: list of colors matching values of `color_by`
    """
    color_by = color_by.astype(float)

    norm = mpl.colors.Normalize(vmin=min_value, vmax=max_value)
    cmap = mpl.colormaps[cmap_name]
    cmap.set_bad(color=bad_color)
    cmap.set_over(color=bad_color)

    mapped_colors = [Color(mpl.colors.to_hex(col)) for col in cmap(norm(color_by))]
    return mapped_colors


def get_first_match(ordered_keys: List[str], tags: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    match_key = None
    match_value = None
    for key in ordered_keys:
        match_value = tags.get(key)
        if match_value:
            match_key = key
            break

    return match_key, match_value


def ohsome_filter(geometry_type: str) -> str:
    if geometry_type == 'relation':
        # currently unused, here as a blueprint if we want to query for relations
        return str(f'type:{geometry_type} and route=ferry')

    return str(
        f'geometry:{geometry_type} and '
        '(highway=* or route=ferry or railway=platform or '
        '(waterway=lock_gate and foot in (yes, designated, official, permissive))) and not '
        '(footway=separate or sidewalk=separate or sidewalk:both=separate or '
        '(sidewalk:right=separate and sidewalk:left=separate) or '
        '(sidewalk:right=separate and sidewalk:left=no) or (sidewalk:right=no and sidewalk:left=separate))'
    )


def safe_string_to_float(potential_number: str | float) -> float:
    try:
        return float(potential_number)
    except (TypeError, ValueError):
        return -1


def create_multicolumn_geojson_artifact(
    features: gpd.GeoSeries,
    layer_name: str,
    caption: str,
    color: List[Color],
    label: List[str],
    resources: ComputationResources,
    extra_columns: list[pd.Series] | None = None,
    primary: bool = True,
    legend_data: ContinuousLegendData | dict[str, Color] | None = None,
    description: str | None = None,
    tags: Set[StrEnum] | tuple = (),
    filename: str | uuid.UUID = uuid.uuid4(),
) -> _Artifact:
    """Create a vector data artifact.

    This will create a GeoJSON file holding all information required to plot a simple map layer.

    :param features: The Geodata. Must have a CRS set.
    :param color: Color of the features. Will be applied to surfaces, lines and points. Must be the same length as the
    features.
    :param label: Label of the features. Must be the same length as the features.
    :param layer_name: Name of the map layer.
    :param caption: A short description of the layer.
    :param description: A longer description of the layer.
    :param tags: Association tags this artifact belongs to.
    :param legend_data: Can be used to display a custom legend. For a continuous legend, use the ContinuousLegendData
    type. For a legend with distinct colors provide a dictionary mapping labels (str) to colors. If not provided, a
    distinct legend will be created from the unique combinations of labels and colors.
    :param resources: The computation resources of the plugin.
    :param extra_columns: List of extra columns in the output geojson.
    :param primary: Is this a primary artifact or does it exhibit additional or contextual information?
    :param filename: A filename for the created file (without extension!).
    :return: The artifact that contains a path-pointer to the created file.
    """
    file_path = resources.computation_dir / f'{filename}.geojson'
    assert not file_path.exists(), (
        'The target artifact data file already exists. Make sure to choose a unique filename.'
    )
    log.debug(f'Writing vector dataset {file_path}.')

    assert len(color) == features.size, 'The number of colors does not match the number of features.'
    color = [color.as_hex() for color in color]

    assert len(label) == features.size, 'The number of labels does not match the number of features.'

    if isinstance(features.index, pd.MultiIndex):
        # Format the index the same way a tuple index would be rendered in `to_file()`
        features.index = "('" + features.index.map("', '".join) + "')"

    output_data = {'color': color, 'label': label}

    if extra_columns is not None:
        for column in extra_columns:
            name = column.name
            assert len(column) == features.size, (
                f'The number of extra values in column {name} does not match the number of features.'
            )
            output_data.update({name: column})

    gdf = gpd.GeoDataFrame(output_data, index=features.index, geometry=features)
    gdf = gdf.to_crs(4326)
    gdf.geometry = shapely.set_precision(gdf.geometry, grid_size=0.0000001)

    gdf.to_file(
        file_path.absolute().as_posix(),
        index=True,
        driver='GeoJSON',
        engine='pyogrio',
        layer_options={'SIGNIFICANT_FIGURES': 7, 'RFC7946': 'YES', 'WRITE_NAME': 'NO'},
    )

    if not legend_data:
        legend_df = gdf.groupby(['color', 'label']).size().index.to_frame(index=False)
        legend_df = legend_df.set_index('label')
        legend_data = legend_df.to_dict()['color']

    result = _Artifact(
        name=layer_name,
        modality=ArtifactModality.MAP_LAYER_GEOJSON,
        file_path=file_path,
        summary=caption,
        description=description,
        tags=tags,
        primary=primary,
        attachments=Attachments(legend=Legend(legend_data=legend_data)),
    )

    log.debug(f'Returning Artifact: {result.model_dump()}.')

    return result


def check_paths_count_limit(aoi: shapely.MultiPolygon, ohsome: OhsomeClient, count_limit: int) -> None:
    """
    Check whether paths count is over than limit. (NOTE: just check path_lines)
    """

    ohsome_responses = ohsome.elements.count.post(bpolys=aoi, filter=ohsome_filter('line')).data
    path_lines_count = sum([response['value'] for response in ohsome_responses['result']])
    log.info(f'There are {path_lines_count} are selected.')
    if path_lines_count > count_limit:
        raise ClimatoologyUserError(
            f'There are too many path segments in the selected area: {path_lines_count} path segments. '
            f'Currently, only areas with a maximum of {count_limit} path segments are allowed. '
            f'Please select a smaller area or a sub-region of your selected area.'
        )
