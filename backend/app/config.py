from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    google_cse_api_key: str = ""
    google_cse_id: str = ""

    brave_search_api_key: str = ""

    output_dir: str = "output"
    learned_skills_path: str = "data/learned_skills.json"
    cors_origin: str = "http://localhost:5173"


settings = Settings()
