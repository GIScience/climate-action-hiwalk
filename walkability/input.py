from typing import Dict, Optional

import geojson_pydantic
import shapely
from pydantic import BaseModel, Field


class ComputeInputWalkability(BaseModel):
    aoi_blueprint: geojson_pydantic.Feature[geojson_pydantic.MultiPolygon, Optional[Dict]] = Field(
        title='Area of Interest Input',
        description='A required area of interest parameter.',
        validate_default=True,
        examples=[
            {
                'type': 'Feature',
                'properties': {},
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

    def get_geom(self) -> shapely.MultiPolygon:
        """Convert the input geojson geometry to a shapely geometry.

        :return: A shapely.MultiPolygon representing the area of interest defined by the user.
        """
        return shapely.geometry.shape(self.aoi_blueprint.geometry)
