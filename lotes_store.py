"""
Persistencia del precio de referencia (venta directa neta, ver DESCUENTO_FERIA
en app.py) que el usuario puede cargar por cada lote de venta del comparador
de ofertas, para saber si una oferta le conviene más que vender directo.
"""
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

LOTES_PATH = Path(__file__).parent / "data" / "lotes.json"


def cargar_referencias_lote() -> dict:
    if not LOTES_PATH.exists():
        return {}
    try:
        return json.loads(LOTES_PATH.read_text(encoding="utf-8"))
    except Exception:
        log.exception("No se pudo leer %s, se ignora el archivo", LOTES_PATH)
        return {}


def guardar_referencia_lote(lote: str, precio_referencia) -> None:
    referencias = cargar_referencias_lote()
    if precio_referencia:
        referencias[lote] = precio_referencia
    else:
        referencias.pop(lote, None)
    LOTES_PATH.parent.mkdir(exist_ok=True)
    LOTES_PATH.write_text(
        json.dumps(referencias, ensure_ascii=False, indent=2), encoding="utf-8",
    )
