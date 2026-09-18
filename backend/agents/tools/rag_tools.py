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


def _sync_simple(docs, vectorstore, force: bool = False) -> int:
    """Sincronização manual via Hashes no SQLite."""
    import sqlite3
    import hashlib
    import os
    from collections import defaultdict
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    if not docs:
        print("[Modo Simple] Nenhum documento encontrado para indexação.")
        return 0

    os.makedirs("bds", exist_ok=True)
    conn = sqlite3.connect("bds/rag_sync.sqlite")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS simple_sync_hashes (filename TEXT PRIMARY KEY, hash TEXT)")
    
    # Agrupa docs por arquivo fonte físico
    docs_by_file = defaultdict(list)
    for doc in docs:
        filename = doc.metadata.get("source", "unknown")
        if filename != "unknown" and os.path.exists(filename):
            docs_by_file[filename].append(doc)

    files_to_index = []
    
    for filename, file_docs in docs_by_file.items():
        hasher = hashlib.md5()
        with open(filename, 'rb') as f:
            hasher.update(f.read())
        file_hash = hasher.hexdigest()
        
        cursor.execute("SELECT hash FROM simple_sync_hashes WHERE filename = ?", (filename,))
        row = cursor.fetchone()
        
        # Se force=True, ou se o arquivo é novo (row is None), ou se o hash mudou:
        if force or row is None or row[0] != file_hash:
            status = "Sobrescrevendo (force=True)" if force else ("Novo" if row is None else "Modificado")
            print(f"[Debug] Indexando [{status}] {filename} | DB Hash: {row[0] if row else 'None'} | Computado: {file_hash}")
            
            # Se for force=True ou se já existia, remove chunks antigos deste arquivo do vectorstore
            if row is not None or force:
                try:
                    vectorstore.delete(where={"source": filename})
                except Exception:
                    pass
            files_to_index.extend(file_docs)
            cursor.execute("INSERT OR REPLACE INTO simple_sync_hashes (filename, hash) VALUES (?, ?)", (filename, file_hash))
            
    conn.commit()
    conn.close()
    
    updated_files_count = len(set(d.metadata.get("source") for d in files_to_index))
    
    if files_to_index:
        print(f"[Modo Simple] Indexando {updated_files_count} arquivo(s) ({len(files_to_index)} seções/páginas)...")
        splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=80)
        chunks = splitter.split_documents(files_to_index)
        if chunks:
            vectorstore.add_documents(chunks)
        return updated_files_count
    else:
        print("[Modo Simple] Nenhum arquivo local precisou ser indexado (já atualizado).")
        return 0


def _sync_api(docs, vectorstore):
    """Sincronização Avançada usando LangChain Indexing API."""
    print("[Modo API] ALERTA: A API de indexação oficial (SQLRecordManager) foi descontinuada e removida")
    print("[Modo API] do pacote base na versão atual do Langchain (v1.2+) instalada neste ambiente.")
    print("[Modo API] Por favor, utilize RAG_SYNC_MODE=\"simple\" para a engine nativa via MD5, que")
    print("[Modo API] é mais rápida e não depende de pacotes legados.")
    return


def load_local_documents(data_dir: str = "fonte_de_dados"):
    """Carrega documentos físicos da pasta (.txt, .pdf, .docx)."""
    import os
    from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader, Docx2txtLoader
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        
    docs_txt = []
    docs_pdf = []
    docs_docx = []
    
    # Loader para .TXT (com fallback Latin-1)
    try:
        txt_loader = DirectoryLoader(data_dir, glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"}, show_progress=False)
        docs_txt.extend(txt_loader.load())
    except Exception:
        txt_loader = DirectoryLoader(data_dir, glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={"encoding": "latin-1"}, show_progress=False)
        docs_txt.extend(txt_loader.load())
    
    # Loader para .PDF
    pdf_loader = DirectoryLoader(data_dir, glob="**/*.pdf", loader_cls=PyPDFLoader, show_progress=False)
    docs_pdf.extend(pdf_loader.load())
    
    # Loader para .DOCX
    docx_loader = DirectoryLoader(data_dir, glob="**/*.docx", loader_cls=Docx2txtLoader, show_progress=False)
    docs_docx.extend(docx_loader.load())

    return docs_txt + docs_pdf + docs_docx


def sync_local_files_to_vectorstore(vectorstore, force: bool = False, data_dir: str = "fonte_de_dados") -> int:
    """Sincroniza os arquivos locais de data_dir no vectorstore com detecção de hash ou sobrescrita forçada."""
    docs = load_local_documents(data_dir=data_dir)
    return _sync_simple(docs, vectorstore, force=force)


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
    Lista os tópicos disponíveis na base de conhecimento interna.
    Use quando o usuário quiser saber quais assuntos estão documentados.
    """
    import os
    data_dir = "fonte_de_dados"
    if not os.path.exists(data_dir):
        return "Nenhum tópico disponível (pasta vazia)."
    
    try:
        files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
        if not files:
            return "Nenhum arquivo encontrado na fonte de dados."
            
        topicos = [f"• {f}" for f in files]
        return "📚 Arquivos disponíveis na base de conhecimento:\n" + "\n".join(topicos)
    except Exception as e:
        return f"Erro ao acessar fonte_de_dados: {e}"


RAG_TOOLS = [buscar_documentos, listar_topicos_disponiveis]
