from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    env: str = "development"
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://docintel:docintel@localhost:5432/docintelligence"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # AI Models
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    # Extrator: modelo principal para extração e geração de regras
    # Padrão: Groq Llama (grátis). Trocar para "claude-sonnet-4-6" quando tiver Anthropic.
    extractor_model: str = "llama-3.3-70b-versatile"
    extractor_provider: str = "groq"  # "groq" | "anthropic"
    # Validador: modelo diferente do extrator para evitar viés correlacionado
    validator_model: str = "llama-3.1-8b-instant"

    # Storage (Cloudflare R2 / S3-compatible)
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "docintelligence"

    # Pipeline thresholds — configuráveis sem redeploy
    threshold_l1: float = 0.85
    threshold_l2: float = 0.82
    threshold_l3: float = 0.78

    # Learning loop
    learning_loop_auto_promote: float = 0.90   # confiança mínima para promover regra direto
    learning_loop_queue_human: float = 0.70    # abaixo disso vai para revisão humana
    learning_loop_accumulate_n: int = 3        # docs necessários para promover regra média

    # Limites
    max_file_size_mb: int = 50
    rule_cache_ttl_seconds: int = 300

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.env == "production"


settings = Settings()
