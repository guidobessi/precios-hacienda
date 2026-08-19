"""
Tests de persistencia de ofertas_store.py (usa un archivo temporal, no toca
el data/ofertas.json real).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import ofertas_store
from comparador_ofertas import Oferta


def test_cargar_sin_archivo_devuelve_lista_vacia(tmp_path, monkeypatch):
    monkeypatch.setattr(ofertas_store, "OFERTAS_PATH", tmp_path / "no_existe.json")
    assert ofertas_store.cargar_ofertas() == []


def test_guardar_y_cargar_ida_y_vuelta(tmp_path, monkeypatch):
    monkeypatch.setattr(ofertas_store, "OFERTAS_PATH", tmp_path / "ofertas.json")
    ofertas = [
        Oferta(comprador="A", precio_base=5000, tipo_precio="en_pie"),
        Oferta(comprador="B", precio_base=9000, tipo_precio="gancho", rinde_pct=57, plazo_dias=30),
    ]
    ofertas_store.guardar_ofertas(ofertas)
    recuperadas = ofertas_store.cargar_ofertas()
    assert len(recuperadas) == 2
    assert recuperadas[0].comprador == "A"
    assert recuperadas[1].rinde_pct == 57
    assert recuperadas[1].plazo_dias == 30


def test_archivo_corrupto_no_rompe(tmp_path, monkeypatch):
    p = tmp_path / "ofertas.json"
    p.write_text("esto no es json valido{{{")
    monkeypatch.setattr(ofertas_store, "OFERTAS_PATH", p)
    assert ofertas_store.cargar_ofertas() == []
