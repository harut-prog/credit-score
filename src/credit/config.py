from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MODEL_PATH: str = "artifacts/baseline_logreg.joblib"
    LOG_LEVEL: str = "INFO"

    POSTGRES_HOST: str | None = None
    POSTGRES_PORT: int | None = None
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str | None = None

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def database_url(self) -> str | None:
        if not self.POSTGRES_HOST:
            return None
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()