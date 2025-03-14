from enum import Enum
from typing import Self, Dict

from climatoology.utility.Naturalness import NaturalnessIndex
from pydantic import BaseModel, Field, model_validator

from walkability.components.utils.misc import PathCategory


class WalkingSpeed(Enum):
    SLOW = 'slow'
    MEDIUM = 'medium'
    FAST = 'fast'


WALKING_SPEED_MAP = {WalkingSpeed.SLOW: 2, WalkingSpeed.MEDIUM: 4, WalkingSpeed.FAST: 6}
WALKING_SPEED_MAP_STRING = {k.value: v for k, v in WALKING_SPEED_MAP.items()}


class PathRating(BaseModel):
    designated: float = Field(
        title='Designated Path Rating',
        description='Qualitative (between 0..1) rating of paths designated for exclusive pedestrian use.',
        ge=0,
        le=1,
        examples=[1.0],
        default=1.0,
    )
    designated_shared_with_bikes: float = Field(
        title='Designated Shared with Bikes Path Rating',
        description='Qualitative (between 0..1) rating of paths shared with bikes.',
        ge=0,
        le=1,
        examples=[0.8],
        default=0.8,
    )

    shared_with_motorized_traffic_low_speed: float = Field(
        title='Shared with motorized traffic low speed Path Rating',
        description='Qualitative rating (between 0..1) of streets without a sidewalk, with low '
        'speed limits, such as living streets or service ways.',
        ge=0,
        le=1,
        examples=[0.6],
        default=0.6,
    )
    shared_with_motorized_traffic_medium_speed: float = Field(
        title='Shared with motorized traffic medium speed Path Rating',
        description='Qualitative rating (between 0..1) of streets without a sidewalk, '
        'with medium speed limits up to 30 km/h',
        ge=0,
        le=1,
        examples=[0.4],
        default=0.4,
    )
    shared_with_motorized_traffic_high_speed: float = Field(
        title='Shared with motorized traffic high speed Path Rating',
        description='Qualitative rating (between 0..1) of streets without a sidewalk, '
        'with higher speed limits up to 50 km/h',
        ge=0,
        le=1,
        examples=[0.2],
        default=0.2,
    )
    not_walkable: float = Field(
        title='Not Walkable Path Rating',
        description='Qualitative rating (between 0..1) of paths that are not walkable.',
        ge=0,
        le=1,
        examples=[0.0],
        default=0.0,
    )
    unknown: float = Field(
        title='Unknown Path Rating',
        description='Qualitative (between 0..1) rating of paths that are in principle walkable but '
        'cannot be fit in one of the other categories (default -9999, which is out of scale)',
        ge=0,
        le=1,
        examples=[0.0],
        default=0.0,
    )

    @model_validator(mode='after')
    def check_order(self) -> Self:
        assert (
            self.not_walkable
            <= self.shared_with_motorized_traffic_high_speed
            <= self.shared_with_motorized_traffic_medium_speed
            <= self.shared_with_motorized_traffic_low_speed
            <= self.designated_shared_with_bikes
            <= self.designated
        ), 'Qualitative rating must respect semantic order of categories!'
        return self


class ComputeInputWalkability(BaseModel):
    walkable_time: float = Field(
        title='Maximum Trip Duration',
        description='Maximum duration of a single trip in minutes.',
        ge=0,
        examples=[15],
        default=15,
    )
    walking_speed: WalkingSpeed = Field(
        title='Walking Speed',
        description='Choose a walking speed category. The categories map to the following speed in km/h: '
        f'{WALKING_SPEED_MAP_STRING}',
        examples=[WalkingSpeed.MEDIUM],
        default=WalkingSpeed.MEDIUM,
    )
    naturalness_index: NaturalnessIndex = Field(
        title='Naturalness Index',
        description='Which index to use as basis of the naturalness estimation.',
        examples=[NaturalnessIndex.NDVI],
        default=NaturalnessIndex.NDVI,
    )
    path_rating: PathRating = Field(
        title='Path Rating Mapping',
        description='Qualitative rating for each of the available path categories.',
        examples=[PathRating()],
        default=PathRating(),
    )
    admin_level: int = Field(
        title='Administrative level',
        description='The administrative level the results should be aggregated to. See the '
        '[OSM wiki documentation](https://wiki.openstreetmap.org/wiki/Tag:boundary=administrative) for '
        'available values.',
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
