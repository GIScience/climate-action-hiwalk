import uuid
from enum import Enum
from typing import Optional, Self, Dict, Callable

import geojson_pydantic
import geopandas as gpd
import shapely
from pydantic import BaseModel, Field, field_validator, model_validator
from pyproj import CRS, Transformer
from shapely.ops import transform

from walkability.utils import PathCategory


class AoiProperties(BaseModel):
    name: str = Field(
        title='Name',
        description='The name of the area of interest i.e. a human readable description.',
        examples=['Heidelberg'],
    )
    id: str = Field(
        title='ID',
        description='A unique identifier of the area of interest.',
        examples=[uuid.uuid4()],
    )


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
    shared_with_bikes: float = Field(
        title='Shared with Bikes Path Rating',
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
    inaccessible: float = Field(
        title='Inaccessible Path Rating',
        description='Qualitative rating (between 0..1) of paths that are not walkable.',
        ge=0,
        le=1,
        examples=[0.0],
        default=0.0,
    )
    missing_data: float = Field(
        title='Missing Data Path Rating',
        description='Qualitative (between 0..1) rating of paths that are in principle walkable but are missing data (default -9999, which is out of scale)',
        ge=0,
        le=1,
        examples=[0.0],
        default=-9999,
    )

    @model_validator(mode='after')
    def check_order(self) -> Self:
        assert (
            self.inaccessible
            <= self.shared_with_motorized_traffic_high_speed
            <= self.shared_with_motorized_traffic_medium_speed
            <= self.shared_with_motorized_traffic_low_speed
            <= self.shared_with_bikes
            <= self.designated
        ), 'Qualitative rating must respect semantic order of categories!'
        return self


class IDW(Enum):
    POLYNOMIAL = 'Polynomial decay related to retail and park amenities according to Frank et al 2021'
    STEP_FUNCTION = 'Step function reflecting statistical findings on walking path distance according to Xia et al 2018'
    NONE = 'No distance weighting'


class ComputeInputWalkability(BaseModel):
    aoi: geojson_pydantic.Feature[geojson_pydantic.MultiPolygon, AoiProperties] = Field(
        title='Area of Interest Input',
        description='A required area of interest parameter.',
        validate_default=True,
        examples=[
            {
                'type': 'Feature',
                'properties': {'name': 'Heidelberg', 'id': 'Q12345'},
                'geometry': {
                    'type': 'MultiPolygon',
                    'coordinates': [
                        [
                            [
                                [12.3, 48.22],
                                [12.3, 48.34],
                                [12.48, 48.34],
                                [12.48, 48.22],
                                [12.3, 48.22],
                            ]
                        ]
                    ],
                },
            }
        ],
    )
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

    @classmethod
    @field_validator('aoi')
    def assert_aoi_properties_not_null(cls, aoi: geojson_pydantic.Feature) -> geojson_pydantic.Feature:
        assert aoi.properties, 'AOI properties are required.'
        return aoi

    def get_aoi_geom(self) -> shapely.MultiPolygon:
        """Convert the input geojson geometry to a shapely geometry.

        :return: A shapely.MultiPolygon representing the area of interest defined by the user.
        """
        return shapely.geometry.shape(self.aoi.geometry)

    def get_utm_zone(self) -> CRS:
        return gpd.GeoSeries(data=self.get_aoi_geom(), crs='EPSG:4326').estimate_utm_crs()

    def get_buffered_aoi(self) -> shapely.MultiPolygon:
        wgs84 = CRS('EPSG:4326')
        utm = self.get_utm_zone()

        geographic_projection_function = Transformer.from_crs(wgs84, utm, always_xy=True).transform
        wgs84_projection_function = Transformer.from_crs(utm, wgs84, always_xy=True).transform
        projected_aoi = transform(geographic_projection_function, self.get_aoi_geom())
        buffered_aoi = projected_aoi.buffer(self.get_max_walking_distance())
        return transform(wgs84_projection_function, buffered_aoi)

    def get_aoi_properties(self) -> AoiProperties:
        """Return the properties of the aoi.

        :return:
        """
        return self.aoi.properties

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
