from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    naturalness_host: str
    naturalness_port: int
    naturalness_path: str
    max_path_limit: int = 100000

    feature_flag_ohsome2: bool = False
    ohsome_base_url: Optional[str] = None

    model_config = SettingsConfigDict(env_file='.env')  # dead: disable


class FeatureFlags(BaseSettings):
    experimental: bool = Field(
        default=False,
        description='Whether to turn on experimental features and results',
        alias=AliasChoices('EXPERIMENTAL', 'FEATURE_FLAG_EXPERIMENTAL'),
    )

    model_config = SettingsConfigDict(env_file='.env.feature')  # dead: disable
