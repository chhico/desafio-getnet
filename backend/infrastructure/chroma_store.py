import os
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader, Docx2txtLoader
from backend.domain.interfaces import VectorStoreRepository
from backend.core.config import settings

# class ChromaStore(VectorStoreRepository):
#     def __init__(self, data_dir: str = "fonte_de_dados", persist_dir: str = settings.CHROMA_PERSIST_DIR):
#         self.data_dir = data_dir
#         self.persist_dir = persist_dir
#         self.embeddings = OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY)
#         self.vectorstore = self._init_vectorstore()
# 
#     def _init_vectorstore(self) -> Chroma:
#         if not os.path.exists(self.data_dir):
#             os.makedirs(self.data_dir, exist_ok=True)
# 
#         docs = self._load_documents()
#         
#         vs = Chroma(
#             persist_directory=self.persist_dir, 
#             embedding_function=self.embeddings
#         )
# 
#         if settings.RAG_SYNC_MODE == "simple":
#             self._sync_simple(docs, vs)
# 
#         return vs
# 
#     def _load_documents(self):
#         docs_txt = []
#         docs_pdf = []
#         docs_docx = []
# 
#         try:
#             txt_loader = DirectoryLoader(self.data_dir, glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"}, show_progress=False)
#             docs_txt.extend(txt_loader.load())
#         except Exception:
#             txt_loader = DirectoryLoader(self.data_dir, glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={"encoding": "latin-1"}, show_progress=False)
#             docs_txt.extend(txt_loader.load())
# 
#         pdf_loader = DirectoryLoader(self.data_dir, glob="**/*.pdf", loader_cls=PyPDFLoader, show_progress=False)
#         docs_pdf.extend(pdf_loader.load())
# 
#         docx_loader = DirectoryLoader(self.data_dir, glob="**/*.docx", loader_cls=Docx2txtLoader, show_progress=False)
#         docs_docx.extend(docx_loader.load())
# 
#         docs = docs_txt + docs_pdf + docs_docx
# 
#         if not docs:
#             from langchain_core.documents import Document
#             docs = [Document(page_content="Base de conhecimento vazia.", metadata={"source": "dummy.txt"})]
# 
#         return docs
# 
#     def _sync_simple(self, docs, vectorstore):
#         import sqlite3
#         import hashlib
#         
#         conn = sqlite3.connect("bds/rag_sync.sqlite")
#         cursor = conn.cursor()
#         cursor.execute("CREATE TABLE IF NOT EXISTS simple_sync_hashes (filename TEXT PRIMARY KEY, hash TEXT)")
#         
#         new_or_updated_docs = []
#         
#         for doc in docs:
#             filename = doc.metadata.get("source", "unknown")
#             if filename == "unknown" or not os.path.exists(filename):
#                 continue
#                 
#             hasher = hashlib.md5()
#             with open(filename, 'rb') as f:
#                 hasher.update(f.read())
#             file_hash = hasher.hexdigest()
#             
#             cursor.execute("SELECT hash FROM simple_sync_hashes WHERE filename = ?", (filename,))
#             row = cursor.fetchone()
#             
#             if row is None or row[0] != file_hash:
#                 new_or_updated_docs.append(doc)
#                 cursor.execute("INSERT OR REPLACE INTO simple_sync_hashes (filename, hash) VALUES (?, ?)", (filename, file_hash))
#                 
#         conn.commit()
#         conn.close()
#         
#         if new_or_updated_docs:
#             splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
#             chunks = splitter.split_documents(new_or_updated_docs)
#             if chunks:
#                 vectorstore.add_documents(chunks)
# 
#     def search_similar(self, query: str, context: Optional[str] = None) -> str:
#         k = 3
#         docs = self.vectorstore.similarity_search(query, k=k)
#         if not docs:
#             return "Nenhum documento relevante encontrado para esta consulta."
# 
#         resultados = []
#         for i, doc in enumerate(docs, 1):
#             resultados.append(f"📄 Trecho {i}:\n{doc.page_content}")
# 
#         return "\n\n".join(resultados)
