#!/usr/bin/env node
// Calculadora open-source de impuestos en Argentina 2026 (Node ≥ 18, sin dependencias).
// Monotributo, Responsable Inscripto, retenciones e-commerce y Factura E.
//
// Todas las cifras salen de data/escalas-2026.json (el mismo archivo que lee el CLI de Python).
// Los montos se calculan en enteros (centavos) y las multiplicaciones en BigInt, para que
// Python y Node den exactamente los mismos números.
//
// Mantenido por Contablix — https://contablix.ar

import { readFileSync, realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

const DATA_URL = new URL('./data/escalas-2026.json', import.meta.url);

export const CENTAVOS = 100; // montos: enteros en centavos (sufijo _c)
export const UNIDADES = 10_000; // porcentajes y tipo de cambio: enteros x 10.000 (sufijo _u); 1 % = 10.000
const MONTO_MAXIMO_PESOS = 10 ** 12; // límite de entrada para garantizar paridad exacta con Python

export const CONDICIONES_RG5319 = [
  'ri',
  'ri_ddjj_sin_presentar',
  'ri_sin_dfe',
  'ri_limitado',
  'mono_excedido',
  'mono',
  'no_categorizado',
];

// ---------------------------------------------------------------------------
// Números: parseo exacto, redondeo y formato argentino
// ---------------------------------------------------------------------------

const NUMERO_RE = /^(\d+)(?:[.,](\d+))?$/;

/** Convierte '1234,56' o '1234.56' en un entero escalado (redondeo mitad hacia arriba). */
export function parseEscalado(texto, decimales) {
  const s = String(texto).trim();
  const m = NUMERO_RE.exec(s);
  if (!m) {
    throw new Error(
      `número inválido: '${texto}' (usá dígitos y, si hace falta, decimales con punto o coma; sin separador de miles)`,
    );
  }
  const entero = m[1];
  const frac = m[2] ?? '';
  const conservados = (frac + '0'.repeat(decimales)).slice(0, decimales);
  let valor = BigInt(entero) * 10n ** BigInt(decimales) + BigInt(conservados || '0');
  if (frac.length > decimales && frac[decimales] >= '5') valor += 1n;
  if (valor > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error('número fuera de rango');
  return Number(valor);
}

function divRedondeoBig(n, d) {
  const negativo = n < 0n;
  const a = negativo ? -n : n;
  let q = a / d;
  const r = a % d;
  if (2n * r >= d) q += 1n;
  return negativo ? -q : q;
}

/** a * b / d con redondeo mitad lejos de cero, sin perder precisión. */
export function mulDiv(a, b, d) {
  return Number(divRedondeoBig(BigInt(a) * BigInt(b), BigInt(d)));
}

/** Aplica una alícuota (en unidades de 1/10.000 %) a un monto en centavos. */
export function pctDe(montoC, alicuotaU) {
  return mulDiv(montoC, alicuotaU, 100 * UNIDADES);
}

function miles(n) {
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

function fmtMonto(centavos, simbolo) {
  const signo = centavos < 0 ? '-' : '';
  const abs = Math.abs(centavos);
  const entero = Math.floor(abs / CENTAVOS);
  const cent = abs % CENTAVOS;
  let texto = miles(entero);
  if (cent) texto += ',' + String(cent).padStart(2, '0');
  return `${signo}${simbolo} ${texto}`;
}

export const fmtPesos = (centavos) => fmtMonto(centavos, '$');
export const fmtUsd = (centavos) => fmtMonto(centavos, 'USD');

/** Número escalado x 10.000 con coma decimal y sin ceros sobrantes (35000 -> '3,5'). */
export function fmtUnidades(unidades) {
  const signo = unidades < 0 ? '-' : '';
  const abs = Math.abs(unidades);
  const entero = Math.floor(abs / UNIDADES);
  const dec = abs % UNIDADES;
  let texto = miles(entero);
  if (dec) texto += ',' + String(dec).padStart(4, '0').replace(/0+$/, '');
  return signo + texto;
}

/** Tipo de cambio con dos decimales si alcanzan (1.450,50) o hasta cuatro si hacen falta. */
export function fmtTipoCambio(unidades) {
  if (unidades % CENTAVOS === 0) return fmtPesos(unidades / CENTAVOS);
  return `$ ${fmtUnidades(unidades)}`;
}

export const fmtPct = (unidades) => `${fmtUnidades(unidades)} %`;

const numeroPublico = (valor, escala) => valor / escala;

/**
 * Convierte la representación interna (enteros escalados) a números para --json.
 * Claves con sufijo _c: centavos -> pesos. Sufijo _u: x10.000 -> número.
 */
export function aPublico(obj) {
  if (Array.isArray(obj)) return obj.map(aPublico);
  if (obj !== null && typeof obj === 'object') {
    const out = {};
    for (const [clave, valor] of Object.entries(obj)) {
      if (clave.endsWith('_c')) out[clave.slice(0, -2)] = valor === null ? null : numeroPublico(valor, CENTAVOS);
      else if (clave.endsWith('_u')) out[clave.slice(0, -2)] = valor === null ? null : numeroPublico(valor, UNIDADES);
      else out[clave] = aPublico(valor);
    }
    return out;
  }
  return obj;
}

// ---------------------------------------------------------------------------
// Datos
// ---------------------------------------------------------------------------

export function cargarDatos(ruta = DATA_URL) {
  return JSON.parse(readFileSync(ruta, 'utf8'));
}

function sobre(data, subcomando, entrada, resultado, notas, link) {
  return {
    subcomando,
    datos: { version: data.meta.version_datos, escala_desde: data.meta.escala_desde },
    entrada,
    resultado,
    notas,
    link: data.links[link],
  };
}

// ---------------------------------------------------------------------------
// Monotributo
// ---------------------------------------------------------------------------

function indiceCategoria(categorias, valorC, campo) {
  const i = categorias.findIndex((cat) => valorC <= cat[campo] * CENTAVOS);
  return i === -1 ? null : i;
}

const cuotaC = (cat, actividad) => (actividad === 'servicios' ? cat.cuota_servicios : cat.cuota_bienes) * CENTAVOS;

/** Categoría por ingresos brutos anuales (sin alquileres). */
export function encuadrar(data, ingresosC, actividad) {
  const categorias = data.monotributo.categorias;
  const i = indiceCategoria(categorias, ingresosC, 'tope_ingresos');
  if (i === null) return { categoria: null, cuota_mensual_c: null, excluido: true };
  const cat = categorias[i];
  return { categoria: cat.categoria, cuota_mensual_c: cuotaC(cat, actividad), excluido: false };
}

export function calcularMonotributo(data, ingresosC, actividad, alquileresC = null) {
  const mono = data.monotributo;
  const categorias = mono.categorias;
  const ultima = categorias[categorias.length - 1];
  const topeKC = ultima.tope_ingresos * CENTAVOS;

  const iIng = indiceCategoria(categorias, ingresosC, 'tope_ingresos');
  const iAlq = alquileresC !== null ? indiceCategoria(categorias, alquileresC, 'tope_alquileres') : null;
  const excluidoIng = iIng === null;
  const excluidoAlq = alquileresC !== null && iAlq === null;
  const excluido = excluidoIng || excluidoAlq;

  const resultado = {
    categoria: null,
    excluido,
    categoria_por_ingresos: iIng !== null ? categorias[iIng].categoria : null,
    categoria_por_alquileres: iAlq !== null ? categorias[iAlq].categoria : null,
    cuota_mensual_c: null,
    tope_ingresos_categoria_c: null,
    margen_al_tope_c: null,
    margen_al_tope_pct_u: null,
    siguiente_categoria: null,
    tope_categoria_k_c: topeKC,
    exceso_sobre_tope_k_c: excluidoIng ? ingresosC - topeKC : null,
    alerta: null,
  };
  const notas = [mono.textos.composicion, mono.textos.otros_parametros];

  if (excluido) {
    const motivos = [];
    if (excluidoIng) {
      motivos.push(
        `tus ingresos brutos superan en ${fmtPesos(ingresosC - topeKC)} el tope de la categoría ` +
          `${ultima.categoria} (${fmtPesos(topeKC)})`,
      );
    }
    if (excluidoAlq) {
      motivos.push(`tus alquileres superan el tope máximo de ${fmtPesos(ultima.tope_alquileres * CENTAVOS)}`);
    }
    resultado.alerta = 'ALERTA DE EXCLUSIÓN: ' + motivos.join(' y ') + '.';
    notas.unshift(mono.textos.exclusion);
  } else {
    const i = Math.max(iIng ?? 0, iAlq ?? 0);
    const cat = categorias[i];
    const topeC = cat.tope_ingresos * CENTAVOS;
    const margenC = topeC - ingresosC;
    resultado.categoria = cat.categoria;
    resultado.cuota_mensual_c = cuotaC(cat, actividad);
    resultado.tope_ingresos_categoria_c = topeC;
    resultado.margen_al_tope_c = margenC;
    resultado.margen_al_tope_pct_u = mulDiv(margenC, 100 * 100, topeC) * 100;
    if (i + 1 < categorias.length) {
      const sig = categorias[i + 1];
      resultado.siguiente_categoria = {
        categoria: sig.categoria,
        tope_ingresos_c: sig.tope_ingresos * CENTAVOS,
        cuota_mensual_c: cuotaC(sig, actividad),
      };
    }
  }

  const entrada = { ingresos_anuales_c: ingresosC, actividad, alquileres_anuales_c: alquileresC };
  return sobre(data, 'monotributo', entrada, resultado, notas, 'monotributo');
}

// ---------------------------------------------------------------------------
// Responsable Inscripto
// ---------------------------------------------------------------------------

export function calcularRi(
  data,
  ventasC,
  comprasC,
  alicuotaIibbU,
  autonomosC,
  alicuotaIvaVentasU = 21 * UNIDADES,
  alicuotaIvaComprasU = 21 * UNIDADES,
) {
  const ri = data.responsable_inscripto;
  const debitoC = pctDe(ventasC, alicuotaIvaVentasU);
  const creditoC = pctDe(comprasC, alicuotaIvaComprasU);
  const saldoC = debitoC - creditoC;
  const ivaPagarC = Math.max(saldoC, 0);
  const iibbC = pctDe(ventasC, alicuotaIibbU);
  const resultado = {
    iva_debito_c: debitoC,
    iva_credito_c: creditoC,
    saldo_iva_c: saldoC,
    iva_a_pagar_c: ivaPagarC,
    saldo_a_favor_iva_c: Math.max(-saldoC, 0),
    iibb_c: iibbC,
    autonomos_c: autonomosC,
    subtotal_mensual_sin_ganancias_c: ivaPagarC + iibbC + autonomosC,
    ganancias_estimada: false,
    ganancias_escala_min_pct_u: ri.ganancias.escala_min_pct * UNIDADES,
    ganancias_escala_max_pct_u: ri.ganancias.escala_max_pct * UNIDADES,
  };
  const notas = [ri.ganancias.texto, ri.iibb.texto, ri.autonomos];
  if (autonomosC === 0) notas.push('No informaste autónomos (--autonomos): el subtotal no los incluye.');
  notas.push(ri.referencia_simulador.texto);
  const entrada = {
    ventas_netas_mensuales_c: ventasC,
    alicuota_iva_ventas_pct_u: alicuotaIvaVentasU,
    compras_netas_con_iva_c: comprasC,
    alicuota_iva_compras_pct_u: alicuotaIvaComprasU,
    alicuota_iibb_pct_u: alicuotaIibbU,
    autonomos_mensual_c: autonomosC,
  };
  return sobre(data, 'ri', entrada, resultado, notas, 'responsable_inscripto');
}

// ---------------------------------------------------------------------------
// Retenciones y percepciones e-commerce
// ---------------------------------------------------------------------------

export function condicionRg5319(data, clave) {
  const cond = data.percepcion_iva_rg5319.condiciones.find((c) => c.clave === clave);
  if (!cond) throw new Error(`condición desconocida: ${clave}`);
  return cond;
}

export function calcularRetenciones(data, montoC, condicion, alicuotaSirtacU = 0, alicuotaSircupaU = 0) {
  const ret = data.retenciones_iibb;
  const cond = condicionRg5319(data, condicion);
  const alicuotaIvaU = parseEscalado(cond.porcentaje, 4);
  const percepcionC = pctDe(montoC, alicuotaIvaU);
  const sirtacC = pctDe(montoC, alicuotaSirtacU);
  const sircupaC = pctDe(montoC, alicuotaSircupaU);
  const totalC = percepcionC + sirtacC + sircupaC;
  const resultado = {
    condicion_descripcion: cond.descripcion,
    percepcion_iva_rg5319_pct_u: alicuotaIvaU,
    percepcion_iva_rg5319_c: percepcionC,
    retencion_sirtac_c: sirtacC,
    retencion_sircupa_c: sircupaC,
    total_retenido_percibido_c: totalC,
    neto_cobrado_c: montoC - totalC,
  };
  const notas = [ret.rg5554.texto, ret.pago_a_cuenta];
  if (condicion.startsWith('ri')) notas.push(data.percepcion_iva_rg5319.computo);
  if (condicion === 'no_categorizado') notas.push(data.habitualidad_rg5794.texto);
  if (condicion === 'mono') notas.push(ret.comisiones);
  notas.push(ret.base_calculo);
  const entrada = {
    monto_c: montoC,
    condicion,
    alicuota_sirtac_pct_u: alicuotaSirtacU,
    alicuota_sircupa_pct_u: alicuotaSircupaU,
  };
  return sobre(data, 'retenciones', entrada, resultado, notas, 'ecommerce');
}

// ---------------------------------------------------------------------------
// Factura E
// ---------------------------------------------------------------------------

export function calcularFacturaE(data, usdC, tcU, persona, ingresos12mC, actividad, condicion = null) {
  const fe = data.factura_e;
  const cond = condicion ?? (persona === 'humana' ? 'monotributo' : 'ri');
  if (persona === 'sociedad' && cond === 'monotributo') throw new Error(fe.sociedad_monotributo);

  const pesosC = mulDiv(usdC, tcU, UNIDADES);
  let impacto = null;
  if (cond === 'monotributo') {
    const antes = encuadrar(data, ingresos12mC, actividad);
    const despuesIngresosC = ingresos12mC + pesosC;
    const despues = encuadrar(data, despuesIngresosC, actividad);
    impacto = {
      antes: { ingresos_12m_c: ingresos12mC, ...antes },
      despues: { ingresos_12m_c: despuesIngresosC, ...despues },
      cambia_categoria: antes.categoria !== despues.categoria,
    };
  }
  const regla = fe.regla_cambiaria[persona];
  const tope = fe.tope_historico;
  const resultado = {
    pesos_c: pesosC,
    impacto_monotributo: impacto,
    regla_cambiaria: { persona, normas: regla.normas, texto: regla.texto },
    tope_historico_usd: { monto: tope.monto_usd, vigente: tope.vigente },
  };
  const notas = [fe.definicion, fe.tipo_cambio, fe.punto_de_venta];
  notas.push(cond === 'monotributo' ? fe.monotributo : fe.responsable_inscripto);
  notas.push(tope.texto);
  if (actividad === 'bienes') notas.push(fe.bienes);
  const entrada = {
    usd_c: usdC,
    tipo_cambio_u: tcU,
    persona,
    condicion: cond,
    ingresos_12m_c: ingresos12mC,
    actividad,
  };
  return sobre(data, 'factura-e', entrada, resultado, notas, 'freelancers');
}

// ---------------------------------------------------------------------------
// Salida de texto
// ---------------------------------------------------------------------------

function bloque(titulo, filas) {
  const ancho = Math.max(...filas.map(([etiqueta]) => etiqueta.length)) + 1;
  return [titulo, ...filas.map(([etiqueta, valor]) => `  ${(etiqueta + ':').padEnd(ancho)}  ${valor}`)];
}

function renderMonotributo(s) {
  const { entrada: e, resultado: r } = s;
  const filas = [['Ingresos brutos anuales', fmtPesos(e.ingresos_anuales_c)]];
  if (e.alquileres_anuales_c !== null) filas.push(['Alquileres anuales', fmtPesos(e.alquileres_anuales_c)]);
  filas.push(['Actividad', e.actividad]);
  if (e.alquileres_anuales_c !== null) {
    filas.push(['Categoría por ingresos', r.categoria_por_ingresos ?? 'fuera de escala']);
    filas.push(['Categoría por alquileres', r.categoria_por_alquileres ?? 'fuera de escala']);
  }
  if (r.excluido) {
    filas.push(['Categoría', 'EXCLUIDO del monotributo']);
    if (r.exceso_sobre_tope_k_c !== null) filas.push(['Exceso sobre el tope de K', fmtPesos(r.exceso_sobre_tope_k_c)]);
  } else {
    filas.push(['Categoría', r.categoria]);
    filas.push(['Cuota mensual', fmtPesos(r.cuota_mensual_c)]);
    filas.push([`Tope de ingresos de ${r.categoria}`, fmtPesos(r.tope_ingresos_categoria_c)]);
    filas.push(['Margen al tope', `${fmtPesos(r.margen_al_tope_c)} (${fmtPct(r.margen_al_tope_pct_u)})`]);
    const sig = r.siguiente_categoria;
    if (sig === null) {
      filas.push(['Siguiente categoría', 'no hay: superar el tope de K es exclusión']);
    } else {
      filas.push([
        'Siguiente categoría',
        `${sig.categoria} · tope ${fmtPesos(sig.tope_ingresos_c)} · cuota ${fmtPesos(sig.cuota_mensual_c)}`,
      ]);
    }
  }
  const lineas = bloque(`Monotributo · escala vigente desde ${s.datos.escala_desde}`, filas);
  if (r.alerta) lineas.push('', `  ${r.alerta}`);
  return lineas;
}

function renderRi(s) {
  const { entrada: e, resultado: r } = s;
  const filas = [
    ['Ventas netas del mes', fmtPesos(e.ventas_netas_mensuales_c)],
    [`IVA débito (${fmtPct(e.alicuota_iva_ventas_pct_u)})`, fmtPesos(r.iva_debito_c)],
    ['Compras netas con IVA discriminado', fmtPesos(e.compras_netas_con_iva_c)],
    [`IVA crédito (${fmtPct(e.alicuota_iva_compras_pct_u)})`, fmtPesos(r.iva_credito_c)],
  ];
  if (r.saldo_iva_c >= 0) filas.push(['Saldo de IVA a pagar', fmtPesos(r.iva_a_pagar_c)]);
  else filas.push(['Saldo técnico a favor (IVA)', fmtPesos(r.saldo_a_favor_iva_c)]);
  filas.push(
    [`IIBB (${fmtPct(e.alicuota_iibb_pct_u)} s/ ventas netas)`, fmtPesos(r.iibb_c)],
    ['Autónomos', fmtPesos(r.autonomos_c)],
    ['Subtotal mensual sin Ganancias', fmtPesos(r.subtotal_mensual_sin_ganancias_c)],
    [
      'Ganancias',
      `no se estima acá (escala anual ${fmtPct(r.ganancias_escala_min_pct_u)}` +
        ` a ${fmtPct(r.ganancias_escala_max_pct_u)}): usá el simulador`,
    ],
  );
  return bloque('Responsable Inscripto · estimación mensual', filas);
}

function renderRetenciones(s) {
  const { entrada: e, resultado: r } = s;
  const filas = [
    ['Monto cobrado (base)', fmtPesos(e.monto_c)],
    ['Condición', r.condicion_descripcion],
    [`Percepción IVA RG 5319 (${fmtPct(r.percepcion_iva_rg5319_pct_u)})`, fmtPesos(r.percepcion_iva_rg5319_c)],
    [`Retención IIBB SIRTAC (${fmtPct(e.alicuota_sirtac_pct_u)})`, fmtPesos(r.retencion_sirtac_c)],
    [`Retención IIBB SIRCUPA (${fmtPct(e.alicuota_sircupa_pct_u)})`, fmtPesos(r.retencion_sircupa_c)],
    ['Total retenido y percibido', fmtPesos(r.total_retenido_percibido_c)],
    ['Neto cobrado', fmtPesos(r.neto_cobrado_c)],
  ];
  return bloque('Retenciones y percepciones e-commerce · estimación por cobro', filas);
}

function renderFacturaE(s) {
  const { entrada: e, resultado: r } = s;
  const filas = [
    ['Monto facturado', fmtUsd(e.usd_c)],
    ['Tipo de cambio (BNA vendedor divisa)', fmtTipoCambio(e.tipo_cambio_u)],
    ['Equivalente en pesos', fmtPesos(r.pesos_c)],
    ['Persona', e.persona],
    ['Condición', e.condicion === 'monotributo' ? 'monotributo' : 'Responsable Inscripto'],
  ];
  const imp = r.impacto_monotributo;
  if (imp !== null) {
    for (const [etiqueta, lado] of [
      ['Ingresos 12 meses (antes)', imp.antes],
      ['Ingresos 12 meses (con esta factura)', imp.despues],
    ]) {
      const encuadre = lado.excluido
        ? 'EXCLUIDO (supera el tope de K)'
        : `Cat. ${lado.categoria} · cuota ${fmtPesos(lado.cuota_mensual_c)}`;
      filas.push([etiqueta, `${fmtPesos(lado.ingresos_12m_c)} → ${encuadre}`]);
    }
    filas.push(['Cambia de categoría', imp.cambia_categoria ? 'sí' : 'no']);
  }
  const lineas = bloque('Factura E · exportación', filas);
  lineas.push('', `  Régimen cambiario vigente: ${r.regla_cambiaria.texto}`);
  return lineas;
}

const RENDERERS = {
  monotributo: renderMonotributo,
  ri: renderRi,
  retenciones: renderRetenciones,
  'factura-e': renderFacturaE,
};

export function renderTexto(s) {
  const lineas = RENDERERS[s.subcomando](s);
  lineas.push('');
  for (const nota of s.notas) lineas.push(`  - ${nota}`);
  lineas.push('');
  lineas.push(`→ ${s.link.anchor}: ${s.link.url}`);
  return lineas.join('\n');
}

export function renderJson(s) {
  return JSON.stringify(aPublico(s), null, 2);
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

class ErrorDeUso extends Error {}

function ayuda(data) {
  const iva = data.iva.alicuotas.map((a) => String(a.porcentaje)).join('|');
  return `uso: calc-impuestos-ar SUBCOMANDO [opciones] [--json]

Calculadora open-source de impuestos en Argentina 2026 (monotributo, RI, retenciones e-commerce, Factura E).

subcomandos:
  monotributo  --ingresos N --actividad servicios|bienes [--alquileres N]
  ri           --ventas-mensuales N --alicuota-iibb X [--compras-con-iva N] [--autonomos N]
               [--alicuota-iva ${iva}] [--alicuota-iva-compras ${iva}]
  retenciones  --monto N --condicion ${CONDICIONES_RG5319.join('|')}
               [--alicuota-sirtac X] [--alicuota-sircupa X]
  factura-e    --usd N --tc N [--persona humana|sociedad] [--ingresos-12m N]
               [--actividad servicios|bienes] [--condicion monotributo|ri]

opciones comunes:
  --json       salida en JSON (para scripts)
  -h, --help   muestra esta ayuda

Montos en pesos, sin separador de miles; decimales con punto o coma.
Mantenido por ${data.meta.mantenido_por}.`;
}

const OPCIONES = {
  monotributo: ['ingresos', 'actividad', 'alquileres'],
  ri: ['ventas-mensuales', 'compras-con-iva', 'alicuota-iibb', 'autonomos', 'alicuota-iva', 'alicuota-iva-compras'],
  retenciones: ['monto', 'condicion', 'alicuota-sirtac', 'alicuota-sircupa'],
  'factura-e': ['usd', 'tc', 'persona', 'ingresos-12m', 'actividad', 'condicion'],
};

function requerido(valores, nombre) {
  const v = valores[nombre];
  if (v === undefined) throw new ErrorDeUso(`falta el argumento obligatorio --${nombre}`);
  return v;
}

function elegir(valor, nombre, opciones) {
  if (!opciones.includes(valor)) {
    throw new ErrorDeUso(`--${nombre}: opción inválida '${valor}' (elegí entre ${opciones.join(', ')})`);
  }
  return valor;
}

function monto(nombre, valor) {
  if (valor === undefined) return null;
  let c;
  try {
    c = parseEscalado(valor, 2);
  } catch (err) {
    throw new ErrorDeUso(`--${nombre}: ${err.message}`);
  }
  if (c > MONTO_MAXIMO_PESOS * CENTAVOS) throw new ErrorDeUso(`--${nombre}: monto fuera de rango`);
  return c;
}

function porcentaje(nombre, valor, maximo = 100) {
  let u;
  try {
    u = parseEscalado(valor, 4);
  } catch (err) {
    throw new ErrorDeUso(`--${nombre}: ${err.message}`);
  }
  if (u > maximo * UNIDADES) throw new ErrorDeUso(`--${nombre}: la alícuota no puede superar ${maximo} %`);
  return u;
}

function tipoCambio(valor) {
  let u;
  try {
    u = parseEscalado(valor, 4);
  } catch (err) {
    throw new ErrorDeUso(`--tc: ${err.message}`);
  }
  if (u === 0 || u > MONTO_MAXIMO_PESOS * UNIDADES) {
    throw new ErrorDeUso('--tc: el tipo de cambio tiene que ser mayor a 0 y razonable');
  }
  return u;
}

/** Ejecuta el CLI y devuelve { codigo, salida, error } sin tocar process (testeable). */
export function ejecutar(argv, data = cargarDatos()) {
  if (argv.length === 0 || argv[0] === '-h' || argv[0] === '--help') {
    const texto = ayuda(data);
    return argv.length === 0 ? { codigo: 2, salida: '', error: texto } : { codigo: 0, salida: texto, error: '' };
  }
  const [subcomando, ...resto] = argv;
  try {
    if (!(subcomando in OPCIONES)) throw new ErrorDeUso(`subcomando inválido '${subcomando}'`);
    const options = { json: { type: 'boolean' }, help: { type: 'boolean', short: 'h' } };
    for (const nombre of OPCIONES[subcomando]) options[nombre] = { type: 'string' };
    let valores;
    try {
      ({ values: valores } = parseArgs({ args: resto, options, strict: true, allowPositionals: false }));
    } catch (err) {
      throw new ErrorDeUso(err.message);
    }
    if (valores.help) return { codigo: 0, salida: ayuda(data), error: '' };

    const ivaChoices = data.iva.alicuotas.map((a) => String(a.porcentaje));
    let s;
    try {
      if (subcomando === 'monotributo') {
        s = calcularMonotributo(
          data,
          monto('ingresos', requerido(valores, 'ingresos')),
          elegir(requerido(valores, 'actividad'), 'actividad', ['servicios', 'bienes']),
          monto('alquileres', valores.alquileres),
        );
      } else if (subcomando === 'ri') {
        s = calcularRi(
          data,
          monto('ventas-mensuales', requerido(valores, 'ventas-mensuales')),
          monto('compras-con-iva', valores['compras-con-iva'] ?? '0'),
          porcentaje('alicuota-iibb', requerido(valores, 'alicuota-iibb')),
          monto('autonomos', valores.autonomos ?? '0'),
          parseEscalado(elegir(valores['alicuota-iva'] ?? '21', 'alicuota-iva', ivaChoices), 4),
          parseEscalado(elegir(valores['alicuota-iva-compras'] ?? '21', 'alicuota-iva-compras', ivaChoices), 4),
        );
      } else if (subcomando === 'retenciones') {
        const maximoSirtac = data.retenciones_iibb.sirtac.alicuota_maxima_pct;
        s = calcularRetenciones(
          data,
          monto('monto', requerido(valores, 'monto')),
          elegir(requerido(valores, 'condicion'), 'condicion', CONDICIONES_RG5319),
          porcentaje('alicuota-sirtac', valores['alicuota-sirtac'] ?? '0', maximoSirtac),
          porcentaje('alicuota-sircupa', valores['alicuota-sircupa'] ?? '0'),
        );
      } else {
        s = calcularFacturaE(
          data,
          monto('usd', requerido(valores, 'usd')),
          tipoCambio(requerido(valores, 'tc')),
          elegir(valores.persona ?? 'humana', 'persona', ['humana', 'sociedad']),
          monto('ingresos-12m', valores['ingresos-12m'] ?? '0'),
          elegir(valores.actividad ?? 'servicios', 'actividad', ['servicios', 'bienes']),
          valores.condicion === undefined ? null : elegir(valores.condicion, 'condicion', ['monotributo', 'ri']),
        );
      }
    } catch (err) {
      if (err instanceof ErrorDeUso) throw err;
      throw new ErrorDeUso(err.message);
    }
    return { codigo: 0, salida: valores.json ? renderJson(s) : renderTexto(s), error: '' };
  } catch (err) {
    if (!(err instanceof ErrorDeUso)) throw err;
    return { codigo: 2, salida: '', error: `uso: calc-impuestos-ar ${subcomando} [opciones]\ncalc-impuestos-ar: error: ${err.message}` };
  }
}

function esPrincipal() {
  if (!process.argv[1]) return false;
  try {
    return realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url));
  } catch {
    return false;
  }
}

if (esPrincipal()) {
  const { codigo, salida, error } = ejecutar(process.argv.slice(2));
  if (salida) process.stdout.write(salida + '\n');
  if (error) process.stderr.write(error + '\n');
  process.exitCode = codigo;
}
