import logging

import geopandas as gpd
import openrouteservice
import shapely.ops
from climatoology.base.baseoperator import BaseOperator, AoiProperties, _Artifact
from climatoology.base.computation import ComputationResources
from climatoology.base.info import _Info
from climatoology.utility.Naturalness import NaturalnessUtility
from climatoology.utility.exception import ClimatoologyUserError
from ohsome import OhsomeClient
from shapely import make_valid

from walkability.components.categorise_paths.path_categorisation import path_categorisation, subset_walkable_paths
from walkability.components.categorise_paths.path_categorisation_artifacts import build_path_categorisation_artifact
from walkability.components.categorise_paths.path_summarisation import (
    summarise_by_area,
    summarise_aoi,
    summarise_detour,
    summarise_naturalness,
    summarise_slope,
)
from walkability.components.naturalness.naturalness_analysis import naturalness_analysis
from walkability.components.naturalness.naturalness_artifacts import (
    build_naturalness_summary_bar_artifact,
)
from walkability.components.network_analyses.detour_analysis import (
    build_detour_summary_artifact,
    detour_factor_analysis,
)
from walkability.components.slope.slope_analysis import slope_analysis
from walkability.components.slope.slope_artifacts import (
    build_slope_summary_bar_artifact,
)
from walkability.components.utils.geometry import get_utm_zone, get_buffered_aoi
from walkability.components.utils.misc import (
    fetch_osm_data,
    ohsome_filter,
    WALKABLE_CATEGORIES,
)
from walkability.components.utils.ORSSettings import ORSSettings
from walkability.core.info import get_info
from walkability.core.input import ComputeInputWalkability, WalkabilityIndicators, WALKING_SPEED_MAP, WalkingSpeed

log = logging.getLogger(__name__)


class OperatorWalkability(BaseOperator[ComputeInputWalkability]):
    def __init__(
        self,
        naturalness_utility: NaturalnessUtility,
        ors_api_key: str,
        ors_snapping_rate_limit: int = 100,
        ors_snapping_request_size_limit: int = 4999,
        ors_directions_rate_limit: int = 40,
        ors_directions_waypoint_limit: int = 50,
        ors_base_url: str | None = None,
    ):
        super().__init__()
        self.naturalness_utility = naturalness_utility
        self.ohsome = OhsomeClient(user_agent='CA Plugin Walkability')

        if ors_base_url is None:
            ors_client = openrouteservice.Client(key=ors_api_key)
        else:
            ors_client = openrouteservice.Client(key=ors_api_key, base_url=ors_base_url)

        self.ors_settings = ORSSettings(
            client=ors_client,
            snapping_rate_limit=ors_snapping_rate_limit,
            snapping_request_size_limit=ors_snapping_request_size_limit,
            directions_rate_limit=ors_directions_rate_limit,
            directions_waypoint_limit=ors_directions_waypoint_limit,
        )
        self.admin_level = 1
        self.max_walking_distance = (1000 / 60) * WALKING_SPEED_MAP[WalkingSpeed.MEDIUM] * 15

        log.debug('Initialised walkability operator with ohsome client and Naturalness Utility')

    def info(self) -> _Info:
        return get_info()

    def compute(
        self,
        resources: ComputationResources,
        aoi: shapely.MultiPolygon,
        aoi_properties: AoiProperties,
        params: ComputeInputWalkability,
    ) -> list[_Artifact]:
        log.info(f'Handling compute request: {params.model_dump()} in context: {resources}')

        artifacts = []

        line_paths, line_paths_buffered, polygon_paths = self._get_paths(
            aoi=aoi, max_walking_distance=self.max_walking_distance
        )
        number_of_paths = len(line_paths)
        max_paths = 100000
        if number_of_paths > max_paths:
            raise ClimatoologyUserError(
                f'There are too many path segments in the selected area: {number_of_paths} path segments. Currently, only areas with a maximum of {max_paths} path segments are allowed. Please select a smaller area or a sub-region of your selected area'
            )

        with self.catch_exceptions(indicator_name='Sub-district areal summary charts', resources=resources):
            areal_summaries = dict()  # Empty dict in case summaries fail
            areal_summaries = summarise_by_area(
                paths=line_paths,
                aoi=aoi,
                admin_level=self.admin_level,
                projected_crs=get_utm_zone(aoi),
                ohsome_client=self.ohsome,
            )

            with self.catch_exceptions(
                indicator_name='Areal summary charts for Walkable Path Categories and Surface Quality',
                resources=resources,
            ):
                (
                    aoi_summary_category_stacked_bar,
                    aoi_summary_quality_stacked_bar,
                ) = summarise_aoi(paths=line_paths, projected_crs=get_utm_zone(aoi))

        path_artifacts = build_path_categorisation_artifact(
            paths_line=line_paths,
            paths_polygon=polygon_paths,
            areal_summaries=areal_summaries,
            aoi_summary_category_stacked_bar=aoi_summary_category_stacked_bar,
            aoi_summary_quality_stacked_bar=aoi_summary_quality_stacked_bar,
            walkable_categories=WALKABLE_CATEGORIES,
            resources=resources,
        )
        artifacts.extend(path_artifacts)

        line_paths, line_paths_buffered = subset_walkable_paths(
            line_paths,
            line_paths_buffered,
            walkable_categories=WALKABLE_CATEGORIES,
        )
        if line_paths.empty or line_paths_buffered.empty:
            return artifacts

        if WalkabilityIndicators.DETOURS in params.indicators_to_compute:
            with self.catch_exceptions(indicator_name='Detour Factors', resources=resources):
                detour_artifact, hexgrid_detour = detour_factor_analysis(
                    aoi=aoi,
                    ors_settings=self.ors_settings,
                    resources=resources,
                )
                detour_summary = summarise_detour(hexgrid=hexgrid_detour, projected_crs=get_utm_zone(aoi))
                detour_summary_artifact = build_detour_summary_artifact(
                    aoi_aggregate=detour_summary, resources=resources
                )
                artifacts.extend([detour_artifact, detour_summary_artifact])

        if WalkabilityIndicators.NATURALNESS in params.indicators_to_compute:
            with self.catch_exceptions(indicator_name='Naturalness', resources=resources):
                naturalness_artifact, line_paths_naturalness = naturalness_analysis(
                    line_paths=line_paths,
                    polygon_paths=polygon_paths,
                    index=params.naturalness_index,
                    resources=resources,
                    naturalness_utility=self.naturalness_utility,
                )
                naturalness_summary_bar = summarise_naturalness(
                    paths=line_paths_naturalness, projected_crs=get_utm_zone(aoi)
                )
                naturalness_summary_bar_artifact = build_naturalness_summary_bar_artifact(
                    aoi_aggregate=naturalness_summary_bar, resources=resources
                )
                artifacts.extend([naturalness_artifact, naturalness_summary_bar_artifact])

        if WalkabilityIndicators.SLOPE in params.indicators_to_compute:
            with self.catch_exceptions(indicator_name='Slope', resources=resources):
                slope_artifact, line_paths_slope = slope_analysis(
                    line_paths=line_paths, aoi=aoi, ors_client=self.ors_settings.client, resources=resources
                )
                slope_summary_bar = summarise_slope(paths=line_paths_slope, projected_crs=get_utm_zone(aoi))
                slope_summary_bar_artifact = build_slope_summary_bar_artifact(
                    aoi_aggregate=slope_summary_bar, resources=resources
                )
                artifacts.extend([slope_artifact, slope_summary_bar_artifact])

        return artifacts

    def _get_paths(
        self, aoi: shapely.MultiPolygon, max_walking_distance: float
    ) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
        aoi_buffered = get_buffered_aoi(aoi, max_walking_distance)

        log.debug('Extracting paths')
        line_paths_buffered = fetch_osm_data(aoi_buffered, ohsome_filter('line'), self.ohsome)
        polygon_paths = fetch_osm_data(aoi, ohsome_filter('polygon'), self.ohsome)

        invalid_line = ~line_paths_buffered.is_valid
        line_paths_buffered.loc[invalid_line, 'geometry'] = line_paths_buffered.loc[invalid_line, 'geometry'].apply(
            make_valid
        )
        invalid_polygon = ~polygon_paths.is_valid
        polygon_paths.loc[invalid_polygon, 'geometry'] = polygon_paths.loc[invalid_polygon, 'geometry'].apply(
            make_valid
        )
        log.debug('Finished extracting paths')

        line_paths_buffered, polygon_paths = path_categorisation(
            paths_line=line_paths_buffered, paths_polygon=polygon_paths
        )

        line_paths = gpd.clip(line_paths_buffered, aoi, keep_geom_type=True).explode(ignore_index=True)

        return line_paths, line_paths_buffered, polygon_paths
