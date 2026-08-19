"""
Persistencia de las categorías favoritas elegidas en la barra lateral, para
que sobrevivan a un reload del navegador (una sesión nueva de Streamlit
perdía la selección y volvía siempre al default hardcodeado).
"""
import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

FAVORITOS_PATH = Path(__file__).parent / "data" / "favoritos.json"


def cargar_favoritos() -> Optional[list]:
    """Devuelve la lista guardada, o None si todavía no se guardó nada
    (para que el caller pueda usar su propio default de fábrica)."""
    if not FAVORITOS_PATH.exists():
        return None
    try:
        return json.loads(FAVORITOS_PATH.read_text(encoding="utf-8"))
    except Exception:
        log.exception("No se pudo leer %s, se ignora el archivo", FAVORITOS_PATH)
        return None


def guardar_favoritos(favoritos: list) -> None:
    FAVORITOS_PATH.parent.mkdir(exist_ok=True)
    FAVORITOS_PATH.write_text(
        json.dumps(favoritos, ensure_ascii=False, indent=2), encoding="utf-8",
    )
