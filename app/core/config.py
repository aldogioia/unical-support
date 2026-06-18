from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Unical Support MVP"
    DATABASE_URL: str = "postgresql+psycopg://postgres:root@localhost:5432/unical_support"
    SECRET_KEY: str = "super_secret_jwt_key_cambiami_in_produzione"
    ALGORITHM: str = "HS256"
    REDIS_URL: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()