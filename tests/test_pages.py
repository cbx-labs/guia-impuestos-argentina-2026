"""La landing de GitHub Pages sale del JSON y enlaza los 7 destinos sin nofollow."""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("generar_pages", RAIZ / "scripts" / "generar_pages.py")
assert _spec and _spec.loader
generar_pages = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generar_pages)

HTML = (RAIZ / "docs" / "index.html").read_text(encoding="utf-8")


class TestPages(unittest.TestCase):
    def test_docs_index_esta_regenerado(self) -> None:
        datos = json.loads((RAIZ / "data" / "escalas-2026.json").read_text(encoding="utf-8"))
        self.assertEqual(HTML, generar_pages.generar(datos))

    def test_siete_enlaces_sin_nofollow(self) -> None:
        destinos = [
            "https://contablix.ar",
            "https://contablix.ar/calculadora-monotributo",
            "https://contablix.ar/impuestos-responsable-inscripto",
            "https://contablix.ar/servicios/consultoria-ecommerce",
            "https://contablix.ar/servicios/freelancers-contractors",
            "https://contablix.ar/servicios/importadores",
            "https://pacioli.ar",
        ]
        anclas = re.findall(r"<a [^>]*>", HTML)
        for url in destinos:
            with self.subTest(url=url):
                self.assertTrue(any(f'href="{url}"' in ancla for ancla in anclas))
        self.assertNotIn("nofollow", HTML)

    def test_canonical_propio(self) -> None:
        self.assertIn(f'<link rel="canonical" href="{generar_pages.URL_PAGES}">', HTML)


if __name__ == "__main__":
    unittest.main()
