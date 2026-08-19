"""
Tests de persistencia de favoritos_store.py (usa un archivo temporal, no toca
el data/favoritos.json real).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import favoritos_store


def test_cargar_sin_archivo_devuelve_none(tmp_path, monkeypatch):
    monkeypatch.setattr(favoritos_store, "FAVORITOS_PATH", tmp_path / "no_existe.json")
    assert favoritos_store.cargar_favoritos() is None


def test_guardar_y_cargar_ida_y_vuelta(tmp_path, monkeypatch):
    monkeypatch.setattr(favoritos_store, "FAVORITOS_PATH", tmp_path / "favoritos.json")
    favoritos = ["Terneros 160-180 Kg. · Invernada", "NOVILLITOS Esp. h 390 · Faena MAG"]
    favoritos_store.guardar_favoritos(favoritos)
    assert favoritos_store.cargar_favoritos() == favoritos


def test_archivo_corrupto_devuelve_none(tmp_path, monkeypatch):
    p = tmp_path / "favoritos.json"
    p.write_text("no es json valido{{{")
    monkeypatch.setattr(favoritos_store, "FAVORITOS_PATH", p)
    assert favoritos_store.cargar_favoritos() is None
