from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = ""
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Partner API keys are valid for this long from the moment they're revealed.
    API_KEY_MAX_TTL_DAYS: int = 90
    # Days a company has to reveal an approved key before the approval lapses.
    API_KEY_REVEAL_WINDOW_DAYS: int = 7
    # Requests a company may have waiting (pending or approved) at once.
    API_KEY_MAX_OPEN_REQUESTS: int = 5
    # Requests one API key may make per minute before getting 429.
    API_KEY_RATE_LIMIT_PER_MINUTE: int = 120
    # Failed API key attempts per client IP per minute that are audited; past
    # this, failures get 429 and are no longer written to the audit log.
    API_KEY_FAILED_ATTEMPTS_PER_MINUTE: int = 20

    # Comma-separated IPs of reverse proxies whose X-Forwarded-For header is
    # trusted. Empty means the header is ignored and the socket peer is used.
    TRUSTED_PROXIES: str = ""

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

    @property
    def trusted_proxies(self) -> set[str]:
        return {ip.strip() for ip in self.TRUSTED_PROXIES.split(",") if ip.strip()}

settings = Settings()
