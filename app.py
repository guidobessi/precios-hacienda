import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from precios_hacienda import fetch_invernada, fetch_faena_canuelas, fetch_faena_mag

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

st.set_page_config(page_title="Precios Hacienda", page_icon="🐄", layout="wide")

st.title("🐄 Precios de Mercado de Hacienda")
st.caption(
    "Invernada y Faena — deCampoaCampo (Invernada + Cañuelas) y Mercado Agroganadero. "
    "Los precios se actualizan automáticamente cada 30 minutos."
)


@st.cache_data(ttl=1800, show_spinner="Consultando deCampoaCampo (invernada)...")
def _invernada() -> pd.DataFrame:
    return pd.DataFrame(fetch_invernada())


@st.cache_data(ttl=1800, show_spinner="Consultando deCampoaCampo (Cañuelas)...")
def _faena_canuelas() -> pd.DataFrame:
    return pd.DataFrame(fetch_faena_canuelas())


@st.cache_data(ttl=1800, show_spinner="Consultando Mercado Agroganadero...")
def _faena_mag() -> pd.DataFrame:
    return pd.DataFrame(fetch_faena_mag())


def _cargar(fetch_fn, nombre: str) -> pd.DataFrame:
    try:
        return fetch_fn()
    except Exception as e:
        st.error(f"No se pudo traer {nombre}: {e}")
        log.exception("Error trayendo %s", nombre)
        return pd.DataFrame()


col_btn, col_ts = st.columns([1, 4])
with col_btn:
    if st.button("🔄 Actualizar ahora", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with col_ts:
    st.caption(f"Última consulta: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

inv = _cargar(_invernada, "deCampoaCampo Invernada")
can = _cargar(_faena_canuelas, "deCampoaCampo Cañuelas")
mag = _cargar(_faena_mag, "Mercado Agroganadero")

tab_inv, tab_faena = st.tabs(["🐄 Invernada", "🥩 Faena"])

with tab_inv:
    if inv.empty:
        st.info("Sin datos de invernada disponibles.")
    else:
        sub_m, sub_h, sub_v = st.tabs(["Machos", "Hembras", "Vientres"])
        for grupo, tab in [("Machos", sub_m), ("Hembras", sub_h), ("Vientres", sub_v)]:
            with tab:
                g = inv[inv["grupo"] == grupo][
                    ["categoria", "precio", "precio_usd", "variacion", "cantidad", "precio_anterior"]
                ].rename(columns={
                    "categoria": "Categoría", "precio": "Precio ($/Kg+IVA)",
                    "precio_usd": "Precio (US$/Kg)", "variacion": "Var. semanal",
                    "cantidad": "Cabezas operadas", "precio_anterior": "Precio semana ant.",
                })
                st.dataframe(g, hide_index=True, use_container_width=True)

with tab_faena:
    st.subheader("Cañuelas (ex Mercado de Liniers)")
    if can.empty:
        st.info("Sin datos de Cañuelas disponibles.")
    else:
        g = can[["categoria", "precio", "precio_usd", "variacion", "cantidad", "precio_anterior"]].rename(columns={
            "categoria": "Categoría", "precio": "Precio ($/Kg+IVA)",
            "precio_usd": "Precio (US$/Kg)", "variacion": "Var. vs. semana ant.",
            "cantidad": "Cabezas operadas", "precio_anterior": "Precio semana ant.",
        })
        st.dataframe(g, hide_index=True, use_container_width=True)

    st.subheader("Mercado Agroganadero")
    if mag.empty:
        st.info("Sin datos de Mercado Agroganadero disponibles.")
    else:
        g = mag[["categoria", "precio_min", "precio_max", "precio", "cantidad"]].rename(columns={
            "categoria": "Categoría", "precio_min": "Mínimo", "precio_max": "Máximo",
            "precio": "Promedio", "cantidad": "Cabezas",
        })
        st.dataframe(g, hide_index=True, use_container_width=True)
        st.caption(f"Remate del {mag['fecha_dato'].iloc[0].strftime('%d/%m/%Y')}")

st.divider()
st.caption(
    "Fuentes: [deCampoaCampo](https://www.decampoacampo.com) y "
    "[Mercado Agroganadero](https://www.mercadoagroganadero.com.ar). "
    "Esta página no está afiliada a ninguna de las dos."
)
