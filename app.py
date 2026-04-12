import pandas as pd
import streamlit as st
import plotly.express as px

# =========================
# CONFIGURACIÓN
# =========================
st.set_page_config(page_title="Control de Gastos", layout="wide")

# Carga segura desde Secrets
if "SHEET_URL" in st.secrets:
    GOOGLE_SHEET_CSV_URL = st.secrets["SHEET_URL"]
else:
    st.error("🚨 Error: Configura 'SHEET_URL' en los Secrets de Streamlit.")
    st.stop()

# =========================
# CARGA Y CACHE DE DATOS
# =========================
@st.cache_data(ttl=600)
def load_data(url: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(url)
        df.columns = [c.strip() for c in df.columns]

        if "Fecha" in df.columns:
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", dayfirst=True)
        
        if "Monto" in df.columns:
            df["Monto"] = (
                df["Monto"].astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)

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
    st.stop()

# --- SIDEBAR (Filtros Limpios) ---
st.sidebar.header("🔍 Filtros")

mostrar_outliers = st.sidebar.toggle("Incluir Outliers en gráficos", value=False)

anios = sorted(df_raw["Año"].dropna().unique().astype(int))
anios_sel = st.sidebar.multiselect("Años", anios, default=anios)

categorias = sorted(df_raw["Categoría_final"].dropna().unique())
categorias_sel = st.sidebar.multiselect("Categorías", categorias, default=categorias)

# Filtrado base
df_filtered = df_raw[df_raw["Año"].isin(anios_sel) & df_raw["Categoría_final"].isin(categorias_sel)].copy()

# Separar Outliers para auditoría
df_outliers_list = df_filtered[df_filtered["Tipo"] == "Outlier"]

if not mostrar_outliers:
    df_filtered = df_filtered[df_filtered["Tipo"] != "Outlier"]

# =========================
# DASHBOARD (Layout Responsivo)
# =========================
st.title("📊 Control de Gastos")

# KPIs Principales: Se apilan solos en celular
k1, k2, k3 = st.columns(3)

total = df_filtered["Monto"].sum()
discrecional = df_filtered[df_filtered["Tipo"] == "Discrecional"]["Monto"].sum()
ratio_fuga = (discrecional / total * 100) if total > 0 else 0

k1.metric("Gasto Total", format_currency(total))
k2.metric("Gasto Discrecional", format_currency(discrecional), 
          delta=f"{ratio_fuga:.1f}% del total", delta_color="inverse")
k3.metric("Movimientos", len(df_filtered))

st.markdown("---")

# Gráficos Secundarios: Se apilan solos en celular
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📅 Evolución Mensual")
    evo = df_filtered.groupby(["Año", "Mes", "Mes Texto"])["Monto"].sum().reset_index().sort_values(["Año", "Mes"])
    evo["Periodo"] = evo["Mes Texto"] + " " + evo["Año"].astype(str)
    fig_evo = px.line(evo, x="Periodo", y="Monto", markers=True, line_shape="spline")
    st.plotly_chart(fig_evo, use_container_width=True)

with col_right:
    st.subheader("🛍️ Gasto por Categoría")
    cat = df_filtered.groupby("Categoría_final")["Monto"].sum().reset_index().sort_values("Monto")
    fig_cat = px.bar(cat, x="Monto", y="Categoría_final", orientation="h")
    st.plotly_chart(fig_cat, use_container_width=True)

# Sección de Fugas (Ancho completo)
st.subheader("⚠️ Top Fugas (Discrecional)")
fugas = df_filtered[df_filtered["Tipo"] == "Discrecional"].groupby("Subcategoría")["Monto"].sum().reset_index()
fugas = fugas.sort_values("Monto", ascending=False).head(10)
fig_fugas = px.bar(fugas, x="Monto", y="Subcategoría", orientation="h", color="Monto", color_continuous_scale="Reds")
st.plotly_chart(fig_fugas, use_container_width=True)

# --- DETALLE Y OUTLIERS ---
st.markdown("---")
tab1, tab2 = st.tabs(["📄 Detalle", "🚨 Outliers"])

with tab1:
    cols_ver = ["Fecha", "Categoría_final", "Subcategoría", "Monto", "Descripción"]
    st.dataframe(df_filtered[cols_ver].sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)

with tab2:
    if not df_outliers_list.empty:
        # Recuperamos la leyenda aquí también
        st.warning("⚠️ Estos gastos han sido detectados como Outliers y están excluidos de los cálculos principales para no distorsionar tus promedios.")
        st.dataframe(df_outliers_list[cols_ver], use_container_width=True, hide_index=True)
    else:
        st.info("No hay gastos marcados como Outliers en este periodo.")

st.sidebar.markdown("---")
st.sidebar.caption("💡 **Nota sobre Outliers:** Los outliers son gastos extraordinarios que se excluyen por defecto para que puedas ver tu comportamiento de gasto real del día a día.")
st.caption("Base: Google Sheets | Outliers excluidos por defecto para análisis limpio")
