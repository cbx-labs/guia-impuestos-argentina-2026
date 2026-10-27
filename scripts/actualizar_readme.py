#!/usr/bin/env python3
"""Regenera las tablas del README desde data/escalas-2026.json.

Uso:
    python3 scripts/actualizar_readme.py          # reescribe README.md
    python3 scripts/actualizar_readme.py --check  # exit 1 si el README quedó desactualizado

Cada tabla vive entre marcadores <!-- generado:NOMBRE --> y <!-- /generado:NOMBRE -->.
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import calculadora_impuestos_ar as calc  # noqa: E402

README = RAIZ / "README.md"


def _pesos(n: int) -> str:
    return calc.fmt_pesos(n * calc.CENTAVOS)


def _pct(valor: Any) -> str:
    return calc.fmt_pct(calc.parse_escalado(valor, 4))


def _tabla(encabezado: list[str], filas: list[list[str]], alineacion: list[str]) -> str:
    lineas = ["| " + " | ".join(encabezado) + " |", "|" + "|".join(alineacion) + "|"]
    lineas += ["| " + " | ".join(f) + " |" for f in filas]
    return "\n".join(lineas)


# Ejemplos de la CLI que se pegan en el README con su salida real (Python y Node imprimen lo mismo).
EJEMPLOS: dict[str, tuple[str, list[str]]] = {
    "ejemplo-monotributo": ("python3 calculadora_impuestos_ar.py",
                            ["monotributo", "--ingresos", "30000000", "--actividad", "servicios"]),
    "ejemplo-ri": ("node index.js",
                   ["ri", "--ventas-mensuales", "2000000", "--compras-con-iva", "500000",
                    "--alicuota-iibb", "3.5", "--autonomos", "50000"]),
    "ejemplo-retenciones": ("node index.js",
                            ["retenciones", "--monto", "100000", "--condicion", "ri",
                             "--alicuota-sirtac", "2", "--alicuota-sircupa", "0.5"]),
    "ejemplo-factura-e": ("python3 calculadora_impuestos_ar.py",
                          ["factura-e", "--usd", "2000", "--tc", "1450.5", "--persona", "humana",
                           "--ingresos-12m", "28000000", "--actividad", "servicios"]),
    "ejemplo-json": ("node index.js",
                     ["retenciones", "--monto", "250000", "--condicion", "mono", "--alicuota-sirtac", "2", "--json"]),
}


def _salida_cli(data: dict[str, Any], argv: list[str]) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        codigo = calc.ejecutar(argv, data)
    if codigo != 0:
        raise SystemExit(f"el ejemplo {argv} salió con código {codigo}")
    return buffer.getvalue().rstrip("\n")


def bloques(data: dict[str, Any]) -> dict[str, str]:
    mono = data["monotributo"]
    monotributo = _tabla(
        ["Cat.", "Ingresos brutos anuales (tope)", "Cuota mensual servicios", "Cuota mensual bienes",
         "Alquileres anuales (tope)"],
        [[c["categoria"], _pesos(c["tope_ingresos"]), _pesos(c["cuota_servicios"]), _pesos(c["cuota_bienes"]),
          _pesos(c["tope_alquileres"])] for c in mono["categorias"]],
        [":---:", "---:", "---:", "---:", "---:"],
    )
    monotributo += f"\n\n{mono['textos']['composicion']} Fuente: {mono['fuente']}. {data['meta']['vigencia']}"

    iva = _tabla(
        ["Alícuota", "Nombre", "Cuándo aplica"],
        [[_pct(a["porcentaje"]), a["nombre"], a["aplica"]] for a in data["iva"]["alicuotas"]],
        [":---:", "---", "---"],
    )

    comprobantes = _tabla(
        ["Tipo", "Quién la emite", "A quién"],
        [[f"Factura {c['tipo']}", c["emite"], c["receptor"]] for c in data["iva"]["comprobantes"]],
        [":---:", "---", "---"],
    )

    rg = data["percepcion_iva_rg5319"]
    rg5319 = _tabla(
        ["Tu situación frente a IVA", "Clave en la CLI", "Percepción"],
        [[c["descripcion"], f"`{c['clave']}`", _pct(c["porcentaje"])] for c in rg["condiciones"]],
        ["---", "---", ":---:"],
    )
    hab = data["habitualidad_rg5794"]
    rg5319 += "\n\n" + _tabla(
        ["Criterio de habitualidad (no categorizados)", "Umbral"],
        [
            ["Operaciones en un mes", f"{hab['operaciones_mes']} o más, por {_pesos(hab['monto_minimo_pesos'])} o más"],
            ["Operaciones por mes durante un cuatrimestre",
             f"{hab['operaciones_mes_cuatrimestre']} o más, por {_pesos(hab['monto_minimo_pesos'])} o más"],
            ["Bienes usados de uso personal (umbral de monto)", _pesos(hab["monto_usados_uso_personal_pesos"])],
        ],
        ["---", "---"],
    )
    rg5319 += f"\n\nNormas: {rg['normas']}; habitualidad: {hab['norma']}."

    fuentes = "\n".join(f"- **{f['norma']}**: {f['tema']}." for f in data["fuentes"])
    ejemplos = {
        nombre: f"```text\n$ {prog} {' '.join(argv)}\n{_salida_cli(data, argv)}\n```"
        for nombre, (prog, argv) in EJEMPLOS.items()
    }
    return {
        **ejemplos,
        "monotributo": monotributo,
        "iva": iva,
        "comprobantes": comprobantes,
        "rg5319": rg5319,
        "fuentes": fuentes,
    }


def aplicar(readme: str, data: dict[str, Any]) -> str:
    for nombre, contenido in bloques(data).items():
        patron = re.compile(
            rf"(<!-- generado:{nombre} -->\n)(?:.*?\n)?(<!-- /generado:{nombre} -->)", re.DOTALL
        )
        if not patron.search(readme):
            raise SystemExit(f"README.md no tiene los marcadores del bloque «{nombre}»")
        readme = patron.sub(lambda m: m.group(1) + contenido + "\n" + m.group(2), readme)
    return readme


def main(argv: list[str]) -> int:
    data = calc.cargar_datos()
    actual = README.read_text(encoding="utf-8")
    nuevo = aplicar(actual, data)
    if "--check" in argv:
        if nuevo != actual:
            print("README.md está desactualizado: corré python3 scripts/actualizar_readme.py", file=sys.stderr)
            return 1
        print("README.md sincronizado con data/escalas-2026.json")
        return 0
    README.write_text(nuevo, encoding="utf-8")
    print("README.md actualizado")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
