"""
Comparador de ofertas de compradores de hacienda.

Cada comprador cotiza distinto: precio final o "en gancho" (media res, según
rinde), con o sin IVA incluido, con o sin comisión, y a distintos plazos de
pago. normalizar_oferta() lleva todas las variantes a un mismo precio
comparable: $/Kg en pie, bruto con IVA, neto de comisión, y ajustado a valor
presente según el plazo de pago (para que una oferta más alta a 60 días no
parezca mejor que una más baja al contado sin darte cuenta).
"""
from dataclasses import dataclass


@dataclass
class Oferta:
    comprador: str
    precio_base: float
    tipo_precio: str  # "en_pie" | "gancho"
    rinde_pct: float = 56.0  # sólo aplica si tipo_precio == "gancho"
    incluye_iva: bool = False
    iva_pct: float = 10.5
    tiene_comision: bool = False
    comision_pct: float = 0.0
    plazo_dias: int = 0
    tasa_mensual_pct: float = 3.0
    peso_total_kg: float = 0.0


def normalizar_oferta(o: Oferta) -> dict:
    precio_en_pie = o.precio_base * (o.rinde_pct / 100) if o.tipo_precio == "gancho" else o.precio_base

    precio_bruto_iva = precio_en_pie if o.incluye_iva else precio_en_pie * (1 + o.iva_pct / 100)

    comision = o.comision_pct if o.tiene_comision else 0.0
    precio_neto_comision = precio_bruto_iva * (1 - comision / 100)

    meses = o.plazo_dias / 30
    factor_descuento = (1 + o.tasa_mensual_pct / 100) ** meses
    precio_final = precio_neto_comision / factor_descuento

    return {
        "comprador": o.comprador,
        "precio_base": o.precio_base,
        "tipo_precio": o.tipo_precio,
        "rinde_pct": o.rinde_pct,
        "precio_en_pie": precio_en_pie,
        "precio_bruto_iva": precio_bruto_iva,
        "comision_pct": comision,
        "precio_neto_comision": precio_neto_comision,
        "plazo_dias": o.plazo_dias,
        "tasa_mensual_pct": o.tasa_mensual_pct,
        "precio_final": precio_final,
        "monto_total": precio_final * o.peso_total_kg if o.peso_total_kg else None,
    }
