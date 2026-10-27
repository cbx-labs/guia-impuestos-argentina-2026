"""Pruebas de resultado de la calculadora (Python). Sin mocks: datos reales del JSON."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import calculadora_impuestos_ar as calc  # noqa: E402

DATA = calc.cargar_datos()


def pesos(n: int) -> int:
    return n * 100


def correr(*argv: str) -> tuple[int, str]:
    salida = io.StringIO()
    errores = io.StringIO()
    with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
        try:
            codigo = calc.ejecutar(list(argv))
        except SystemExit as exc:
            codigo = int(exc.code)
    return codigo, salida.getvalue()


class TestFormato(unittest.TestCase):
    def test_pesos_formato_argentino(self) -> None:
        self.assertEqual(calc.fmt_pesos(123456789), "$ 1.234.567,89")
        self.assertEqual(calc.fmt_pesos(pesos(84613)), "$ 84.613")
        self.assertEqual(calc.fmt_pesos(5), "$ 0,05")
        self.assertEqual(calc.fmt_pesos(-pesos(1000)), "-$ 1.000")

    def test_parseo_exacto_con_coma_o_punto_y_redondeo(self) -> None:
        self.assertEqual(calc.parse_escalado("1234,56", 2), 123456)
        self.assertEqual(calc.parse_escalado("1234.56", 2), 123456)
        self.assertEqual(calc.parse_escalado("1234,565", 2), 123457)
        self.assertEqual(calc.parse_escalado("1234,564", 2), 123456)
        with self.assertRaises(ValueError):
            calc.parse_escalado("1.234.567", 2)


class TestMonotributo(unittest.TestCase):
    def test_caso_de_aceptacion_30_millones_servicios(self) -> None:
        r = calc.calcular_monotributo(DATA, pesos(30_000_000), "servicios")["resultado"]
        self.assertEqual(r["categoria"], "D")
        self.assertEqual(r["cuota_mensual_c"], pesos(84_613))
        self.assertEqual(r["margen_al_tope_c"], pesos(628_651))
        codigo, salida = correr("monotributo", "--ingresos", "30000000", "--actividad", "servicios")
        self.assertEqual(codigo, 0)
        self.assertIn("Categoría:                D", salida)
        self.assertIn("$ 84.613", salida)
        self.assertIn("https://contablix.ar/calculadora-monotributo", salida)

    def test_ingreso_exactamente_en_el_tope_queda_en_la_categoria(self) -> None:
        r = calc.calcular_monotributo(DATA, pesos(12_009_410), "servicios")["resultado"]
        self.assertEqual(r["categoria"], "A")
        self.assertEqual(r["margen_al_tope_c"], 0)

    def test_un_peso_arriba_del_tope_sube_de_categoria(self) -> None:
        r = calc.calcular_monotributo(DATA, pesos(12_009_411), "servicios")["resultado"]
        self.assertEqual(r["categoria"], "B")
        self.assertEqual(r["cuota_mensual_c"], pesos(56_379))

    def test_un_centavo_arriba_del_tope_tambien_sube(self) -> None:
        r = calc.calcular_monotributo(DATA, pesos(30_628_651) + 1, "bienes")["resultado"]
        self.assertEqual(r["categoria"], "E")
        self.assertEqual(r["cuota_mensual_c"], pesos(108_268))

    def test_bienes_y_servicios_tienen_cuota_distinta_desde_c(self) -> None:
        serv = calc.calcular_monotributo(DATA, pesos(20_000_000), "servicios")["resultado"]
        bien = calc.calcular_monotributo(DATA, pesos(20_000_000), "bienes")["resultado"]
        self.assertEqual((serv["categoria"], serv["cuota_mensual_c"]), ("C", pesos(66_020)))
        self.assertEqual((bien["categoria"], bien["cuota_mensual_c"]), ("C", pesos(64_531)))

    def test_tope_exacto_de_k_no_excluye_y_no_hay_siguiente(self) -> None:
        r = calc.calcular_monotributo(DATA, pesos(126_610_839), "servicios")["resultado"]
        self.assertEqual(r["categoria"], "K")
        self.assertFalse(r["excluido"])
        self.assertEqual(r["cuota_mensual_c"], pesos(1_614_446))
        self.assertIsNone(r["siguiente_categoria"])

    def test_superar_k_es_exclusion_con_alerta(self) -> None:
        sobre = calc.calcular_monotributo(DATA, pesos(126_610_840), "servicios")
        r = sobre["resultado"]
        self.assertTrue(r["excluido"])
        self.assertIsNone(r["categoria"])
        self.assertIsNone(r["cuota_mensual_c"])
        self.assertEqual(r["exceso_sobre_tope_k_c"], pesos(1))
        self.assertIn("ALERTA DE EXCLUSIÓN", r["alerta"])
        self.assertIn("Responsable Inscripto", sobre["notas"][0])
        codigo, salida = correr("monotributo", "--ingresos", "126610840", "--actividad", "servicios")
        self.assertEqual(codigo, 0)
        self.assertIn("EXCLUIDO del monotributo", salida)

    def test_alquileres_pueden_subir_la_categoria(self) -> None:
        r = calc.calcular_monotributo(DATA, pesos(1_000_000), "servicios", pesos(3_000_000))["resultado"]
        self.assertEqual(r["categoria_por_ingresos"], "A")
        self.assertEqual(r["categoria_por_alquileres"], "C")
        self.assertEqual(r["categoria"], "C")
        self.assertEqual(r["cuota_mensual_c"], pesos(66_020))

    def test_alquileres_sobre_el_maximo_excluyen(self) -> None:
        r = calc.calcular_monotributo(DATA, pesos(1_000_000), "bienes", pesos(8_378_659))["resultado"]
        self.assertTrue(r["excluido"])
        self.assertIsNone(r["exceso_sobre_tope_k_c"])
        self.assertIn("alquileres", r["alerta"])

    def test_escala_es_consistente(self) -> None:
        cats = DATA["monotributo"]["categorias"]
        self.assertEqual([c["categoria"] for c in cats], list("ABCDEFGHIJK"))
        for prev, cur in zip(cats, cats[1:]):
            self.assertLess(prev["tope_ingresos"], cur["tope_ingresos"])
            self.assertLess(prev["cuota_servicios"], cur["cuota_servicios"])
            self.assertLessEqual(prev["tope_alquileres"], cur["tope_alquileres"])
        for c in cats:
            self.assertGreaterEqual(c["cuota_servicios"], c["cuota_bienes"])


class TestResponsableInscripto(unittest.TestCase):
    def test_iva_iibb_y_autonomos(self) -> None:
        r = calc.calcular_ri(DATA, pesos(2_000_000), pesos(500_000), 35_000, pesos(50_000))["resultado"]
        self.assertEqual(r["iva_debito_c"], pesos(420_000))
        self.assertEqual(r["iva_credito_c"], pesos(105_000))
        self.assertEqual(r["iva_a_pagar_c"], pesos(315_000))
        self.assertEqual(r["iibb_c"], pesos(70_000))
        self.assertEqual(r["subtotal_mensual_sin_ganancias_c"], pesos(435_000))
        self.assertFalse(r["ganancias_estimada"])

    def test_saldo_a_favor_no_suma_al_subtotal(self) -> None:
        r = calc.calcular_ri(DATA, pesos(100_000), pesos(300_000), 30_000, 0)["resultado"]
        self.assertEqual(r["saldo_iva_c"], -pesos(42_000))
        self.assertEqual(r["saldo_a_favor_iva_c"], pesos(42_000))
        self.assertEqual(r["iva_a_pagar_c"], 0)
        self.assertEqual(r["subtotal_mensual_sin_ganancias_c"], pesos(3_000))

    def test_alicuota_reducida_redondea_al_centavo(self) -> None:
        r = calc.calcular_ri(DATA, 12_345, 0, 0, 0, 105_000)["resultado"]
        # $ 123,45 x 10,5 % = $ 12,96225 -> $ 12,96
        self.assertEqual(r["iva_debito_c"], 1_296)

    def test_cli_deriva_ganancias_al_simulador(self) -> None:
        codigo, salida = correr("ri", "--ventas-mensuales", "2000000", "--compras-con-iva", "500000",
                                "--alicuota-iibb", "3.5", "--autonomos", "50000")
        self.assertEqual(codigo, 0)
        self.assertIn("Ganancias:", salida)
        self.assertIn("no se estima", salida)
        self.assertIn("https://contablix.ar/impuestos-responsable-inscripto", salida)


class TestRetenciones(unittest.TestCase):
    ESPERADO_RG5319 = {
        "ri": 1, "ri_ddjj_sin_presentar": 3, "ri_sin_dfe": 5, "ri_limitado": 7,
        "mono_excedido": 7, "mono": 0, "no_categorizado": 8,
    }

    def test_tabla_rg5319_por_condicion(self) -> None:
        for condicion, pct in self.ESPERADO_RG5319.items():
            with self.subTest(condicion=condicion):
                r = calc.calcular_retenciones(DATA, pesos(100_000), condicion)["resultado"]
                self.assertEqual(r["percepcion_iva_rg5319_c"], pesos(1_000 * pct))

    def test_monotributista_dentro_de_parametros_no_sufre_percepcion(self) -> None:
        r = calc.calcular_retenciones(DATA, pesos(250_000), "mono", 20_000, 0)["resultado"]
        self.assertEqual(r["percepcion_iva_rg5319_c"], 0)
        self.assertEqual(r["retencion_sirtac_c"], pesos(5_000))
        self.assertEqual(r["neto_cobrado_c"], pesos(245_000))

    def test_suma_de_regimenes_y_neto(self) -> None:
        r = calc.calcular_retenciones(DATA, pesos(100_000), "ri", 20_000, 5_000)["resultado"]
        self.assertEqual(r["total_retenido_percibido_c"], pesos(3_500))
        self.assertEqual(r["neto_cobrado_c"], pesos(96_500))

    def test_no_categorizado_explica_habitualidad(self) -> None:
        notas = calc.calcular_retenciones(DATA, pesos(1_000), "no_categorizado")["notas"]
        self.assertTrue(any("$ 750.000" in n and "$ 1.500.000" in n for n in notas))

    def test_sirtac_mayor_al_maximo_es_error_de_uso(self) -> None:
        codigo, _ = correr("retenciones", "--monto", "1000", "--condicion", "ri", "--alicuota-sirtac", "5.01")
        self.assertEqual(codigo, 2)

    def test_cli_recuerda_pago_a_cuenta_y_link(self) -> None:
        codigo, salida = correr("retenciones", "--monto", "100000", "--condicion", "ri", "--alicuota-sirtac", "2")
        self.assertEqual(codigo, 0)
        self.assertIn("pago a cuenta", salida)
        self.assertIn("RG 5554", salida)
        self.assertIn("https://contablix.ar/servicios/consultoria-ecommerce", salida)


class TestFacturaE(unittest.TestCase):
    def test_pesos_al_tipo_de_cambio_y_salto_de_categoria(self) -> None:
        sobre = calc.calcular_factura_e(DATA, pesos(2_000), 14_505_000, "humana", pesos(28_000_000), "servicios")
        r = sobre["resultado"]
        self.assertEqual(r["pesos_c"], pesos(2_901_000))
        imp = r["impacto_monotributo"]
        self.assertEqual(imp["antes"]["categoria"], "D")
        self.assertEqual(imp["despues"]["categoria"], "E")
        self.assertEqual(imp["despues"]["cuota_mensual_c"], pesos(119_811))
        self.assertTrue(imp["cambia_categoria"])
        self.assertIn("8330", r["regla_cambiaria"]["normas"])

    def test_tope_usd_36000_es_historico_no_vigente(self) -> None:
        r = calc.calcular_factura_e(DATA, pesos(50_000), 10_000_000, "humana", 0, "servicios")["resultado"]
        self.assertEqual(r["tope_historico_usd"], {"monto": 36_000, "vigente": False})
        self.assertIn("no estás obligada a liquidar", r["regla_cambiaria"]["texto"])

    def test_factura_que_hace_superar_k_avisa_exclusion(self) -> None:
        imp = calc.calcular_factura_e(DATA, pesos(10_000), 14_000_000, "humana", pesos(120_000_000),
                                      "servicios")["resultado"]["impacto_monotributo"]
        self.assertTrue(imp["despues"]["excluido"])

    def test_sociedad_liquida_en_el_mlc_y_no_es_monotributo(self) -> None:
        r = calc.calcular_factura_e(DATA, pesos(1_000), 10_000_000, "sociedad", 0, "servicios")["resultado"]
        self.assertIsNone(r["impacto_monotributo"])
        self.assertIn("8137", r["regla_cambiaria"]["normas"])
        codigo, _ = correr("factura-e", "--usd", "1000", "--tc", "1000", "--persona", "sociedad",
                           "--condicion", "monotributo")
        self.assertEqual(codigo, 2)

    def test_cli_link_freelancers(self) -> None:
        codigo, salida = correr("factura-e", "--usd", "2000", "--tc", "1450.5", "--ingresos-12m", "20000000")
        self.assertEqual(codigo, 0)
        self.assertIn("$ 2.901.000", salida)
        self.assertIn("https://contablix.ar/servicios/freelancers-contractors", salida)


class TestJson(unittest.TestCase):
    def test_salida_json_en_pesos(self) -> None:
        codigo, salida = correr("monotributo", "--ingresos", "30000000", "--actividad", "servicios", "--json")
        self.assertEqual(codigo, 0)
        datos = json.loads(salida)
        self.assertEqual(datos["resultado"]["categoria"], "D")
        self.assertEqual(datos["resultado"]["cuota_mensual"], 84613)
        self.assertEqual(datos["resultado"]["margen_al_tope_pct"], 2.05)
        self.assertEqual(datos["link"]["url"], "https://contablix.ar/calculadora-monotributo")


if __name__ == "__main__":
    unittest.main()
