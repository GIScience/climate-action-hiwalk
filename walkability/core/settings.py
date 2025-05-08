from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    naturalness_host: str
    naturalness_port: int
    naturalness_path: str

    ors_api_key: str
    ors_snapping_rate_limit: int
    ors_snapping_request_size_limit: int = 4999
    ors_directions_rate_limit: int
    ors_directions_waypoint_limit: int = 50
    ors_base_url: str | None = None

    model_config = SettingsConfigDict(env_file='.env')
