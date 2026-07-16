import logging
import os

import boto3
import geopandas as gpd
import shapely.ops
from botocore import UNSIGNED
from botocore.config import Config
from climatoology.base.baseoperator import AoiProperties, Artifact, BaseOperator
from climatoology.base.computation import ComputationResources
from climatoology.base.exception import ClimatoologyUserError
from climatoology.base.plugin_info import PluginInfo
from climatoology.utility.naturalness import NaturalnessIndex, NaturalnessUtility
from mobility_tools.settings import ORSSettings, S3Settings
from ohsome import OhsomeClient
from pydantic import BaseModel
from pydantic_extra_types.language_code import LanguageAlpha2

from walkability.components.categorise_paths.path_categorisation import path_categorisation, subset_walkable_paths
from walkability.components.categorise_paths.path_categorisation_artifacts import build_path_categorisation_artifact
from walkability.components.categorise_paths.path_summarisation import summarise_aoi, summarise_by_area
from walkability.components.comfort.comfort_artifacts import compute_comfort_artifacts
from walkability.components.comfort.comfort_poi_filters import PointsOfInterest
from walkability.components.naturalness.naturalness_analysis import naturalness_analysis
from walkability.components.network_analyses.detour_analysis import detour_factor_analysis
from walkability.components.path_lighting.path_lighting_analysis import path_lighting_analysis
from walkability.components.shade.shade_analysis import shade_analysis
from walkability.components.shade.utility.config import S3ShadeConfig
from walkability.components.shade.utility.download import download_tile_spec
from walkability.components.slope.slope_analysis import compute_slope_analysis
from walkability.components.utils.geometry import get_utm_zone
from walkability.components.utils.misc import (
    WALKABLE_CATEGORIES,
    check_paths_count_limit,
    fetch_osm_data,
    ohsome_filter,
)
from walkability.core.info import get_info
from walkability.core.input import ComputeInputWalkability, WalkabilityIndicators

log = logging.getLogger(__name__)


class OperatorWalkability(BaseOperator[ComputeInputWalkability]):
    def __init__(
        self,
        naturalness_utility: NaturalnessUtility,
        ors_settings: ORSSettings,
        s3_settings: S3Settings,
        shade_config: S3ShadeConfig,
        max_path_limit: int,
    ):
        super().__init__()
        self.naturalness_utility = naturalness_utility
        self.ohsome = OhsomeClient(user_agent='CA Plugin Walkability')

        self.shade_config = shade_config
        if not shade_config.cache_dir.exists():
            os.makedirs(shade_config.cache_dir)

        self.shade_client = boto3.client(
            's3', config=Config(user_agent='climate-action-navigator_walkability', signature_version=UNSIGNED)
        )
        self.shade_tiles = download_tile_spec(
            shade_config=shade_config, shade_client=self.shade_client, download_dir=shade_config.cache_dir
        )

        self.ors_settings = ors_settings
        self.s3_settings = s3_settings
        self.admin_level = 1

        max_walking_distance_map = {
            PointsOfInterest.DRINKING_WATER: 200,
            PointsOfInterest.SEATING: 200,
            PointsOfInterest.REMAINDER: 1000,
            PointsOfInterest.PUBLIC_TOILET: 500,
            PointsOfInterest.SHELTERED_BENCH: 200,
        }
        self.max_walking_distance_map = {k: round(v, -1) for k, v in max_walking_distance_map.items()}

        log.debug('Initialised walkability operator with ohsome client and Naturalness Utility')

        self.max_path_limit = max_path_limit

    def info(self) -> PluginInfo:
        return get_info()

    def compute(  # dead: disable
        self,
        *,
        resources: ComputationResources,
        aoi: shapely.MultiPolygon,
        aoi_properties: AoiProperties,
        params: ComputeInputWalkability | BaseModel,
        language: LanguageAlpha2 | None = None,
        **kwargs,
    ) -> list[Artifact]:
        log.info(f'Handling compute request: {params.model_dump()} in context: {resources}')

        artifacts = []

        if self.max_path_limit > 0:
            check_paths_count_limit(aoi=aoi, ohsome=self.ohsome, count_limit=self.max_path_limit)

        line_paths, polygon_paths = self._get_paths(aoi=aoi)

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

        line_paths = subset_walkable_paths(
            line_paths,
            walkable_categories=WALKABLE_CATEGORIES,
        )
        line_paths = next(line_paths)
        if line_paths.empty:
            return artifacts

        if WalkabilityIndicators.DETOURS in params.optional_indicators:
            with self.catch_exceptions(indicator_name='Detour Factors', resources=resources):
                detour_artifacts = detour_factor_analysis(
                    aoi=aoi,
                    paths=line_paths,
                    ors_settings=self.ors_settings,
                    resources=resources,
                )

                artifacts.extend(detour_artifacts)

        if WalkabilityIndicators.NATURALNESS in params.optional_indicators:
            with self.catch_exceptions(indicator_name='Greenness', resources=resources):
                naturalness_artifacts = naturalness_analysis(
                    line_paths=line_paths,
                    polygon_paths=polygon_paths,
                    index=NaturalnessIndex.NDVI,
                    resources=resources,
                    naturalness_utility=self.naturalness_utility,
                )

                artifacts.extend(naturalness_artifacts)

        # disabled for now to no show silly results until we manage to build a proper utility for it
        if WalkabilityIndicators.SLOPE in params.optional_indicators:
            with self.catch_exceptions(indicator_name='Slope', resources=resources):
                slope_artifacts = compute_slope_analysis(
                    paths=line_paths, s3settings=self.s3_settings, resources=resources
                )
                artifacts.extend(slope_artifacts)

        if WalkabilityIndicators.COMFORT in params.optional_indicators:
            with self.catch_exceptions(indicator_name='Comfort Indicators', resources=resources):
                log.info('Computing Comfort Indicators')
                comfort_artifacts = compute_comfort_artifacts(
                    paths=line_paths,
                    aoi=aoi,
                    max_walking_distance_map=self.max_walking_distance_map,
                    ohsome_client=self.ohsome,
                    ors_settings=self.ors_settings,
                    resources=resources,
                )
                artifacts.extend(comfort_artifacts)
                log.info('Comfort Computed')

        if WalkabilityIndicators.LIGHT in params.optional_indicators:
            with self.catch_exceptions(indicator_name='Path Lighting Indicators', resources=resources):
                log.info('Computing Path Lighting Indicators')
                light_path_artifact = path_lighting_analysis(
                    line_paths=line_paths,
                    polygon_paths=polygon_paths,
                    resources=resources,
                )
                artifacts.extend(light_path_artifact)
                log.info('Path Lighting Indicators Computed')

        if WalkabilityIndicators.SHADE in params.optional_indicators:
            with self.catch_exceptions(indicator_name='Tree Shade', resources=resources):
                log.info('Computing Tree Shade')
                shade_artifacts = shade_analysis(
                    paths=line_paths,
                    tile_spec=self.shade_tiles,
                    shade_client=self.shade_client,
                    shade_config=self.shade_config,
                    resources=resources,
                )
                artifacts.extend(shade_artifacts)
                log.info('Tree Shade Computed')

        return artifacts

    def _get_paths(self, aoi: shapely.MultiPolygon) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        log.debug('Extracting paths')
        line_paths = fetch_osm_data(aoi, ohsome_filter('line'), self.ohsome)
        polygon_paths = fetch_osm_data(aoi, ohsome_filter('polygon'), self.ohsome)

        line_paths = self.clean_geometries(aoi, line_paths, 'LineString')
        polygon_paths = self.clean_geometries(aoi, polygon_paths, 'Polygon')

        log.debug('Finished extracting paths')

        line_paths = path_categorisation(geometries=line_paths)
        polygon_paths = path_categorisation(geometries=polygon_paths)

        if line_paths.empty and polygon_paths.empty:
            raise ClimatoologyUserError(
                'No accessible paths for walking were found in your area. Please select a larger area'
            )

        return line_paths, polygon_paths

    def clean_geometries(self, aoi: shapely.MultiPolygon, geometries: gpd.GeoDataFrame, geom_name: str):
        geometries = geometries.explode(ignore_index=True)
        geometries['geometry'] = geometries.make_valid()

        # reclipping
        geometries = gpd.clip(geometries, aoi, keep_geom_type=True).explode(ignore_index=True)
        geometries = geometries[geometries['geometry'].geom_type.str.contains(geom_name)]

        # setting precision and remove paths that are sub-precision length, i.e. empty after set_precision
        geometries['geometry'] = geometries.set_precision(grid_size=0.0000001)
        geometries = geometries[~geometries.geometry.is_empty]

        return geometries
