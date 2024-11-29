from enum import Enum
from typing import Optional, Self, Dict, Callable

from pydantic import BaseModel, Field, model_validator

from walkability.utils import PathCategory


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
        default=-9999,
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


class IDW(Enum):
    POLYNOMIAL = 'Polynomial decay related to retail and park amenities according to Frank et al 2021'
    STEP_FUNCTION = 'Step function reflecting statistical findings on walking path distance according to Xia et al 2018'
    NONE = 'No distance weighting'


class ComputeInputWalkability(BaseModel):
    walkable_time: Optional[float] = Field(
        title='Maximum Trip Duration',
        description='Maximum duration of a single trip in minutes.',
        ge=0,
        examples=[15],
        default=15,
    )
    walking_speed: Optional[WalkingSpeed] = Field(
        title='Walking Speed',
        description='Choose a walking speed category. The categories map to the following speed in km/h: '
        f'{WALKING_SPEED_MAP_STRING}',
        examples=[WalkingSpeed.MEDIUM],
        default=WalkingSpeed.MEDIUM,
    )
    path_rating: Optional[PathRating] = Field(
        title='Path Rating Mapping',
        description='Qualitative rating for each of the available path categories.',
        examples=[PathRating()],
        default=PathRating(),
    )
    admin_level: Optional[int] = Field(
        title='Administrative level',
        description='The administrative level the results should be aggregated to. See the '
        '[OSM wiki documentation](https://wiki.openstreetmap.org/wiki/Tag:boundary=administrative) for '
        'available values.',
        ge=6,
        le=12,
        examples=[9],
        default=9,
    )
    idw_method: Optional[IDW] = Field(
        title='Distance Weighting',
        description='The function that should be used to model distance weighting. The approach is often called '
        'Inverse Distance Weighting (IDW) or Distance Decay. Walking trips exhibit a certain distribution. Many '
        'trips are rather short while long trips are relatively seldom. This attribute defines which '
        'function will be used to weight close vs. distant trip targets.',
        examples=[IDW.STEP_FUNCTION],
        default=IDW.STEP_FUNCTION,
    )

    def get_max_walking_distance(self) -> float:
        """Calculate the maximum walking distance in m."""
        return (1000 / 60) * WALKING_SPEED_MAP[self.walking_speed] * self.walkable_time

    def get_path_rating_mapping(self) -> Dict[PathCategory, float]:
        mapping = self.path_rating.model_dump()
        return {PathCategory(k): v for k, v in mapping.items()}

    def get_distance_weighting_function(self) -> Callable[[float], float]:
        match self.idw_method:
            case IDW.STEP_FUNCTION:

                def step_func(distance: float) -> float:
                    if distance < 400:
                        return 1
                    elif distance < 800:
                        return 0.6
                    elif distance < 1200:
                        return 0.25
                    elif distance < 1800:
                        return 0.08
                    else:
                        return 0

                return step_func
            case IDW.POLYNOMIAL:

                def original_polynom(distance_km: float):
                    return (
                        335.9229 * distance_km**5
                        - 1327.84 * distance_km**4
                        + 1802.56 * distance_km**3
                        - 935.68 * distance_km**2
                        + 61.92 * distance_km
                        + 100.1072
                    )

                def scaled_polynom(distance: float) -> float:
                    if distance > 1500:
                        return 0.0

                    weight = original_polynom(distance / 1000.0)
                    weight = weight / 100.0

                    if weight > 1.0:
                        return 1.0
                    elif weight < 0.0:
                        return 0.0
                    else:
                        return weight

                return scaled_polynom

            case IDW.NONE:
                return lambda distance: 1
