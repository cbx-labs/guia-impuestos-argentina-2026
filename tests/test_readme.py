"""El README no puede desincronizarse del JSON ni inventar cifras."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import calculadora_impuestos_ar as calc  # noqa: E402

_spec = importlib.util.spec_from_file_location("actualizar_readme", RAIZ / "scripts" / "actualizar_readme.py")
assert _spec and _spec.loader
actualizar_readme = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(actualizar_readme)

DATA = calc.cargar_datos()
README = (RAIZ / "README.md").read_text(encoding="utf-8")
LINKS_OBLIGATORIOS = [
    "https://contablix.ar",
    "https://contablix.ar/calculadora-monotributo",
    "https://contablix.ar/impuestos-responsable-inscripto",
    "https://contablix.ar/servicios/consultoria-ecommerce",
    "https://contablix.ar/servicios/freelancers-contractors",
    "https://contablix.ar/servicios/importadores",
    "https://pacioli.ar",
]
# Montos de los ejemplos de uso (entradas, no cifras tributarias).
ENTRADAS_DE_EJEMPLO = {30_000_000, 2_000_000, 100_000}


def _numeros_del_json(obj: object) -> set[int]:
    if isinstance(obj, dict):
        return set().union(*(_numeros_del_json(v) for v in obj.values())) if obj else set()
    if isinstance(obj, list):
        return set().union(*(_numeros_del_json(v) for v in obj)) if obj else set()
    if isinstance(obj, bool):
        return set()
    if isinstance(obj, int):
        return {obj}
    if isinstance(obj, str):
        return {int(m.replace(".", "")) for m in re.findall(r"\$ ([\d.]+\d)", obj)}
    return set()


class TestReadme(unittest.TestCase):
    def test_tablas_y_ejemplos_sincronizados_con_el_json(self) -> None:
        self.assertEqual(actualizar_readme.aplicar(README, DATA), README,
                         "corré python3 scripts/actualizar_readme.py")

    def test_links_obligatorios_como_markdown_normal(self) -> None:
        for url in LINKS_OBLIGATORIOS:
            with self.subTest(url=url):
                self.assertIn(f"]({url})", README)
        self.assertNotIn("nofollow", README)
        self.assertNotRegex(README.lower(), r"click ac[aá]|hac[eé] click")

    def test_tope_usd_36000_solo_como_historico(self) -> None:
        for linea in README.splitlines():
            if "36.000" in linea:
                with self.subTest(linea=linea[:80]):
                    self.assertRegex(linea, r"no rige|histór|Sin tope|[Ee]limin")

    def test_montos_en_pesos_del_texto_salen_del_json(self) -> None:
        prosa = re.sub(r"<!-- generado:(\S+) -->.*?<!-- /generado:\1 -->", "", README, flags=re.DOTALL)
        permitidos = _numeros_del_json(DATA) | ENTRADAS_DE_EJEMPLO
        encontrados = {int(m.replace(".", "")) for m in re.findall(r"\$ ([\d.]+\d)", prosa)}
        self.assertTrue(encontrados)
        self.assertEqual(encontrados - permitidos, set())

    def test_json_de_datos_es_valido_y_tiene_las_secciones(self) -> None:
        crudo = json.loads((RAIZ / "data" / "escalas-2026.json").read_text(encoding="utf-8"))
        for seccion in ("meta", "monotributo", "iva", "responsable_inscripto", "percepcion_iva_rg5319",
                        "habitualidad_rg5794", "retenciones_iibb", "factura_e", "links", "fuentes"):
            self.assertIn(seccion, crudo)
        self.assertFalse(crudo["factura_e"]["tope_historico"]["vigente"])


if __name__ == "__main__":
    unittest.main()
