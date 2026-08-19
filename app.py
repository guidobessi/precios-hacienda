import logging
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from precios_hacienda import fetch_invernada, fetch_faena_canuelas, fetch_faena_mag
from comparador_ofertas import Oferta, normalizar_oferta
from ofertas_store import cargar_ofertas, guardar_ofertas

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

st.set_page_config(page_title="Precios Hacienda", page_icon="🐄", layout="wide")

VERDE_SUBE = "#2E7D4F"
ROJO_BAJA = "#C1443C"
GRIS_IGUAL = "#9AA39B"
COLOR_TENDENCIA = {"Sube": VERDE_SUBE, "Baja": ROJO_BAJA, "Estable": GRIS_IGUAL, "Sin dato": GRIS_IGUAL}

COLOR_FONDO_INVERNADA = "#E3F3FB"  # celeste pastel
BORDE_FONDO_INVERNADA = "#BFE2F2"
COLOR_FONDO_FAENA = "#E4E8FB"  # azul pastel
BORDE_FONDO_FAENA = "#C4CDF5"

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    [data-testid="stMetric"] { text-align: center; }
    [data-testid="stMetricLabel"] { justify-content: center; }
    [data-testid="stMetricDelta"] { justify-content: center; }

    .app-title {
        text-align: center; text-transform: uppercase; letter-spacing: 2px;
        font-weight: 800; margin-bottom: 0.1rem;
    }
    .app-subtitle { text-align: center; color: #5B6B62; margin-bottom: 1rem; }

    div[data-testid="stVerticalBlock"][class*="st-key-"] {
        border-radius: 14px !important;
        box-shadow: 0 2px 10px rgba(30, 60, 40, 0.08);
    }
    h2, h3 { letter-spacing: 0.3px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<h1 class="app-title">🐄 Precios de Mercado de Hacienda</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="app-subtitle">Invernada y Faena — deCampoaCampo (Invernada + Cañuelas) y MAG.</p>',
    unsafe_allow_html=True,
)


# ─── Carga de datos ─────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner="Consultando deCampoaCampo (invernada)...")
def _invernada() -> pd.DataFrame:
    return pd.DataFrame(fetch_invernada())


@st.cache_data(ttl=1800, show_spinner="Consultando deCampoaCampo (Cañuelas)...")
def _faena_canuelas() -> pd.DataFrame:
    return pd.DataFrame(fetch_faena_canuelas())


@st.cache_data(ttl=1800, show_spinner="Consultando MAG...")
def _faena_mag() -> pd.DataFrame:
    return pd.DataFrame(fetch_faena_mag())


def _cargar(fetch_fn, nombre: str) -> pd.DataFrame:
    try:
        return fetch_fn()
    except Exception as e:
        st.error(f"No se pudo traer {nombre}: {e}")
        log.exception("Error trayendo %s", nombre)
        return pd.DataFrame()


def tendencia(v) -> str:
    if pd.isna(v):
        return "Sin dato"
    if v > 0:
        return "Sube"
    if v < 0:
        return "Baja"
    return "Estable"


def filtrar_y_ordenar(df: pd.DataFrame, precio_col: str, variacion_col: str = "variacion") -> pd.DataFrame:
    if df.empty:
        return df
    d = df.copy()
    if busqueda:
        d = d[d["categoria"].str.contains(busqueda, case=False, na=False)]
    sort_col = {"Precio": precio_col, "Variación": variacion_col, "Cantidad operada": "cantidad"}[orden_por]
    if sort_col in d.columns:
        d = d.sort_values(sort_col, ascending=not orden_desc, na_position="last")
    return d


def construir_catalogo(*fuentes_con_label) -> pd.DataFrame:
    """Une inv/can/mag en un solo catálogo con una etiqueta de fuente legible,
    para poder buscar cualquier categoría sin importar de dónde viene."""
    partes = []
    for df, label in fuentes_con_label:
        if df.empty:
            continue
        t = df.copy()
        t["fuente_label"] = label
        partes.append(t)
    if not partes:
        return pd.DataFrame()
    cat = pd.concat(partes, ignore_index=True, sort=False)
    cat["clave"] = cat["categoria"] + " · " + cat["fuente_label"]
    return cat


def tarjeta_favorito(col, fila: pd.Series, signo: str, usar_usd: bool, decimales: int, key: str):
    precio_col = "precio_usd" if usar_usd else "precio"
    precio_anterior_col = "precio_anterior_usd" if usar_usd else "precio_anterior"
    variacion_col = "variacion_usd" if usar_usd else "variacion"
    precio_val = fila.get(precio_col)
    unidad = fila.get("unidad")
    unidad = unidad if pd.notna(unidad) else "Kg"

    if fila.get("tipo") == "invernada":
        color_fondo, color_borde = COLOR_FONDO_INVERNADA, BORDE_FONDO_INVERNADA
    else:
        color_fondo, color_borde = COLOR_FONDO_FAENA, BORDE_FONDO_FAENA
    col.markdown(
        f"<style>.st-key-{key} {{ background-color: {color_fondo}; border-color: {color_borde} !important; }}</style>",
        unsafe_allow_html=True,
    )

    with col, st.container(border=True, key=key):
        st.caption(fila["fuente_label"])
        st.markdown(f"**{fila['categoria']}**")
        if pd.isna(precio_val):
            st.write(f"Sin dato en {signo}" if usar_usd else "Sin dato")
            return
        st.metric(f"{signo}/{unidad}", f"{signo} {precio_val:,.{decimales}f}")

        delta = fila.get(variacion_col)
        precio_anterior = fila.get(precio_anterior_col)
        if pd.notna(delta):
            texto_delta = f"{signo}{delta:+,.{decimales}f}"
            if pd.notna(precio_anterior) and precio_anterior:
                texto_delta += f" ({delta / precio_anterior * 100:+.1f}%)"
            color = VERDE_SUBE if delta > 0 else (ROJO_BAJA if delta < 0 else GRIS_IGUAL)
            flecha = "▲" if delta > 0 else ("▼" if delta < 0 else "▬")
            st.markdown(f":{('green' if delta > 0 else 'red' if delta < 0 else 'gray')}[{flecha} {texto_delta}]")
        periodo = fila.get("periodo_comparacion")
        if pd.notna(periodo):
            st.caption(f"vs. semana del {periodo}")

        cantidad = fila.get("cantidad")
        if pd.notna(cantidad):
            st.caption(f"{int(cantidad):,} cabezas operadas")


def grafico_barras(d: pd.DataFrame, precio_col: str, titulo_x: str, color_col: str = None, color_map: dict = None, decimales: int = 0):
    if d.empty:
        st.info("Sin datos para mostrar con estos filtros.")
        return
    d = d.sort_values(precio_col, ascending=True)
    fig = px.bar(
        d, x=precio_col, y="categoria", orientation="h",
        color=color_col, color_discrete_map=color_map,
        text=precio_col, template="plotly_white",
    )
    fig.update_traces(texttemplate=f"%{{text:,.{decimales}f}}", textposition="outside", cliponaxis=False)
    fig.update_layout(
        showlegend=bool(color_col), height=max(320, 34 * len(d)),
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title=titulo_x, yaxis_title="", legend_title_text="",
        font_family="Inter, sans-serif",
    )
    st.plotly_chart(fig, use_container_width=True)


def tabla_estilizada(d: pd.DataFrame, columnas: dict, var_col_original: str = None, precio_col_original: str = None, decimales: int = 0):
    if d.empty:
        return
    g = d[list(columnas.keys())].rename(columns=columnas)
    num_cols = g.select_dtypes(include="number").columns
    col_renombrada = columnas.get(var_col_original)
    col_precio_renombrada = columnas.get(precio_col_original)

    def fmt(c):
        if c == col_renombrada:
            return "{:+,.%df}" % decimales
        if c == col_precio_renombrada:
            return "{:,.%df}" % decimales
        return "{:,.0f}"

    formatos = {c: fmt(c) for c in num_cols}
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
can = _cargar(_faena_canuelas, "De Campo a Campo (Cañuelas)")
mag = _cargar(_faena_mag, "MAG")

catalogo = construir_catalogo(
    (inv, "Invernada"), (can, "Faena Cañuelas"), (mag, "Faena MAG"),
)

FAVORITOS_DEFAULT = [
    "Terneros 160-180 Kg. · Invernada",
    "Novillitos hasta 390 Kg. · Faena Cañuelas",
    "Vaquillonas hasta 390 Kg. · Faena Cañuelas",
    "Vacas Buenas · Faena Cañuelas",
]

# ─── Filtros (sidebar) ──────────────────────────────────────────────────────

with st.sidebar:
    st.header("⭐ Tus categorías")
    opciones_favoritos = sorted(catalogo["clave"].unique()) if not catalogo.empty else []
    favoritos_sel = st.multiselect(
        "Elegí las que querés ver siempre arriba de todo",
        opciones_favoritos,
        default=[f for f in FAVORITOS_DEFAULT if f in opciones_favoritos],
    )
    st.divider()
    st.header("🔍 Explorar todo")
    moneda = st.radio("Moneda", ["Pesos ($)", "Dólares (US$)"], index=0)
    busqueda = st.text_input("Buscar categoría", placeholder="ej. novillo, ternero...")
    orden_por = st.selectbox("Ordenar por", ["Precio", "Variación", "Cantidad operada"])
    orden_desc = st.toggle("Orden descendente", value=True)
    st.divider()
    st.caption("Los precios se refrescan solos cada 30 min, o tocá **Actualizar ahora**.")

usar_usd = moneda.startswith("Dólares")
signo = "US$" if usar_usd else "$"
decimales = 2 if usar_usd else 0
col_variacion = "variacion_usd" if usar_usd else "variacion"

# ─── Tus precios (favoritos) ────────────────────────────────────────────────

if favoritos_sel:
    st.subheader("🎯 Tus precios")
    cols = st.columns(len(favoritos_sel))
    for idx, (col, clave) in enumerate(zip(cols, favoritos_sel)):
        fila = catalogo[catalogo["clave"] == clave].iloc[0]
        tarjeta_favorito(col, fila, signo, usar_usd, decimales, key=f"favcard_{idx}")
    st.divider()

# ─── Comparador de ofertas ──────────────────────────────────────────────────

st.subheader("🧮 Comparador de ofertas")
st.caption(
    "Cargá las ofertas de cada comprador, aunque vengan en formatos distintos "
    "(precio final o en gancho, con o sin IVA, con o sin comisión, a distinto plazo de pago) "
    "y te decimos cuál conviene aceptar en igualdad de condiciones. "
    "Quedan guardadas aunque recargues la página — las borrás vos cuando quieras."
)

if "ofertas" not in st.session_state:
    st.session_state["ofertas"] = cargar_ofertas()

with st.form("form_oferta", clear_on_submit=True):
    c1, c2 = st.columns(2)
    comprador = c1.text_input("Comprador")
    tipo_precio = c2.radio("Tipo de precio", ["Precio final (en pie)", "Precio en gancho (media res)"], horizontal=True)
    es_gancho = tipo_precio.startswith("Precio en gancho")

    c3, c4 = st.columns(2)
    precio_base = c3.number_input("Precio informado ($/Kg)", min_value=0.0, step=10.0, format="%.2f")
    rinde_pct = c4.number_input(
        "Rinde de la media res (%)", min_value=40.0, max_value=65.0, value=56.0, step=0.5,
        help="Sólo se usa si elegiste 'Precio en gancho' — convierte a $/Kg en pie.",
    )

    c5, c6 = st.columns(2)
    incluye_iva = c5.radio("¿El precio ya incluye IVA?", ["No, hay que sumarlo", "Sí, ya incluido"], horizontal=True) == "Sí, ya incluido"
    iva_pct = c6.number_input("IVA (%)", min_value=0.0, value=10.5, step=0.5, help="Sólo se usa si el precio no incluye IVA.")

    c7, c8 = st.columns(2)
    tiene_comision = c7.checkbox("Tiene comisión")
    comision_pct = c8.number_input("Comisión (%)", min_value=0.0, value=3.0, step=0.5, help="Sólo se usa si tildaste 'Tiene comisión'.")

    c9, c10, c11 = st.columns(3)
    plazo_dias = c9.number_input("Plazo de pago (días)", min_value=0, value=0, step=5)
    tasa_mensual_pct = c10.number_input(
        "Tasa mensual esperada (%)", min_value=0.0, value=3.0, step=0.5,
        help="Costo de oportunidad / inflación mensual que asumís. Se usa para descontar a valor "
             "presente las ofertas con plazo de pago mayor a contado — no afecta si el plazo es 0.",
    )
    peso_total_kg = c11.number_input("Peso total del lote (Kg, opcional)", min_value=0.0, value=0.0, step=100.0)

    agregar = st.form_submit_button("➕ Agregar oferta")
    if agregar:
        if not comprador.strip() or precio_base <= 0:
            st.warning("Completá al menos el nombre del comprador y el precio.")
        else:
            st.session_state["ofertas"].append(Oferta(
                comprador=comprador.strip(),
                precio_base=precio_base,
                tipo_precio="gancho" if es_gancho else "en_pie",
                rinde_pct=rinde_pct,
                incluye_iva=incluye_iva,
                iva_pct=iva_pct,
                tiene_comision=tiene_comision,
                comision_pct=comision_pct,
                plazo_dias=plazo_dias,
                tasa_mensual_pct=tasa_mensual_pct,
                peso_total_kg=peso_total_kg,
            ))
            guardar_ofertas(st.session_state["ofertas"])
            st.rerun()

if st.session_state["ofertas"]:
    resultados = sorted(
        ((idx, normalizar_oferta(o)) for idx, o in enumerate(st.session_state["ofertas"])),
        key=lambda par: par[1]["precio_final"], reverse=True,
    )
    for puesto, (idx, r) in enumerate(resultados):
        with st.container(border=True, key=f"offercard_{idx}"):
            c_info, c_precio, c_borrar = st.columns([3, 2, 1])
            with c_info:
                nombre = f"🏆 **{r['comprador']}**" if puesto == 0 else f"**{r['comprador']}**"
                st.markdown(nombre)
                detalle = f"${r['precio_base']:,.2f}/Kg" + (" en gancho" if r["tipo_precio"] == "gancho" else " en pie")
                if r["plazo_dias"]:
                    detalle += f" · {r['plazo_dias']} días de plazo"
                else:
                    detalle += " · contado"
                st.caption(detalle)
            with c_precio:
                st.metric("Comparable ($/Kg en pie)", f"${r['precio_final']:,.2f}")
                if r["monto_total"]:
                    st.caption(f"Monto total est.: ${r['monto_total']:,.0f}")
            with c_borrar:
                if st.button("🗑️", key=f"del_oferta_{idx}"):
                    st.session_state["ofertas"].pop(idx)
                    guardar_ofertas(st.session_state["ofertas"])
                    st.rerun()
            with st.expander("Ver cálculo"):
                pasos = [f"Precio informado: ${r['precio_base']:,.2f}/Kg"]
                if r["tipo_precio"] == "gancho":
                    pasos.append(f"Equivalente en pie (× {r['rinde_pct']:.0f}% de rinde): ${r['precio_en_pie']:,.2f}/Kg")
                pasos.append(f"Bruto con IVA: ${r['precio_bruto_iva']:,.2f}/Kg")
                if r["comision_pct"]:
                    pasos.append(f"Neto de comisión ({r['comision_pct']:.1f}%): ${r['precio_neto_comision']:,.2f}/Kg")
                if r["plazo_dias"]:
                    pasos.append(
                        f"Ajustado a valor presente ({r['plazo_dias']} días @ {r['tasa_mensual_pct']:.1f}%/mes): "
                        f"**${r['precio_final']:,.2f}/Kg**"
                    )
                for i, paso in enumerate(pasos, 1):
                    st.write(f"{i}. {paso}")

    if st.button("🗑️ Borrar todas las ofertas"):
        st.session_state["ofertas"] = []
        guardar_ofertas([])
        st.rerun()

st.divider()

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
        d = filtrar_y_ordenar(d, precio_col, col_variacion)
        d = d.assign(Tendencia=d[col_variacion].apply(tendencia))

        # "Vientres" se cotiza por bulto/cabeza, no por Kg — no se puede mezclar
        # en el mismo gráfico/escala que el resto sin distorsionar los valores.
        for unidad, etiqueta in [("Kg", "por Kg"), ("Bulto", "por cabeza (vientres preñados / con cría)")]:
            d_u = d[d["unidad"] == unidad]
            if d_u.empty:
                continue
            st.markdown(f"##### Precios {etiqueta}")
            grafico_barras(d_u, precio_col, f"Precio ({signo}/{unidad})", color_col="Tendencia", color_map=COLOR_TENDENCIA, decimales=decimales)
            with st.expander(f"Ver tabla completa — {etiqueta}"):
                cols = {
                    "categoria": "Categoría", "grupo": "Grupo",
                    precio_col: f"Precio ({signo}/{unidad})", col_variacion: "Var. semanal",
                    "cantidad": "Cabezas operadas",
                }
                tabla_estilizada(d_u, cols, var_col_original=col_variacion, precio_col_original=precio_col, decimales=decimales)

# ─── Faena ─────────────────────────────────────────────────────────────────

with tab_faena:
    st.subheader("De Campo a Campo")
    st.caption("Cañuelas — ex Mercado de Liniers")
    if can.empty:
        st.info("Sin datos de Cañuelas disponibles.")
    else:
        precio_col = "precio_usd" if usar_usd else "precio"
        d = filtrar_y_ordenar(can, precio_col, col_variacion)
        d = d.assign(Tendencia=d[col_variacion].apply(tendencia))

        grafico_barras(d, precio_col, f"Precio ({signo}/Kg + IVA)", color_col="Tendencia", color_map=COLOR_TENDENCIA, decimales=decimales)
        with st.expander("Ver tabla completa"):
            cols = {
                "categoria": "Categoría", precio_col: f"Precio ({signo}/Kg)",
                col_variacion: "Var. vs. semana ant.", "cantidad": "Cabezas operadas",
            }
            tabla_estilizada(d, cols, var_col_original=col_variacion, precio_col_original=precio_col, decimales=decimales)

    st.subheader("MAG")
    st.caption("Mercado Agroganadero")
    if mag.empty:
        st.info("Sin datos de MAG disponibles.")
    else:
        d = mag.copy()
        if busqueda:
            d = d[d["categoria"].str.contains(busqueda, case=False, na=False)]
        d["Grupo"] = d["categoria"].str.split().str[0].str.title()
        sort_col = {"Precio": "precio", "Variación": "precio", "Cantidad operada": "cantidad"}[orden_por]
        d = d.sort_values(sort_col, ascending=not orden_desc)

        grafico_barras(d, "precio", "Precio máximo ($/Kg + IVA)", color_col="Grupo")
        with st.expander("Ver tabla completa"):
            cols = {
                "categoria": "Categoría", "precio_min": "Mínimo", "precio_max": "Máximo",
                "precio_promedio": "Promedio", "cantidad": "Cabezas",
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
