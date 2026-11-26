from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Government Knowledge & Policy Assistant"
    app_environment: str = "development"
    database_url: str
    qdrant_url: str = ""
    qdrant_api_key: SecretStr = SecretStr("")
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "llama-3.3-70b-versatile"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_upload_size_mb: int = 20
    government_website_urls: tuple[str, ...] = (
        "https://www.gov.za",
        "https://www.dpsa.gov.za",
        "https://www.sita.co.za",
        "https://www.treasury.gov.za",
        "https://www.justice.gov.za",
        "https://www.dws.gov.za",
        "https://www.gov.za/documents",
    )
    rag_min_similarity: float = Field(default=0.35, ge=0.0, le=1.0)
    rag_top_k: int = Field(default=5, ge=1, le=20)


settings = Settings()
