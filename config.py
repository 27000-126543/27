from pydantic_settings import BaseSettings
from datetime import time


class Settings(BaseSettings):
    APP_NAME: str = "销售佣金与渠道返利管理系统"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite:///./commission_system.db"

    SECRET_KEY: str = "your-secret-key-change-in-production-please"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    REPORT_GENERATION_DAY: int = 5
    REPORT_GENERATION_TIME: time = time(2, 0, 0)

    COMMISSION_APPROVAL_THRESHOLD: float = 100000.0

    CRM_API_BASE: str = "http://mock-crm-api.internal"
    ORDER_API_BASE: str = "http://mock-order-api.internal"
    FINANCE_API_BASE: str = "http://mock-finance-api.internal"

    DATA_SYNC_HOUR: int = 1
    DATA_SYNC_MINUTE: int = 30

    LOG_RETENTION_DAYS: int = 365

    class Config:
        env_file = ".env"


settings = Settings()
