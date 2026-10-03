# ==============================================================================
# GETNET MULTI-AGENT CUSTOMER SUPPORT — DOCKERFILE
# Multi-stage build otimizado para produção, segurança e performance
# ==============================================================================

# Estágio 1: Builder e Instalação de Dependências
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Estágio 2: Runtime Final e Leve
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia pacotes e binários construídos do builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copia o código da aplicação
COPY . .

# Garante criação dos diretórios persistidos de banco de dados e arquivos locais
RUN mkdir -p /app/bds /app/fonte_de_dados /app/frontend

EXPOSE 8001

# Healthcheck interno do container
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8001/health || exit 1

# Comando padrão de inicialização do servidor ASGI
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
