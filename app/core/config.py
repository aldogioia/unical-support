from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

class Settings(BaseSettings):
    PROJECT_NAME: str = "Unical Support MVP"
    DATABASE_URL: str = ""
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"  # Impostato un default sicuro, ma comunque validato se sovrascritto
    REDIS_URL: str = ""
    GOOGLE_API_KEY: str = ""
    GOOGLE_API_KEY_2: str = ""
    GROQ_API_KEY: str = ""
    FEEDBACK_EMAIL_SENDER: str = ""
    FEEDBACK_EMAIL_PASSWORD: str = ""
    FEEDBACK_EMAIL_RECIPIENT: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:4200,http://localhost"

    @model_validator(mode='after')
    def validate_critical_settings(self) -> "Settings":
        # 1. Controllo SECRET_KEY
        if not self.SECRET_KEY or self.SECRET_KEY.strip() == "":
            raise ValueError(
                "CRITICAL ERROR: La variabile 'SECRET_KEY' non è impostata o è vuota nel file .env. "
                "L'applicazione non può avviarsi per motivi di sicurezza."
            )
        
        if len(self.SECRET_KEY) < 32:
            raise ValueError(
                "CRITICAL ERROR: La 'SECRET_KEY' deve essere lunga almeno 32 caratteri."
            )

        # 2. Controllo DATABASE_URL
        if not self.DATABASE_URL or self.DATABASE_URL.strip() == "":
            raise ValueError(
                "CRITICAL ERROR: La variabile 'DATABASE_URL' non è impostata nel file .env."
            )

        # 3. Controllo ALGORITHM
        if not self.ALGORITHM or self.ALGORITHM.strip() == "":
            raise ValueError(
                "CRITICAL ERROR: La variabile 'ALGORITHM' non è impostata o è vuota nel file .env."
            )

        # 4. Controllo REDIS_URL
        if not self.REDIS_URL or self.REDIS_URL.strip() == "":
            raise ValueError(
                "CRITICAL ERROR: La variabile 'REDIS_URL' non è impostata nel file .env."
            )

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()