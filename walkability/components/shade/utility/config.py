from pathlib import Path

from pydantic import Field, computed_field
from pydantic.dataclasses import dataclass


@dataclass
class S3ShadeConfig:
    cache_dir: Path = Field(description='A directory to cache downloaded files to.')
    bucket: str = Field(
        description='The AWS bucket containing the tree canopy data.',
        default='dataforgood-fb-data',
    )
    base_path: Path = Field(
        description="The base path to the tree canopy data. All 'object' and 'subdir' values are relative to this base path.",
        default=Path('forests/v1/alsgedi_global_v6_float'),
    )
    tiles_object: str = Field(
        description='The object name for the tile specification (relative to base_path).',
        default='tiles.geojson',
    )
    canopy_heights_subdir: str = Field(
        description='The subdirectory path for the canopy heights data (relative to base_path).',
        default='chm',
    )
    cloud_mask_subdir: str = Field(
        description='The subdirectory path for the masks data (relative to base_path).',
        default='msk',
    )
    metadata_subdir: str = Field(
        description='The subdirectory path for the metadata (relative to base_path).',
        default='metadata',
    )

    @computed_field
    @property
    def canopy_heights_path(self) -> Path:
        return self.base_path / f'{self.canopy_heights_subdir}'

    @computed_field
    @property
    def cloud_mask_path(self) -> Path:
        return self.base_path / f'{self.cloud_mask_subdir}'

    @computed_field
    @property
    def metadata_path(self) -> Path:
        return self.base_path / f'{self.metadata_path}'
