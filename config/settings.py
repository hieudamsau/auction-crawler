from pydantic_settings import BaseSettings
from pydantic import Field


class DatabaseSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5432
    user: str = "auction"
    password: str = "auction_pass"
    name: str = "auction_db"

    model_config = {"env_prefix": "DB_"}

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    db: int = 0

    model_config = {"env_prefix": "REDIS_"}

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class MeiliSettings(BaseSettings):
    host: str = "http://localhost:7700"
    master_key: str = "auction_master_key"

    model_config = {"env_prefix": "MEILI_"}


class CrawlSettings(BaseSettings):
    delay_between_pages: float = Field(default=1.5, description="Seconds between page requests")
    delay_between_details: float = Field(default=1.0, description="Seconds between detail requests")
    max_retries: int = 3
    request_timeout: float = 30.0
    page_size_dgts: int = 50
    page_size_taisancong: int = 20
    checkpoint_interval: int = 100
    user_agent: str = "AuctionCrawler/0.1 (research project)"

    model_config = {"env_prefix": "CRAWL_"}


class AppSettings(BaseSettings):
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    meili: MeiliSettings = Field(default_factory=MeiliSettings)
    crawl: CrawlSettings = Field(default_factory=CrawlSettings)

    raw_data_dir: str = "data/raw"
    log_level: str = "INFO"

    model_config = {"env_prefix": "APP_"}


settings = AppSettings()
