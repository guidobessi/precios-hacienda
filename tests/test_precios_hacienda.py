"""
Tests de parseo de precios_hacienda.py usando muestras reales (sin red).
Ejecutar con: pytest tests/
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from precios_hacienda import (
    _num_ar,
    _dd_mm_to_date,
    _parse_invernada_json,
    _parse_gordo_json,
    _parse_mag_html,
)

INVERNADA_SAMPLE = {
    "semana_actual": {"hasta": "18/08", "desde": "11/08"},
    "semana_pasada": {"hasta": "10/08", "desde": "03/08"},
    "cotizacion_semana_actual": "1515.17",
    "data": [
        {
            "categoria": "Terneros -160 Kg.",
            "cantidad_semana_1": 2190, "cantidad_semana_2": 654,
            "precio_semana_1": 6630, "precio_semana_2": 6920,
            "precio_semana_1_usd": 4.38, "precio_semana_2_usd": 4.56,
            "variacion_precio_semana_1": -290, "variacion_precio_semana_1_usd": -0.18,
        },
        {
            "categoria": "Terneros 160-180 Kg.",
            "cantidad_semana_1": 2141, "cantidad_semana_2": 1316,
            "precio_semana_1": 6520, "precio_semana_2": 6540,
            "precio_semana_1_usd": 4.30, "precio_semana_2_usd": 4.31,
            "variacion_precio_semana_1": -20, "variacion_precio_semana_1_usd": -0.01,
        },
    ],
}

GORDO_SAMPLE = {
    "hoy": "18/08/2026",
    "semana_pasada": {"hasta": "17/08", "desde": "10/08"},
    "data": [
        {
            "categoria": "Novillitos hasta 390 Kg.",
            "cantidad_semana_1": 563, "cantidad_semana_2": 2085,
            "precio_semana_1": 4990, "precio_semana_2": 5020,
            "precio_semana_1_usd": 3.29, "precio_semana_2_usd": 3.31,
            "variacion_precio_semana_1": -30, "variacion_precio_semana_1_usd": -0.02,
        },
    ],
}

MAG_HTML_SAMPLE = """
<html><body>
<h6>PRECIOS POR CATEGORIA RESOL-2018-32-APN-SGA#MPYT DESDE EL MARTES 18/08/2026 AL MARTES 18/08/2026<BR>PRECIOS DEFINITIVOS</h6>
<Table Align="Center" CellSpacing=1 CellPadding=0 Border=0 class="table table-striped">
<TR VAlign="Bottom"><TH>Categoría</TH><TH colspan="4">Precios</TH><TH colspan="3">Totales</TH><TH>Prom.</TH></TR>
<TR VAlign="Bottom"><TH></TH><TH>Mínimo</TH><TH>Máximo</TH><TH>Promedio</TH><TH>Mediana</TH><TH>Cabezas</TH><TH>Importe</TH><TH>Kgs</TH><TH>Kgs</TH></TR>
<TR VAlign="Bottom"><TD><BR>NOVILLOS Esp.Joven + 430 </TD><TD Align="Center">3200,000</TD><TD Align="Center">4700,000</TD><TD Align="Center">4461,294</TD><TD Align="Center">4600,000</TD><TD Align="Right">478</TD><TD Align="Right">$1.019.651.000,00</TD><TD Align="Right">228.555</TD><TD Align="Right">478</TD></TR>
<TR VAlign="Bottom"><TD></TD><TD></TD><TD></TD><TD Align="Center">-------</TD><TD></TD><TD Align="Right">--------</TD><TD Align="Right">--------------------</TD><TD Align="Right">-------------</TD><TD Align="Right">------</TD></TR>
</Table>
</body></html>
"""


def test_num_ar_parses_ar_formatted_numbers():
    assert _num_ar("3200,000") == 3200.0
    assert _num_ar("4.383,697") == 4383.697
    assert _num_ar("$1.019.651.000,00") == 1019651000.0
    assert _num_ar("228.555") == 228555.0


def test_dd_mm_to_date_same_year():
    assert _dd_mm_to_date("18/08", hoy=date(2026, 8, 18)) == date(2026, 8, 18)


def test_dd_mm_to_date_year_rollover():
    assert _dd_mm_to_date("31/12", hoy=date(2026, 1, 3)) == date(2025, 12, 31)


def test_parse_invernada_json():
    rows = _parse_invernada_json(INVERNADA_SAMPLE, "Machos", hoy=date(2026, 8, 18))
    assert len(rows) == 2
    r0 = rows[0]
    assert r0["categoria"] == "Terneros -160 Kg."
    assert r0["fuente"] == "decampoacampo_invernada"
    assert r0["grupo"] == "Machos"
    assert r0["unidad"] == "Kg"
    assert r0["precio"] == 6630
    assert r0["precio_anterior"] == 6920
    assert r0["variacion_usd"] == -0.18
    assert r0["fecha_dato"] == date(2026, 8, 18)
    assert r0["periodo_comparacion"] == "03/08 al 10/08"


def test_parse_invernada_json_vientres_es_bulto():
    rows = _parse_invernada_json(INVERNADA_SAMPLE, "Vientres", hoy=date(2026, 8, 18))
    assert rows[0]["unidad"] == "Bulto"


def test_parse_gordo_json():
    rows = _parse_gordo_json(GORDO_SAMPLE)
    assert len(rows) == 1
    r0 = rows[0]
    assert r0["fuente"] == "decampoacampo_faena"
    assert r0["categoria"] == "Novillitos hasta 390 Kg."
    assert r0["precio"] == 4990
    assert r0["fecha_dato"] == date(2026, 8, 18)
    assert r0["periodo_comparacion"] == "10/08 al 17/08"


def test_parse_mag_html():
    rows = _parse_mag_html(MAG_HTML_SAMPLE)
    assert len(rows) == 1  # la fila de subtotal (categoría "-------") se descarta
    r0 = rows[0]
    assert r0["fuente"] == "mag_faena"
    assert r0["categoria"] == "NOVILLOS Esp.Joven + 430"
    assert r0["precio_min"] == 3200.0
    assert r0["precio_max"] == 4700.0
    assert r0["precio"] == 4700.0  # el precio "principal" de MAG es el máximo, no el promedio
    assert r0["precio_promedio"] == 4461.294
    assert r0["cantidad"] == 478
    assert r0["fecha_dato"] == date(2026, 8, 18)
