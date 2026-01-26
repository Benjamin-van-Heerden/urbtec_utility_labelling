from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings

load_dotenv()


class SourceClient(BaseModel):
    name: str
    db_name: str


# QA environment clients (mobixhep_* databases)
QA_CLIENTS = [
    SourceClient(name="Huurkor", db_name="mobixhep_huurkor"),
    SourceClient(name="TopCharge", db_name="mobixhep_topcharge"),
    SourceClient(name="Paxton", db_name="mobixhep_paxton"),
    SourceClient(name="MRC", db_name="mobixhep_mrc"),
]

# Prod environment clients (mobixenn_mobiX_* databases)
PROD_CLIENTS = [
    SourceClient(name="Huurkor", db_name="mobixenn_mobiX_c507db"),
    SourceClient(name="TopCharge", db_name="mobixenn_mobiX_c509db"),
    SourceClient(name="Pharoah", db_name="mobixenn_mobiX_c522db"),
    SourceClient(name="Paxton", db_name="mobixenn_mobiX_c502db"),
    SourceClient(name="MRC", db_name="mobixenn_mobiX_c510db"),
    SourceClient(name="solver", db_name="mobixenn_mobiX_c506db"),
]

# Target distribution for labelled items: water, electricity
TARGET_DISTRIBUTION = {
    "water": 0.70,
    "electricity": 0.30,
}


class Settings(BaseSettings):
    jwt_salt: str = ""

    # Environment: "qa" or "prod"
    app_env: str = "qa"

    # Source database credentials (shared across all clients)
    source_db_host: str = ""
    source_db_port: int = 3306
    source_db_user: str = ""
    source_db_password: str = ""


def get_env_or_die():
    settings = Settings()

    if not settings.jwt_salt:
        raise ValueError("JWT salt is not set")

    if not settings.source_db_host:
        raise ValueError("Source DB host is not set")

    return settings


ENV_SETTINGS = get_env_or_die()

# Select clients based on environment
SOURCE_CLIENTS = PROD_CLIENTS if ENV_SETTINGS.app_env == "prod" else QA_CLIENTS
