from enum import Enum
from typing import Set

from pydantic import BaseModel, Field

from walkability.core.settings import FeatureFlags

feature_flags = FeatureFlags()


class WalkabilityIndicators(Enum):
    SLOPE = 'Slope'
    NATURALNESS = 'Greenness'
    DETOURS = 'Detour Factor'
    COMFORT = 'Comfort Factor'
    SHADE = 'Shade'


class ComputeInputWalkability(BaseModel):
    optional_indicators: Set[WalkabilityIndicators] = Field(
        title='Optional indicators',
        description='Computing these indicators for large areas may exceed '
        'the time limit for individual assessments in the Climate Action Navigator.',
        examples=[set()],
        default=set(),
        # Override the json schema to hide the shade option if the feature flag is not activated
        json_schema_extra={
            'enum': [
                opt.value
                for opt in WalkabilityIndicators
                if (opt != WalkabilityIndicators.SHADE or feature_flags.shade)
            ]
        },
    )
