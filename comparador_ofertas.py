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
    lote: str = "General"  # agrupa ofertas que compiten entre sí (mismo lote de venta)
    rinde_pct: float = 56.0  # sólo aplica si tipo_precio == "gancho"
    incluye_iva: bool = False
    iva_pct: float = 10.5
    tiene_comision: bool = False
    comision_pct: float = 0.0
    tiene_achique: bool = False
    achique_pct: float = 0.0  # % de la operación que se cobra en negro (sin factura, sin IVA)
    plazo_dias: int = 0
    tasa_mensual_pct: float = 3.0
    peso_total_kg: float = 0.0


def normalizar_oferta(o: Oferta) -> dict:
    precio_en_pie = o.precio_base * (o.rinde_pct / 100) if o.tipo_precio == "gancho" else o.precio_base

    # Se calculan siempre las dos bases (sin IVA y con IVA), sin importar
    # cómo haya cotizado el comprador, para poder comparar ofertas que vienen
    # en formatos distintos ("precio final" vs. "+ IVA") una al lado de la otra.
    if o.incluye_iva:
        precio_con_iva = precio_en_pie
        precio_sin_iva = precio_en_pie / (1 + o.iva_pct / 100)
    else:
        precio_sin_iva = precio_en_pie
        precio_con_iva = precio_en_pie * (1 + o.iva_pct / 100)

    # Achique: la parte que se cobra en negro no lleva IVA (misma lógica que
    # pct_facturado/pct_negro en La Uno Agro) — sólo la porción facturada
    # recibe el recargo de IVA, la porción en negro se suma tal cual.
    achique = o.achique_pct if o.tiene_achique else 0.0
    pct_facturado = 1 - achique / 100
    pct_negro = achique / 100
    precio_con_achique = precio_con_iva * pct_facturado + precio_sin_iva * pct_negro

    comision = o.comision_pct if o.tiene_comision else 0.0
    precio_neto_comision = precio_con_achique * (1 - comision / 100)

    meses = o.plazo_dias / 30
    factor_descuento = (1 + o.tasa_mensual_pct / 100) ** meses
    precio_final = precio_neto_comision / factor_descuento

    return {
        "comprador": o.comprador,
        "lote": o.lote,
        "precio_base": o.precio_base,
        "tipo_precio": o.tipo_precio,
        "rinde_pct": o.rinde_pct,
        "precio_en_pie": precio_en_pie,
        "precio_sin_iva": precio_sin_iva,
        "precio_con_iva": precio_con_iva,
        "achique_pct": achique,
        "precio_con_achique": precio_con_achique,
        "comision_pct": comision,
        "precio_neto_comision": precio_neto_comision,
        "plazo_dias": o.plazo_dias,
        "tasa_mensual_pct": o.tasa_mensual_pct,
        "precio_final": precio_final,
        "monto_total": precio_final * o.peso_total_kg if o.peso_total_kg else None,
    }
