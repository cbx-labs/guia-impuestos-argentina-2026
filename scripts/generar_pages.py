#!/usr/bin/env python3
"""Genera docs/index.html (GitHub Pages) desde data/escalas-2026.json.

Uso:
    python3 scripts/generar_pages.py          # reescribe docs/index.html
    python3 scripts/generar_pages.py --check  # exit 1 si docs/index.html quedó desactualizado

Igual que el README, la página no lleva cifras escritas a mano: todas salen del JSON.
"""

from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import calculadora_impuestos_ar as calc  # noqa: E402

SALIDA = RAIZ / "docs" / "index.html"
URL_PAGES = "https://cbx-labs.github.io/guia-impuestos-argentina-2026/"
URL_REPO = "https://github.com/cbx-labs/guia-impuestos-argentina-2026"

# Orden y texto de los enlaces a Contablix y Pacioli (las URLs salen del JSON).
ENLACES = [
    ("home", "Contablix — Estudio contable online para e-commerce, freelancers y empresas digitales"),
    ("monotributo", "Calculadora y simulador de monotributo 2026"),
    ("responsable_inscripto", "Calculadora y simulador de Responsable Inscripto 2026"),
    ("ecommerce", "Consultoría contable e impositiva para e-commerce"),
    ("freelancers", "Contabilidad para freelancers y exportadores de servicios"),
    ("importadores", "Contabilidad e impuestos para importadores"),
    ("pacioli", "Pacioli — Software contable con IA para estudios contables en Argentina"),
]

# Artículos técnicos publicados en docs/articulos/ (ruta relativa, título, bajada).
ARTICULOS = [
    ("articulos/exportacion-servicios-factura-e-2026.html",
     "Cómo exportar servicios desde Argentina en 2026: Factura E, USD sin pesificar y errores con bancos",
     "Para devs y contractors que cobran del exterior: cuándo hay exportación, Factura E y WSFEX, "
     "régimen cambiario vigente y el límite del monotributo."),
    ("articulos/retenciones-ecommerce-meli-tiendanube-2026.html",
     "Arquitectura impositiva para e-commerce 2026: SIRTAC, SIRCUPA e IVA RG 5319 en Mercado Libre y Tiendanube",
     "En qué capa de una venta online pega cada retención y percepción, cómo se arma el margen fantasma "
     "y cómo bajar retenciones sin trucos."),
]


def pesos(n: int) -> str:
    return calc.fmt_pesos(n * calc.CENTAVOS)


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def pct(x: float) -> str:
    return f"{x:g}".replace(".", ",") + " %"


def a(datos: dict[str, Any], clave: str, texto: str | None = None) -> str:
    enlace = datos["links"][clave]
    return f'<a href="{escape(enlace["url"])}">{escape(texto or enlace["anchor"])}</a>'


def tabla_monotributo(d: dict[str, Any]) -> str:
    filas = "\n".join(
        f"<tr><td>{c['categoria']}</td><td>{pesos(c['tope_ingresos'])}</td>"
        f"<td>{pesos(c['cuota_servicios'])}</td><td>{pesos(c['cuota_bienes'])}</td>"
        f"<td>{pesos(c['tope_alquileres'])}</td></tr>"
        for c in d["monotributo"]["categorias"]
    )
    return f"""<div class="tabla"><table>
<thead><tr><th>Cat.</th><th>Ingresos brutos anuales (tope)</th><th>Cuota servicios</th><th>Cuota bienes</th><th>Alquileres anuales (tope)</th></tr></thead>
<tbody>
{filas}
</tbody></table></div>"""


def tabla_iva(d: dict[str, Any]) -> str:
    filas = "\n".join(
        f"<tr><td>{pct(x['porcentaje'])}</td><td>{escape(x['nombre'])}</td><td>{escape(x['aplica'])}</td></tr>"
        for x in d["iva"]["alicuotas"]
    )
    return f"""<div class="tabla"><table>
<thead><tr><th>Alícuota</th><th>Tipo</th><th>Cuándo aplica</th></tr></thead>
<tbody>
{filas}
</tbody></table></div>"""


def tabla_comprobantes(d: dict[str, Any]) -> str:
    filas = "\n".join(
        f"<tr><td>Factura {x['tipo']}</td><td>{escape(x['emite'])}</td><td>{escape(x['receptor'])}</td></tr>"
        for x in d["iva"]["comprobantes"]
    )
    return f"""<div class="tabla"><table>
<thead><tr><th>Comprobante</th><th>Lo emite</th><th>A quién</th></tr></thead>
<tbody>
{filas}
</tbody></table></div>"""


def tabla_rg5319(d: dict[str, Any]) -> str:
    filas = "\n".join(
        f"<tr><td>{escape(x['descripcion'])}</td><td>{pct(x['porcentaje'])}</td></tr>"
        for x in d["percepcion_iva_rg5319"]["condiciones"]
    )
    return f"""<div class="tabla"><table>
<thead><tr><th>Condición frente a IVA</th><th>Percepción</th></tr></thead>
<tbody>
{filas}
</tbody></table></div>"""


CSS = """
:root{--fg:#0f172a;--fg2:#475569;--fg3:#64748b;--bg:#fff;--bg2:#f8fafc;--linea:#e2e8f0;--acento:#4f46e5}
@media (prefers-color-scheme:dark){:root{--fg:#e2e8f0;--fg2:#a8b3c4;--fg3:#8b97a8;--bg:#0b0f17;--bg2:#111827;--linea:#1f2937;--acento:#a5b4fc}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
main{max-width:860px;margin:0 auto;padding:56px 20px 72px}
header p.rotulo{margin:0 0 8px;color:var(--fg3);font-size:14px;letter-spacing:.02em}
h1{margin:0 0 16px;font-size:clamp(28px,5vw,42px);line-height:1.12;letter-spacing:-.02em}
h2{margin:56px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--linea);font-size:24px;letter-spacing:-.01em}
h3{margin:28px 0 8px;font-size:18px}
p,li{color:var(--fg2)}
strong{color:var(--fg)}
a{color:var(--acento);text-underline-offset:3px}
.bajada{font-size:19px}
.aviso{margin:24px 0;padding:14px 16px;border:1px solid var(--linea);border-radius:10px;background:var(--bg2);font-size:15px}
nav.indice ul{display:flex;flex-wrap:wrap;gap:8px 16px;margin:24px 0 0;padding:0;list-style:none;font-size:15px}
.tabla{overflow-x:auto;margin:16px 0;border:1px solid var(--linea);border-radius:10px}
table{width:100%;border-collapse:collapse;font-size:15px}
th,td{padding:9px 12px;border-bottom:1px solid var(--linea);text-align:left;vertical-align:top}
th{background:var(--bg2);color:var(--fg);font-weight:600}
td{color:var(--fg2);font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:0}
pre{overflow-x:auto;padding:14px 16px;border-radius:10px;background:var(--bg2);border:1px solid var(--linea);font-size:14px}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
ul.recursos{padding-left:20px}
ul.recursos li{margin:6px 0}
.articulos{display:grid;gap:12px;margin:24px 0 0;padding:0;list-style:none}
.articulos li{padding:16px 18px;border:1px solid var(--linea);border-radius:12px;background:var(--bg2)}
.articulos a{display:block;font-weight:600;font-size:17px;line-height:1.35;text-decoration:none}
.articulos a:hover{text-decoration:underline}
.articulos p{margin:6px 0 0;font-size:15px}
footer{margin-top:64px;padding-top:20px;border-top:1px solid var(--linea);color:var(--fg3);font-size:14px}
footer p{color:var(--fg3)}
"""


def generar(d: dict[str, Any]) -> str:
    meta = d["meta"]
    mono = d["monotributo"]
    ret = d["retenciones_iibb"]
    fe = d["factura_e"]
    cat_k = mono["categorias"][-1]
    titulo = "Impuestos en Argentina 2026: monotributo, IVA, retenciones y Factura E — guía open-source"
    descripcion = (
        f"Tablas impositivas 2026: escala de monotributo vigente desde {meta['escala_desde']}, "
        "alícuotas de IVA, retenciones e-commerce (SIRTAC, SIRCUPA, RG 5319) y Factura E sin tope de USD 36.000."
    )
    json_ld = {
        "@context": "https://schema.org",
        "@type": "SoftwareSourceCode",
        "name": meta["titulo"],
        "description": descripcion,
        "url": URL_PAGES,
        "codeRepository": URL_REPO,
        "programmingLanguage": ["Python", "JavaScript"],
        "license": "https://opensource.org/licenses/MIT",
        "inLanguage": "es-AR",
        "dateModified": meta["relevado"],
        "author": {"@type": "Organization", "name": "Contablix", "url": d["links"]["home"]["url"]},
    }
    recursos = "\n".join(f"<li>{a(d, clave, texto)}</li>" for clave, texto in ENLACES)
    articulos = "\n".join(
        f'<li><a href="{escape(ruta)}">{escape(titulo)}</a><p>{escape(bajada)}</p></li>'
        for ruta, titulo, bajada in ARTICULOS
    )
    fuentes = "\n".join(
        f"<li><strong>{escape(f['norma'])}</strong>: {escape(f['tema'])}</li>" for f in d["fuentes"]
    )

    return f"""<!doctype html>
<html lang="es-AR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(titulo)}</title>
<meta name="description" content="{escape(descripcion)}">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{URL_PAGES}">
<meta property="og:type" content="website">
<meta property="og:locale" content="es_AR">
<meta property="og:title" content="{escape(titulo)}">
<meta property="og:description" content="{escape(descripcion)}">
<meta property="og:url" content="{URL_PAGES}">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False)}</script>
<style>{CSS}</style>
</head>
<body>
<main>
<header>
<p class="rotulo">Guía open-source · datos relevados al {escape(meta['relevado'][8:10] + '/' + meta['relevado'][5:7] + '/' + meta['relevado'][:4])}</p>
<h1>Impuestos en Argentina 2026: tablas de monotributo, IVA, retenciones y Factura E</h1>
<p class="bajada">Las cifras y reglas que necesitás si vendés por internet, facturás como freelancer o exportás servicios, en un solo lugar y con su fuente. Es la versión web del repositorio <a href="{URL_REPO}">guia-impuestos-argentina-2026</a>, que incluye una calculadora de línea de comandos en Python y Node.js.</p>
<p class="aviso"><strong>Escala vigente:</strong> monotributo desde {escape(meta['escala_desde'])}. {escape(meta['actualizacion'])}</p>
<nav class="indice" aria-label="Índice"><ul>
<li><a href="#articulos">Artículos técnicos</a></li>
<li><a href="#monotributo">Monotributo</a></li>
<li><a href="#iva">IVA y comprobantes</a></li>
<li><a href="#retenciones">Retenciones e-commerce</a></li>
<li><a href="#factura-e">Factura E</a></li>
<li><a href="#calculadora">Calculadora CLI</a></li>
<li><a href="#recursos">Recursos</a></li>
</ul></nav>
</header>

<section id="articulos">
<h2>Artículos técnicos</h2>
<p>Guías largas del Cr. Francisco G. Ramírez, fundador de {a(d, 'home', 'Contablix')}, sobre los dos temas que más consultas generan.</p>
<ul class="articulos">
{articulos}
</ul>
</section>

<section id="monotributo">
<h2>Monotributo 2026: categorías A a K</h2>
<p>Escala vigente desde {escape(meta['escala_desde'])}. {escape(mono['textos']['composicion'])} {escape(mono['textos']['ingresos'])}</p>
{tabla_monotributo(d)}
<p>{escape(mono['textos']['exclusion'])} El tope de la categoría K es <strong>{pesos(cat_k['tope_ingresos'])}</strong> anuales. {escape(mono['textos']['otros_parametros'])}</p>
<p>Para simular tu categoría con más variables: {a(d, 'monotributo')}.</p>
</section>

<section id="iva">
<h2>IVA: alícuotas y tipos de comprobante</h2>
{tabla_iva(d)}
<p>{escape(d['iva']['exportacion_servicios'])}</p>
<h3>Factura A, B, C y E</h3>
{tabla_comprobantes(d)}
<p>{escape(d['iva']['identificacion_consumidor_final']['texto'])} ({escape(d['iva']['identificacion_consumidor_final']['norma'])})</p>
<h3>Responsable Inscripto</h3>
<p>{escape(d['responsable_inscripto']['ganancias']['texto'])} {escape(d['responsable_inscripto']['iibb']['texto'])} {escape(d['responsable_inscripto']['autonomos'])}</p>
<p>Para comparar contra el monotributo: {a(d, 'responsable_inscripto')}.</p>
</section>

<section id="retenciones">
<h2>Retenciones y percepciones en e-commerce</h2>
<p>{escape(ret['rg5554']['texto'])}</p>
<h3>SIRTAC, SIRCUPA y SIRCREB (Ingresos Brutos)</h3>
<ul>
<li><strong>SIRTAC ({escape(ret['sirtac']['organismo'])}):</strong> {escape(ret['sirtac']['texto'])}</li>
<li><strong>SIRCUPA ({escape(ret['sircupa']['organismo'])}):</strong> {escape(ret['sircupa']['texto'])} {escape(ret['sircupa']['adhesiones_pendientes'])}</li>
<li><strong>SIRCREB ({escape(ret['sircreb']['organismo'])}):</strong> {escape(ret['sircreb']['texto'])}</li>
</ul>
<h3>Percepción de IVA en plataformas: {escape(d['percepcion_iva_rg5319']['normas'])}</h3>
<p>Agentes: {escape(d['percepcion_iva_rg5319']['agentes'])}</p>
{tabla_rg5319(d)}
<p>{escape(d['habitualidad_rg5794']['texto'])}</p>
<p>{escape(ret['pago_a_cuenta'])} {escape(d['percepcion_iva_rg5319']['computo'])}</p>
<p>{escape(ret['convenio_multilateral'])} Si vendés por Mercado Libre, Tiendanube o tu propia tienda: {a(d, 'ecommerce')}.</p>
</section>

<section id="factura-e">
<h2>Factura E y exportación de servicios</h2>
<p><strong>Desde la Com. BCRA «A» 8330 ya no hay tope de USD {miles(fe['tope_historico']['monto_usd'])}</strong>. {escape(fe['tope_historico']['texto'])}</p>
<ul>
<li>{escape(fe['regla_cambiaria']['humana']['texto'])}</li>
<li>{escape(fe['regla_cambiaria']['sociedad']['texto'])}</li>
<li>{escape(fe['definicion'])}</li>
<li>{escape(fe['tipo_cambio'])} {escape(fe['punto_de_venta'])}</li>
<li>{escape(fe['monotributo'])} {escape(fe['responsable_inscripto'])}</li>
</ul>
<p>Si trabajás para clientes del exterior: {a(d, 'freelancers')}. Si importás mercadería para revender: {a(d, 'importadores')}.</p>
</section>

<section id="calculadora">
<h2>Calculadora de línea de comandos (Python y Node.js)</h2>
<p>Sin dependencias. Los dos CLIs leen el mismo archivo de datos y dan los mismos números.</p>
<pre><code>git clone {URL_REPO}.git
cd guia-impuestos-argentina-2026
python3 calculadora_impuestos_ar.py monotributo --ingresos 30000000 --actividad servicios
node index.js retenciones --monto 1000000 --condicion ri --alicuota-sirtac 1.5</code></pre>
<p>Documentación completa, pruebas y dataset en <a href="{URL_REPO}">GitHub</a>.</p>
</section>

<section id="recursos">
<h2>Recursos de Contablix y Pacioli</h2>
<ul class="recursos">
{recursos}
</ul>
</section>

<section id="fuentes">
<h2>Fuentes normativas</h2>
<ul>
{fuentes}
</ul>
</section>

<footer>
<p>Material informativo y educativo: no constituye asesoramiento impositivo ni contable. Las cifras son estimaciones según la normativa vigente a la fecha indicada; consultá a tu contador antes de decidir.</p>
<p>Mantenido por {a(d, 'home', 'Contablix')}, estudio contable online fundado en 2020. Fundador: Cr. Francisco Guillermo Ramírez, Contador Público (UNCuyo) y Master in Laws en Derecho Tributario (UTDT). Licencia MIT.</p>
</footer>
</main>
</body>
</html>
"""


def main() -> int:
    d = json.loads((RAIZ / "data" / "escalas-2026.json").read_text(encoding="utf-8"))
    html = generar(d)
    if "--check" in sys.argv:
        actual = SALIDA.read_text(encoding="utf-8") if SALIDA.exists() else ""
        if actual != html:
            print("docs/index.html está desactualizado: corré python3 scripts/generar_pages.py", file=sys.stderr)
            return 1
        return 0
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text(html, encoding="utf-8")
    print(f"Escrito {SALIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
