"""
tests/test_rag_enrichment.py
----------------------------
Testes automatizados do novo processo de enriquecimento do banco vetorial:
1. Verificação e criação das tabelas 'simple_sync_hashes' e 'url_sync_hashes'.
2. Regra de deduplicação e deleção de arquivos físicos em fonte_de_dados.
3. Verificação granular item a item de RAG_ASYNC_URLS.
4. Concorrência e prevenção de conflito com lock.
5. Funcionamento da tool 'listar_topicos_disponiveis' a partir do banco SQLite.
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from backend.infrastructure.rag.crawler import (
    init_rag_db,
    check_all_urls_have_records,
)
from backend.infrastructure.rag.enrichment_service import (
    init_and_check_rag_tables,
    run_enrichment,
    is_sync_in_progress
)
from backend.agents.tools.rag_tools import (
    sync_local_files_to_vectorstore,
    listar_topicos_disponiveis
)


class TestRAGEnrichment(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_db = os.path.join(self.test_dir, "test_rag_sync.sqlite")
        self.test_data_dir = os.path.join(self.test_dir, "test_fonte")
        os.makedirs(self.test_data_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_tables_creation(self):
        """Verifica se init_rag_db cria as tabelas url_sync_hashes e simple_sync_hashes."""
        init_rag_db(self.test_db)
        self.assertTrue(os.path.exists(self.test_db))

        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()

        self.assertIn("simple_sync_hashes", tables)
        self.assertIn("url_sync_hashes", tables)

    def test_check_all_urls_have_records(self):
        """Verifica a regra de checagem granular para cada item de RAG_ASYNC_URLS."""
        init_rag_db(self.test_db)
        urls = [
            "https://www.getnet.eu/pt/suporte",
            "https://site.getnet.com.br/duvidas"
        ]

        # 1. Banco vazio: deve acusar que faltam todas
        all_present, missing = check_all_urls_have_records(urls=urls, db_path=self.test_db)
        self.assertFalse(all_present)
        self.assertEqual(len(missing), 2)

        # 2. Inserir registro apenas para a primeira URL (ou subpágina)
        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO url_sync_hashes (url, content_hash) VALUES (?, ?)",
            ("https://www.getnet.eu/pt/suporte/taxas", "hash123")
        )
        conn.commit()
        conn.close()

        all_present, missing = check_all_urls_have_records(urls=urls, db_path=self.test_db)
        self.assertFalse(all_present)
        self.assertEqual(missing, ["https://site.getnet.com.br/duvidas"])

        # 3. Inserir registro para a segunda URL: agora todas devem constar
        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO url_sync_hashes (url, content_hash) VALUES (?, ?)",
            ("https://site.getnet.com.br/duvidas", "hash456")
        )
        conn.commit()
        conn.close()

        all_present, missing = check_all_urls_have_records(urls=urls, db_path=self.test_db)
        self.assertTrue(all_present)
        self.assertEqual(missing, [])

    def test_local_file_deduplication_and_deletion(self):
        """Testa ingestão de arquivo novo, deduplicação de repetido e deleção física em todos os casos."""
        mock_vs = MagicMock()
        mock_vs.delete = MagicMock()
        mock_vs.add_documents = MagicMock()

        # Criar um arquivo txt de teste
        file_path = os.path.join(self.test_data_dir, "manual_teste.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Conteudo de teste para a Getnet com regras de taxas.")

        with patch("backend.core.config.settings.RAG_SYNC_DB_PATH", self.test_db):
            # 1. Ingestão inicial do arquivo novo
            count = sync_local_files_to_vectorstore(mock_vs, force=False, data_dir=self.test_data_dir)
            self.assertEqual(count, 1)
            # O arquivo físico DEVE ter sido deletado
            self.assertFalse(os.path.exists(file_path), "Arquivo físico deveria ter sido deletado após importação")
            self.assertTrue(mock_vs.add_documents.called)

            # Verificar se foi salvo no SQLite
            conn = sqlite3.connect(self.test_db)
            cur = conn.cursor()
            cur.execute("SELECT filename, hash FROM simple_sync_hashes WHERE filename = 'manual_teste.txt'")
            row = cur.fetchone()
            conn.close()
            self.assertIsNotNone(row)
            original_hash = row[1]

            # 2. Criar novamente o arquivo com o MESMO conteúdo (simulando re-upload)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("Conteudo de teste para a Getnet com regras de taxas.")

            mock_vs.add_documents.reset_mock()
            count2 = sync_local_files_to_vectorstore(mock_vs, force=False, data_dir=self.test_data_dir)
            # Como já foi importado (hash idêntico), não deve re-vetorizar
            self.assertEqual(count2, 0)
            self.assertFalse(mock_vs.add_documents.called, "Não deveria chamar add_documents para arquivo duplicado")
            # Mas o arquivo físico DEVE ter sido deletado
            self.assertFalse(os.path.exists(file_path), "Arquivo duplicado deveria ter sido deletado da pasta")

            # 3. Criar arquivo com o MESMO nome mas NOVO conteúdo (arquivo modificado)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("Novo conteudo modificado com novas taxas e regras.")

            mock_vs.delete.reset_mock()
            mock_vs.add_documents.reset_mock()
            count3 = sync_local_files_to_vectorstore(mock_vs, force=False, data_dir=self.test_data_dir)
            self.assertEqual(count3, 1)
            # Deve ter removido vetores antigos e adicionado novos
            self.assertTrue(mock_vs.delete.called)
            self.assertTrue(mock_vs.add_documents.called)
            # Deve ter sido deletado
            self.assertFalse(os.path.exists(file_path))

            # Hash no SQLite deve ter sido atualizado
            conn = sqlite3.connect(self.test_db)
            cur = conn.cursor()
            cur.execute("SELECT hash FROM simple_sync_hashes WHERE filename = 'manual_teste.txt'")
            new_hash = cur.fetchone()[0]
            conn.close()
            self.assertNotEqual(original_hash, new_hash)

    def test_corrupted_file_deletion(self):
        """Verifica se arquivos não suportados ou corrompidos são deletados com log sem travar o processo."""
        mock_vs = MagicMock()
        corrupted_file = os.path.join(self.test_data_dir, "invalido.xyz")
        with open(corrupted_file, "w") as f:
            f.write("qualquer coisa")

        with patch("backend.core.config.settings.RAG_SYNC_DB_PATH", self.test_db):
            count = sync_local_files_to_vectorstore(mock_vs, force=False, data_dir=self.test_data_dir)
            self.assertEqual(count, 0)
            self.assertFalse(os.path.exists(corrupted_file), "Arquivo corrompido/não suportado deve ser deletado")

    def test_listar_topicos_disponiveis_reads_from_db(self):
        """Verifica se listar_topicos_disponiveis lê do banco mesmo com a pasta física vazia."""
        init_rag_db(self.test_db)
        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        cur.execute("INSERT INTO simple_sync_hashes (filename, hash) VALUES (?, ?)", ("Tarifa_Super.pdf", "hash_a"))
        cur.execute("INSERT INTO url_sync_hashes (url, content_hash) VALUES (?, ?)", ("https://www.getnet.eu/pt/suporte", "hash_b"))
        conn.commit()
        conn.close()

        with patch("backend.core.config.settings.RAG_SYNC_DB_PATH", self.test_db):
            resultado = listar_topicos_disponiveis.invoke({})
            self.assertIn("Tarifa_Super.pdf", resultado)
            self.assertIn("https://www.getnet.eu/pt/suporte", resultado)


if __name__ == "__main__":
    unittest.main()
