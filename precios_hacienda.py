"""
Precios de mercado de hacienda (invernada y faena) desde fuentes públicas:
  - deCampoaCampo: invernada (Machos/Hembras/Vientres) y faena (Cañuelas)
  - Mercado Agroganadero: precios por categoría de faena

Cada fuente se separa en `_parse_*` (puro, sin red, testeable) y `fetch_*`
(hace el GET y llama al parser correspondiente).
"""
import re
from datetime import date, datetime, timedelta
from typing import Optional

import requests
from lxml import html as lxml_html

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 20

DCAC_AJAX_URL = "https://www.decampoacampo.com/gh_funciones.php"
MAG_URL = "https://www.mercadoagroganadero.com.ar/dll/hacienda1.dll/haciinfo000502"

INVERNADA_GRUPOS = [(1, "Machos"), (2, "Hembras"), (3, "Vientres")]


# ─── Helpers ────────────────────────────────────────────────────────────────

def _num_ar(s: str) -> float:
    """Convierte un número con formato AR ('1.019.651.000,00' o '3200,000') a float."""
    s = s.strip().lstrip("$").strip()
    s = s.replace(".", "").replace(",", ".")
    return float(s)


def _dd_mm_to_date(dd_mm: str, hoy: Optional[date] = None) -> date:
    """Convierte 'DD/MM' (sin año) a date, asumiendo el año actual salvo que
    el resultado quede muy en el futuro (cruce de fin de año)."""
    hoy = hoy or date.today()
    dia, mes = (int(x) for x in dd_mm.split("/"))
    d = date(hoy.year, mes, dia)
    if d > hoy + timedelta(days=3):
        d = date(hoy.year - 1, mes, dia)
    return d


# ─── deCampoaCampo · Invernada ──────────────────────────────────────────────

def _parse_invernada_json(data: dict, grupo: str, hoy: Optional[date] = None) -> list[dict]:
    fecha_dato = _dd_mm_to_date(data["semana_actual"]["hasta"], hoy)
    # deCampoaCampo vende "Vientres" (vacas/vaquillonas preñadas o con cría)
    # por bulto/cabeza, no por Kg — no se puede comparar en la misma escala
    # que el resto de las categorías de invernada.
    unidad = "Bulto" if grupo == "Vientres" else "Kg"
    rows = []
    for item in data["data"]:
        rows.append({
            "fuente": "decampoacampo_invernada",
            "tipo": "invernada",
            "grupo": grupo,
            "unidad": unidad,
            "categoria": item["categoria"],
            "precio": float(item["precio_semana_1"]),
            "precio_usd": item.get("precio_semana_1_usd"),
            "precio_anterior": float(item["precio_semana_2"]),
            "variacion": item.get("variacion_precio_semana_1"),
            "cantidad": item.get("cantidad_semana_1"),
            "fecha_dato": fecha_dato,
        })
    return rows


def fetch_invernada() -> list[dict]:
    rows = []
    for p, grupo in INVERNADA_GRUPOS:
        r = requests.get(
            DCAC_AJAX_URL,
            params={"function": "getListadoPreciosInvernada", "p": p, "m": "peso"},
            headers=HEADERS, timeout=TIMEOUT,
        )
        r.raise_for_status()
        rows.extend(_parse_invernada_json(r.json(), grupo))
    return rows


# ─── deCampoaCampo · Faena (Cañuelas) ───────────────────────────────────────

def _parse_gordo_json(data: dict) -> list[dict]:
    fecha_dato = datetime.strptime(data["hoy"], "%d/%m/%Y").date()
    rows = []
    for item in data["data"]:
        rows.append({
            "fuente": "decampoacampo_faena",
            "tipo": "faena",
            "grupo": None,
            "categoria": item["categoria"],
            "precio": float(item["precio_semana_1"]),
            "precio_usd": item.get("precio_semana_1_usd"),
            "precio_anterior": float(item["precio_semana_2"]),
            "variacion": item.get("variacion_precio_semana_1"),
            "cantidad": item.get("cantidad_semana_1"),
            "fecha_dato": fecha_dato,
        })
    return rows


def fetch_faena_canuelas() -> list[dict]:
    r = requests.get(
        DCAC_AJAX_URL,
        params={"function": "getListadoPreciosGordo"},
        headers=HEADERS, timeout=TIMEOUT,
    )
    r.raise_for_status()
    return _parse_gordo_json(r.json())


# ─── Mercado Agroganadero · Faena ───────────────────────────────────────────

_FECHA_RE = re.compile(r"AL\s+\S+\s+(\d{2}/\d{2}/\d{4})")


def _parse_mag_html(html_text: str) -> list[dict]:
    m = _FECHA_RE.search(html_text)
    if not m:
        raise ValueError("No se encontró la fecha del reporte en la página de Mercado Agroganadero")
    fecha_dato = datetime.strptime(m.group(1), "%d/%m/%Y").date()

    doc = lxml_html.fromstring(html_text)
    trs = doc.xpath('//table[contains(@class,"table-striped")]//tr')

    rows = []
    for tr in trs:
        tds = tr.xpath("./td")
        if len(tds) != 9:
            continue
        categoria = tds[0].text_content().strip()
        if not categoria or categoria.startswith("-"):
            continue
        try:
            rows.append({
                "fuente": "mag_faena",
                "tipo": "faena",
                "grupo": None,
                "categoria": categoria,
                "precio": _num_ar(tds[3].text_content()),  # promedio
                "precio_usd": None,
                "precio_anterior": None,
                "precio_min": _num_ar(tds[1].text_content()),
                "precio_max": _num_ar(tds[2].text_content()),
                "variacion": None,
                "cantidad": int(_num_ar(tds[5].text_content())),
                "fecha_dato": fecha_dato,
            })
        except ValueError:
            pass  # fila de subtotal/totales, no es una categoría
    return rows


def fetch_faena_mag() -> list[dict]:
    r = requests.get(MAG_URL, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return _parse_mag_html(r.text)
