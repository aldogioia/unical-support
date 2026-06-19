from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Unical Support MVP"
    DATABASE_URL: str = "postgresql+psycopg://postgres:root@localhost:5432/unical_support"
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    REDIS_URL: str = "redis://localhost:6379/0"
    GOOGLE_API_KEY: str = ""
    GOOGLE_API_KEY_2: str = ""
    GROQ_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
