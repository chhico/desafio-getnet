"""
tests/test_03_tools_and_internal.py
-----------------------------------
Bateria de Testes Automatizados para Ferramentas Internas e Infraestrutura:
1. Fast-Path Regex & Padrões Determinísticos
2. Crawler de Documentação & Parser HTML/Base64
3. Endpoint de Upload RAG Administrativo & Sanitização de Path Traversal
4. Enriquecimento de RAG, Deduplicação Vetorial e Tabelas SQLite
"""

import os
import io
import shutil
import base64
import sqlite3
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.agents.fast_path import check_fast_path
from backend.infrastructure.rag.crawler import (
    extract_links_from_html,
    is_url_in_scope,
    init_rag_db,
    check_all_urls_have_records,
    IGNORED_EXTENSIONS,
)
from backend.agents.tools.rag_tools import (
    sync_local_files_to_vectorstore,
    listar_topicos_disponiveis,
)
from backend.api.admin import DATA_DIR

client = TestClient(app)


# ============================================================================
# 1. FAST-PATH: PADRÕES DETERMINÍSTICOS E REGEX
# ============================================================================
class TestFastPathPatterns:
    """Testes dos padrões de regex e respostas instantâneas do fast_path.py."""

    @pytest.mark.parametrize("msg", [
        "oi", "Oi", "OI!", "olá", "Ola", "olá getnet", "oie", "opa",
        "bom dia", "Bom dia!", "boa tarde", "boa noite",
        "olá, tudo bem?", "oi tudo bem", "e aí", "eae"
    ])
    def test_greetings(self, msg: str):
        res = check_fast_path(msg)
        assert res is not None, f"Falha ao reconhecer saudação: '{msg}'"
        assert res["agent"] == "knowledge"
        assert res["category"] == "Saudação / Apresentação"
        assert "Olá! Sou o assistente virtual da Getnet" in res["response"]
        assert "Maquininhas e Taxas" in res["response"]

    @pytest.mark.parametrize("msg", [
        "obrigado", "Obrigada!", "muito obrigado", "valeu", "vlw",
        "tchau", "até mais", "até logo", "valeu, até mais", "abraço"
    ])
    def test_thanks_and_closing(self, msg: str):
        res = check_fast_path(msg)
        assert res is not None, f"Falha ao reconhecer agradecimento: '{msg}'"
        assert res["agent"] == "knowledge"
        assert res["category"] == "Agradecimento / Encerramento"
        assert "Por nada!" in res["response"] or "agradece o seu contato" in res["response"]

    @pytest.mark.parametrize("msg", [
        "ok", "Ok.", "beleza", "blz", "entendi", "perfeito", "certo", "show de bola", "combinado"
    ])
    def test_confirmations(self, msg: str):
        res = check_fast_path(msg)
        assert res is not None, f"Falha ao reconhecer confirmação: '{msg}'"
        assert res["agent"] == "knowledge"
        assert res["category"] == "Confirmação"
        assert "Combinado!" in res["response"]

    @pytest.mark.parametrize("msg", [
        "qual o telefone da getnet", "qual é o telefone da getnet?",
        "sac getnet", "0800 getnet", "ouvidoria getnet",
        "qual o whatsapp da getnet", "como ligar na getnet"
    ])
    def test_channels_faq(self, msg: str):
        res = check_fast_path(msg)
        assert res is not None, f"Falha ao reconhecer canais: '{msg}'"
        assert res["agent"] == "knowledge"
        assert res["category"] == "Canais de Atendimento"
        assert "4002-4000" in res["response"]
        assert "0800-648-8000" in res["response"]
        assert "site.getnet.com.br" in res["response"]

    @pytest.mark.parametrize("msg", [
        "Qual é a diferença entre a Get Clássica e a Get Smart?",
        "Como funciona o Pix na maquininha?",
        "Quero consultar minhas vendas de ontem",
        "Minha maquininha está dando erro 99",
        "Quero falar com um atendente humano agora",
        "123.456.789-00",
        "DROP TABLE usuarios;",
        "Qual a taxa de débito?",
    ])
    def test_negative_cases_should_not_trigger_fast_path(self, msg: str):
        res = check_fast_path(msg)
        assert res is None, f"Mensagem não deveria acionar fast-path: '{msg}'"


# ============================================================================
# 2. CRAWLER E EXTRAÇÃO DE LINKS
# ============================================================================
class TestCrawlerExtraction:
    """Testes unitários para extração de links e validação de escopo do crawler."""

    def test_extract_static_anchor_links(self):
        html = """
        <html>
            <body>
                <a href="/pt/suporte/faq">FAQ</a>
                <a href="/pt/suporte/artigo-1">Artigo 1</a>
                <a href="https://site.getnet.com.br/termos">Termos</a>
                <a href="javascript:void(0)">Ignorar</a>
                <a href="#ancora">Ancora</a>
            </body>
        </html>
        """
        links = extract_links_from_html(html, base_path="/pt/suporte")
        assert "/pt/suporte/faq" in links
        assert "/pt/suporte/artigo-1" in links
        assert "https://site.getnet.com.br/termos" in links
        assert "javascript:void(0)" not in links
        assert "#ancora" not in links

    def test_extract_base64_encoded_scripts(self):
        js_payload = """
        const cards = [
            { title: "Estorno", link: "/get-ajuda-estorno/o-que-e-chargeback/", btnLink: "/get-ajuda-estorno" },
            { title: "Pix", link: "/get-ajuda-pix/como-funciona/", btnLink: "/get-ajuda-pix" }
        ];
        """
        b64_encoded = base64.b64encode(js_payload.encode("utf-8")).decode("utf-8")
        html = f"""
        <html>
            <head>
                <script defer src="data:text/javascript;base64,{b64_encoded}"></script>
            </head>
            <body><div class="cards-container"></div></body>
        </html>
        """
        links = extract_links_from_html(html, base_path="/get-ajuda")
        assert "/get-ajuda-estorno/o-que-e-chargeback/" in links
        assert "/get-ajuda-pix/como-funciona/" in links

    def test_extract_inline_scripts(self):
        html = """
        <html>
            <body>
                <script>
                    const pages = [
                        { name: "Receba Já", link: "/get-ajuda-receba-ja/plano-de-recebimento-reduzido/" }
                    ];
                </script>
            </body>
        </html>
        """
        links = extract_links_from_html(html, base_path="/get-ajuda")
        assert "/get-ajuda-receba-ja/plano-de-recebimento-reduzido/" in links

    def test_is_url_in_scope_and_ignored_extensions(self):
        root_domain = "site.getnet.com.br"
        base_path = "/get-ajuda"

        assert is_url_in_scope("https://site.getnet.com.br/get-ajuda/", root_domain, base_path)
        assert is_url_in_scope("https://site.getnet.com.br/get-ajuda-pix/", root_domain, base_path)
        assert not is_url_in_scope("https://site.getnet.com.br/blog/", root_domain, base_path)
        assert not is_url_in_scope("https://outrodominio.com/get-ajuda", root_domain, base_path)

        for ext in [".png", ".jpg", ".pdf", ".zip", ".css", ".js"]:
            assert ext in IGNORED_EXTENSIONS


# ============================================================================
# 3. ENDPOINT DE UPLOAD RAG ADMINISTRATIVO
# ============================================================================
class TestAdminUploadEndpoint:
    """Valida o endpoint POST /api/v1/admin/upload-files-rag."""

    @pytest.fixture(autouse=True)
    def clean_test_files(self):
        test_files = [
            "teste_unitario_rag_1.txt",
            "teste_unitario_rag_2.md",
            "teste_unitario_rag_3.csv",
            "teste_unitario_invalido.exe",
            "teste_sobrescrever.txt",
            "teste_traversal.txt",
        ]
        yield
        for name in test_files:
            p = DATA_DIR / name
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def test_upload_single_valid_file(self):
        filename = "teste_unitario_rag_1.txt"
        content = b"Conteudo de teste para RAG Getnet."

        response = client.post(
            "/api/v1/admin/upload-files-rag",
            files=[("files", (filename, io.BytesIO(content), "text/plain"))]
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["total_saved"] == 1
        assert (DATA_DIR / filename).read_bytes() == content

    def test_upload_multiple_mixed_files(self):
        file_txt = ("teste_unitario_rag_2.md", io.BytesIO(b"# Manual RAG\nTexto"), "text/markdown")
        file_invalid = ("teste_unitario_invalido.exe", io.BytesIO(b"MZBINARY"), "application/octet-stream")

        response = client.post(
            "/api/v1/admin/upload-files-rag",
            files=[("files", file_txt), ("files", file_invalid)]
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_uploaded"] == 2
        assert data["total_saved"] == 1
        assert data["total_ignored"] == 1

    def test_directory_traversal_sanitization(self):
        malicious_name = "../../teste_traversal.txt"
        content = b"Conteudo seguro."

        response = client.post(
            "/api/v1/admin/upload-files-rag",
            files=[("files", (malicious_name, io.BytesIO(content), "text/plain"))]
        )
        assert response.status_code == 200
        data = response.json()
        assert data["saved_files"][0]["filename"] == "teste_traversal.txt"
        assert (DATA_DIR / "teste_traversal.txt").exists()


# ============================================================================
# 4. ENRIQUECIMENTO RAG, TABELAS SQLITE E DEDUPLICAÇÃO
# ============================================================================
class TestRAGEnrichmentAndTools:
    """Testes de banco SQLite, hashes e deduplicação do RAG."""

    @pytest.fixture(autouse=True)
    def setup_temp_env(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_db = os.path.join(self.test_dir, "test_rag_sync.sqlite")
        self.test_data_dir = os.path.join(self.test_dir, "test_fonte")
        os.makedirs(self.test_data_dir, exist_ok=True)
        yield
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_tables_creation(self):
        init_rag_db(self.test_db)
        assert os.path.exists(self.test_db)

        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()

        assert "simple_sync_hashes" in tables
        assert "url_sync_hashes" in tables

    def test_check_all_urls_have_records(self):
        init_rag_db(self.test_db)
        urls = [
            "https://www.getnet.eu/pt/suporte",
            "https://site.getnet.com.br/duvidas"
        ]

        all_present, missing = check_all_urls_have_records(urls=urls, db_path=self.test_db)
        assert not all_present
        assert len(missing) == 2

        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO url_sync_hashes (url, content_hash) VALUES (?, ?)",
            ("https://www.getnet.eu/pt/suporte/taxas", "hash123")
        )
        cur.execute(
            "INSERT INTO url_sync_hashes (url, content_hash) VALUES (?, ?)",
            ("https://site.getnet.com.br/duvidas", "hash456")
        )
        conn.commit()
        conn.close()

        all_present, missing = check_all_urls_have_records(urls=urls, db_path=self.test_db)
        assert all_present
        assert missing == []

    def test_local_file_deduplication_and_deletion(self):
        mock_vs = MagicMock()
        mock_vs.delete = MagicMock()
        mock_vs.add_documents = MagicMock()

        file_path = os.path.join(self.test_data_dir, "manual_teste.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Conteudo de teste para a Getnet com regras de taxas.")

        with patch("backend.core.config.settings.RAG_SYNC_DB_PATH", self.test_db):
            count = sync_local_files_to_vectorstore(mock_vs, force=False, data_dir=self.test_data_dir)
            assert count == 1
            assert not os.path.exists(file_path)

            # Re-upload com mesmo conteúdo: não deve readicionar
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("Conteudo de teste para a Getnet com regras de taxas.")

            mock_vs.add_documents.reset_mock()
            count2 = sync_local_files_to_vectorstore(mock_vs, force=False, data_dir=self.test_data_dir)
            assert count2 == 0
            assert not mock_vs.add_documents.called
            assert not os.path.exists(file_path)

    def test_listar_topicos_disponiveis_from_db(self):
        init_rag_db(self.test_db)
        conn = sqlite3.connect(self.test_db)
        cur = conn.cursor()
        cur.execute("INSERT INTO simple_sync_hashes (filename, hash) VALUES (?, ?)", ("Tarifa_Super.pdf", "hash_a"))
        cur.execute("INSERT INTO url_sync_hashes (url, content_hash) VALUES (?, ?)", ("https://www.getnet.eu/pt/suporte", "hash_b"))
        conn.commit()
        conn.close()

        with patch("backend.core.config.settings.RAG_SYNC_DB_PATH", self.test_db):
            resultado = listar_topicos_disponiveis.invoke({})
            assert "Tarifa_Super.pdf" in resultado
            assert "https://www.getnet.eu/pt/suporte" in resultado
