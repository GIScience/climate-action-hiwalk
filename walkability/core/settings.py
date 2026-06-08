from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    naturalness_host: str
    naturalness_port: int
    naturalness_path: str

    model_config = SettingsConfigDict(env_file='.env')  # dead: disable


class FeatureFlags(BaseSettings):
    shade: bool = False

    model_config = SettingsConfigDict(env_file='.env.feature', env_prefix='feature_flag_')  # dead: disable
