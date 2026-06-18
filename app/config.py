"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    admin_username: str = "admin"
    admin_password: str = "changeme"
    admin_password_hash: str = ""

    secret_key: str = "change-me"

    host: str = "127.0.0.1"
    port: int = 8080

    database_url: str = "sqlite:////data/awgui.db"
    awg_config_dir: str = "/etc/amnezia/amneziawg"

    public_endpoint: str = ""
    default_dns: str = "1.1.1.1, 1.0.0.1"

    wg_bin: str = "awg"
    wg_quick_bin: str = "awg-quick"

    apply_to_system: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
