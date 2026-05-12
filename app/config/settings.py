from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str

    # Reddit
    reddit_user_agent: str = "python:commhealth-analytics:v0.1.0 (by /u/commhealth_user)"
    reddit_request_delay: float = 1.0

    # LLM
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # App
    log_level: str = "INFO"
    environment: str = "development"


settings = Settings()
