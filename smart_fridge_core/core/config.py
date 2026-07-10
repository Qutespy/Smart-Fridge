from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv, find_dotenv

# Подхватываем .env из CWD или из любой родительской директории — это нужно,
# чтобы ключи (в т.ч. GIGACHAT_CREDENTIALS) находились и при запуске uvicorn
# из smart_fridge_core/, и из корня репозитория.
load_dotenv(find_dotenv(usecwd=True))


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./smart_fridge.db"

    SECRET_KEY: str = "your-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    FIREBASE_CREDENTIALS_PATH: Optional[str] = None

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openrouter/free"
    OPENROUTER_TIMEOUT_SECONDS: int = 60
    OPENROUTER_SITE_URL: Optional[str] = "http://localhost:5001"
    OPENROUTER_APP_NAME: Optional[str] = "Smart Fridge"

    GIGACHAT_CREDENTIALS: str = ""
    GIGACHAT_SCOPE: str = "GIGACHAT_API_PERS"
    GIGACHAT_MODEL: str = "GigaChat"
    GIGACHAT_VERIFY_SSL: bool = False
    GIGACHAT_TIMEOUT_SECONDS: int = 60

    AWS_ACCESS_KEY: Optional[str] = None
    AWS_SECRET_KEY: Optional[str] = None
    S3_BUCKET_NAME: str = "smart-fridge-photos"

    REDIS_URL: str = "redis://localhost:6379"

    EXPIRATION_WARNING_DAYS: int = 2
    LOW_STOCK_THRESHOLD: float = 0.5

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
