import logging
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from precios_hacienda import fetch_invernada, fetch_faena_canuelas, fetch_faena_mag
from comparador_ofertas import Oferta, normalizar_oferta
from ofertas_store import cargar_ofertas, guardar_ofertas
from favoritos_store import cargar_favoritos, guardar_favoritos
from lotes_store import cargar_referencias_lote, guardar_referencia_lote

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

DESCUENTO_FERIA = 0.05  # costo aprox. de vender/enviar directo a la feria

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
        precio_neto = precio_val * (1 - DESCUENTO_FERIA)
        st.caption(f"{signo}/{unidad}")
        st.markdown(
            f'<div style="display:flex; align-items:baseline; gap:0.6rem; flex-wrap:wrap;">'
            f'<span style="font-size:1.05rem; color:#8a9490; text-decoration:line-through;">'
            f'{signo} {precio_val:,.{decimales}f}</span>'
            f'<span style="font-size:1.9rem; font-weight:700; line-height:1.1;">'
            f'{signo} {precio_neto:,.{decimales}f}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"Neto de venta directa (−{DESCUENTO_FERIA:.0%})")

        # Siempre se renderizan estas dos líneas (con un texto de reemplazo si
        # la fuente no publica el dato) para que todas las tarjetas midan lo
        # mismo — si no, MAG (sin variación semanal) queda más baja que el
        # resto y las tarjetas se ven desparejas.
        delta = fila.get(variacion_col)
        precio_anterior = fila.get(precio_anterior_col)
        if pd.notna(delta):
            texto_delta = f"{signo}{delta:+,.{decimales}f}"
            if pd.notna(precio_anterior) and precio_anterior:
                texto_delta += f" ({delta / precio_anterior * 100:+.1f}%)"
            color = VERDE_SUBE if delta > 0 else (ROJO_BAJA if delta < 0 else GRIS_IGUAL)
            flecha = "▲" if delta > 0 else ("▼" if delta < 0 else "▬")
            st.markdown(f":{('green' if delta > 0 else 'red' if delta < 0 else 'gray')}[{flecha} {texto_delta}]")
        else:
            st.markdown(":gray[Sin variación disponible]")

        periodo = fila.get("periodo_comparacion")
        fecha_dato = fila.get("fecha_dato")
        if pd.notna(periodo):
            st.caption(f"vs. semana del {periodo}")
        elif pd.notna(fecha_dato):
            st.caption(f"Remate del {fecha_dato.strftime('%d/%m/%Y')}")
        else:
            st.caption("")

        cantidad = fila.get("cantidad")
        if pd.notna(cantidad):
            st.caption(f"{int(cantidad):,} cabezas operadas")
        else:
            st.caption("")


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
can = _cargar(_faena_canuelas, "DCAC")
mag = _cargar(_faena_mag, "MAG")

catalogo = construir_catalogo(
    (inv, "Invernada"), (can, "Faena DCAC"), (mag, "Faena MAG"),
)

FAVORITOS_DEFAULT = [
    "Terneros 160-180 Kg. · Invernada",
    "NOVILLITOS Esp. h 390 · Faena MAG",
    "VAQUILLONAS Esp. h 390 · Faena MAG",
]

# ─── Filtros (sidebar) ──────────────────────────────────────────────────────

with st.sidebar:
    st.header("⭐ Tus categorías")
    opciones_favoritos = sorted(catalogo["clave"].unique()) if not catalogo.empty else []
    favoritos_guardados = cargar_favoritos()
    if favoritos_guardados is None:
        favoritos_guardados = FAVORITOS_DEFAULT
    favoritos_disponibles_hoy = [f for f in favoritos_guardados if f in opciones_favoritos]
    favoritos_sel = st.multiselect(
        "Elegí las que querés ver siempre arriba de todo",
        opciones_favoritos,
        default=favoritos_disponibles_hoy,
    )
    if favoritos_sel != favoritos_disponibles_hoy:
        # Si alguna favorita guardada no está en las opciones de hoy (ej. MAG
        # sin remate todavía), no la tratamos como "el usuario la sacó" — la
        # re-agregamos para no perderla apenas la fuente vuelva a publicarla.
        ausentes_hoy = [f for f in favoritos_guardados if f not in opciones_favoritos]
        guardar_favoritos(favoritos_sel + ausentes_hoy)
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
        sel = catalogo[catalogo["clave"] == clave] if not catalogo.empty else catalogo
        if sel.empty:
            # La fuente de esta categoría no publicó nada en este refresco
            # (ej. MAG sin remate todavía) — se muestra un aviso en vez de
            # romper la página con un índice fuera de rango.
            categoria_txt, _, fuente_txt = clave.partition(" · ")
            with col, st.container(border=True, key=f"favcard_{idx}"):
                st.caption(fuente_txt or "—")
                st.markdown(f"**{categoria_txt}**")
                st.write("Sin dato hoy — la fuente todavía no publicó esta categoría.")
            continue
        fila = sel.iloc[0]
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
if "editando_idx" not in st.session_state:
    st.session_state["editando_idx"] = None

editando_idx = st.session_state["editando_idx"]
if editando_idx is not None and editando_idx >= len(st.session_state["ofertas"]):
    editando_idx = st.session_state["editando_idx"] = None
oferta_editar = st.session_state["ofertas"][editando_idx] if editando_idx is not None else None

if oferta_editar:
    st.info(f"✏️ Editando la oferta de **{oferta_editar.comprador}**.")

# El selector de lote va FUERA del form: adentro de un st.form los widgets no
# reaccionan hasta el submit, y acá necesitamos que aparezca el campo de texto
# apenas se elige "Nuevo lote" — así que este selectbox se resuelve antes.
lotes_existentes = sorted({o.lote for o in st.session_state["ofertas"] if o.lote})
NUEVO_LOTE = "➕ Nuevo lote..."
opciones_lote = [NUEVO_LOTE] + lotes_existentes
lote_sel = st.selectbox(
    "📦 Lote de venta",
    opciones_lote,
    key="lote_selector",
    help="Agrupá las ofertas por lote — cada lote se compara aparte, no se mezclan categorías distintas.",
)
if lote_sel == NUEVO_LOTE:
    lote_nombre = st.text_input(
        "Nombre del lote nuevo", key="lote_nuevo_nombre",
        placeholder="ej. Novillos 400kg - Corral 3",
    ).strip()
else:
    lote_nombre = lote_sel

with st.form("form_oferta", clear_on_submit=True):
    c1, c2 = st.columns(2)
    comprador = c1.text_input("Comprador", value=oferta_editar.comprador if oferta_editar else "")
    opciones_tipo = ["Precio final (en pie)", "Precio en gancho (media res)"]
    tipo_precio = c2.radio(
        "Tipo de precio", opciones_tipo, horizontal=True,
        index=1 if oferta_editar and oferta_editar.tipo_precio == "gancho" else 0,
    )
    es_gancho = tipo_precio.startswith("Precio en gancho")

    c3, c4 = st.columns(2)
    precio_base = c3.number_input(
        "Precio informado ($/Kg)", min_value=0.0, step=10.0, format="%.2f",
        value=float(oferta_editar.precio_base) if oferta_editar else 0.0,
    )
    rinde_pct = c4.number_input(
        "Rinde de la media res (%)", min_value=40.0, max_value=65.0, step=0.5,
        value=float(oferta_editar.rinde_pct) if oferta_editar else 56.0,
        help="Sólo se usa si elegiste 'Precio en gancho' — convierte a $/Kg en pie.",
    )

    c5, c6 = st.columns(2)
    opciones_iva = ["No, hay que sumarlo", "Sí, ya incluido"]
    incluye_iva = c5.radio(
        "¿El precio ya incluye IVA?", opciones_iva, horizontal=True,
        index=1 if oferta_editar and oferta_editar.incluye_iva else 0,
    ) == "Sí, ya incluido"
    iva_pct = c6.number_input(
        "IVA (%)", min_value=0.0, step=0.5, help="Sólo se usa si el precio no incluye IVA.",
        value=float(oferta_editar.iva_pct) if oferta_editar else 10.5,
    )

    c7, c8 = st.columns(2)
    tiene_comision = c7.checkbox("Tiene comisión", value=oferta_editar.tiene_comision if oferta_editar else False)
    comision_pct = c8.number_input(
        "Comisión (%)", min_value=0.0, step=0.5, help="Sólo se usa si tildaste 'Tiene comisión'.",
        value=float(oferta_editar.comision_pct) if oferta_editar else 3.0,
    )

    c7b, c8b = st.columns(2)
    tiene_achique = c7b.checkbox(
        "Tiene achique (parte en negro)", value=oferta_editar.tiene_achique if oferta_editar else False,
        help="Parte de la operación que se cobra sin factura y sin IVA.",
    )
    achique_pct = c8b.number_input(
        "Achique / en negro (%)", min_value=0.0, max_value=100.0, step=5.0,
        value=float(oferta_editar.achique_pct) if oferta_editar else 20.0,
        help="Sólo se usa si tildaste 'Tiene achique'. Esa porción no lleva IVA — "
             "reduce el comparable respecto de tener todo facturado.",
    )

    c9, c10, c11 = st.columns(3)
    plazo_dias = c9.number_input(
        "Plazo de pago (días)", min_value=0, step=5,
        value=int(oferta_editar.plazo_dias) if oferta_editar else 0,
    )
    tasa_mensual_pct = c10.number_input(
        "Tasa mensual esperada (%)", min_value=0.0, step=0.5,
        value=float(oferta_editar.tasa_mensual_pct) if oferta_editar else 3.0,
        help="Costo de oportunidad / inflación mensual que asumís. Se usa para descontar a valor "
             "presente las ofertas con plazo de pago mayor a contado — no afecta si el plazo es 0.",
    )
    peso_total_kg = c11.number_input(
        "Peso total del lote (Kg, opcional)", min_value=0.0, step=100.0,
        value=float(oferta_editar.peso_total_kg) if oferta_editar else 0.0,
    )

    c_guardar, c_cancelar = st.columns([1, 1])
    texto_boton = "💾 Guardar cambios" if oferta_editar else "➕ Agregar oferta"
    agregar = c_guardar.form_submit_button(texto_boton, use_container_width=True)
    cancelar = c_cancelar.form_submit_button("✖️ Cancelar edición", use_container_width=True, disabled=not oferta_editar)

    if cancelar:
        st.session_state["editando_idx"] = None
        st.rerun()

    if agregar:
        if not comprador.strip() or precio_base <= 0:
            st.warning("Completá al menos el nombre del comprador y el precio.")
        elif not lote_nombre:
            st.warning("Elegí o escribí un lote de venta para esta oferta.")
        else:
            nueva_oferta = Oferta(
                comprador=comprador.strip(),
                precio_base=precio_base,
                tipo_precio="gancho" if es_gancho else "en_pie",
                lote=lote_nombre,
                rinde_pct=rinde_pct,
                incluye_iva=incluye_iva,
                iva_pct=iva_pct,
                tiene_comision=tiene_comision,
                comision_pct=comision_pct,
                tiene_achique=tiene_achique,
                achique_pct=achique_pct,
                plazo_dias=plazo_dias,
                tasa_mensual_pct=tasa_mensual_pct,
                peso_total_kg=peso_total_kg,
            )
            if editando_idx is not None:
                st.session_state["ofertas"][editando_idx] = nueva_oferta
                st.session_state["editando_idx"] = None
            else:
                st.session_state["ofertas"].append(nueva_oferta)
            guardar_ofertas(st.session_state["ofertas"])
            st.rerun()

def _iniciar_edicion(idx: int):
    # Debe ir en un on_click: mutar el session_state de un widget con key
    # (acá, "lote_selector") después de que ya se instanció en esta misma
    # corrida del script está prohibido por Streamlit — el callback corre
    # antes de que el script vuelva a renderizar los widgets.
    st.session_state["editando_idx"] = idx
    oferta_target = st.session_state["ofertas"][idx]
    lotes_actuales = sorted({o.lote for o in st.session_state["ofertas"] if o.lote})
    if oferta_target.lote in lotes_actuales:
        st.session_state["lote_selector"] = oferta_target.lote
    else:
        st.session_state["lote_selector"] = NUEVO_LOTE
        st.session_state["lote_nuevo_nombre"] = oferta_target.lote


if st.session_state["ofertas"]:
    indices_por_lote = {}
    for idx, o in enumerate(st.session_state["ofertas"]):
        indices_por_lote.setdefault(o.lote or "General", []).append(idx)

    referencias_lote = cargar_referencias_lote()

    for nombre_lote, indices_lote in indices_por_lote.items():
        st.markdown(f"#### 📦 {nombre_lote}")

        with st.expander("🎯 Precio de referencia (venta directa a feria)"):
            ref_actual = referencias_lote.get(nombre_lote, 0.0)
            ref_nueva = st.number_input(
                "Precio neto de venta directa ($/Kg)", min_value=0.0, step=10.0,
                value=float(ref_actual), key=f"ref_lote_{nombre_lote}",
                help="Copiá el precio 'neto de venta directa' de la tarjeta favorita que "
                     "corresponda a este lote. Cada oferta te va a mostrar si te conviene "
                     "más o menos que vender directo. Dejalo en 0 para no comparar.",
            )
            if ref_nueva != ref_actual:
                guardar_referencia_lote(nombre_lote, ref_nueva if ref_nueva > 0 else None)
                referencias_lote = cargar_referencias_lote()
        referencia = referencias_lote.get(nombre_lote, 0.0)

        resultados = sorted(
            ((idx, normalizar_oferta(st.session_state["ofertas"][idx])) for idx in indices_lote),
            key=lambda par: par[1]["precio_final"], reverse=True,
        )
        for puesto, (idx, r) in enumerate(resultados):
            with st.container(border=True, key=f"offercard_{idx}"):
                c_nombre, c_acciones = st.columns([5, 1])
                with c_nombre:
                    nombre = f"🏆 **{r['comprador']}**" if puesto == 0 else f"**{r['comprador']}**"
                    st.markdown(nombre)
                    detalle = f"${r['precio_base']:,.2f}/Kg" + (" en gancho" if r["tipo_precio"] == "gancho" else " en pie")
                    if r["plazo_dias"]:
                        detalle += f" · {r['plazo_dias']} días de plazo"
                    else:
                        detalle += " · contado"
                    if r["achique_pct"]:
                        detalle += f" · {r['achique_pct']:.0f}% en negro"
                    st.caption(detalle)
                with c_acciones:
                    c_edit, c_del = st.columns(2)
                    c_edit.button(
                        "✏️", key=f"edit_oferta_{idx}", help="Editar esta oferta",
                        on_click=_iniciar_edicion, args=(idx,),
                    )
                    if c_del.button("🗑️", key=f"del_oferta_{idx}", help="Borrar esta oferta"):
                        st.session_state["ofertas"].pop(idx)
                        if st.session_state["editando_idx"] == idx:
                            st.session_state["editando_idx"] = None
                        guardar_ofertas(st.session_state["ofertas"])
                        st.rerun()

                c_siniva, c_coniva, c_final = st.columns(3)
                c_siniva.metric("Sin IVA", f"${r['precio_sin_iva']:,.2f}")
                c_coniva.metric("Con IVA", f"${r['precio_con_iva']:,.2f}")
                c_final.metric("🎯 Comparable (ajustado)", f"${r['precio_final']:,.2f}")
                if r["monto_total"]:
                    st.caption(f"Monto total estimado: ${r['monto_total']:,.0f}")
                if referencia:
                    diferencia = r["precio_final"] - referencia
                    color = "green" if diferencia > 0 else ("red" if diferencia < 0 else "gray")
                    veredicto = "mejor" if diferencia > 0 else ("peor" if diferencia < 0 else "igual")
                    st.markdown(
                        f":{color}[vs. venta directa (${referencia:,.2f}): "
                        f"{diferencia:+,.2f} — {veredicto} que vender en la feria]"
                    )

                with st.expander("Ver cálculo"):
                    pasos = [f"Precio informado: ${r['precio_base']:,.2f}/Kg"]
                    if r["tipo_precio"] == "gancho":
                        pasos.append(f"Equivalente en pie (× {r['rinde_pct']:.0f}% de rinde): ${r['precio_en_pie']:,.2f}/Kg")
                    pasos.append(f"Sin IVA: ${r['precio_sin_iva']:,.2f}/Kg  ·  Con IVA: ${r['precio_con_iva']:,.2f}/Kg")
                    if r["achique_pct"]:
                        pasos.append(
                            f"Con achique ({r['achique_pct']:.0f}% en negro, sin IVA en esa parte): "
                            f"${r['precio_con_achique']:,.2f}/Kg"
                        )
                    if r["comision_pct"]:
                        pasos.append(f"Neto de comisión ({r['comision_pct']:.1f}%): ${r['precio_neto_comision']:,.2f}/Kg")
                    if r["plazo_dias"]:
                        pasos.append(
                            f"Ajustado a valor presente ({r['plazo_dias']} días @ {r['tasa_mensual_pct']:.1f}%/mes): "
                            f"**${r['precio_final']:,.2f}/Kg**"
                        )
                    for i, paso in enumerate(pasos, 1):
                        st.write(f"{i}. {paso}")

        if st.button(f"🗑️ Borrar ofertas de {nombre_lote}", key=f"del_lote_{nombre_lote}"):
            st.session_state["ofertas"] = [
                o for i, o in enumerate(st.session_state["ofertas"]) if i not in indices_lote
            ]
            if st.session_state["editando_idx"] in indices_lote:
                st.session_state["editando_idx"] = None
            guardar_ofertas(st.session_state["ofertas"])
            st.rerun()
        st.divider()

    with st.expander("⚠️ Borrar TODAS las ofertas de TODOS los lotes"):
        if st.button("🗑️ Confirmar: borrar todo"):
            st.session_state["ofertas"] = []
            st.session_state["editando_idx"] = None
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
    st.subheader("DCAC")
    st.caption("Cañuelas — ex Mercado de Liniers")
    if can.empty:
        st.info("Sin datos de DCAC disponibles.")
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
        st.info(
            "MAG todavía no publicó precios por categoría hoy — puede ser que el remate "
            "no haya terminado o que no haya habido operaciones. Probá de nuevo más tarde "
            "o tocá **Actualizar ahora**."
        )
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
