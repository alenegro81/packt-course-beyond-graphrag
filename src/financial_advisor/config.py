from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path so .env is found regardless of the working directory (notebooks, scripts, …)
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")

    # Azure OpenAI
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_chat_deployment: str
    azure_openai_embedding_deployment: str

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str
    neo4j_database: str = "neo4j"

    # NYT Article Search API (Module 3 — news enrichment)
    nyt_api_key: str = ""

    # Nasdaq Data Link / Sharadar (Module 3 — fundamentals + corporate actions)
    nasdaq_data_link_api_key: str = ""


settings = Settings()
