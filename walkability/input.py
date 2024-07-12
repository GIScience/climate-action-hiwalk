import uuid
from enum import Enum
from typing import Optional, Self, Dict

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
    exclusive: float = Field(
        title='Exclusive Path Rating',
        description='Qualitative rating (between 0..1) of paths designated exclusively to pedestrians.',
        ge=0,
        le=1,
        examples=[1.0],
        default=1.0,
    )
    explicit: float = Field(
        title='Explicit Path Rating',
        description='Qualitative (between 0..1) rating of paths explicitly denoted for pedestrian use.',
        ge=0,
        le=1,
        examples=[0.8],
        default=0.8,
    )
    probable_yes: float = Field(
        title='Probable-Path Rating',
        description='Qualitative rating (between 0..1) of paths that are probably walkable like forest tracks or '
        'parking aisles.',
        ge=0,
        le=1,
        examples=[0.6],
        default=0.6,
    )
    potential_but_unknown: float = Field(
        title='Uncertain-Path Rating',
        description='Qualitative rating (between 0..1) of paths that should be walkable but exhibit no information '
        'thereon.',
        ge=0,
        le=1,
        examples=[0.5],
        default=0.5,
    )
    inaccessible: float = Field(
        title='Exclusive Path Rating',
        description='Qualitative rating (between 0..1) of paths that are inaccessible to pedestrians.',
        ge=0,
        le=1,
        examples=[0.0],
        default=0.0,
    )

    @model_validator(mode='after')
    def check_order(self) -> Self:
        assert (
            self.inaccessible <= self.potential_but_unknown <= self.probable_yes <= self.explicit <= self.exclusive
        ), 'Qualitative rating must respect semantic order of categories!'
        return self


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
