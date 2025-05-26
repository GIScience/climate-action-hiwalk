from enum import Enum
from typing import Set

from climatoology.utility.Naturalness import NaturalnessIndex
from pydantic import BaseModel, Field


class WalkabilityIndicators(Enum):
    SLOPE = 'Slope'
    NATURALNESS = 'Naturalness'
    DETOURS = 'Detour Factor'


class WalkingSpeed(Enum):
    SLOW = 'slow'
    MEDIUM = 'medium'
    FAST = 'fast'


WALKING_SPEED_MAP = {WalkingSpeed.SLOW: 2, WalkingSpeed.MEDIUM: 4, WalkingSpeed.FAST: 6}


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
