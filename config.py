from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://passage:passage@localhost:5432/passage"

    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days_default: int = 1
    refresh_token_expire_days_remember_me: int = 30

    google_client_id: str = ""

    kpay_base_url: str = "https://api.kpay-group.com"
    kpay_api_key: str = ""
    kpay_webhook_secret: str = ""

    frontend_url: str = "http://localhost:5500"
    environment: str = "development"


settings = Settings()
