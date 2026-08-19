"""
Tests del comparador de ofertas (comparador_ofertas.py).
Ejecutar con: pytest tests/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from comparador_ofertas import Oferta, normalizar_oferta


def test_precio_final_simple_sin_ajustes():
    o = Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie", incluye_iva=True)
    r = normalizar_oferta(o)
    assert r["precio_final"] == 5000


def test_lote_tiene_default_y_viaja_en_el_resultado():
    o = Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie", incluye_iva=True)
    assert o.lote == "General"
    r = normalizar_oferta(o)
    assert r["lote"] == "General"

    o2 = Oferta(comprador="B", precio_base=5000, tipo_precio="en_pie", incluye_iva=True, lote="Novillos 400kg")
    assert normalizar_oferta(o2)["lote"] == "Novillos 400kg"


def test_suma_iva_cuando_no_esta_incluido():
    o = Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie", incluye_iva=False, iva_pct=10.5)
    r = normalizar_oferta(o)
    assert r["precio_sin_iva"] == 5000
    assert round(r["precio_con_iva"], 2) == round(5000 * 1.105, 2)
    assert round(r["precio_final"], 2) == round(5000 * 1.105, 2)


def test_desglosa_sin_iva_cuando_ya_esta_incluido():
    # Si ya viene con IVA, "sin IVA" se calcula al revés (dividiendo), no
    # queda igual al precio con IVA.
    o = Oferta(comprador="A", precio_base=5525, tipo_precio="en_pie", incluye_iva=True, iva_pct=10.5)
    r = normalizar_oferta(o)
    assert r["precio_con_iva"] == 5525
    assert round(r["precio_sin_iva"], 2) == round(5525 / 1.105, 2)


def test_descuenta_comision():
    o = Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie", incluye_iva=True,
               tiene_comision=True, comision_pct=4)
    r = normalizar_oferta(o)
    assert round(r["precio_final"], 2) == round(5000 * 0.96, 2)


def test_comision_ignorada_si_flag_apagado():
    o = Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie", incluye_iva=True,
               tiene_comision=False, comision_pct=99)
    r = normalizar_oferta(o)
    assert r["precio_final"] == 5000


def test_convierte_precio_en_gancho_por_rinde():
    o = Oferta(comprador="A", precio_base=9000, tipo_precio="gancho", rinde_pct=56, incluye_iva=True)
    r = normalizar_oferta(o)
    assert round(r["precio_en_pie"], 2) == round(9000 * 0.56, 2)
    assert round(r["precio_final"], 2) == round(9000 * 0.56, 2)


def test_precio_final_no_usa_rinde():
    o = Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie", rinde_pct=40, incluye_iva=True)
    r = normalizar_oferta(o)
    assert r["precio_en_pie"] == 5000


def test_descuenta_por_plazo_de_pago():
    o = Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie", incluye_iva=True,
               plazo_dias=30, tasa_mensual_pct=3)
    r = normalizar_oferta(o)
    assert round(r["precio_final"], 2) == round(5000 / 1.03, 2)


def test_sin_plazo_no_hay_descuento():
    o = Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie", incluye_iva=True,
               plazo_dias=0, tasa_mensual_pct=5)
    r = normalizar_oferta(o)
    assert r["precio_final"] == 5000


def test_combina_las_cinco_variables_en_el_orden_correcto():
    # Gancho -> IVA -> comisión -> plazo, en ese orden.
    o = Oferta(
        comprador="Frigorífico X", precio_base=9500, tipo_precio="gancho", rinde_pct=57,
        incluye_iva=False, iva_pct=10.5, tiene_comision=True, comision_pct=3,
        plazo_dias=60, tasa_mensual_pct=4, peso_total_kg=10000,
    )
    r = normalizar_oferta(o)
    esperado_en_pie = 9500 * 0.57
    esperado_bruto = esperado_en_pie * 1.105
    esperado_neto_comision = esperado_bruto * 0.97
    esperado_final = esperado_neto_comision / (1.04 ** 2)
    assert round(r["precio_final"], 4) == round(esperado_final, 4)
    assert round(r["monto_total"], 2) == round(esperado_final * 10000, 2)


def test_monto_total_none_si_no_hay_peso():
    o = Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie", incluye_iva=True)
    r = normalizar_oferta(o)
    assert r["monto_total"] is None


def test_achique_ignorado_si_flag_apagado():
    o = Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie", incluye_iva=False, iva_pct=10.5,
               tiene_achique=False, achique_pct=50)
    r = normalizar_oferta(o)
    assert round(r["precio_final"], 2) == round(5000 * 1.105, 2)


def test_achique_no_lleva_iva_en_la_parte_negra():
    # 5000 sin IVA -> con IVA = 5525. Con 20% de achique: 80% factura con
    # IVA (5525*0.8) + 20% en negro sin IVA (5000*0.2).
    o = Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie", incluye_iva=False, iva_pct=10.5,
               tiene_achique=True, achique_pct=20)
    r = normalizar_oferta(o)
    esperado = (5000 * 1.105) * 0.8 + 5000 * 0.2
    assert round(r["precio_con_achique"], 4) == round(esperado, 4)
    assert round(r["precio_final"], 4) == round(esperado, 4)
    # El achique siempre da un número menor al "todo facturado", porque esa
    # porción se queda sin el recargo de IVA.
    assert r["precio_con_achique"] < r["precio_con_iva"]


def test_achique_100_por_ciento_equivale_a_precio_sin_iva():
    o = Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie", incluye_iva=False, iva_pct=10.5,
               tiene_achique=True, achique_pct=100)
    r = normalizar_oferta(o)
    assert round(r["precio_con_achique"], 4) == round(r["precio_sin_iva"], 4)


def test_achique_se_combina_con_comision_y_plazo():
    o = Oferta(
        comprador="A", precio_base=5000, tipo_precio="en_pie", incluye_iva=False, iva_pct=10.5,
        tiene_achique=True, achique_pct=30, tiene_comision=True, comision_pct=3,
        plazo_dias=30, tasa_mensual_pct=3, peso_total_kg=1000,
    )
    r = normalizar_oferta(o)
    con_achique = (5000 * 1.105) * 0.7 + 5000 * 0.3
    neto_comision = con_achique * 0.97
    esperado_final = neto_comision / 1.03
    assert round(r["precio_final"], 4) == round(esperado_final, 4)
    assert round(r["monto_total"], 2) == round(esperado_final * 1000, 2)
