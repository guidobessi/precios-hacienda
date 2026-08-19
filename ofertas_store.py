"""
Persistencia simple de las ofertas del comparador en un archivo JSON local,
para que no se pierdan al recargar la página (st.session_state solo no alcanza,
se resetea en cada reload del navegador).
"""
import json
import logging
from dataclasses import asdict
from pathlib import Path

from comparador_ofertas import Oferta

log = logging.getLogger(__name__)

OFERTAS_PATH = Path(__file__).parent / "data" / "ofertas.json"


def cargar_ofertas() -> list[Oferta]:
    if not OFERTAS_PATH.exists():
        return []
    try:
        data = json.loads(OFERTAS_PATH.read_text(encoding="utf-8"))
        return [Oferta(**o) for o in data]
    except Exception:
        log.exception("No se pudo leer %s, se ignora el archivo", OFERTAS_PATH)
        return []


def guardar_ofertas(ofertas: list[Oferta]) -> None:
    OFERTAS_PATH.parent.mkdir(exist_ok=True)
    OFERTAS_PATH.write_text(
        json.dumps([asdict(o) for o in ofertas], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
