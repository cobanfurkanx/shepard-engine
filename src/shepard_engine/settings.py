from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", env_prefix="ENGINE_", extra="ignore")
    database_url: SecretStr = SecretStr("postgresql://engine:local@localhost:55432/engine")
    redis_url: SecretStr = SecretStr("redis://localhost:56379/0")
    symbols: str = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT"
    identity_enabled: bool = False
    jwt_secret: SecretStr = SecretStr("")
    jwt_issuer: str = "shepard-engine"
    jwt_audience: str = "shepard-engine-demo"
    access_seconds: int = Field(default=900, ge=60, le=900)
    refresh_seconds: int = Field(default=604800, ge=3600, le=604800)
    allowed_origins: str = "http://localhost:5173"
    retention_days: int = Field(default=7, ge=3, le=30)

    @field_validator("symbols")
    @classmethod
    def valid_symbols(cls, value):
        import re
        symbols = value.split(",")
        if len(symbols) > 20 or len(set(symbols)) != len(symbols):
            raise ValueError("use 1-20 unique symbols")
        if not all(re.fullmatch(r"[A-Z0-9]{2,16}USDT", s) for s in symbols):
            raise ValueError("invalid market symbol")
        return value

    @model_validator(mode="after")
    def valid_secret(self):
        if self.identity_enabled and len(self.jwt_secret.get_secret_value()) < 32:
            raise ValueError("identity requires a random JWT secret of at least 32 characters")
        return self

    @property
    def symbol_set(self):
        return set(self.symbols.split(","))


@lru_cache
def get_settings():
    return Settings()
