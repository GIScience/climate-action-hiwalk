import logging
from typing import List, Dict, Tuple

import geopandas as gpd
import openrouteservice
import shapely.ops
from climatoology.base.baseoperator import BaseOperator, AoiProperties, _Artifact
from climatoology.base.computation import ComputationResources
from climatoology.base.info import _Info
from climatoology.utility.Naturalness import NaturalnessUtility
from ohsome import OhsomeClient

from walkability.components.categorise_paths.path_categorisation import path_categorisation
from walkability.components.categorise_paths.path_categorisation_artifacts import build_path_categorisation_artifact
from walkability.components.categorise_paths.path_summarisation import summarise_by_area
from walkability.components.naturalness.naturalness_analysis import naturalness_analysis
from walkability.components.network_analyses.network_analyses import connectivity_permeability_analyses
from walkability.components.slope.slope_analysis import slope_analysis
from walkability.components.utils.geometry import get_utm_zone, get_buffered_aoi
from walkability.components.utils.misc import (
    fetch_osm_data,
    PathCategory,
    ohsome_filter,
)
from walkability.core.info import get_info
from walkability.core.input import ComputeInputWalkability

log = logging.getLogger(__name__)


class OperatorWalkability(BaseOperator[ComputeInputWalkability]):
    def __init__(self, naturalness_utility: NaturalnessUtility, ors_api_key: str):
        super().__init__()
        self.naturalness_utility = naturalness_utility
        self.ohsome = OhsomeClient(user_agent='CA Plugin Walkability')
        self.ors_client = openrouteservice.Client(key=ors_api_key)
        log.debug('Initialised walkability operator with ohsome client and Naturalness Utility')

    def info(self) -> _Info:
        return get_info()

    def compute(
        self,
        resources: ComputationResources,
        aoi: shapely.MultiPolygon,
        aoi_properties: AoiProperties,
        params: ComputeInputWalkability,
    ) -> List[_Artifact]:
        log.info(f'Handling compute request: {params.model_dump()} in context: {resources}')

        line_paths, line_paths_buffered, polygon_paths = self._get_paths(
            aoi=aoi, max_walking_distance=params.max_walking_distance, rating_map=params.get_path_rating_mapping()
        )

        try:
            areal_summaries = summarise_by_area(
                paths=line_paths,
                aoi=aoi,
                admin_level=params.admin_level,
                projected_crs=get_utm_zone(aoi),
                ohsome_client=self.ohsome,
            )
        except Exception as error:
            log.error(
                'The computation of the areal summaries indicator failed. No artifact will be created.', exc_info=error
            )
            areal_summaries = dict()
        path_artifacts = build_path_categorisation_artifact(
            paths_line=line_paths, paths_polygon=polygon_paths, areal_summaries=areal_summaries, resources=resources
        )

        network_artifacts = connectivity_permeability_analyses(
            line_paths_buffered,
            params.max_walking_distance,
            aoi,
            idw_function=params.get_distance_weighting_function(),
            resources=resources,
        )

        naturalness_artifact = naturalness_analysis(
            line_paths=line_paths,
            aoi=aoi,
            index=params.naturalness_index,
            resources=resources,
            naturalness_utility=self.naturalness_utility,
        )

        slope_artifact = slope_analysis(line_paths=line_paths, aoi=aoi, ors_client=self.ors_client, resources=resources)

        return path_artifacts + list(network_artifacts) + [naturalness_artifact, slope_artifact]

    def _get_paths(
        self, aoi: shapely.MultiPolygon, max_walking_distance: float, rating_map: Dict[PathCategory, float]
    ) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
        aoi_buffered = get_buffered_aoi(aoi, max_walking_distance)

        log.debug('Extracting paths')
        line_paths_buffered = fetch_osm_data(aoi_buffered, ohsome_filter('line'), self.ohsome)
        polygon_paths = fetch_osm_data(aoi, ohsome_filter('polygon'), self.ohsome)
        log.debug('Finished extracting paths')

        line_paths_buffered, polygon_paths = path_categorisation(
            self.ohsome, paths_line=line_paths_buffered, paths_polygon=polygon_paths, aoi=aoi, rating_map=rating_map
        )

        line_paths = gpd.clip(line_paths_buffered, aoi, keep_geom_type=True).explode(ignore_index=True)

        return line_paths, line_paths_buffered, polygon_paths
