"""
tests/test_admin_upload.py
--------------------------
Testes unitários e de integração para o endpoint:
POST /api/v1/admin/upload-files-rag
"""

import io
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.api.admin import DATA_DIR, ALLOWED_EXTENSIONS

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_test_files():
    """Garante limpeza de arquivos temporários de teste antes e depois dos testes."""
    test_files = [
        "teste_unitario_rag_1.txt",
        "teste_unitario_rag_2.md",
        "teste_unitario_rag_3.csv",
        "teste_unitario_invalido.exe",
        "teste_sobrescrever.txt",
        "teste_traversal.txt"
    ]
    yield
    for name in test_files:
        p = DATA_DIR / name
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


def test_upload_single_valid_file():
    """Valida upload de um único arquivo de texto válido."""
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
    assert data["total_ignored"] == 0
    assert len(data["saved_files"]) == 1
    assert data["saved_files"][0]["filename"] == filename

    # Verifica se arquivo realmente existe no disco
    saved_path = DATA_DIR / filename
    assert saved_path.exists()
    assert saved_path.read_bytes() == content


def test_upload_multiple_mixed_files_tolerant():
    """Valida upload de múltiplos arquivos com tolerância parcial a formatos inválidos."""
    file_txt = ("teste_unitario_rag_2.md", io.BytesIO(b"# Manual RAG\nTexto"), "text/markdown")
    file_csv = ("teste_unitario_rag_3.csv", io.BytesIO(b"col1,col2\nval1,val2"), "text/csv")
    file_invalid = ("teste_unitario_invalido.exe", io.BytesIO(b"MZBINARY"), "application/octet-stream")

    response = client.post(
        "/api/v1/admin/upload-files-rag",
        files=[
            ("files", file_txt),
            ("files", file_csv),
            ("files", file_invalid),
        ]
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_uploaded"] == 3
    assert data["total_saved"] == 2
    assert data["total_ignored"] == 1

    saved_names = [f["filename"] for f in data["saved_files"]]
    assert "teste_unitario_rag_2.md" in saved_names
    assert "teste_unitario_rag_3.csv" in saved_names

    ignored = data["ignored_files"][0]
    assert ignored["filename"] == "teste_unitario_invalido.exe"
    assert "não suportado" in ignored["reason"]


def test_upload_overwrite_false_behavior():
    """Valida que com overwrite=False, arquivo existente não é sobrescrito e é ignorado."""
    filename = "teste_sobrescrever.txt"
    original_content = b"Versao Original 1.0"
    new_content = b"Versao Nova 2.0"

    # 1. Cria primeiro upload
    resp1 = client.post(
        "/api/v1/admin/upload-files-rag?overwrite=true",
        files=[("files", (filename, io.BytesIO(original_content), "text/plain"))]
    )
    assert resp1.status_code == 200
    assert (DATA_DIR / filename).read_bytes() == original_content

    # 2. Tenta reenviar com overwrite=false
    resp2 = client.post(
        "/api/v1/admin/upload-files-rag?overwrite=false",
        files=[("files", (filename, io.BytesIO(new_content), "text/plain"))]
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total_saved"] == 0
    assert data2["total_ignored"] == 1
    assert "overwrite=False" in data2["ignored_files"][0]["reason"]
    # Garante que o conteúdo permaneceu inalterado
    assert (DATA_DIR / filename).read_bytes() == original_content

    # 3. Reenvia com overwrite=true
    resp3 = client.post(
        "/api/v1/admin/upload-files-rag?overwrite=true",
        files=[("files", (filename, io.BytesIO(new_content), "text/plain"))]
    )
    assert resp3.status_code == 200
    assert (DATA_DIR / filename).read_bytes() == new_content


def test_directory_traversal_sanitization():
    """Valida que caminhos maliciosos são sanitizados para o basename."""
    malicious_name = "../../teste_traversal.txt"
    content = b"Conteudo seguro."

    response = client.post(
        "/api/v1/admin/upload-files-rag",
        files=[("files", (malicious_name, io.BytesIO(content), "text/plain"))]
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_saved"] == 1
    assert data["saved_files"][0]["filename"] == "teste_traversal.txt"
    # O arquivo deve estar estritamente dentro de DATA_DIR
    assert (DATA_DIR / "teste_traversal.txt").exists()
