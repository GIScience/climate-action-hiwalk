from enum import Enum
from typing import Set

from pydantic import BaseModel, Field


class WalkabilityIndicators(Enum):
    SLOPE = 'Slope'
    NATURALNESS = 'Greenness'
    DETOURS = 'Detour Factor'
    WELLNESS = 'Wellness Factor'


class WalkingSpeed(Enum):
    SLOW = 'slow'
    MEDIUM = 'medium'
    FAST = 'fast'


WALKING_SPEED_MAP = {WalkingSpeed.SLOW: 2, WalkingSpeed.MEDIUM: 4, WalkingSpeed.FAST: 6}


class ComputeInputWalkability(BaseModel):
    optional_indicators: Set[WalkabilityIndicators] = Field(
        title='Optional indicators',
        description='Computing these indicators for large areas may exceed '
        'the time limit for individual assessments in the Climate Action Navigator.',
        examples=[set()],
        default=set(),
    )

    @property
    def max_walking_distance(self) -> float:
        """Calculate the maximum walking distance in m."""
        return (1000 / 60) * WALKING_SPEED_MAP[WalkingSpeed.MEDIUM] * 15
