// Paridad Python ↔ Node: mismos inputs, misma salida (JSON y texto), corriendo ambos CLIs de verdad.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const RAIZ = fileURLToPath(new URL('..', import.meta.url));
const PYTHON = process.env.PYTHON ?? 'python3';

const CASOS = [
  ['monotributo', '--ingresos', '30000000', '--actividad', 'servicios'],
  ['monotributo', '--ingresos', '12009410', '--actividad', 'bienes'],
  ['monotributo', '--ingresos', '12009411', '--actividad', 'bienes'],
  ['monotributo', '--ingresos', '126610839', '--actividad', 'servicios'],
  ['monotributo', '--ingresos', '126610840,5', '--actividad', 'servicios', '--alquileres', '9000000'],
  ['monotributo', '--ingresos', '1000000', '--actividad', 'servicios', '--alquileres', '3000000'],
  ['monotributo', '--ingresos', '0', '--actividad', 'bienes'],
  ['ri', '--ventas-mensuales', '2000000', '--compras-con-iva', '500000', '--alicuota-iibb', '3.5', '--autonomos', '50000'],
  ['ri', '--ventas-mensuales', '123,45', '--compras-con-iva', '999999,99', '--alicuota-iibb', '4,75', '--alicuota-iva', '10.5', '--alicuota-iva-compras', '27'],
  ['retenciones', '--monto', '100000', '--condicion', 'ri', '--alicuota-sirtac', '2', '--alicuota-sircupa', '0.5'],
  ['retenciones', '--monto', '33333,33', '--condicion', 'no_categorizado', '--alicuota-sirtac', '1.75'],
  ['retenciones', '--monto', '250000', '--condicion', 'mono', '--alicuota-sirtac', '5'],
  ['retenciones', '--monto', '987654321,98', '--condicion', 'ri_limitado', '--alicuota-sircupa', '3.3333'],
  ['factura-e', '--usd', '2000', '--tc', '1450.5', '--ingresos-12m', '20000000'],
  ['factura-e', '--usd', '1234,56', '--tc', '1450,1234', '--ingresos-12m', '29000000', '--actividad', 'bienes'],
  ['factura-e', '--usd', '50000', '--tc', '1400', '--persona', 'sociedad'],
  ['factura-e', '--usd', '10000', '--tc', '1400', '--ingresos-12m', '120000000'],
];

function correr(cmd, args) {
  const r = spawnSync(cmd, args, { cwd: RAIZ, encoding: 'utf8' });
  assert.equal(r.status, 0, `${cmd} ${args.join(' ')} salió con ${r.status}: ${r.stderr}`);
  return r.stdout;
}

for (const caso of CASOS) {
  test(`paridad: ${caso.join(' ')}`, () => {
    const py = correr(PYTHON, ['calculadora_impuestos_ar.py', ...caso]);
    const js = correr(process.execPath, ['index.js', ...caso]);
    assert.equal(js, py, 'la salida de texto difiere');
    const pyJson = correr(PYTHON, ['calculadora_impuestos_ar.py', ...caso, '--json']);
    const jsJson = correr(process.execPath, ['index.js', ...caso, '--json']);
    assert.deepEqual(JSON.parse(jsJson), JSON.parse(pyJson));
    assert.equal(jsJson, pyJson, 'el JSON difiere byte a byte');
  });
}
