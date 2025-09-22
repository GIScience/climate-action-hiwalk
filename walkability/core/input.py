from enum import Enum
from typing import Set

from pydantic import BaseModel, Field


class WalkabilityIndicators(Enum):
    # SLOPE = 'Slope'
    NATURALNESS = 'Greenness'
    DETOURS = 'Detour Factor'
    COMFORT = 'Comfort Factor'


class ComputeInputWalkability(BaseModel):
    optional_indicators: Set[WalkabilityIndicators] = Field(
        title='Optional indicators',
        description='Computing these indicators for large areas may exceed '
        'the time limit for individual assessments in the Climate Action Navigator.',
        examples=[set()],
        default=set(),
    )
