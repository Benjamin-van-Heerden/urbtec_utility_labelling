from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    jwt_salt: str = ""


def get_env_or_die():
    settings = Settings()

    if not settings.jwt_salt:
        raise ValueError("JWT salt is not set")

    return settings


ENV_SETTINGS = get_env_or_die()
