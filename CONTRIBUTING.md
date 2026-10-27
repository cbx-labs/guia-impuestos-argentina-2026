# Cómo contribuir

Gracias por sumar. La regla de oro: **toda cifra vive en `data/escalas-2026.json` y tiene una fuente**.

## Actualizar la escala (febrero y agosto)

1. Editá `data/escalas-2026.json`: `monotributo.categorias` y `meta` (`version_datos`, `escala_desde`, `vigencia`).
2. `python3 scripts/actualizar_readme.py` regenera las tablas y los ejemplos del README.
3. `python3 -m unittest` y `npm test` tienen que pasar. Las pruebas que fijan valores de la escala vieja se actualizan con la nueva.
4. En el PR, linkeá la fuente oficial (ARCA, Boletín Oficial, BCRA o COMARB).

## Cambiar lógica

- Python (`calculadora_impuestos_ar.py`) y Node (`index.js`) tienen que dar **los mismos números**: `tests/paridad.test.mjs` corre los dos CLIs con los mismos argumentos y compara la salida byte a byte. Si tocás uno, tocá el otro.
- Trabajá en enteros (centavos y x10.000), nunca en float.
- Agregá una prueba de resultado para el caso borde que te llevó al cambio.

## Qué no aceptamos

- Cifras sin fuente o «estimadas a ojo».
- Reglas vencidas presentadas como vigentes (por ejemplo, el tope de USD 36.000 de Factura E, eliminado en septiembre de 2025, va siempre como dato histórico).
