import logging
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from precios_hacienda import fetch_invernada, fetch_faena_canuelas, fetch_faena_mag

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

st.set_page_config(page_title="Precios Hacienda", page_icon="🐄", layout="wide")

VERDE_SUBE = "#2E7D4F"
ROJO_BAJA = "#C1443C"
GRIS_IGUAL = "#9AA39B"
COLOR_TENDENCIA = {"Sube": VERDE_SUBE, "Baja": ROJO_BAJA, "Estable": GRIS_IGUAL, "Sin dato": GRIS_IGUAL}

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    [data-testid="stMetric"] { text-align: center; }
    [data-testid="stMetricLabel"] { justify-content: center; }
    [data-testid="stMetricDelta"] { justify-content: center; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🐄 Precios de Mercado de Hacienda")
st.caption("Invernada y Faena — deCampoaCampo (Invernada + Cañuelas) y Mercado Agroganadero.")


# ─── Carga de datos ─────────────────────────────────────────────────────────

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


# ─── Filtros (sidebar) ──────────────────────────────────────────────────────

with st.sidebar:
    st.header("🔍 Filtros")
    moneda = st.radio("Moneda", ["Pesos ($)", "Dólares (US$)"], index=0)
    busqueda = st.text_input("Buscar categoría", placeholder="ej. novillo, ternero...")
    orden_por = st.selectbox("Ordenar por", ["Precio", "Variación", "Cantidad operada"])
    orden_desc = st.toggle("Orden descendente", value=True)
    st.divider()
    st.caption("Los precios se refrescan solos cada 30 min, o tocá **Actualizar ahora**.")

usar_usd = moneda.startswith("Dólares")


def tendencia(v) -> str:
    if pd.isna(v):
        return "Sin dato"
    if v > 0:
        return "Sube"
    if v < 0:
        return "Baja"
    return "Estable"


def filtrar_y_ordenar(df: pd.DataFrame, precio_col: str) -> pd.DataFrame:
    if df.empty:
        return df
    d = df.copy()
    if busqueda:
        d = d[d["categoria"].str.contains(busqueda, case=False, na=False)]
    sort_col = {"Precio": precio_col, "Variación": "variacion", "Cantidad operada": "cantidad"}[orden_por]
    if sort_col in d.columns:
        d = d.sort_values(sort_col, ascending=not orden_desc, na_position="last")
    return d


def kpis(d: pd.DataFrame, precio_col: str, moneda_signo: str):
    if d.empty:
        return
    cols = st.columns(4) if "variacion" in d.columns and d["variacion"].notna().any() else st.columns(2)
    with cols[0]:
        with st.container(border=True):
            st.metric("Categorías", len(d))
    with cols[1]:
        with st.container(border=True):
            st.metric("Precio promedio", f"{moneda_signo}{d[precio_col].mean():,.0f}")
    if len(cols) == 4:
        top_sube = d.loc[d["variacion"].idxmax()]
        top_baja = d.loc[d["variacion"].idxmin()]
        with cols[2]:
            with st.container(border=True):
                st.metric("Mayor suba", top_sube["categoria"], delta=f"{top_sube['variacion']:+.0f}")
        with cols[3]:
            with st.container(border=True):
                st.metric("Mayor baja", top_baja["categoria"], delta=f"{top_baja['variacion']:+.0f}")


def grafico_barras(d: pd.DataFrame, precio_col: str, titulo_x: str, color_col: str = None, color_map: dict = None):
    if d.empty:
        st.info("Sin datos para mostrar con estos filtros.")
        return
    d = d.sort_values(precio_col, ascending=True)
    fig = px.bar(
        d, x=precio_col, y="categoria", orientation="h",
        color=color_col, color_discrete_map=color_map,
        text=precio_col, template="plotly_white",
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside", cliponaxis=False)
    fig.update_layout(
        showlegend=bool(color_col), height=max(320, 34 * len(d)),
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title=titulo_x, yaxis_title="", legend_title_text="",
        font_family="Inter, sans-serif",
    )
    st.plotly_chart(fig, use_container_width=True)


def tabla_estilizada(d: pd.DataFrame, columnas: dict, var_col_original: str = None):
    if d.empty:
        return
    g = d[list(columnas.keys())].rename(columns=columnas)
    num_cols = g.select_dtypes(include="number").columns
    col_renombrada = columnas.get(var_col_original)
    formatos = {c: ("{:+,.0f}" if c == col_renombrada else "{:,.0f}") for c in num_cols}
    styler = g.style.format(formatos, na_rep="—")
    if var_col_original and var_col_original in columnas:

        def color_var(s):
            return [f"background-color: {COLOR_TENDENCIA[tendencia(v)]}22; color: {COLOR_TENDENCIA[tendencia(v)]}; font-weight:600" for v in s]

        styler = styler.apply(color_var, subset=[col_renombrada])
    st.dataframe(styler, hide_index=True, use_container_width=True)


# ─── Header: refresh + timestamp ────────────────────────────────────────────

col_btn, col_ts = st.columns([2, 4])
with col_btn:
    if st.button("🔄 Actualizar ahora"):
        st.cache_data.clear()
        st.rerun()
with col_ts:
    st.caption(f"Última consulta: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

inv = _cargar(_invernada, "deCampoaCampo Invernada")
can = _cargar(_faena_canuelas, "deCampoaCampo Cañuelas")
mag = _cargar(_faena_mag, "Mercado Agroganadero")

signo = "US$" if usar_usd else "$"

tab_inv, tab_faena = st.tabs(["🐄 Invernada", "🥩 Faena"])

# ─── Invernada ───────────────────────────────────────────────────────────

with tab_inv:
    if inv.empty:
        st.info("Sin datos de invernada disponibles.")
    else:
        grupos_sel = st.multiselect("Grupo", ["Machos", "Hembras", "Vientres"],
                                     default=["Machos", "Hembras", "Vientres"])
        precio_col = "precio_usd" if usar_usd else "precio"
        d = inv[inv["grupo"].isin(grupos_sel)]
        d = filtrar_y_ordenar(d, precio_col)
        d = d.assign(Tendencia=d["variacion"].apply(tendencia))

        # "Vientres" se cotiza por bulto/cabeza, no por Kg — no se puede mezclar
        # en el mismo gráfico/escala que el resto sin distorsionar los valores.
        for unidad, etiqueta in [("Kg", "por Kg"), ("Bulto", "por cabeza (vientres preñados / con cría)")]:
            d_u = d[d["unidad"] == unidad]
            if d_u.empty:
                continue
            st.markdown(f"##### Precios {etiqueta}")
            kpis(d_u, precio_col, signo)
            grafico_barras(d_u, precio_col, f"Precio ({signo}/{unidad})", color_col="Tendencia", color_map=COLOR_TENDENCIA)
            with st.expander(f"Ver tabla completa — {etiqueta}"):
                cols = {
                    "categoria": "Categoría", "grupo": "Grupo",
                    precio_col: f"Precio ({signo}/{unidad})", "variacion": "Var. semanal",
                    "cantidad": "Cabezas operadas",
                }
                tabla_estilizada(d_u, cols, var_col_original="variacion")

# ─── Faena ─────────────────────────────────────────────────────────────────

with tab_faena:
    st.subheader("Cañuelas (ex Mercado de Liniers)")
    if can.empty:
        st.info("Sin datos de Cañuelas disponibles.")
    else:
        precio_col = "precio_usd" if usar_usd else "precio"
        d = filtrar_y_ordenar(can, precio_col)
        d = d.assign(Tendencia=d["variacion"].apply(tendencia))

        kpis(d, precio_col, signo)
        grafico_barras(d, precio_col, f"Precio ({signo}/Kg + IVA)", color_col="Tendencia", color_map=COLOR_TENDENCIA)
        with st.expander("Ver tabla completa"):
            cols = {
                "categoria": "Categoría", precio_col: f"Precio ({signo}/Kg)",
                "variacion": "Var. vs. semana ant.", "cantidad": "Cabezas operadas",
            }
            tabla_estilizada(d, cols, var_col_original="variacion")

    st.subheader("Mercado Agroganadero")
    if mag.empty:
        st.info("Sin datos de Mercado Agroganadero disponibles.")
    else:
        d = mag.copy()
        if busqueda:
            d = d[d["categoria"].str.contains(busqueda, case=False, na=False)]
        d["Grupo"] = d["categoria"].str.split().str[0].str.title()
        sort_col = {"Precio": "precio", "Variación": "precio", "Cantidad operada": "cantidad"}[orden_por]
        d = d.sort_values(sort_col, ascending=not orden_desc)

        c1, c2, c3 = st.columns(3)
        with c1, st.container(border=True):
            st.metric("Categorías", len(d))
        with c2, st.container(border=True):
            st.metric("Precio promedio", f"${d['precio'].mean():,.0f}")
        with c3, st.container(border=True):
            st.metric("Cabezas totales", f"{int(d['cantidad'].sum()):,}")

        grafico_barras(d, "precio", "Precio promedio ($/Kg + IVA)", color_col="Grupo")
        with st.expander("Ver tabla completa"):
            cols = {
                "categoria": "Categoría", "precio_min": "Mínimo", "precio_max": "Máximo",
                "precio": "Promedio", "cantidad": "Cabezas",
            }
            tabla_estilizada(d, cols)
        if not d.empty:
            st.caption(f"Remate del {d['fecha_dato'].iloc[0].strftime('%d/%m/%Y')}")
        st.caption("Esta fuente no publica precio de la semana anterior, por eso no muestra variación.")

st.divider()
st.caption(
    "Fuentes: [deCampoaCampo](https://www.decampoacampo.com) y "
    "[Mercado Agroganadero](https://www.mercadoagroganadero.com.ar). "
    "Esta página no está afiliada a ninguna de las dos."
)
