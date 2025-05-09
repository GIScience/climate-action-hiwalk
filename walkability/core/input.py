from enum import Enum
from typing import Set, Dict

from climatoology.utility.Naturalness import NaturalnessIndex
from pydantic import BaseModel, Field

from walkability.components.utils.misc import PathCategory


class WalkabilityIndicators(Enum):
    DETOURS = 'Detour factor'
    SLOPE = 'Slope'
    NATURALNESS = 'Naturalness'


class WalkingSpeed(Enum):
    SLOW = 'slow'
    MEDIUM = 'medium'
    FAST = 'fast'


WALKING_SPEED_MAP = {WalkingSpeed.SLOW: 2, WalkingSpeed.MEDIUM: 4, WalkingSpeed.FAST: 6}
WALKING_SPEED_MAP_STRING = {k.value: v for k, v in WALKING_SPEED_MAP.items()}


class ComputeInputWalkability(BaseModel):
    indicators_to_compute: Set[WalkabilityIndicators] = Field(
        title='Optional indicators to compute',
        description='Computing these indicators for large areas may exceed '
        'the time limit for individual assessments in the Climate Action Navigator.',
        examples=[{WalkabilityIndicators.DETOURS}],
        default={
            WalkabilityIndicators.DETOURS,
            WalkabilityIndicators.SLOPE,
            WalkabilityIndicators.NATURALNESS,
        },
    )
    walkable_categories_selection: Set[PathCategory] = Field(
        title='Potentially Walkable Categories',
        description='Selection of path categories considered potentially walkable. For a description of the categories '
        'click "Read more >>" above.',
        examples=[{PathCategory.DESIGNATED}],
        default={
            PathCategory.DESIGNATED,
            PathCategory.DESIGNATED_SHARED_WITH_BIKES,
            PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_LOW_SPEED,
            PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_MEDIUM_SPEED,
            PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_HIGH_SPEED,
            PathCategory.SHARED_WITH_MOTORIZED_TRAFFIC_UNKNOWN_SPEED,
            PathCategory.UNKNOWN,
        },
    )
    walkable_time: float = Field(
        title='Maximum Trip Duration',
        description='Maximum duration of a single trip in minutes.',
        ge=0,
        examples=[15],
        default=15,
    )
    walking_speed: WalkingSpeed = Field(
        title='Walking Speed',
        description='Average walking speed. Categories correspond to the following speeds in km/h: '
        f'{WALKING_SPEED_MAP_STRING}',
        examples=[WalkingSpeed.MEDIUM],
        default=WalkingSpeed.MEDIUM,
    )
    naturalness_index: NaturalnessIndex = Field(
        title='Naturalness Index',
        description='What should naturalness be based on? Choose "NDVI" to focus on measuring the greenness of'
        ' vegetation on and around streets. Choose "WATER" to focus on assessing the presence of water bodies. Choose'
        ' "NATURALNESS" to compute a composite indicator accounting for both vegetation and water bodies.',
        examples=[NaturalnessIndex.NDVI],
        default=NaturalnessIndex.NDVI,
    )
    admin_level: int = Field(
        title='Administrative level',
        description='Administrative level to aggregate results.',
        ge=6,
        le=12,
        examples=[9],
        default=9,
    )

    @property
    def max_walking_distance(self) -> float:
        """Calculate the maximum walking distance in m."""
        return (1000 / 60) * WALKING_SPEED_MAP[self.walking_speed] * self.walkable_time

    def get_path_rating_mapping(self) -> Dict[PathCategory, float]:
        mapping = self.path_rating.model_dump()
        return {PathCategory(k): v for k, v in mapping.items()}
