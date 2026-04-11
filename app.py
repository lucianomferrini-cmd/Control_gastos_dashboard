import pandas as pd
import streamlit as st
import plotly.express as px

# =========================
# CONFIGURACIÓN
# =========================
st.set_page_config(page_title="Dashboard de Gastos", layout="wide")

GOOGLE_SHEET_CSV_URL = st.secrets["SHEET_URL"]

# =========================
# CARGA Y CACHE DE DATOS
# =========================
@st.cache_data(ttl=600)  # Cache por 10 minutos
def load_data(url: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(url)
        df.columns = [c.strip() for c in df.columns]

        # Limpieza de fechas
        if "Fecha" in df.columns:
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", dayfirst=True)
        
        # Limpieza de Montos (manejo de formatos latinos)
        if "Monto" in df.columns:
            df["Monto"] = (
                df["Monto"].astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)

        # Columnas de tiempo
        df["Año"] = df["Fecha"].dt.year
        df["Mes"] = df["Fecha"].dt.month
        meses_map = {
            1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
        }
        df["Mes Texto"] = df["Mes"].map(meses_map)
        return df
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame()

def format_currency(value: float) -> str:
    return f"$ {value:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =========================
# PROCESAMIENTO
# =========================
df_raw = load_data(GOOGLE_SHEET_CSV_URL)

if df_raw.empty:
    st.warning("No hay datos disponibles. Verifica la URL de Google Sheets.")
    st.stop()

# --- SIDEBAR (Filtros y Configuración) ---
st.sidebar.header("⚙️ Configuración")
view_mode = st.sidebar.radio("Vista de Dashboard", ["🖥️ Horizontal (PC)", "📱 Vertical (Móvil)"])

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filtros")

# Filtro Outliers
mostrar_outliers = st.sidebar.toggle("Incluir Outliers en gráficos", value=False)

# Filtro de tiempo
anios = sorted(df_raw["Año"].dropna().unique().astype(int))
anios_sel = st.sidebar.multiselect("Años", anios, default=anios)

categorias = sorted(df_raw["Categoría_final"].dropna().unique())
categorias_sel = st.sidebar.multiselect("Categorías", categorias, default=categorias)

# Aplicar filtrado base
df_filtered = df_raw[df_raw["Año"].isin(anios_sel) & df_raw["Categoría_final"].isin(categorias_sel)].copy()

# Separar Outliers para el listado especial
df_outliers_list = df_filtered[df_filtered["Tipo"] == "Outlier"]

if not mostrar_outliers:
    df_filtered = df_filtered[df_filtered["Tipo"] != "Outlier"]

# =========================
# DASHBOARD
# =========================
st.title("📊 Control de Gastos")

# KPIs principales
total = df_filtered["Monto"].sum()
discrecional = df_filtered[df_filtered["Tipo"] == "Discrecional"]["Monto"].sum()
ratio_fuga = (discrecional / total * 100) if total > 0 else 0

# Adaptar KPIs según vista
if view_mode == "🖥️ Horizontal (PC)":
    k1, k2, k3 = st.columns(3)
else:
    k1, k2, k3 = st.container(), st.container(), st.container()

k1.metric("Gasto Total", format_currency(total))
k2.metric("Gasto Discrecional (Fugas)", format_currency(discrecional), delta=f"{ratio_fuga:.1f}% del total", delta_color="inverse")
k3.metric("Movimientos", len(df_filtered))

st.markdown("---")

# --- GRÁFICOS ---
if view_mode == "🖥️ Horizontal (PC)":
    col_left, col_right = st.columns(2)
else:
    col_left, col_right = st.container(), st.container()

with col_left:
    st.subheader("📅 Evolución Mensual")
    evo = df_filtered.groupby(["Año", "Mes", "Mes Texto"])["Monto"].sum().reset_index().sort_values(["Año", "Mes"])
    evo["Periodo"] = evo["Mes Texto"] + " " + evo["Año"].astype(str)
    fig_evo = px.line(evo, x="Periodo", y="Monto", markers=True, line_shape="spline", color_discrete_sequence=["#00CC96"])
    st.plotly_chart(fig_evo, use_container_width=True)

with col_right:
    st.subheader("🛍️ Gasto por Categoría")
    cat = df_filtered.groupby("Categoría_final")["Monto"].sum().reset_index().sort_values("Monto")
    fig_cat = px.bar(cat, x="Monto", y="Categoría_final", orientation="h", color_discrete_sequence=["#636EFA"])
    st.plotly_chart(fig_cat, use_container_width=True)

# Sección de Fugas
st.subheader("⚠️ Top Fugas (Gasto Discrecional)")
fugas = df_filtered[df_filtered["Tipo"] == "Discrecional"].groupby("Subcategoría")["Monto"].sum().reset_index()
fugas = fugas.sort_values("Monto", ascending=False).head(10)
fig_fugas = px.bar(fugas, x="Monto", y="Subcategoría", orientation="h", color="Monto", color_continuous_scale="Reds")
st.plotly_chart(fig_fugas, use_container_width=True)

# --- DETALLE Y OUTLIERS ---
st.markdown("---")
tab1, tab2 = st.tabs(["📄 Detalle de Movimientos", "🚨 Outliers Detectados"])

with tab1:
    cols_ver = ["Fecha", "Categoría_final", "Subcategoría", "Monto", "Descripción"]
    st.dataframe(df_filtered[cols_ver].sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)

with tab2:
    if not df_outliers_list.empty:
        st.warning(f"Se han detectado {len(df_outliers_list)} gastos como Outliers en el periodo seleccionado.")
        st.dataframe(df_outliers_list[cols_ver], use_container_width=True, hide_index=True)
    else:
        st.success("No hay gastos marcados como Outliers en este filtro.")

st.caption("Tip: Si estás en el celular, usa el modo 'Vertical' en el sidebar para una mejor lectura.")
