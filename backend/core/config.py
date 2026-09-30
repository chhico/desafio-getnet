import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Meta
    PROJECT_NAME: str = "desafio-get"
    VERSION: str = "2.0.0"
    
    # LLM & Agente
    OPENAI_API_KEY: str = Field(default="")
    AGENT_MODEL: str = "gpt-4o-mini"
    ROUTER_MODEL: Optional[str] = None
    SUPPORT_MODEL: Optional[str] = None
    KNOWLEDGE_MODEL: Optional[str] = None
    ESCALATION_MODEL: Optional[str] = None
    AGENT_TEMPERATURE: float = 0.0
    AGENT_MAX_ITERATIONS: int = 10

    def get_router_model(self) -> str:
        return self.ROUTER_MODEL or self.AGENT_MODEL

    def get_support_model(self) -> str:
        return self.SUPPORT_MODEL or self.AGENT_MODEL

    def get_knowledge_model(self) -> str:
        return self.KNOWLEDGE_MODEL or self.AGENT_MODEL

    def get_escalation_model(self) -> str:
        return self.ESCALATION_MODEL or self.AGENT_MODEL
    
    # Segurança (Removida conforme solicitação)
    # API_SECRET_KEY: str = Field(...)
    # API_ADMIN_KEY: str = Field(...)

    # DB e Vector
    MEMORY_BACKEND: str = "sqlite"
    VECTOR_DB: str = "chroma"
    CHROMA_PERSIST_DIR: str = "bds/chroma_db"
    CHECKPOINT_DB_PATH: str = "bds/checkpoints.sqlite"
    CONFIG_DB_PATH: str = "bds/config.db"
    RAG_SYNC_DB_PATH: str = "bds/rag_sync.sqlite"
    RAG_SYNC_MODE: str = "simple"
    RAG_ASYNC_URLS: str = "https://www.getnet.eu/pt/suporte, https://site.getnet.com.br/get-ajuda/"
    RAG_SYNC_URLS: str = "https://site.getnet.com.br/blog/"
    RAG_CRAWLER_MAX_DEPTH: int = 2
    RAG_CRAWLER_MAX_PAGES: int = 100
    RAG_WEB_SYNC_CRON: str = "0 3 * * *"

    # LangChain / LangSmith Tracing
    LANGCHAIN_TRACING_V2: str = "false"
    LANGSMITH_TRACING: Optional[str] = None
    LANGCHAIN_API_KEY: str = ""
    LANGSMITH_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "desafio-get"
    LANGSMITH_PROJECT: Optional[str] = None
    LANGCHAIN_ENDPOINT: Optional[str] = "https://api.smith.langchain.com"
    LANGSMITH_ENDPOINT: Optional[str] = None
    
    # Server Port
    PORT: int = 8001

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    def validate_keys(self) -> None:
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY é obrigatória.")

settings = Settings()

# Propaga automaticamente para o os.environ (mandatório para o LangChainTracer interceptar as execuções)
tracing_enabled = (settings.LANGCHAIN_TRACING_V2.lower() == "true") or (
    settings.LANGSMITH_TRACING and settings.LANGSMITH_TRACING.lower() == "true"
)
api_key = settings.LANGCHAIN_API_KEY or settings.LANGSMITH_API_KEY or ""
project = settings.LANGSMITH_PROJECT or settings.LANGCHAIN_PROJECT or "desafio-get"
endpoint = settings.LANGSMITH_ENDPOINT or settings.LANGCHAIN_ENDPOINT or "https://api.smith.langchain.com"

if tracing_enabled:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_TRACING"] = "true"
if api_key:
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGSMITH_API_KEY"] = api_key
if project:
    os.environ["LANGCHAIN_PROJECT"] = project
    os.environ["LANGSMITH_PROJECT"] = project
if endpoint:
    os.environ["LANGCHAIN_ENDPOINT"] = endpoint
    os.environ["LANGSMITH_ENDPOINT"] = endpoint

# Criar os diretórios necessários
for folder in ["bds", "fonte_de_dados"]:
    os.makedirs(folder, exist_ok=True)

