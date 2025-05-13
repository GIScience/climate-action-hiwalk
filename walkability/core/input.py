from enum import Enum
from typing import Set, Dict

from climatoology.utility.Naturalness import NaturalnessIndex
from pydantic import BaseModel, Field

from walkability.components.utils.misc import PathCategory


class WalkabilityIndicators(Enum):
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
        title='Optional indicators',
        description='Computing these indicators for large areas may exceed '
        'the time limit for individual assessments in the Climate Action Navigator.',
        examples=[],
        default=[],
    )
    naturalness_index: NaturalnessIndex = Field(
        title='What to include in naturalness calculation?',
        description='Choose NDVI to include only vegetation greenness, WATER to include only water bodies, and NATURALNESS to include both.',
        examples=[NaturalnessIndex.NDVI],
        default=NaturalnessIndex.NDVI,
    )

    @property
    def max_walking_distance(self) -> float:
        """Calculate the maximum walking distance in m."""
        return (1000 / 60) * WALKING_SPEED_MAP[WalkingSpeed.MEDIUM] * 15

    def get_path_rating_mapping(self) -> Dict[PathCategory, float]:
        mapping = self.path_rating.model_dump()
        return {PathCategory(k): v for k, v in mapping.items()}
