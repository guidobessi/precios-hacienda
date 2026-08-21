"""
Tests de persistencia de lotes_store.py (usa un archivo temporal, no toca
el data/lotes.json real).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import lotes_store


def test_cargar_sin_archivo_devuelve_diccionario_vacio(tmp_path, monkeypatch):
    monkeypatch.setattr(lotes_store, "LOTES_PATH", tmp_path / "no_existe.json")
    assert lotes_store.cargar_referencias_lote() == {}


def test_guardar_y_cargar_referencia(tmp_path, monkeypatch):
    monkeypatch.setattr(lotes_store, "LOTES_PATH", tmp_path / "lotes.json")
    lotes_store.guardar_referencia_lote("Novillos 400kg", 5225.0)
    assert lotes_store.cargar_referencias_lote() == {"Novillos 400kg": 5225.0}


def test_guardar_referencia_en_cero_la_elimina(tmp_path, monkeypatch):
    monkeypatch.setattr(lotes_store, "LOTES_PATH", tmp_path / "lotes.json")
    lotes_store.guardar_referencia_lote("Novillos 400kg", 5225.0)
    lotes_store.guardar_referencia_lote("Novillos 400kg", 0)
    assert lotes_store.cargar_referencias_lote() == {}


def test_no_pisa_referencias_de_otros_lotes(tmp_path, monkeypatch):
    monkeypatch.setattr(lotes_store, "LOTES_PATH", tmp_path / "lotes.json")
    lotes_store.guardar_referencia_lote("Novillos 400kg", 5225.0)
    lotes_store.guardar_referencia_lote("Vaquillonas 350kg", 4500.0)
    assert lotes_store.cargar_referencias_lote() == {
        "Novillos 400kg": 5225.0,
        "Vaquillonas 350kg": 4500.0,
    }
