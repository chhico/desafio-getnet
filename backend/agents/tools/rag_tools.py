"""
tools/rag_tools.py
------------------
Ferramentas do RAG Agent (Retrieval-Augmented Generation).

RAG = buscar documentos relevantes + gerar resposta baseada neles.

Arquitetura:
1. Documentos são fragmentados em chunks
2. Chunks viram vetores numéricos (embeddings)
3. Na consulta, busca-se os chunks mais similares
4. O LLM responde usando esses chunks como contexto

Esta implementação usa FAISS (banco vetorial local, sem servidor).
Em produção, troque por Pinecone, Weaviate, pgvector ou similar.
"""

from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.core.config import settings

# ---------------------------------------------------------------------------
# Ingestão Dinâmica de Arquivos Locais
# ---------------------------------------------------------------------------

_vectorstore = None


def load_single_file_documents(file_path: str):
    """Carrega um arquivo individual (.pdf, .docx, .txt, etc.)."""
    import os
    ext = os.path.splitext(file_path)[1].lower()
    base_name = os.path.basename(file_path)

    if ext == ".pdf":
        from langchain_community.document_loaders import PyPDFLoader
        loader = PyPDFLoader(file_path)
        docs = loader.load()
    elif ext == ".docx":
        from langchain_community.document_loaders import Docx2txtLoader
        loader = Docx2txtLoader(file_path)
        docs = loader.load()
    elif ext in [".txt", ".md", ".csv", ".json", ".log"]:
        from langchain_community.document_loaders import TextLoader
        try:
            loader = TextLoader(file_path, encoding="utf-8")
            docs = loader.load()
        except Exception:
            loader = TextLoader(file_path, encoding="latin-1")
            docs = loader.load()
    else:
        raise ValueError(f"Formato de arquivo não suportado: '{ext}'")

    for doc in docs:
        doc.metadata["source"] = base_name
        doc.metadata["type"] = "local_file"

    return docs


def sync_local_files_to_vectorstore(vectorstore, force: bool = False, data_dir: str = "fonte_de_dados") -> int:
    """
    Processa arquivos locais em data_dir com deduplicação por hash MD5.
    Regras:
    - Se o hash já existir no SQLite, pula a vetorização e deleta o arquivo.
    - Se for um arquivo modificado (mesmo nome, hash diferente), remove vetores antigos, indexa e deleta.
    - Se for um arquivo novo, indexa e deleta o arquivo.
    - Se force=True, reindexa mesmo se o hash existir e deleta o arquivo.
    - Se o arquivo for corrompido/ilegível, gera log de erro e deleta o arquivo.
    - Se ocorrer erro de rede com a API da OpenAI na vetorização, mantém o arquivo para nova tentativa.
    """
    import os
    import hashlib
    import sqlite3
    import logging
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from backend.infrastructure.rag.crawler import init_rag_db

    logger = logging.getLogger(__name__)

    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        return 0

    files = [
        os.path.join(data_dir, f) for f in os.listdir(data_dir)
        if os.path.isfile(os.path.join(data_dir, f))
    ]

    if not files:
        logger.info(f"[Sync Local] Nenhum arquivo disponível na pasta '{data_dir}'.")
        return 0

    db_path = getattr(settings, "RAG_SYNC_DB_PATH", "bds/rag_sync.sqlite")
    init_rag_db(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    processed_count = 0
    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)

    for file_path in files:
        base_name = os.path.basename(file_path)
        logger.info(f"[Sync Local] Analisando arquivo: {base_name}")

        # 1. Calcular hash MD5 do conteúdo
        try:
            hasher = hashlib.md5()
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            file_hash = hasher.hexdigest()
        except Exception as e:
            logger.error(f"[Sync Local] Falha ao ler bytes de '{base_name}': {e}. Deletando arquivo corrompido.")
            try:
                os.remove(file_path)
            except Exception:
                pass
            continue

        # 2. Consultar registros na tabela simple_sync_hashes
        cursor.execute("SELECT filename, hash FROM simple_sync_hashes WHERE hash = ?", (file_hash,))
        hash_match = cursor.fetchone()

        cursor.execute("SELECT hash FROM simple_sync_hashes WHERE filename = ? OR filename = ?", (base_name, file_path))
        name_match = cursor.fetchone()

        # 3. Avaliar se o arquivo já foi importado (e force=False)
        if not force and hash_match is not None:
            logger.info(
                f"[Sync Local] Arquivo '{base_name}' já foi importado anteriormente "
                f"(hash {file_hash[:8]}... já registrado para '{hash_match[0]}'). "
                f"Pulando vetorização e deletando arquivo físico."
            )
            cursor.execute("INSERT OR REPLACE INTO simple_sync_hashes (filename, hash) VALUES (?, ?)", (base_name, file_hash))
            conn.commit()
            try:
                os.remove(file_path)
                logger.info(f"[Sync Local] Arquivo físico '{base_name}' deletado com sucesso.")
            except Exception as e:
                logger.warning(f"[Sync Local] Não foi possível deletar '{base_name}': {e}")
            continue

        # 4. Caso precise importar/reimportar:
        try:
            docs = load_single_file_documents(file_path)
        except Exception as e:
            logger.error(f"[Sync Local] Erro ao parsear arquivo '{base_name}': {e}. Deletando arquivo para evitar travamentos.")
            try:
                os.remove(file_path)
            except Exception:
                pass
            continue

        if not docs:
            logger.warning(f"[Sync Local] Arquivo '{base_name}' não possui conteúdo legível. Deletando arquivo.")
            try:
                os.remove(file_path)
            except Exception:
                pass
            continue

        # Remove chunks antigos caso existam
        if name_match is not None or force:
            logger.info(f"[Sync Local] Removendo vetores antigos do arquivo '{base_name}'...")
            try:
                vectorstore.delete(where={"source": base_name})
            except Exception:
                pass
            try:
                vectorstore.delete(where={"source": file_path})
            except Exception:
                pass

        # 5. Vetorização (OpenAI Embeddings -> ChromaDB)
        try:
            chunks = splitter.split_documents(docs)
            if chunks:
                vectorstore.add_documents(chunks)
                logger.info(f"[Sync Local] '{base_name}' vetorizado com sucesso: {len(chunks)} chunks gerados.")

            cursor.execute("INSERT OR REPLACE INTO simple_sync_hashes (filename, hash) VALUES (?, ?)", (base_name, file_hash))
            conn.commit()
            processed_count += 1

            # 6. Deleta arquivo com sucesso
            try:
                os.remove(file_path)
                logger.info(f"[Sync Local] Arquivo físico '{base_name}' deletado após importação bem-sucedida.")
            except Exception as e:
                logger.warning(f"[Sync Local] Não foi possível deletar '{base_name}': {e}")

        except Exception as e:
            logger.error(f"[Sync Local] Erro na vetorização/OpenAI para '{base_name}': {e}. Mantendo arquivo para nova tentativa.")

    conn.close()
    return processed_count


def _sync_simple(docs, vectorstore, force: bool = False) -> int:
    """Wrapper retrocompatível."""
    return sync_local_files_to_vectorstore(vectorstore, force=force)


def load_local_documents(data_dir: str = "fonte_de_dados"):
    """Carrega documentos físicos remanescentes na pasta (retrocompatibilidade)."""
    import os
    if not os.path.exists(data_dir):
        return []
    docs = []
    for f in os.listdir(data_dir):
        full = os.path.join(data_dir, f)
        if os.path.isfile(full):
            try:
                docs.extend(load_single_file_documents(full))
            except Exception:
                pass
    return docs


def _get_vectorstore():
    """Inicializa o vectorstore carregando os arquivos físicos."""
    global _vectorstore
    if _vectorstore is None:
        embeddings = OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY)
        
        # Roteamento do Vector DB e Sincronização
        if settings.VECTOR_DB == "chroma":
            from langchain_chroma import Chroma
            persist_dir = settings.CHROMA_PERSIST_DIR
            
            _vectorstore = Chroma(
                persist_directory=persist_dir, 
                embedding_function=embeddings
            )
            
            # Sincronizar o conteúdo usando as técnicas controladas por variável
            sync_mode = getattr(settings, "RAG_SYNC_MODE", "simple")
            if sync_mode == "simple":
                sync_local_files_to_vectorstore(_vectorstore, force=False)
            elif sync_mode == "api":
                docs = load_local_documents()
                _sync_api(docs, _vectorstore)
                
        else:
            # Fallback padrão FAISS (In-Memory)
            docs = load_local_documents()
            if not docs:
                from langchain_core.documents import Document
                docs = [Document(page_content="Base de conhecimento vazia.", metadata={"source": "dummy.txt"})]
            print("[FAISS] Modo In-Memory detectado. Vetorizando arquivos do zero...")
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            chunks = splitter.split_documents(docs)
            _vectorstore = FAISS.from_documents(chunks, embeddings)
            
    return _vectorstore


# ---------------------------------------------------------------------------
# Ferramentas
# ---------------------------------------------------------------------------

@tool
def buscar_documentos(query: str, num_resultados: int = 3) -> str:
    """
    Busca documentos internos relevantes para responder a pergunta.
    Use quando o usuário perguntar sobre políticas, procedimentos,
    manuais técnicos ou qualquer informação da base de conhecimento interna.

    Args:
        query: Pergunta ou termos de busca
        num_resultados: Número de documentos a retornar (padrão: 3)
    """
    try:
        vs = _get_vectorstore()
        docs = vs.similarity_search(query, k=num_resultados)
        if not docs:
            return "Nenhum documento relevante encontrado para esta consulta."

        resultados = []
        import os
        for i, doc in enumerate(docs, 1):
            raw_source = doc.metadata.get("source", "Base de Conhecimento")
            if raw_source.startswith("http://") or raw_source.startswith("https://"):
                source_label = f"🌐 URL: {raw_source}"
            elif raw_source != "Base de Conhecimento":
                source_label = f"📄 Arquivo: {os.path.basename(raw_source)}"
            else:
                source_label = "📄 Arquivo: Base de Conhecimento"
            resultados.append(f"Fonte [{source_label}] - Trecho {i}:\n{doc.page_content}")

        return "\n\n".join(resultados)
    except Exception as e:
        return f"Erro ao buscar documentos: {str(e)}"


@tool
def listar_topicos_disponiveis() -> str:
    """
    Lista os tópicos e documentos disponíveis na base de conhecimento interna.
    Use quando o usuário quiser saber quais assuntos, manuais ou páginas web estão documentados.
    """
    import os
    import sqlite3
    db_path = getattr(settings, "RAG_SYNC_DB_PATH", "bds/rag_sync.sqlite")

    arquivos = []
    urls = []

    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT filename FROM simple_sync_hashes ORDER BY filename ASC")
            arquivos = [os.path.basename(row[0]) for row in cur.fetchall()]

            cur.execute("SELECT url FROM url_sync_hashes ORDER BY url ASC")
            urls = [row[0] for row in cur.fetchall()]
            conn.close()
        except Exception as e:
            return f"Erro ao acessar base de conhecimento: {e}"

    # Complementa com eventuais arquivos na pasta física temporária
    data_dir = "fonte_de_dados"
    if os.path.exists(data_dir):
        try:
            fisicos = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
            for f in fisicos:
                if f not in arquivos:
                    arquivos.append(f)
        except Exception:
            pass

    if not arquivos and not urls:
        return "Nenhum documento ou página web indexado na base de conhecimento."

    linhas = ["📚 Base de Conhecimento Getnet:"]
    if arquivos:
        linhas.append("\n📄 Manuais e Documentos:")
        for a in arquivos:
            linhas.append(f"  • {a}")
    if urls:
        linhas.append("\n🌐 Páginas Oficiais Sincronizadas:")
        for u in urls[:15]:
            linhas.append(f"  • {u}")
        if len(urls) > 15:
            linhas.append(f"  • ... e mais {len(urls) - 15} subpáginas.")

    return "\n".join(linhas)


RAG_TOOLS = [buscar_documentos, listar_topicos_disponiveis]
