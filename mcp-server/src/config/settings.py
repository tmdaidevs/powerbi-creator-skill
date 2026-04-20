from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    fabric_api_base_url: str = "https://api.fabric.microsoft.com/v1"
    powerbi_api_base_url: str = "https://api.powerbi.com/v1.0/myorg"
    tenant_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    use_managed_identity: bool = False
    default_timeout_seconds: int = 30
    max_retries: int = 5
    async_poll_interval_seconds: int = 3
    async_poll_timeout_seconds: int = 120
    backup_directory: str = "./backups"
    bulk_max_workers: int = 4
    default_style_guide_path: str | None = None
    audit_log_path: str = "./audit.jsonl"
    cache_ttl_seconds: int = 60

    model_config = SettingsConfigDict(env_prefix="PBIR_MCP_", env_file=".env", extra="ignore")


settings = Settings()
