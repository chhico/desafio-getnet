"""
tests/test_crawler.py
---------------------
Testes unitários para as novas funcionalidades do crawler:
1. Extração de links de tags <a> estáticas.
2. Extração de links de scripts com data URI Base64 (padrão Getnet).
3. Extração de links de scripts inline.
4. Validação de escopo de URL (subdiretório e rotas hifenizadas).
5. Exclusão de extensões estáticas (.png, .css, .pdf, etc.).
"""

import unittest
import base64
from backend.infrastructure.rag.crawler import (
    extract_links_from_html,
    is_url_in_scope,
    IGNORED_EXTENSIONS
)


class TestCrawlerLinkExtraction(unittest.TestCase):

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
        self.assertIn("/pt/suporte/faq", links)
        self.assertIn("/pt/suporte/artigo-1", links)
        self.assertIn("https://site.getnet.com.br/termos", links)
        self.assertNotIn("javascript:void(0)", links)
        self.assertNotIn("#ancora", links)

    def test_extract_base64_encoded_scripts(self):
        # Simula o payload exato da Getnet
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
            <body>
                <div class="cards-container"></div>
            </body>
        </html>
        """
        links = extract_links_from_html(html, base_path="/get-ajuda")
        self.assertIn("/get-ajuda-estorno/o-que-e-chargeback/", links)
        self.assertIn("/get-ajuda-estorno", links)
        self.assertIn("/get-ajuda-pix/como-funciona/", links)
        self.assertIn("/get-ajuda-pix", links)

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
        self.assertIn("/get-ajuda-receba-ja/plano-de-recebimento-reduzido/", links)

    def test_is_url_in_scope_directory_hierarchy(self):
        # Caso clássico: https://www.getnet.eu/pt/suporte
        root_domain = "www.getnet.eu"
        base_path = "/pt/suporte"

        self.assertTrue(is_url_in_scope("https://www.getnet.eu/pt/suporte", root_domain, base_path))
        self.assertTrue(is_url_in_scope("https://www.getnet.eu/pt/suporte/faq", root_domain, base_path))
        self.assertTrue(is_url_in_scope("https://www.getnet.eu/pt/suporte/artigo/123", root_domain, base_path))
        self.assertFalse(is_url_in_scope("https://www.getnet.eu/pt/empresa", root_domain, base_path))
        self.assertFalse(is_url_in_scope("https://outrodominio.com/pt/suporte", root_domain, base_path))

    def test_is_url_in_scope_hyphenated_prefix(self):
        # Caso Getnet Brasil: https://site.getnet.com.br/get-ajuda/
        root_domain = "site.getnet.com.br"
        base_path = "/get-ajuda"

        self.assertTrue(is_url_in_scope("https://site.getnet.com.br/get-ajuda/", root_domain, base_path))
        self.assertTrue(is_url_in_scope("https://site.getnet.com.br/get-ajuda-receba-ja/", root_domain, base_path))
        self.assertTrue(is_url_in_scope("https://site.getnet.com.br/get-ajuda-receba-ja/plano-de-recebimento-reduzido/", root_domain, base_path))
        self.assertTrue(is_url_in_scope("https://site.getnet.com.br/get-ajuda-pix/", root_domain, base_path))
        self.assertFalse(is_url_in_scope("https://site.getnet.com.br/blog/", root_domain, base_path))
        self.assertFalse(is_url_in_scope("https://site.getnet.com.br/login", root_domain, base_path))
        self.assertFalse(is_url_in_scope("https://site.getnet.com.br/ofertas", root_domain, base_path))

    def test_ignored_extensions(self):
        for ext in [".png", ".jpg", ".pdf", ".zip", ".css", ".js"]:
            self.assertIn(ext, IGNORED_EXTENSIONS)


if __name__ == "__main__":
    unittest.main()
