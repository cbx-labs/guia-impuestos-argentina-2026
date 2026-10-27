#!/usr/bin/env python3
"""Calculadora open-source de impuestos en Argentina 2026.

Monotributo, Responsable Inscripto, retenciones e-commerce y Factura E.
Sin dependencias: Python 3.9+ y la biblioteca estándar.

Todas las cifras salen de data/escalas-2026.json (el mismo archivo que lee index.js).
Los montos se calculan en enteros (centavos) para que Python y Node den exactamente
los mismos números.

Mantenido por Contablix — https://contablix.ar
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

DATA_PATH = Path(__file__).resolve().parent / "data" / "escalas-2026.json"

CENTAVOS = 100  # montos: enteros en centavos (sufijo _c)
UNIDADES = 10_000  # porcentajes y tipo de cambio: enteros x 10.000 (sufijo _u); 1 % = 10.000
MONTO_MAXIMO_PESOS = 10**12  # límite de entrada para garantizar paridad exacta con Node

CONDICIONES_RG5319 = (
    "ri",
    "ri_ddjj_sin_presentar",
    "ri_sin_dfe",
    "ri_limitado",
    "mono_excedido",
    "mono",
    "no_categorizado",
)

Data = dict[str, Any]


# ---------------------------------------------------------------------------
# Números: parseo exacto, redondeo y formato argentino
# ---------------------------------------------------------------------------

_NUMERO_RE = re.compile(r"^(\d+)(?:[.,](\d+))?$")


def parse_escalado(texto: Any, decimales: int) -> int:
    """Convierte '1234,56' o '1234.56' en un entero escalado (redondeo mitad hacia arriba)."""
    s = str(texto).strip()
    m = _NUMERO_RE.match(s)
    if not m:
        raise ValueError(
            f"número inválido: {texto!r} (usá dígitos y, si hace falta, decimales con punto o coma; sin separador de miles)"
        )
    entero, frac = m.group(1), m.group(2) or ""
    conservados = (frac + "0" * decimales)[:decimales]
    valor = int(entero) * 10**decimales + int(conservados or "0")
    if len(frac) > decimales and frac[decimales] >= "5":
        valor += 1
    return valor


def div_redondeo(n: int, d: int) -> int:
    """División entera redondeando la mitad lejos de cero."""
    q, r = divmod(abs(n), d)
    if 2 * r >= d:
        q += 1
    return -q if n < 0 else q


def mul_div(a: int, b: int, d: int) -> int:
    return div_redondeo(a * b, d)


def pct_de(monto_c: int, alicuota_u: int) -> int:
    """Aplica una alícuota (en unidades de 1/10.000 %) a un monto en centavos."""
    return mul_div(monto_c, alicuota_u, 100 * UNIDADES)


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def fmt_monto(centavos: int, simbolo: str = "$") -> str:
    signo = "-" if centavos < 0 else ""
    entero, cent = divmod(abs(centavos), CENTAVOS)
    texto = _miles(entero)
    if cent:
        texto += f",{cent:02d}"
    return f"{signo}{simbolo} {texto}"


def fmt_pesos(centavos: int) -> str:
    return fmt_monto(centavos, "$")


def fmt_usd(centavos: int) -> str:
    return fmt_monto(centavos, "USD")


def fmt_unidades(unidades: int) -> str:
    """Número escalado x 10.000 con coma decimal y sin ceros sobrantes (35000 -> '3,5')."""
    signo = "-" if unidades < 0 else ""
    entero, dec = divmod(abs(unidades), UNIDADES)
    texto = _miles(entero)
    if dec:
        texto += "," + f"{dec:04d}".rstrip("0")
    return signo + texto


def fmt_tipo_cambio(unidades: int) -> str:
    """Tipo de cambio con dos decimales si alcanzan (1.450,50) o hasta cuatro si hacen falta."""
    if unidades % CENTAVOS == 0:
        return fmt_pesos(unidades // CENTAVOS)
    return f"$ {fmt_unidades(unidades)}"


def fmt_pct(unidades: int) -> str:
    return f"{fmt_unidades(unidades)} %"


def _numero_publico(valor: int, escala: int) -> int | float:
    return valor // escala if valor % escala == 0 else valor / escala


def a_publico(obj: Any) -> Any:
    """Convierte la representación interna (enteros escalados) a números para --json.

    Claves con sufijo _c: centavos -> pesos. Sufijo _u: x10.000 -> número.
    """
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for clave, valor in obj.items():
            if clave.endswith("_c"):
                out[clave[:-2]] = None if valor is None else _numero_publico(valor, CENTAVOS)
            elif clave.endswith("_u"):
                out[clave[:-2]] = None if valor is None else _numero_publico(valor, UNIDADES)
            else:
                out[clave] = a_publico(valor)
        return out
    if isinstance(obj, list):
        return [a_publico(x) for x in obj]
    return obj


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------


def cargar_datos(ruta: Path = DATA_PATH) -> Data:
    with ruta.open(encoding="utf-8") as fh:
        return json.load(fh)


def _sobre(data: Data, subcomando: str, entrada: dict[str, Any], resultado: dict[str, Any],
           notas: list[str], link: str) -> dict[str, Any]:
    return {
        "subcomando": subcomando,
        "datos": {
            "version": data["meta"]["version_datos"],
            "escala_desde": data["meta"]["escala_desde"],
        },
        "entrada": entrada,
        "resultado": resultado,
        "notas": notas,
        "link": data["links"][link],
    }


# ---------------------------------------------------------------------------
# Monotributo
# ---------------------------------------------------------------------------


def _indice_categoria(categorias: list[dict[str, Any]], valor_c: int, campo: str) -> Optional[int]:
    for i, cat in enumerate(categorias):
        if valor_c <= cat[campo] * CENTAVOS:
            return i
    return None


def _cuota_c(cat: dict[str, Any], actividad: str) -> int:
    return cat["cuota_servicios" if actividad == "servicios" else "cuota_bienes"] * CENTAVOS


def encuadrar(data: Data, ingresos_c: int, actividad: str) -> dict[str, Any]:
    """Categoría por ingresos brutos anuales (sin alquileres)."""
    categorias = data["monotributo"]["categorias"]
    i = _indice_categoria(categorias, ingresos_c, "tope_ingresos")
    if i is None:
        return {"categoria": None, "cuota_mensual_c": None, "excluido": True}
    cat = categorias[i]
    return {"categoria": cat["categoria"], "cuota_mensual_c": _cuota_c(cat, actividad), "excluido": False}


def calcular_monotributo(data: Data, ingresos_c: int, actividad: str,
                         alquileres_c: Optional[int] = None) -> dict[str, Any]:
    mono = data["monotributo"]
    categorias: list[dict[str, Any]] = mono["categorias"]
    ultima = categorias[-1]
    tope_k_c = ultima["tope_ingresos"] * CENTAVOS

    i_ing = _indice_categoria(categorias, ingresos_c, "tope_ingresos")
    i_alq = _indice_categoria(categorias, alquileres_c, "tope_alquileres") if alquileres_c is not None else None
    excluido_ing = i_ing is None
    excluido_alq = alquileres_c is not None and i_alq is None
    excluido = excluido_ing or excluido_alq

    resultado: dict[str, Any] = {
        "categoria": None,
        "excluido": excluido,
        "categoria_por_ingresos": categorias[i_ing]["categoria"] if i_ing is not None else None,
        "categoria_por_alquileres": categorias[i_alq]["categoria"] if i_alq is not None else None,
        "cuota_mensual_c": None,
        "tope_ingresos_categoria_c": None,
        "margen_al_tope_c": None,
        "margen_al_tope_pct_u": None,
        "siguiente_categoria": None,
        "tope_categoria_k_c": tope_k_c,
        "exceso_sobre_tope_k_c": ingresos_c - tope_k_c if excluido_ing else None,
        "alerta": None,
    }
    notas = [mono["textos"]["composicion"], mono["textos"]["otros_parametros"]]

    if excluido:
        motivos = []
        if excluido_ing:
            motivos.append(
                f"tus ingresos brutos superan en {fmt_pesos(ingresos_c - tope_k_c)} el tope de la categoría "
                f"{ultima['categoria']} ({fmt_pesos(tope_k_c)})"
            )
        if excluido_alq:
            motivos.append(
                f"tus alquileres superan el tope máximo de {fmt_pesos(ultima['tope_alquileres'] * CENTAVOS)}"
            )
        resultado["alerta"] = "ALERTA DE EXCLUSIÓN: " + " y ".join(motivos) + "."
        notas.insert(0, mono["textos"]["exclusion"])
    else:
        i = max(i_ing if i_ing is not None else 0, i_alq if i_alq is not None else 0)
        cat = categorias[i]
        tope_c = cat["tope_ingresos"] * CENTAVOS
        margen_c = tope_c - ingresos_c
        resultado["categoria"] = cat["categoria"]
        resultado["cuota_mensual_c"] = _cuota_c(cat, actividad)
        resultado["tope_ingresos_categoria_c"] = tope_c
        resultado["margen_al_tope_c"] = margen_c
        resultado["margen_al_tope_pct_u"] = mul_div(margen_c, 100 * 100, tope_c) * 100
        if i + 1 < len(categorias):
            sig = categorias[i + 1]
            resultado["siguiente_categoria"] = {
                "categoria": sig["categoria"],
                "tope_ingresos_c": sig["tope_ingresos"] * CENTAVOS,
                "cuota_mensual_c": _cuota_c(sig, actividad),
            }

    entrada = {"ingresos_anuales_c": ingresos_c, "actividad": actividad, "alquileres_anuales_c": alquileres_c}
    return _sobre(data, "monotributo", entrada, resultado, notas, "monotributo")


# ---------------------------------------------------------------------------
# Responsable Inscripto
# ---------------------------------------------------------------------------


def calcular_ri(data: Data, ventas_c: int, compras_c: int, alicuota_iibb_u: int, autonomos_c: int,
                alicuota_iva_ventas_u: int = 21 * UNIDADES,
                alicuota_iva_compras_u: int = 21 * UNIDADES) -> dict[str, Any]:
    ri = data["responsable_inscripto"]
    debito_c = pct_de(ventas_c, alicuota_iva_ventas_u)
    credito_c = pct_de(compras_c, alicuota_iva_compras_u)
    saldo_c = debito_c - credito_c
    iva_pagar_c = max(saldo_c, 0)
    iibb_c = pct_de(ventas_c, alicuota_iibb_u)
    resultado = {
        "iva_debito_c": debito_c,
        "iva_credito_c": credito_c,
        "saldo_iva_c": saldo_c,
        "iva_a_pagar_c": iva_pagar_c,
        "saldo_a_favor_iva_c": max(-saldo_c, 0),
        "iibb_c": iibb_c,
        "autonomos_c": autonomos_c,
        "subtotal_mensual_sin_ganancias_c": iva_pagar_c + iibb_c + autonomos_c,
        "ganancias_estimada": False,
        "ganancias_escala_min_pct_u": ri["ganancias"]["escala_min_pct"] * UNIDADES,
        "ganancias_escala_max_pct_u": ri["ganancias"]["escala_max_pct"] * UNIDADES,
    }
    notas = [ri["ganancias"]["texto"], ri["iibb"]["texto"], ri["autonomos"]]
    if autonomos_c == 0:
        notas.append("No informaste autónomos (--autonomos): el subtotal no los incluye.")
    notas.append(ri["referencia_simulador"]["texto"])
    entrada = {
        "ventas_netas_mensuales_c": ventas_c,
        "alicuota_iva_ventas_pct_u": alicuota_iva_ventas_u,
        "compras_netas_con_iva_c": compras_c,
        "alicuota_iva_compras_pct_u": alicuota_iva_compras_u,
        "alicuota_iibb_pct_u": alicuota_iibb_u,
        "autonomos_mensual_c": autonomos_c,
    }
    return _sobre(data, "ri", entrada, resultado, notas, "responsable_inscripto")


# ---------------------------------------------------------------------------
# Retenciones y percepciones e-commerce
# ---------------------------------------------------------------------------


def condicion_rg5319(data: Data, clave: str) -> dict[str, Any]:
    for cond in data["percepcion_iva_rg5319"]["condiciones"]:
        if cond["clave"] == clave:
            return cond
    raise ValueError(f"condición desconocida: {clave}")


def calcular_retenciones(data: Data, monto_c: int, condicion: str, alicuota_sirtac_u: int = 0,
                         alicuota_sircupa_u: int = 0) -> dict[str, Any]:
    ret = data["retenciones_iibb"]
    cond = condicion_rg5319(data, condicion)
    alicuota_iva_u = parse_escalado(cond["porcentaje"], 4)
    percepcion_c = pct_de(monto_c, alicuota_iva_u)
    sirtac_c = pct_de(monto_c, alicuota_sirtac_u)
    sircupa_c = pct_de(monto_c, alicuota_sircupa_u)
    total_c = percepcion_c + sirtac_c + sircupa_c
    resultado = {
        "condicion_descripcion": cond["descripcion"],
        "percepcion_iva_rg5319_pct_u": alicuota_iva_u,
        "percepcion_iva_rg5319_c": percepcion_c,
        "retencion_sirtac_c": sirtac_c,
        "retencion_sircupa_c": sircupa_c,
        "total_retenido_percibido_c": total_c,
        "neto_cobrado_c": monto_c - total_c,
    }
    notas = [ret["rg5554"]["texto"], ret["pago_a_cuenta"]]
    if condicion.startswith("ri"):
        notas.append(data["percepcion_iva_rg5319"]["computo"])
    if condicion == "no_categorizado":
        notas.append(data["habitualidad_rg5794"]["texto"])
    if condicion == "mono":
        notas.append(ret["comisiones"])
    notas.append(ret["base_calculo"])
    entrada = {
        "monto_c": monto_c,
        "condicion": condicion,
        "alicuota_sirtac_pct_u": alicuota_sirtac_u,
        "alicuota_sircupa_pct_u": alicuota_sircupa_u,
    }
    return _sobre(data, "retenciones", entrada, resultado, notas, "ecommerce")


# ---------------------------------------------------------------------------
# Factura E
# ---------------------------------------------------------------------------


def calcular_factura_e(data: Data, usd_c: int, tc_u: int, persona: str, ingresos_12m_c: int,
                       actividad: str, condicion: Optional[str] = None) -> dict[str, Any]:
    fe = data["factura_e"]
    if condicion is None:
        condicion = "monotributo" if persona == "humana" else "ri"
    if persona == "sociedad" and condicion == "monotributo":
        raise ValueError(fe["sociedad_monotributo"])

    pesos_c = mul_div(usd_c, tc_u, UNIDADES)
    impacto: Optional[dict[str, Any]] = None
    if condicion == "monotributo":
        antes = encuadrar(data, ingresos_12m_c, actividad)
        despues_ingresos_c = ingresos_12m_c + pesos_c
        despues = encuadrar(data, despues_ingresos_c, actividad)
        impacto = {
            "antes": {"ingresos_12m_c": ingresos_12m_c, **antes},
            "despues": {"ingresos_12m_c": despues_ingresos_c, **despues},
            "cambia_categoria": antes["categoria"] != despues["categoria"],
        }
    regla = fe["regla_cambiaria"][persona]
    tope = fe["tope_historico"]
    resultado = {
        "pesos_c": pesos_c,
        "impacto_monotributo": impacto,
        "regla_cambiaria": {"persona": persona, "normas": regla["normas"], "texto": regla["texto"]},
        "tope_historico_usd": {"monto": tope["monto_usd"], "vigente": tope["vigente"]},
    }
    notas = [fe["definicion"], fe["tipo_cambio"], fe["punto_de_venta"]]
    notas.append(fe["monotributo"] if condicion == "monotributo" else fe["responsable_inscripto"])
    notas.append(tope["texto"])
    if actividad == "bienes":
        notas.append(fe["bienes"])
    entrada = {
        "usd_c": usd_c,
        "tipo_cambio_u": tc_u,
        "persona": persona,
        "condicion": condicion,
        "ingresos_12m_c": ingresos_12m_c,
        "actividad": actividad,
    }
    return _sobre(data, "factura-e", entrada, resultado, notas, "freelancers")


# ---------------------------------------------------------------------------
# Salida de texto
# ---------------------------------------------------------------------------


def _bloque(titulo: str, filas: list[tuple[str, str]]) -> list[str]:
    ancho = max(len(etiqueta) for etiqueta, _ in filas) + 1
    return [titulo] + [f"  {(etiqueta + ':').ljust(ancho)}  {valor}" for etiqueta, valor in filas]


def _render_monotributo(s: dict[str, Any]) -> list[str]:
    e, r = s["entrada"], s["resultado"]
    filas = [("Ingresos brutos anuales", fmt_pesos(e["ingresos_anuales_c"]))]
    if e["alquileres_anuales_c"] is not None:
        filas.append(("Alquileres anuales", fmt_pesos(e["alquileres_anuales_c"])))
    filas.append(("Actividad", e["actividad"]))
    if e["alquileres_anuales_c"] is not None:
        filas.append(("Categoría por ingresos", r["categoria_por_ingresos"] or "fuera de escala"))
        filas.append(("Categoría por alquileres", r["categoria_por_alquileres"] or "fuera de escala"))
    if r["excluido"]:
        filas.append(("Categoría", "EXCLUIDO del monotributo"))
        if r["exceso_sobre_tope_k_c"] is not None:
            filas.append(("Exceso sobre el tope de K", fmt_pesos(r["exceso_sobre_tope_k_c"])))
    else:
        filas.append(("Categoría", r["categoria"]))
        filas.append(("Cuota mensual", fmt_pesos(r["cuota_mensual_c"])))
        filas.append((f"Tope de ingresos de {r['categoria']}", fmt_pesos(r["tope_ingresos_categoria_c"])))
        filas.append(("Margen al tope",
                      f"{fmt_pesos(r['margen_al_tope_c'])} ({fmt_pct(r['margen_al_tope_pct_u'])})"))
        sig = r["siguiente_categoria"]
        if sig is None:
            filas.append(("Siguiente categoría", "no hay: superar el tope de K es exclusión"))
        else:
            filas.append(("Siguiente categoría",
                          f"{sig['categoria']} · tope {fmt_pesos(sig['tope_ingresos_c'])}"
                          f" · cuota {fmt_pesos(sig['cuota_mensual_c'])}"))
    lineas = _bloque(f"Monotributo · escala vigente desde {s['datos']['escala_desde']}", filas)
    if r["alerta"]:
        lineas += ["", f"  {r['alerta']}"]
    return lineas


def _render_ri(s: dict[str, Any]) -> list[str]:
    e, r = s["entrada"], s["resultado"]
    filas = [
        ("Ventas netas del mes", fmt_pesos(e["ventas_netas_mensuales_c"])),
        (f"IVA débito ({fmt_pct(e['alicuota_iva_ventas_pct_u'])})", fmt_pesos(r["iva_debito_c"])),
        ("Compras netas con IVA discriminado", fmt_pesos(e["compras_netas_con_iva_c"])),
        (f"IVA crédito ({fmt_pct(e['alicuota_iva_compras_pct_u'])})", fmt_pesos(r["iva_credito_c"])),
    ]
    if r["saldo_iva_c"] >= 0:
        filas.append(("Saldo de IVA a pagar", fmt_pesos(r["iva_a_pagar_c"])))
    else:
        filas.append(("Saldo técnico a favor (IVA)", fmt_pesos(r["saldo_a_favor_iva_c"])))
    filas += [
        (f"IIBB ({fmt_pct(e['alicuota_iibb_pct_u'])} s/ ventas netas)", fmt_pesos(r["iibb_c"])),
        ("Autónomos", fmt_pesos(r["autonomos_c"])),
        ("Subtotal mensual sin Ganancias", fmt_pesos(r["subtotal_mensual_sin_ganancias_c"])),
        ("Ganancias", f"no se estima acá (escala anual {fmt_pct(r['ganancias_escala_min_pct_u'])}"
                      f" a {fmt_pct(r['ganancias_escala_max_pct_u'])}): usá el simulador"),
    ]
    return _bloque("Responsable Inscripto · estimación mensual", filas)


def _render_retenciones(s: dict[str, Any]) -> list[str]:
    e, r = s["entrada"], s["resultado"]
    filas = [
        ("Monto cobrado (base)", fmt_pesos(e["monto_c"])),
        ("Condición", r["condicion_descripcion"]),
        (f"Percepción IVA RG 5319 ({fmt_pct(r['percepcion_iva_rg5319_pct_u'])})",
         fmt_pesos(r["percepcion_iva_rg5319_c"])),
        (f"Retención IIBB SIRTAC ({fmt_pct(e['alicuota_sirtac_pct_u'])})", fmt_pesos(r["retencion_sirtac_c"])),
        (f"Retención IIBB SIRCUPA ({fmt_pct(e['alicuota_sircupa_pct_u'])})", fmt_pesos(r["retencion_sircupa_c"])),
        ("Total retenido y percibido", fmt_pesos(r["total_retenido_percibido_c"])),
        ("Neto cobrado", fmt_pesos(r["neto_cobrado_c"])),
    ]
    return _bloque("Retenciones y percepciones e-commerce · estimación por cobro", filas)


def _render_factura_e(s: dict[str, Any]) -> list[str]:
    e, r = s["entrada"], s["resultado"]
    filas = [
        ("Monto facturado", fmt_usd(e["usd_c"])),
        ("Tipo de cambio (BNA vendedor divisa)", fmt_tipo_cambio(e["tipo_cambio_u"])),
        ("Equivalente en pesos", fmt_pesos(r["pesos_c"])),
        ("Persona", e["persona"]),
        ("Condición", "monotributo" if e["condicion"] == "monotributo" else "Responsable Inscripto"),
    ]
    imp = r["impacto_monotributo"]
    if imp is not None:
        for etiqueta, lado in (("Ingresos 12 meses (antes)", imp["antes"]), ("Ingresos 12 meses (con esta factura)", imp["despues"])):
            if lado["excluido"]:
                encuadre = "EXCLUIDO (supera el tope de K)"
            else:
                encuadre = f"Cat. {lado['categoria']} · cuota {fmt_pesos(lado['cuota_mensual_c'])}"
            filas.append((etiqueta, f"{fmt_pesos(lado['ingresos_12m_c'])} → {encuadre}"))
        filas.append(("Cambia de categoría", "sí" if imp["cambia_categoria"] else "no"))
    lineas = _bloque("Factura E · exportación", filas)
    lineas += ["", f"  Régimen cambiario vigente: {r['regla_cambiaria']['texto']}"]
    return lineas


_RENDERERS = {
    "monotributo": _render_monotributo,
    "ri": _render_ri,
    "retenciones": _render_retenciones,
    "factura-e": _render_factura_e,
}


def render_texto(sobre: dict[str, Any]) -> str:
    lineas = _RENDERERS[sobre["subcomando"]](sobre)
    lineas.append("")
    lineas += [f"  - {nota}" for nota in sobre["notas"]]
    lineas.append("")
    lineas.append(f"→ {sobre['link']['anchor']}: {sobre['link']['url']}")
    return "\n".join(lineas)


def render_json(sobre: dict[str, Any]) -> str:
    return json.dumps(a_publico(sobre), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _monto(parser: argparse.ArgumentParser, nombre: str, valor: Optional[str]) -> Optional[int]:
    if valor is None:
        return None
    try:
        c = parse_escalado(valor, 2)
    except ValueError as exc:
        parser.error(f"{nombre}: {exc}")
    if c > MONTO_MAXIMO_PESOS * CENTAVOS:
        parser.error(f"{nombre}: monto fuera de rango")
    return c


def _porcentaje(parser: argparse.ArgumentParser, nombre: str, valor: str, maximo: int = 100) -> int:
    try:
        u = parse_escalado(valor, 4)
    except ValueError as exc:
        parser.error(f"{nombre}: {exc}")
    if u > maximo * UNIDADES:
        parser.error(f"{nombre}: la alícuota no puede superar {maximo} %")
    return u


def _tipo_cambio(parser: argparse.ArgumentParser, valor: str) -> int:
    try:
        u = parse_escalado(valor, 4)
    except ValueError as exc:
        parser.error(f"--tc: {exc}")
    if u == 0 or u > MONTO_MAXIMO_PESOS * UNIDADES:
        parser.error("--tc: el tipo de cambio tiene que ser mayor a 0 y razonable")
    return u


def construir_parser(data: Data) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="calculadora_impuestos_ar.py",
        description="Calculadora open-source de impuestos en Argentina 2026 (monotributo, RI, retenciones e-commerce, Factura E).",
        epilog=f"Datos: {data['meta']['vigencia']} Mantenido por {data['meta']['mantenido_por']}.",
    )
    comun = argparse.ArgumentParser(add_help=False)
    comun.add_argument("--json", action="store_true", help="salida en JSON (para scripts)")
    sub = parser.add_subparsers(dest="subcomando", required=True, metavar="SUBCOMANDO")

    p = sub.add_parser("monotributo", parents=[comun], help="categoría y cuota de monotributo")
    p.add_argument("--ingresos", required=True, help="ingresos brutos de los últimos 12 meses, en pesos")
    p.add_argument("--actividad", required=True, choices=("servicios", "bienes"))
    p.add_argument("--alquileres", help="(opcional) alquileres anuales devengados, en pesos")

    iva_choices = [fmt_unidades(parse_escalado(a["porcentaje"], 4)).replace(",", ".") for a in data["iva"]["alicuotas"]]
    p = sub.add_parser("ri", parents=[comun], help="estimación mensual de Responsable Inscripto")
    p.add_argument("--ventas-mensuales", required=True, help="ventas netas de IVA del mes, en pesos")
    p.add_argument("--compras-con-iva", default="0", help="compras netas (sin IVA) con IVA discriminado, en pesos")
    p.add_argument("--alicuota-iibb", required=True, help="alícuota de IIBB en %% (ej. 3.5)")
    p.add_argument("--autonomos", default="0", help="cuota mensual de autónomos de tu categoría, en pesos")
    p.add_argument("--alicuota-iva", default="21", choices=iva_choices, help="alícuota de IVA de tus ventas")
    p.add_argument("--alicuota-iva-compras", default="21", choices=iva_choices, help="alícuota de IVA de tus compras")

    p = sub.add_parser("retenciones", parents=[comun], help="percepción IVA RG 5319 + SIRTAC + SIRCUPA sobre un cobro")
    p.add_argument("--monto", required=True, help="monto del cobro, en pesos")
    p.add_argument("--condicion", required=True, choices=CONDICIONES_RG5319)
    p.add_argument("--alicuota-sirtac", default="0", help="alícuota SIRTAC del padrón en %% (0 si no te alcanza)")
    p.add_argument("--alicuota-sircupa", default="0", help="alícuota SIRCUPA del padrón en %% (0 si no te alcanza)")

    p = sub.add_parser("factura-e", parents=[comun], help="Factura E: pesos, impacto en monotributo y régimen cambiario")
    p.add_argument("--usd", required=True, help="monto facturado en dólares")
    p.add_argument("--tc", required=True, help="tipo de cambio BNA vendedor divisa del día hábil anterior")
    p.add_argument("--persona", default="humana", choices=("humana", "sociedad"))
    p.add_argument("--ingresos-12m", default="0", help="ingresos brutos de los últimos 12 meses antes de esta factura, en pesos")
    p.add_argument("--actividad", default="servicios", choices=("servicios", "bienes"))
    p.add_argument("--condicion", choices=("monotributo", "ri"),
                   help="monotributo o ri (por defecto: monotributo para persona humana, ri para sociedad)")
    return parser


def ejecutar(argv: Optional[list[str]] = None, data: Optional[Data] = None) -> int:
    data = data if data is not None else cargar_datos()
    parser = construir_parser(data)
    args = parser.parse_args(argv)

    try:
        if args.subcomando == "monotributo":
            sobre = calcular_monotributo(
                data, _monto(parser, "--ingresos", args.ingresos), args.actividad,
                _monto(parser, "--alquileres", args.alquileres),
            )
        elif args.subcomando == "ri":
            sobre = calcular_ri(
                data,
                _monto(parser, "--ventas-mensuales", args.ventas_mensuales),
                _monto(parser, "--compras-con-iva", args.compras_con_iva),
                _porcentaje(parser, "--alicuota-iibb", args.alicuota_iibb),
                _monto(parser, "--autonomos", args.autonomos),
                parse_escalado(args.alicuota_iva, 4),
                parse_escalado(args.alicuota_iva_compras, 4),
            )
        elif args.subcomando == "retenciones":
            maximo_sirtac = data["retenciones_iibb"]["sirtac"]["alicuota_maxima_pct"]
            sobre = calcular_retenciones(
                data,
                _monto(parser, "--monto", args.monto),
                args.condicion,
                _porcentaje(parser, "--alicuota-sirtac", args.alicuota_sirtac, maximo_sirtac),
                _porcentaje(parser, "--alicuota-sircupa", args.alicuota_sircupa),
            )
        else:
            sobre = calcular_factura_e(
                data,
                _monto(parser, "--usd", args.usd),
                _tipo_cambio(parser, args.tc),
                args.persona,
                _monto(parser, "--ingresos-12m", args.ingresos_12m),
                args.actividad,
                args.condicion,
            )
    except ValueError as exc:
        parser.error(str(exc))

    print(render_json(sobre) if args.json else render_texto(sobre))
    return 0


def main() -> None:
    sys.exit(ejecutar())


if __name__ == "__main__":
    main()
