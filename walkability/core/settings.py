from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    naturalness_host: str
    naturalness_port: int
    naturalness_path: str

    ors_api_key: str

    model_config = SettingsConfigDict(env_file='.env')
