// Pruebas de resultado de la calculadora (Node). Sin mocks: datos reales del JSON.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  cargarDatos,
  calcularMonotributo,
  calcularRi,
  calcularRetenciones,
  calcularFacturaE,
  ejecutar,
  fmtPesos,
  parseEscalado,
} from '../index.js';

const DATA = cargarDatos();
const pesos = (n) => n * 100;

test('formato argentino y parseo exacto', () => {
  assert.equal(fmtPesos(123456789), '$ 1.234.567,89');
  assert.equal(fmtPesos(pesos(84613)), '$ 84.613');
  assert.equal(parseEscalado('1234,565', 2), 123457);
  assert.equal(parseEscalado('1234.564', 2), 123456);
  assert.throws(() => parseEscalado('1.234.567', 2));
});

test('aceptación: $ 30.000.000 en servicios es Cat. D con cuota $ 84.613', () => {
  const { codigo, salida } = ejecutar(['monotributo', '--ingresos', '30000000', '--actividad', 'servicios']);
  assert.equal(codigo, 0);
  assert.match(salida, /Categoría:\s+D\n/);
  assert.ok(salida.includes('$ 84.613'));
  assert.ok(salida.includes('https://contablix.ar/calculadora-monotributo'));
});

test('ingreso exactamente en el tope queda en la categoría; un peso arriba sube', () => {
  assert.equal(calcularMonotributo(DATA, pesos(12_009_410), 'servicios').resultado.categoria, 'A');
  const arriba = calcularMonotributo(DATA, pesos(12_009_411), 'servicios').resultado;
  assert.equal(arriba.categoria, 'B');
  assert.equal(arriba.cuota_mensual_c, pesos(56_379));
});

test('tope de K exacto no excluye; un peso arriba es exclusión con alerta', () => {
  const k = calcularMonotributo(DATA, pesos(126_610_839), 'bienes').resultado;
  assert.equal(k.categoria, 'K');
  assert.equal(k.cuota_mensual_c, pesos(702_103));
  assert.equal(k.siguiente_categoria, null);
  const fuera = calcularMonotributo(DATA, pesos(126_610_840), 'bienes').resultado;
  assert.equal(fuera.excluido, true);
  assert.equal(fuera.exceso_sobre_tope_k_c, pesos(1));
  assert.match(fuera.alerta, /ALERTA DE EXCLUSIÓN/);
});

test('alquileres suben la categoría', () => {
  const r = calcularMonotributo(DATA, pesos(1_000_000), 'servicios', pesos(3_000_000)).resultado;
  assert.equal(r.categoria, 'C');
  assert.equal(r.cuota_mensual_c, pesos(66_020));
});

test('RI: IVA, IIBB y autónomos; Ganancias no se estima', () => {
  const r = calcularRi(DATA, pesos(2_000_000), pesos(500_000), 35_000, pesos(50_000)).resultado;
  assert.equal(r.iva_a_pagar_c, pesos(315_000));
  assert.equal(r.iibb_c, pesos(70_000));
  assert.equal(r.subtotal_mensual_sin_ganancias_c, pesos(435_000));
  assert.equal(r.ganancias_estimada, false);
});

test('RG 5319: monotributista dentro de parámetros → 0 %; no categorizado → 8 %', () => {
  const mono = calcularRetenciones(DATA, pesos(250_000), 'mono', 20_000, 0).resultado;
  assert.equal(mono.percepcion_iva_rg5319_c, 0);
  assert.equal(mono.neto_cobrado_c, pesos(245_000));
  const nc = calcularRetenciones(DATA, pesos(100_000), 'no_categorizado').resultado;
  assert.equal(nc.percepcion_iva_rg5319_c, pesos(8_000));
});

test('SIRTAC por encima del máximo del padrón es error de uso', () => {
  const { codigo } = ejecutar(['retenciones', '--monto', '1000', '--condicion', 'ri', '--alicuota-sirtac', '5.01']);
  assert.equal(codigo, 2);
});

test('Factura E: pesos al TC, salto de categoría y régimen vigente sin tope', () => {
  const r = calcularFacturaE(DATA, pesos(2_000), 14_505_000, 'humana', pesos(28_000_000), 'servicios').resultado;
  assert.equal(r.pesos_c, pesos(2_901_000));
  assert.equal(r.impacto_monotributo.antes.categoria, 'D');
  assert.equal(r.impacto_monotributo.despues.categoria, 'E');
  assert.deepEqual(r.tope_historico_usd, { monto: 36_000, vigente: false });
  const soc = calcularFacturaE(DATA, pesos(1_000), 10_000_000, 'sociedad', 0, 'servicios').resultado;
  assert.equal(soc.impacto_monotributo, null);
  assert.match(soc.regla_cambiaria.normas, /8137/);
});

test('cada subcomando termina con su link de contablix.ar', () => {
  const casos = [
    [['monotributo', '--ingresos', '1', '--actividad', 'bienes'], 'https://contablix.ar/calculadora-monotributo'],
    [['ri', '--ventas-mensuales', '1', '--alicuota-iibb', '3'], 'https://contablix.ar/impuestos-responsable-inscripto'],
    [['retenciones', '--monto', '1', '--condicion', 'mono'], 'https://contablix.ar/servicios/consultoria-ecommerce'],
    [['factura-e', '--usd', '1', '--tc', '1'], 'https://contablix.ar/servicios/freelancers-contractors'],
  ];
  for (const [argv, url] of casos) {
    const { codigo, salida } = ejecutar(argv);
    assert.equal(codigo, 0);
    assert.ok(salida.trimEnd().endsWith(url), `${argv[0]} debería terminar en ${url}`);
  }
});
