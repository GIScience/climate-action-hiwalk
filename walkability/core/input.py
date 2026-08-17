from enum import Enum
from typing import Set

from pydantic import BaseModel, Field

from walkability.core.settings import FeatureFlags


class WalkabilityIndicators(Enum):
    SLOPE = 'Slope'
    NATURALNESS = 'Greenness'
    DETOURS = 'Detour Factor'
    COMFORT = 'Comfort Factor'
    SHADE = 'Tree Shade'
    LIGHT = 'Path Lighting'
    TACTILE_PAVING = 'Tactile Paving'
    VARIETY_OF_POIS = 'Variety of POIs'


# These indicators will not be available for selection if `FEATURE_FLAG_EXPERIMENTAL=False`
EXPERIMENTAL_INDICATORS = {WalkabilityIndicators.TACTILE_PAVING}

feature_flags = FeatureFlags()
optional_indicators_schema = None
if not feature_flags.experimental:
    optional_indicators_schema = {
        'enum': [opt.value for opt in WalkabilityIndicators if opt not in EXPERIMENTAL_INDICATORS]
    }


class ComputeInputWalkability(BaseModel):
    optional_indicators: Set[WalkabilityIndicators] = Field(
        title='Optional indicators',
        description='Computing these indicators for large areas may exceed '
        'the time limit for individual assessments in the Climate Action Navigator.',
        examples=[set()],
        default=set(),
        # Override the json schema to hide the shade option if the feature flag is not activated
        json_schema_extra=optional_indicators_schema,
    )
