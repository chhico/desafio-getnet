import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Meta
    PROJECT_NAME: str = "desafio-get"
    VERSION: str = "2.0.0"
    
    # LLM & Agente
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    AGENT_MODEL: str = Field("gpt-4o-mini", env="AGENT_MODEL")
    ROUTER_MODEL: Optional[str] = Field(None, env="ROUTER_MODEL")
    SUPPORT_MODEL: Optional[str] = Field(None, env="SUPPORT_MODEL")
    KNOWLEDGE_MODEL: Optional[str] = Field(None, env="KNOWLEDGE_MODEL")
    ESCALATION_MODEL: Optional[str] = Field(None, env="ESCALATION_MODEL")
    AGENT_TEMPERATURE: float = Field(0.0, env="AGENT_TEMPERATURE")
    AGENT_MAX_ITERATIONS: int = Field(10, env="AGENT_MAX_ITERATIONS")

    def get_router_model(self) -> str:
        return self.ROUTER_MODEL or self.AGENT_MODEL

    def get_support_model(self) -> str:
        return self.SUPPORT_MODEL or self.AGENT_MODEL

    def get_knowledge_model(self) -> str:
        return self.KNOWLEDGE_MODEL or self.AGENT_MODEL

    def get_escalation_model(self) -> str:
        return self.ESCALATION_MODEL or self.AGENT_MODEL
    
    # Seguran\u00e7a (Removida conforme solicita\u00e7\u00e3o)
    # API_SECRET_KEY: str = Field(..., env="API_SECRET_KEY")
    # API_ADMIN_KEY: str = Field(..., env="API_ADMIN_KEY")

    # DB e Vector
    MEMORY_BACKEND: str = Field("sqlite", env="MEMORY_BACKEND")
    VECTOR_DB: str = Field("chroma", env="VECTOR_DB")
    CHROMA_PERSIST_DIR: str = Field("bds/chroma_db", env="CHROMA_PERSIST_DIR")
    CHECKPOINT_DB_PATH: str = Field("bds/checkpoints.sqlite", env="CHECKPOINT_DB_PATH")
    CONFIG_DB_PATH: str = Field("bds/config.db", env="CONFIG_DB_PATH")
    RAG_SYNC_DB_PATH: str = Field("bds/rag_sync.sqlite", env="RAG_SYNC_DB_PATH")
    RAG_SYNC_MODE: str = Field("simple", env="RAG_SYNC_MODE")
    RAG_ASYNC_URLS: str = Field("https://www.getnet.eu/pt/suporte, https://site.getnet.com.br/get-ajuda/", env="RAG_ASYNC_URLS")
    RAG_SYNC_URLS: str = Field("https://site.getnet.com.br/blog/", env="RAG_SYNC_URLS")
    RAG_CRAWLER_MAX_DEPTH: int = Field(2, env="RAG_CRAWLER_MAX_DEPTH")
    RAG_CRAWLER_MAX_PAGES: int = Field(100, env="RAG_CRAWLER_MAX_PAGES")
    RAG_WEB_SYNC_CRON: str = Field("0 3 * * *", env="RAG_WEB_SYNC_CRON")

    # LangChain / LangSmith Tracing
    LANGCHAIN_TRACING_V2: str = Field("false", env="LANGCHAIN_TRACING_V2")
    LANGSMITH_TRACING: Optional[str] = Field(None, env="LANGSMITH_TRACING")
    LANGCHAIN_API_KEY: str = Field("", env="LANGCHAIN_API_KEY")
    LANGSMITH_API_KEY: Optional[str] = Field(None, env="LANGSMITH_API_KEY")
    LANGCHAIN_PROJECT: str = Field("desafio-get", env="LANGCHAIN_PROJECT")
    LANGSMITH_PROJECT: Optional[str] = Field(None, env="LANGSMITH_PROJECT")
    LANGCHAIN_ENDPOINT: Optional[str] = Field("https://api.smith.langchain.com", env="LANGCHAIN_ENDPOINT")
    LANGSMITH_ENDPOINT: Optional[str] = Field(None, env="LANGSMITH_ENDPOINT")
    
    # Server Port
    PORT: int = Field(8001, env="PORT")

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignora campos extras no .env

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

