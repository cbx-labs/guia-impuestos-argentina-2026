# Guía y Calculadora Open-Source de Impuestos en Argentina 2026

**Monotributo, Responsable Inscripto, IIBB, retenciones e-commerce y Factura E**

[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-green.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](calculadora_impuestos_ar.py)
[![Node ≥ 18](https://img.shields.io/badge/node-%E2%89%A518-brightgreen.svg)](index.js)
[![Sin dependencias](https://img.shields.io/badge/dependencias-0-lightgrey.svg)](package.json)

Una referencia abierta y una calculadora de línea de comandos para entender cuánto pagás de impuestos en Argentina en 2026 si vendés por internet, facturás como freelancer o exportás servicios. Está pensada para developers, founders, sellers de e-commerce y freelancers que prefieren ver la regla y el número en el mismo lugar, sin vueltas.

- **Un único archivo de datos** ([`data/escalas-2026.json`](data/escalas-2026.json)) con la escala de monotributo, las alícuotas y las reglas vigentes. Lo leen los dos CLIs y lo podés usar como dataset.
- **Dos CLIs equivalentes**, en Python (sólo biblioteca estándar) y en Node (sin dependencias), con pruebas que verifican que den exactamente los mismos números.
- **Cada cifra tiene su fuente**: la norma o la página donde se publicó. Lo que no se puede reducir a un número fijo (Ganancias, autónomos, alícuotas de padrón) se explica y se pide como dato de entrada.

Lo mantiene [Contablix, estudio contable online para e-commerce, freelancers y empresas digitales](https://contablix.ar), y se actualiza cada vez que cambia la escala.

> **Datos vigentes:** escala de monotributo desde agosto 2026 (próxima actualización: febrero 2027). Normativa relevada al 27/10/2026.

## Índice

- [Quick start](#quick-start)
- [Monotributo 2026: categorías A a K](#monotributo-2026-categorías-a-a-k)
- [IVA: alícuotas 21 %, 10,5 % y 27 %](#iva-alícuotas-21--105--y-27-)
- [Tipos de comprobante: Factura A, B, C y E](#tipos-de-comprobante-factura-a-b-c-y-e)
- [Responsable Inscripto: qué pagás y cómo se calcula](#responsable-inscripto-qué-pagás-y-cómo-se-calcula)
- [Retenciones y percepciones en e-commerce](#retenciones-y-percepciones-en-e-commerce)
- [Factura E y exportación de servicios](#factura-e-y-exportación-de-servicios)
- [Qué no cubre esta calculadora](#qué-no-cubre-esta-calculadora)
- [Para contadores y estudios contables](#para-contadores-y-estudios-contables)
- [Uso como librería](#uso-como-librería)
- [Fuentes normativas](#fuentes-normativas)
- [Contribuir](#contribuir)
- [Descargo](#descargo)
- [Créditos / Mantenido por](#créditos--mantenido-por)

## Quick start

No hay nada que instalar: cloná el repo y corré cualquiera de los dos CLIs.

```bash
git clone https://github.com/cbx-labs/guia-impuestos-argentina-2026.git
cd guia-impuestos-argentina-2026

# Python 3.9+
python3 calculadora_impuestos_ar.py --help

# Node 18+
node index.js --help
# o instalado como comando global:
npm install -g . && calc-impuestos-ar --help
```

Hay cuatro subcomandos. Los montos van en pesos, sin separador de miles; los decimales, con punto o coma (`1450.5` o `1450,5`). Agregá `--json` a cualquiera para obtener salida para scripts.

| Subcomando | Para qué | Argumentos |
|---|---|---|
| `monotributo` | Categoría, cuota, margen al tope y alerta de exclusión | `--ingresos N --actividad servicios\|bienes [--alquileres N]` |
| `ri` | IVA débito/crédito/saldo, IIBB y autónomos de un mes | `--ventas-mensuales N --alicuota-iibb X [--compras-con-iva N] [--autonomos N] [--alicuota-iva 21\|10.5\|27] [--alicuota-iva-compras 21\|10.5\|27]` |
| `retenciones` | Percepción IVA RG 5319 + SIRTAC + SIRCUPA sobre un cobro | `--monto N --condicion ri\|ri_ddjj_sin_presentar\|ri_sin_dfe\|ri_limitado\|mono_excedido\|mono\|no_categorizado [--alicuota-sirtac X] [--alicuota-sircupa X]` |
| `factura-e` | Pesos al tipo de cambio, impacto en tu categoría y régimen cambiario | `--usd N --tc N [--persona humana\|sociedad] [--ingresos-12m N] [--actividad servicios\|bienes] [--condicion monotributo\|ri]` |

Estas son salidas reales (se regeneran desde el código con `scripts/actualizar_readme.py`, así que no pueden quedar viejas). Python y Node imprimen exactamente lo mismo.

**Monotributo** — ¿en qué categoría quedo con $ 30.000.000 de facturación anual en servicios?

<!-- generado:ejemplo-monotributo -->
```text
$ python3 calculadora_impuestos_ar.py monotributo --ingresos 30000000 --actividad servicios
Monotributo · escala vigente desde agosto 2026
  Ingresos brutos anuales:  $ 30.000.000
  Actividad:                servicios
  Categoría:                D
  Cuota mensual:            $ 84.613
  Tope de ingresos de D:    $ 30.628.651
  Margen al tope:           $ 628.651 (2,05 %)
  Siguiente categoría:      E · tope $ 36.028.231 · cuota $ 119.811

  - La cuota incluye impuesto integrado + aporte jubilatorio (SIPA) + obra social. Valores redondeados al peso.
  - La categoría también depende de la superficie afectada y la energía eléctrica consumida; esta calculadora modela ingresos brutos y, si lo informás, alquileres.

→ Calculadora y simulador de monotributo 2026: https://contablix.ar/calculadora-monotributo
```
<!-- /generado:ejemplo-monotributo -->

**Responsable Inscripto** — un mes con $ 2.000.000 de ventas netas:

<!-- generado:ejemplo-ri -->
```text
$ node index.js ri --ventas-mensuales 2000000 --compras-con-iva 500000 --alicuota-iibb 3.5 --autonomos 50000
Responsable Inscripto · estimación mensual
  Ventas netas del mes:                $ 2.000.000
  IVA débito (21 %):                   $ 420.000
  Compras netas con IVA discriminado:  $ 500.000
  IVA crédito (21 %):                  $ 105.000
  Saldo de IVA a pagar:                $ 315.000
  IIBB (3,5 % s/ ventas netas):        $ 70.000
  Autónomos:                           $ 50.000
  Subtotal mensual sin Ganancias:      $ 435.000
  Ganancias:                           no se estima acá (escala anual 5 % a 35 %): usá el simulador

  - Ganancias de persona humana: escala progresiva del 5 % al 35 % sobre la ganancia neta ANUAL, con anticipos. No se puede estimar con un mes de ventas: necesita la escala anual, deducciones y gastos del año.
  - Ingresos Brutos es provincial: servicios profesionales en CABA y PBA rondan el 3,5 % a 5 %; en el interior, entre 1 % y 4,5 %. Confirmá la alícuota de tu actividad y jurisdicción.
  - Autónomos es un monto fijo mensual que depende de tu categoría: la calculadora lo toma como dato de entrada.
  - Según el simulador de Contablix, $ 20.000.000 anuales en servicios equivalen a una carga total estimada de unos $ 760.000 por mes. Es una referencia, no una regla.

→ Simulador de impuestos Responsable Inscripto 2026: https://contablix.ar/impuestos-responsable-inscripto
```
<!-- /generado:ejemplo-ri -->

**Retenciones** — un cobro de $ 100.000 en una plataforma, siendo RI:

<!-- generado:ejemplo-retenciones -->
```text
$ node index.js retenciones --monto 100000 --condicion ri --alicuota-sirtac 2 --alicuota-sircupa 0.5
Retenciones y percepciones e-commerce · estimación por cobro
  Monto cobrado (base):            $ 100.000
  Condición:                       Responsable Inscripto sin incumplimientos
  Percepción IVA RG 5319 (1 %):    $ 1.000
  Retención IIBB SIRTAC (2 %):     $ 2.000
  Retención IIBB SIRCUPA (0,5 %):  $ 500
  Total retenido y percibido:      $ 3.500
  Neto cobrado:                    $ 96.500

  - Desde el 1/9/2024 no hay retenciones de IVA ni de Ganancias sobre cobros electrónicos (RG 5554/2024, que abrogó las RG 140, 4011 y 4622).
  - Todo lo retenido o percibido es pago a cuenta, no un costo: se computa en la DDJJ de IIBB (local o Convenio Multilateral, SIFERE WEB → «Carga de Deducciones») o en la de IVA en el caso de la percepción RG 5319.
  - El Responsable Inscripto la computa en la DDJJ de IVA del período o de los cinco siguientes; si queda saldo a favor persistente, corresponde pedir el certificado de exclusión (RG 2226).
  - Base de cálculo simplificada: se aplica cada alícuota sobre el monto informado. La base exacta y si un mismo cobro sufre SIRTAC y SIRCUPA a la vez dependen del régimen, del medio de cobro y del agente; si un régimen no te alcanza, poné su alícuota en 0.

→ Consultoría impositiva para e-commerce: https://contablix.ar/servicios/consultoria-ecommerce
```
<!-- /generado:ejemplo-retenciones -->

**Factura E** — una factura de USD 2.000 a un cliente del exterior, siendo monotributista:

<!-- generado:ejemplo-factura-e -->
```text
$ python3 calculadora_impuestos_ar.py factura-e --usd 2000 --tc 1450.5 --persona humana --ingresos-12m 28000000 --actividad servicios
Factura E · exportación
  Monto facturado:                       USD 2.000
  Tipo de cambio (BNA vendedor divisa):  $ 1.450,50
  Equivalente en pesos:                  $ 2.901.000
  Persona:                               humana
  Condición:                             monotributo
  Ingresos 12 meses (antes):             $ 28.000.000 → Cat. D · cuota $ 84.613
  Ingresos 12 meses (con esta factura):  $ 30.901.000 → Cat. E · cuota $ 119.811
  Cambia de categoría:                   sí

  Régimen cambiario vigente: Persona humana: no estás obligada a liquidar (pesificar) los cobros de exportación de servicios, sin límite de monto (Com. «A» 8330 del 18/9/2025; la Com. «A» 8417 del 9/4/2026 extendió la excepción a todos los conceptos de servicios). Condición: acreditarlos en una cuenta en moneda extranjera a tu nombre en una entidad local dentro de los 20 días hábiles del cobro (Com. «A» 8116). El banco no puede cobrarte comisión por esa acreditación (sólo trasladar cargos de bancos del exterior).

  - Exportación de servicios = el servicio se utiliza o explota efectivamente en el exterior. No alcanza con que el cliente sea extranjero.
  - Tipo de cambio vendedor divisa del Banco Nación del día hábil cambiario anterior (RG 5616/2024); Comprobantes en línea lo completa solo.
  - Necesitás un punto de venta específico de exportación (o WSFEX si facturás por web service).
  - El monotributista puede emitir Factura E; lo exportado SUMA a los ingresos brutos que definen la categoría.
  - Dato histórico: hasta septiembre de 2025 existía un tope de USD 36.000 anuales para que las personas humanas no liquidaran sus cobros de exportación de servicios. La Com. BCRA «A» 8330 (18/9/2025) lo eliminó: hoy no hay tope.

→ Contador para freelancers y contractors que exportan servicios: https://contablix.ar/servicios/freelancers-contractors
```
<!-- /generado:ejemplo-factura-e -->

**Salida JSON** — la misma lógica, para integrarla en tus scripts:

<details>
<summary>Ver ejemplo de <code>--json</code></summary>

<!-- generado:ejemplo-json -->
```text
$ node index.js retenciones --monto 250000 --condicion mono --alicuota-sirtac 2 --json
{
  "subcomando": "retenciones",
  "datos": {
    "version": "2026-08",
    "escala_desde": "agosto 2026"
  },
  "entrada": {
    "monto": 250000,
    "condicion": "mono",
    "alicuota_sirtac_pct": 2,
    "alicuota_sircupa_pct": 0
  },
  "resultado": {
    "condicion_descripcion": "Monotributista dentro de parámetros (no sufre la percepción)",
    "percepcion_iva_rg5319_pct": 0,
    "percepcion_iva_rg5319": 0,
    "retencion_sirtac": 5000,
    "retencion_sircupa": 0,
    "total_retenido_percibido": 5000,
    "neto_cobrado": 245000
  },
  "notas": [
    "Desde el 1/9/2024 no hay retenciones de IVA ni de Ganancias sobre cobros electrónicos (RG 5554/2024, que abrogó las RG 140, 4011 y 4622).",
    "Todo lo retenido o percibido es pago a cuenta, no un costo: se computa en la DDJJ de IIBB (local o Convenio Multilateral, SIFERE WEB → «Carga de Deducciones») o en la de IVA en el caso de la percepción RG 5319.",
    "Las comisiones de Mercado Libre llevan IVA: son crédito fiscal para el Responsable Inscripto y costo para el monotributista.",
    "Base de cálculo simplificada: se aplica cada alícuota sobre el monto informado. La base exacta y si un mismo cobro sufre SIRTAC y SIRCUPA a la vez dependen del régimen, del medio de cobro y del agente; si un régimen no te alcanza, poné su alícuota en 0."
  ],
  "link": {
    "url": "https://contablix.ar/servicios/consultoria-ecommerce",
    "anchor": "Consultoría impositiva para e-commerce"
  }
}
```
<!-- /generado:ejemplo-json -->

</details>

## Monotributo 2026: categorías A a K

Escala vigente desde agosto de 2026. Te encuadrás por tus **ingresos brutos de los últimos 12 meses** (todo lo facturado, incluida la exportación con Factura E). Si además alquilás el local, el tope de alquileres también define la categoría: quedás en la más alta de las dos.

<!-- generado:monotributo -->
| Cat. | Ingresos brutos anuales (tope) | Cuota mensual servicios | Cuota mensual bienes | Alquileres anuales (tope) |
|:---:|---:|---:|---:|---:|
| A | $ 12.009.410 | $ 49.527 | $ 49.527 | $ 2.792.886 |
| B | $ 17.595.183 | $ 56.379 | $ 56.379 | $ 2.792.886 |
| C | $ 24.670.494 | $ 66.020 | $ 64.531 | $ 3.816.944 |
| D | $ 30.628.651 | $ 84.613 | $ 82.565 | $ 3.816.944 |
| E | $ 36.028.231 | $ 119.811 | $ 108.268 | $ 4.841.003 |
| F | $ 45.151.659 | $ 150.784 | $ 129.931 | $ 4.841.003 |
| G | $ 53.995.799 | $ 230.313 | $ 158.815 | $ 5.771.965 |
| H | $ 81.924.660 | $ 522.707 | $ 317.895 | $ 8.378.658 |
| I | $ 91.699.762 | $ 963.748 | $ 474.993 | $ 8.378.658 |
| J | $ 105.012.519 | $ 1.167.300 | $ 580.794 | $ 8.378.658 |
| K | $ 126.610.839 | $ 1.614.446 | $ 702.103 | $ 8.378.658 |

La cuota incluye impuesto integrado + aporte jubilatorio (SIPA) + obra social. Valores redondeados al peso. Fuente: contablix.ar/calculadora-monotributo («Datos oficiales de ARCA»). Escala de monotributo vigente desde agosto 2026 hasta la próxima actualización (febrero 2027).
<!-- /generado:monotributo -->

Cómo leer la tabla:

- **Tope exacto = te quedás en la categoría.** Con $ 30.628.651 sos D; con un peso más, E. La calculadora trabaja al centavo.
- **Servicios vs. venta de bienes.** En A y B la cuota es la misma para las dos actividades; desde C, la de bienes es más baja. Elegí `--actividad bienes` si vendés productos (por ejemplo, en Mercado Libre o Tiendanube) y `servicios` si facturás horas o proyectos.
- **Actualización y recategorización.** La escala se actualiza en febrero y agosto (Ley 27.618, por IPC). Vos te recategorizás en enero y julio, con ventana hasta el 5 de febrero y el 5 de agosto.
- **Exclusión.** Superar el tope de K ($ 126.610.839) es exclusión de pleno derecho: pasás a Responsable Inscripto, con IVA y Ganancias. La CLI te avisa con una alerta y te dice por cuánto te pasaste.
- **Otros parámetros.** La categoría también depende de la superficie afectada y de la energía consumida; acá se modelan ingresos y alquileres.

Si querés simularlo con más variables o comparar escenarios, usá la [calculadora y simulador de monotributo 2026 de Contablix](https://contablix.ar/calculadora-monotributo).

## IVA: alícuotas 21 %, 10,5 % y 27 %

<!-- generado:iva -->
| Alícuota | Nombre | Cuándo aplica |
|:---:|---|---|
| 21 % | General | La regla: la mayoría de las ventas de bienes y prestaciones de servicios. |
| 10,5 % | Reducida | Ciertos bienes, construcción de vivienda, intereses y algunos alimentos. |
| 27 % | Incrementada | Servicios públicos (luz, gas, agua, telecomunicaciones) prestados a Responsables Inscriptos y a sujetos que no son consumidores finales. |
<!-- /generado:iva -->

- **Exportación de servicios:** va sin IVA; si sos Responsable Inscripto recuperás el IVA de las compras vinculadas (art. 43 de la Ley de IVA).
- **Identificación del consumidor final:** desde la RG 5700/2025, sólo tenés que identificar al consumidor final en operaciones desde $ 10.000.000.
- **El monotributista no cobra ni computa IVA:** el IVA de lo que compra (por ejemplo, las comisiones de Mercado Libre) es costo.

## Tipos de comprobante: Factura A, B, C y E

<!-- generado:comprobantes -->
| Tipo | Quién la emite | A quién |
|:---:|---|---|
| Factura A | Responsable Inscripto | Responsables Inscriptos y monotributistas (RG 5003) |
| Factura B | Responsable Inscripto | Consumidores finales y exentos |
| Factura C | Monotributista | Cualquier cliente del país (no discrimina IVA) |
| Factura E | Responsable Inscripto o monotributista | Clientes del exterior (exportación) |
<!-- /generado:comprobantes -->

## Responsable Inscripto: qué pagás y cómo se calcula

Acá no hay una tabla única de cuotas: la carga depende de tus márgenes, tu provincia y tu categoría de autónomos. Por eso la CLI calcula lo que se puede calcular con un mes de datos (IVA e IIBB) y te pide el resto.

| Impuesto | Cómo se calcula | Periodicidad | En la CLI |
|---|---|---|---|
| **IVA** | Débito fiscal (ventas × alícuota) − crédito fiscal (compras con IVA discriminado × alícuota) | Mensual | Se calcula |
| **Ganancias** (persona humana) | Escala progresiva del 5 % al 35 % sobre la ganancia neta **anual**, con anticipos | Anual + anticipos | No se estima: necesita la escala anual, deducciones y gastos del año |
| **Ingresos Brutos** | Alícuota provincial sobre ventas netas. Servicios profesionales en CABA y PBA: ~3,5 % a 5 %; interior: ~1 % a 4,5 % | Mensual | Se calcula con tu alícuota (`--alicuota-iibb`) |
| **Autónomos** | Monto fijo mensual según tu categoría | Mensual | Lo cargás vos (`--autonomos`) |

Como orden de magnitud, según el simulador de Contablix, $ 20.000.000 anuales en servicios equivalen a una carga total estimada de unos $ 760.000 por mes. Es una referencia, no una regla: tus números pueden ser muy distintos.

Para sumar Ganancias con la escala anual y comparar contra el monotributo, usá el [simulador de impuestos Responsable Inscripto 2026](https://contablix.ar/impuestos-responsable-inscripto).

## Retenciones y percepciones en e-commerce

Si vendés por Mercado Libre, cobrás con Mercado Pago o tenés tienda propia en Tiendanube, una parte de cada cobro no te llega. Casi todo es **pago a cuenta**: plata que después descontás de tus impuestos, no un costo, siempre que la computes.

| Régimen | Qué alcanza | Quién lo administra | Alícuota | Estado |
|---|---|---|---|---|
| **RG 5554/2024** | Retenciones de IVA y Ganancias sobre cobros electrónicos | ARCA | — | **Ya NO se retiene** desde el 1/9/2024 (abrogó las RG 140, 4011 y 4622) |
| **SIRTAC** | IIBB sobre cobros con tarjeta, QR y medios de pago liquidados | COMARB | Según padrón mensual de tu CUIT (hasta 5 %) | Vigente |
| **SIRCUPA** | IIBB sobre acreditaciones en cuentas de pago (CVU, como Mercado Pago) | COMARB | Según padrón; sin mínimo nacional | Vigente. CABA, Santa Fe y La Pampa anunciaron adhesión, sin norma ni fecha publicada al 22/10/2026 |
| **SIRCREB** | IIBB sobre acreditaciones bancarias (CBU) | COMARB | Según padrón | Vigente |
| **RG 5319/2023** (mod. RG 5794/2025) | Percepción de IVA en plataformas como Mercado Libre | ARCA | Según tu situación (tabla de abajo) | Vigente; alícuotas nuevas desde el 1/12/2025 |

SIRCUPA no alcanza, entre otras, las transferencias entre cuentas propias, los sueldos ni las transferencias del exterior.

### Percepción de IVA RG 5319: alícuota según tu situación

<!-- generado:rg5319 -->
| Tu situación frente a IVA | Clave en la CLI | Percepción |
|---|---|:---:|
| Responsable Inscripto sin incumplimientos | `ri` | 1 % |
| Responsable Inscripto con DDJJ sin presentar | `ri_ddjj_sin_presentar` | 3 % |
| Responsable Inscripto sin domicilio fiscal electrónico | `ri_sin_dfe` | 5 % |
| Responsable Inscripto con CUIT limitada, SIPER D o E, o factura M | `ri_limitado` | 7 % |
| Monotributista que excede los parámetros de su categoría | `mono_excedido` | 7 % |
| Monotributista dentro de parámetros (no sufre la percepción) | `mono` | 0 % |
| No categorizado con habitualidad | `no_categorizado` | 8 % |

| Criterio de habitualidad (no categorizados) | Umbral |
|---|---|
| Operaciones en un mes | 10 o más, por $ 750.000 o más |
| Operaciones por mes durante un cuatrimestre | 4 o más, por $ 750.000 o más |
| Bienes usados de uso personal (umbral de monto) | $ 1.500.000 |

Normas: RG 5319/2023, modificada por RG 5794/2025 (desde el 1/12/2025); habitualidad: RG 5794/2025.
<!-- /generado:rg5319 -->

### Cómo recuperar lo retenido

- **IIBB (SIRTAC, SIRCUPA, SIRCREB):** se computa en tu declaración de IIBB, local o de Convenio Multilateral (SIFERE WEB → «Carga de Deducciones»).
- **Percepción de IVA:** si sos RI, la computás en la DDJJ de IVA del período o de los cinco siguientes. Si te queda saldo a favor de forma persistente, corresponde pedir el certificado de exclusión (RG 2226).
- **Retenciones indebidas en PBA:** con la RN 25/2025 de ARBA tenés 90 días para pedir la devolución a la billetera.
- **Vendés a varias provincias:** IIBB va por Convenio Multilateral, y la RG CA 5/2021 da sustento territorial en la provincia del comprador por presencia digital.

Si te descuentan más de lo que te corresponde o no sabés en qué padrón estás, una [consultoría impositiva para e-commerce](https://contablix.ar/servicios/consultoria-ecommerce) suele pagarse sola con lo que recuperás.

## Factura E y exportación de servicios

**Qué es exportar servicios:** el servicio se utiliza o explota efectivamente en el exterior. No alcanza con que el cliente sea extranjero.

- **Tipo de cambio:** vendedor divisa del Banco Nación del día hábil cambiario anterior (RG 5616/2024). Comprobantes en línea lo completa solo.
- **Punto de venta:** necesitás uno específico de exportación (o WSFEX si facturás por web service).
- **Monotributo:** podés emitir Factura E, pero lo exportado **suma** a los ingresos que definen tu categoría. El subcomando `factura-e` te muestra si esa factura te hace subir de categoría o te deja afuera.
- **Responsable Inscripto:** la exportación va sin IVA y recuperás el IVA de las compras vinculadas (art. 43).

### El tope de USD 36.000 ya no rige

| Tema | Hasta septiembre de 2025 (histórico) | Régimen vigente |
|---|---|---|
| Persona humana | Tope de USD 36.000 anuales para no liquidar los cobros de exportación de servicios | **Sin tope.** La Com. BCRA «A» 8330 (18/9/2025) exceptuó a las personas humanas de liquidar (pesificar) esos cobros, sin límite de monto. La Com. «A» 8417 (9/4/2026) extendió la excepción a todos los conceptos de servicios |
| Condición | — | Acreditar los dólares en una cuenta en moneda extranjera a tu nombre en una entidad local dentro de los 20 días hábiles del cobro (Com. «A» 8116). El banco no puede cobrarte comisión por esa acreditación (sólo trasladar cargos de bancos del exterior) |
| Sociedades | Obligadas a liquidar | **Siguen obligadas** a ingresar y liquidar en el Mercado Libre de Cambios dentro de los 20 días hábiles (Com. «A» 8137) |

Si trabajás para clientes de afuera y querés ordenar facturación, categoría y cobro, mirá el servicio de [contador para freelancers y contractors que exportan servicios](https://contablix.ar/servicios/freelancers-contractors).

## Qué no cubre esta calculadora

Preferimos decirlo claro antes que darte un número falso:

- **Ganancias**: necesita la escala anual, deducciones personales y gastos; se explica, no se calcula.
- **Autónomos**: el monto depende de tu categoría; lo cargás como dato.
- **Alícuotas de padrón (SIRTAC, SIRCUPA, SIRCREB)**: cambian por CUIT y por mes; las cargás vos. Si un régimen no te alcanza, poné 0.
- **Base exacta de cada retención**: la CLI aplica cada alícuota sobre el monto informado. Si un mismo cobro sufre SIRTAC y SIRCUPA a la vez depende del medio de cobro y del agente.
- **Importaciones**: si traés mercadería del exterior para revender, el IVA y las percepciones en la aduana cambian tu flujo de caja y no están modelados acá. Para eso conviene un [asesoramiento impositivo para importadores](https://contablix.ar/servicios/importadores).
- **Exportación de bienes**: tiene otras reglas aduaneras y cambiarias.

## Para contadores y estudios contables

Si llevás clientes monotributistas o sellers de e-commerce, este repo te sirve como **dataset y API de referencia**:

- `data/escalas-2026.json` es un JSON plano y versionado con la escala, las alícuotas y la tabla de la RG 5319. Podés leerlo desde una planilla, un script o tu sistema interno.
- `--json` en cualquier subcomando devuelve una estructura estable (entrada, resultado, notas y link), útil para procesos por lote.
- Las funciones son puras y están testeadas al centavo, con paridad Python ↔ Node.

Si lo que buscás es automatizar el trabajo del estudio de punta a punta (recategorizaciones, declaraciones, conciliación de retenciones de muchos CUIT a la vez), para eso está [Pacioli, software contable con IA para estudios contables en Argentina](https://pacioli.ar).

## Uso como librería

**Python**

```python
import calculadora_impuestos_ar as calc

data = calc.cargar_datos()
sobre = calc.calcular_monotributo(data, ingresos_c=30_000_000 * 100, actividad="servicios")
print(sobre["resultado"]["categoria"])                         # D
print(calc.fmt_pesos(sobre["resultado"]["cuota_mensual_c"]))   # $ 84.613
```

**Node**

```js
import { cargarDatos, calcularMonotributo, fmtPesos } from './index.js';

const data = cargarDatos();
const { resultado } = calcularMonotributo(data, 30_000_000 * 100, 'servicios');
console.log(resultado.categoria, fmtPesos(resultado.cuota_mensual_c)); // D $ 84.613
```

Internamente todo se calcula en **enteros**: los montos en centavos (claves `_c`) y los porcentajes y el tipo de cambio multiplicados por 10.000 (claves `_u`; 1 % = 10.000). El redondeo es al centavo, mitad hacia arriba. Así Python y Node dan el mismo resultado sin errores de punto flotante. La salida `--json` ya viene convertida a pesos y porcentajes.

## Fuentes normativas

<!-- generado:fuentes -->
- **Ley 27.618**: Monotributo: actualización semestral de la escala por IPC (febrero y agosto).
- **Ley de IVA (art. 43)**: Alícuotas 21 %, 10,5 % y 27 %; recupero del IVA de compras vinculadas a exportaciones.
- **RG 5003**: Factura A a monotributistas.
- **RG 5700/2025**: Identificación del consumidor final desde $ 10.000.000 por operación.
- **RG 5554/2024**: Fin de las retenciones de IVA y Ganancias sobre cobros electrónicos (abrogó RG 140, 4011 y 4622).
- **RG 5319/2023**: Percepción de IVA en plataformas de comercio electrónico.
- **RG 5794/2025**: Nuevas alícuotas de la RG 5319 y criterios de habitualidad (desde el 1/12/2025).
- **RG 2226**: Certificado de exclusión de percepciones de IVA.
- **SIRTAC (COMARB)**: Retención de IIBB sobre tarjetas, QR y medios de pago.
- **SIRCUPA (COMARB)**: Retención de IIBB sobre acreditaciones en cuentas de pago (CVU).
- **SIRCREB (COMARB)**: Retención de IIBB sobre acreditaciones bancarias (CBU).
- **ARBA RN 25/2025**: Devolución de retenciones indebidas en billeteras (90 días).
- **RG CA 5/2021 (Comisión Arbitral)**: Sustento territorial por presencia digital en Convenio Multilateral.
- **RG 5616/2024**: Tipo de cambio para Factura E.
- **Com. BCRA «A» 8116**: Acreditación en cuenta en moneda extranjera dentro de los 20 días hábiles.
- **Com. BCRA «A» 8137**: Obligación de liquidar para sociedades.
- **Com. BCRA «A» 8330**: Eliminación del tope de USD 36.000 para personas humanas (18/9/2025).
- **Com. BCRA «A» 8417**: Extensión de la excepción a todos los conceptos de servicios (9/4/2026).
<!-- /generado:fuentes -->

La escala de monotributo y las alícuotas de la RG 5319 se tomaron de los datos oficiales de ARCA publicados en contablix.ar; las reglas de Factura E, de las Comunicaciones del BCRA citadas.

## Contribuir

La escala de monotributo cambia **dos veces por año, en febrero y agosto**. Actualizarla lleva cinco minutos porque todas las cifras viven en un solo archivo:

1. Editá [`data/escalas-2026.json`](data/escalas-2026.json): `monotributo.categorias` (topes, cuotas y alquileres) y `meta` (versión y vigencia). No hay números en el código.
2. Regenerá las tablas y ejemplos del README: `python3 scripts/actualizar_readme.py`.
3. Corré las pruebas: `python3 -m unittest` y `npm test`. Algunas pruebas fijan valores de la escala (por ejemplo, el caso de $ 30.000.000 → D): actualizalas con la escala nueva.
4. Abrí un PR citando la fuente oficial del cambio.

Si encontrás una regla mal explicada o una norma nueva, abrí un issue con el link a la norma. Más detalle en [CONTRIBUTING.md](CONTRIBUTING.md).

## Descargo

Esta guía y la calculadora son material informativo y educativo. **No constituyen asesoramiento impositivo ni contable.** Las cifras son estimaciones basadas en la normativa vigente a la fecha indicada y pueden cambiar; tu situación concreta puede tener particularidades (jurisdicción, actividad, regímenes especiales, exenciones) que cambian el resultado. Antes de tomar una decisión, consultá a tu contador.

## Créditos / Mantenido por

Mantenido por **[Contablix](https://contablix.ar)**, estudio contable online para e-commerce, freelancers y empresas digitales, fundado en 2020: +250 clientes activos, +1000 emprendedores confiaron en nosotros y 5,0 en Google.

Fundador: **Cr. Francisco Guillermo Ramírez**, Contador Público (UNCuyo) y Master in Laws en Derecho Tributario (UTDT), con más de 12 años de experiencia en impuestos para emprendedores y empresas digitales.

Licencia [MIT](LICENSE) © 2026 Contablix.
