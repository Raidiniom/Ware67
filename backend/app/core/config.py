from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = ""
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"

    # An empty key still signs tokens, so anyone could forge one. Fail at
    # startup instead of running with it.
    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def secret_must_be_set(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("JWT_SECRET_KEY must be set (see Local_Development_Setup.md)")
        return value

settings = Settings()
