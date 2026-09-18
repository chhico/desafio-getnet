import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Meta
    PROJECT_NAME: str = "desafio-get"
    VERSION: str = "2.0.0"
    
    # LLM & Agente
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    AGENT_MODEL: str = Field("gpt-4o", env="AGENT_MODEL")
    AGENT_TEMPERATURE: float = Field(0.0, env="AGENT_TEMPERATURE")
    AGENT_MAX_ITERATIONS: int = Field(10, env="AGENT_MAX_ITERATIONS")
    
    # Seguran\u00e7a (Removida conforme solicita\u00e7\u00e3o)
    # API_SECRET_KEY: str = Field(..., env="API_SECRET_KEY")
    # API_ADMIN_KEY: str = Field(..., env="API_ADMIN_KEY")

    # DB e Vector
    MEMORY_BACKEND: str = Field("sqlite", env="MEMORY_BACKEND")
    VECTOR_DB: str = Field("chroma", env="VECTOR_DB")
    CHROMA_PERSIST_DIR: str = Field("bds/chroma_db", env="CHROMA_PERSIST_DIR")
    CHECKPOINT_DB_PATH: str = Field("bds/checkpoints.sqlite", env="CHECKPOINT_DB_PATH")
    CONFIG_DB_PATH: str = Field("bds/config.db", env="CONFIG_DB_PATH")
    RAG_SYNC_MODE: str = Field("simple", env="RAG_SYNC_MODE")
    RAG_SYNC_URLS: str = Field("https://www.getnet.eu/pt/suporte", env="RAG_SYNC_URLS")
    RAG_CRAWLER_MAX_DEPTH: int = Field(2, env="RAG_CRAWLER_MAX_DEPTH")
    RAG_WEB_SYNC_CRON: str = Field("0 3 * * *", env="RAG_WEB_SYNC_CRON")

    # LangChain
    LANGCHAIN_TRACING_V2: str = Field("false", env="LANGCHAIN_TRACING_V2")
    LANGCHAIN_API_KEY: str = Field("", env="LANGCHAIN_API_KEY")
    LANGCHAIN_PROJECT: str = Field("desafio-get", env="LANGCHAIN_PROJECT")
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignora campos extras no .env

    def validate_keys(self) -> None:
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY \u00e9 obrigat\u00f3ria.")

settings = Settings()

# Criar os diretórios necessários
for folder in ["bds", "fonte_de_dados"]:
    os.makedirs(folder, exist_ok=True)
