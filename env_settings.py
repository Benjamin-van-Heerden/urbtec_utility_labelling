from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    jwt_salt: str = ""

    # Source database credentials (Huurkor)
    source_db_host: str = ""
    source_db_port: int = 3306
    source_db_user: str = ""
    source_db_password: str = ""
    source_db_name: str = ""
    source_client_name: str = "Huurkor"


def get_env_or_die():
    settings = Settings()

    if not settings.jwt_salt:
        raise ValueError("JWT salt is not set")

    if not settings.source_db_host:
        raise ValueError("Source DB host is not set")

    return settings


ENV_SETTINGS = get_env_or_die()
