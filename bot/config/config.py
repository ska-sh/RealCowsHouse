from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str

    PLAY_GAMES: bool = True
    POINTS: list[int] = [95, 155]
    TON_AMOUNT: list[float] = [0.095, 0.135]

    USE_REF: bool = False
    REF_ID: str = 'kentId6168926126'

    USE_PROXY_FROM_FILE: bool = True

    DO_TASKS: bool = False

settings = Settings()


