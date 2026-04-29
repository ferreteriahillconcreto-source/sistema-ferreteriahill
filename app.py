import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import time
import json
import hashlib
import base64
from io import BytesIO

# ============================================
# CONFIGURACIÓN INICIAL - FERRETERIA CHILL
# ============================================
st.set_page_config(
    page_title="FERRETERIA CHILL",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# SISTEMA DE TEMA (OSCURO/CLARO)
# ============================================
if 'tema' not in st.session_state:
    st.session_state.tema = 'claro'

def aplicar_tema():
    if st.session_state.tema == 'oscuro':
        return """
            <style>
            .stApp { background-color: #1e1e1e; color: #ffffff; }
            .main-header { color: #ffffff !important; }
            .stMarkdown, .stText, p, span, label, h1, h2, h3, h4 { color: #ffffff !important; }
            .stDataFrame { background-color: #2d2d2d; }
            </style>
        """
    else:
        return """
            <style>
            .stApp { background-color: #f8f9fa; }
            .main-header { color: #1e3c72 !important; }
            </style>
        """

st.markdown(aplicar_tema(), unsafe_allow_html=True)

st.markdown("""
    <style>
    .main-header { font-size: 2.5rem; font-weight: 700; text-align: center; margin-bottom: 2rem; text-shadow: 2px 2px 4px rgba(0,0,0,0.1); }
    .stButton > button { border-radius: 8px; font-weight: 600; transition: all 0.3s ease; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
    .success-box { background-color: #d4edda; color: #155724; padding: 1rem; border-radius: 8px; border-left: 5px solid #28a745; }
    .warning-box { background-color: #fff3cd; color: #856404; padding: 1rem; border-radius: 8px; border-left: 5px solid #ffc107; }
    .error-box { background-color: #f8d7da; color: #721c24; padding: 1rem; border-radius: 8px; border-left: 5px solid #dc3545; }
    .product-card { background-color: white; padding: 1rem; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 1rem; }
    .badge-stock-bajo { background-color: #dc3545; color: white; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.7rem; font-weight: 600; margin-left: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

# ============================================
# CONEXIÓN A SUPABASE (cambiar por tus secretos)
# ============================================
URL = "https://dhkunafosiyvofunehsd.supabase.co/rest/v1/"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRoa3VuYWZvc2l5dm9mdW5laHNkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc0ODkwMDMsImV4cCI6MjA5MzA2NTAwM30.4XuCCQagKXY-nBEngrBg3gJSL4HFIuvZK6AjTilfHUM"
CLAVE_ADMIN = "1234"  # Solo para eliminar productos

db = create_client(URL, KEY)

# ============================================
# FUNCIONES DE USUARIOS Y PERMISOS
# ============================================
def cargar_usuarios():
    res = db.table("usuarios").select("*").order("id").execute()
    return res.data if res.data else []

def login(usuario_nombre, clave):
    res = db.table("usuarios").select("*").eq("nombre", usuario_nombre).eq("activo", True).execute()
    if res.data:
        user = res.data[0]
        if user['clave'] == clave:
            st.session_state.usuario_actual = user
            st.markdown(f"""
                <script>
                localStorage.setItem('usuario_actual', JSON.stringify({json.dumps(user)}));
                </script>
            """, unsafe_allow_html=True)
            return True
    return False

def logout():
    st.session_state.usuario_actual = None
    st.markdown("""
        <script>
        localStorage.removeItem('usuario_actual');
        </script>
    """, unsafe_allow_html=True)
    st.query_params.clear()
    st.rerun()

def es_admin():
    user = st.session_state.get('usuario_actual')
    return user is not None and user.get('rol') == 'admin'

def tiene_permiso(modulo):
    user = st.session_state.get('usuario_actual')
    if not user:
        return False
    rol = user.get('rol')
    if rol == 'admin':
        return True
    modulos_empleado = ["🛒 PUNTO DE VENTA", "💸 GASTOS", "📜 HISTORIAL", "📊 CIERRE DE CAJA"]
    return modulo in modulos_empleado

# ============================================
# PERSISTENCIA DE SESIÓN (localStorage)
# ============================================
st.markdown("""
    <script>
    function obtenerUsuario() {
        const user = localStorage.getItem('usuario_actual');
        return user ? JSON.parse(user) : null;
    }
    </script>
""", unsafe_allow_html=True)

if 'usuario_actual' not in st.session_state or st.session_state.usuario_actual is None:
    if 'usuario_local' not in st.query_params:
        st.markdown("""
            <script>
            const user = localStorage.getItem('usuario_actual');
            if (user) {
                const usuario = JSON.parse(user);
                window.location.href = window.location.pathname + '?usuario_local=' + encodeURIComponent(user);
            }
            </script>
        """, unsafe_allow_html=True)
        st.session_state.usuario_actual = None
    else:
        usuario_json = st.query_params.get('usuario_local')
        if usuario_json:
            try:
                st.session_state.usuario_actual = json.loads(usuario_json)
                st.query_params.clear()
            except:
                st.session_state.usuario_actual = None
        else:
            st.session_state.usuario_actual = None
else:
    if st.session_state.usuario_actual:
        st.markdown(f"""
            <script>
            const current = localStorage.getItem('usuario_actual');
            if (!current) {{
                localStorage.setItem('usuario_actual', JSON.stringify({json.dumps(st.session_state.usuario_actual)}));
            }}
            </script>
        """, unsafe_allow_html=True)

# ============================================
# VERIFICAR TURNO ACTIVO
# ============================================
try:
    response = db.table("cierres").select("*").eq("estado", "abierto").order("fecha_apertura", desc=True).limit(1).execute()
    turno_activo = response.data[0] if response.data else None
    if turno_activo:
        st.session_state.id_turno = turno_activo['id']
        st.session_state.tasa_dia = turno_activo.get('tasa_apertura', 1.0)
        st.session_state.fondo_bs = turno_activo.get('fondo_bs', 0)
        st.session_state.fondo_usd = turno_activo.get('fondo_usd', 0)
    else:
        st.session_state.id_turno = None
except Exception as e:
    st.session_state.id_turno = None

# ============================================
# FUNCIONES AUXILIARES
# ============================================
def requiere_turno():
    if not st.session_state.id_turno:
        st.warning("⚠️ No hay un turno activo. Debe abrir caja en el módulo 'Cierre de Caja'.")
        st.stop()

def requiere_usuario():
    if not st.session_state.usuario_actual:
        st.warning("⚠️ Debe iniciar sesión para acceder a este módulo.")
        st.stop()

def formatear_usd(valor):
    return f"${valor:,.2f}"

def formatear_bs(valor):
    return f"{valor:,.2f} Bs"

def exportar_excel(df, nombre_archivo):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{nombre_archivo}.xlsx">📥 Descargar Excel</a>'
    return href

# ============================================
# MENÚ LATERAL (CON PERMISOS Y LOGIN)
# ============================================
with st.sidebar:
    st.markdown("""
        <div style="background: linear-gradient(135deg, #0a1929 0%, #1a2b3c 100%); padding: 2rem 1rem; border-radius: 0 0 20px 20px; text-align: center; margin-top: -1rem; margin-bottom: 1rem;">
            <h1 style="color: white; margin: 0; font-size: 2.2rem; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">🔧 FERRETERIA CHILL</h1>
            <h2 style="color: #ffd700; margin: 0; font-size: 1.5rem; letter-spacing: 1px;">Soluciones en herramientas y materiales</h2>
            <p style="color: rgba(255,255,255,0.9); margin-top: 0.5rem; font-style: italic;">Calidad y servicio desde 2025</p>
        </div>
    """, unsafe_allow_html=True)
    
    col_tema1, col_tema2 = st.columns(2)
    with col_tema1:
        if st.button("☀️ Claro", use_container_width=True):
            st.session_state.tema = 'claro'
            st.rerun()
    with col_tema2:
        if st.button("🌙 Oscuro", use_container_width=True):
            st.session_state.tema = 'oscuro'
            st.rerun()
    st.divider()
    
    # Login
    if not st.session_state.usuario_actual:
        with st.expander("🔐 Acceso al sistema", expanded=True):
            col_user1, col_user2 = st.columns(2)
            with col_user1:
                usuarios_activos = [u['nombre'] for u in cargar_usuarios() if u['activo']]
                if not usuarios_activos:
                    usuarios_activos = ["admin"]
                usuario_sel = st.selectbox("Usuario", usuarios_activos)
            with col_user2:
                clave_input = st.text_input("Clave", type="password")
            if st.button("✅ Ingresar", use_container_width=True):
                if login(usuario_sel, clave_input):
                    st.success(f"Bienvenido {st.session_state.usuario_actual['nombre']}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Clave incorrecta o usuario inactivo")
    else:
        st.success(f"👤 Usuario: {st.session_state.usuario_actual['nombre']} ({st.session_state.usuario_actual['rol']})")
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            logout()
    
    st.divider()
    
    # Tasa informativa
    with st.container(border=True):
        st.markdown("**💱 TASA BCV**")
        st.metric("Bs/USD", f"{st.session_state.get('tasa_dia', 60.0):.2f}")
        st.caption("Tasa fijada al abrir el turno")
    st.divider()
    
    # Construir lista de módulos según permisos
    modulos_disponibles = []
    if tiene_permiso("📦 INVENTARIO"):
        modulos_disponibles.append("📦 INVENTARIO")
    if tiene_permiso("🛒 PUNTO DE VENTA"):
        modulos_disponibles.append("🛒 PUNTO DE VENTA")
    if tiene_permiso("💸 GASTOS"):
        modulos_disponibles.append("💸 GASTOS")
    if tiene_permiso("📜 HISTORIAL"):
        modulos_disponibles.append("📜 HISTORIAL")
    if tiene_permiso("📊 CIERRE DE CAJA"):
        modulos_disponibles.append("📊 CIERRE DE CAJA")
    if es_admin():
        modulos_disponibles.append("👥 ADMINISTRACIÓN")
    
    opcion = st.radio("MÓDULOS", modulos_disponibles, label_visibility="collapsed")
    st.divider()
    st.success("✅ Conectado a Internet")
    if st.session_state.id_turno:
        st.info(f"📍 Turno activo: #{st.session_state.id_turno}")
    else:
        st.error("🔴 Caja cerrada")

# ============================================
# MÓDULO 1: INVENTARIO (ADAPTADO PARA FERRETERIA)
# ============================================
if opcion == "📦 INVENTARIO":
    st.markdown("<h1 class='main-header'>📦 Gestión de Inventario - Ferreteria Chill</h1>", unsafe_allow_html=True)
    
    CATEGORIAS_FERRETERIA = [
        "Herramientas", "Pinturas", "Electricidad", "Plomería",
        "Ferretería general", "Construcción", "Jardinería", "Seguridad", "Otros"
    ]
    
    try:
        response = db.table("inventario").select("*").order("nombre").execute()
        df = pd.DataFrame(response.data) if response.data else pd.DataFrame()
        
        if not df.empty:
            if 'categoria' not in df.columns:
                df['categoria'] = 'Otros'
            if 'codigo_barras' not in df.columns:
                df['codigo_barras'] = ''
            # Asegurar columnas nuevas (si no existen, las agregamos vacías para mostrar)
            for col in ['unidad_medida', 'marca', 'proveedor']:
                if col not in df.columns:
                    df[col] = ''
        
        tab1, tab2, tab3, tab4 = st.tabs(["📋 Ver Inventario", "➕ Agregar Producto", "📊 Estadísticas", "📥 Respaldos"])
        
        with tab1:
            col_f1, col_f2, col_f3, col_f4 = st.columns([2, 1, 1, 1])
            with col_f1:
                busqueda = st.text_input("🔍 Buscar producto", placeholder="Nombre o código...")
            with col_f2:
                categoria_filtro = st.selectbox("Categoría", ["Todas"] + CATEGORIAS_FERRETERIA)
            with col_f3:
                ver_bajo_stock = st.checkbox("⚠️ Solo stock bajo")
            with col_f4:
                if st.button("📤 Exportar a Excel", use_container_width=True):
                    if not df.empty:
                        export_df = df[['nombre', 'categoria', 'unidad_medida', 'marca', 'proveedor', 'stock', 'costo', 'precio_detal', 'precio_mayor', 'min_mayor']].copy()
                        export_df.columns = ['Producto', 'Categoría', 'Unidad', 'Marca', 'Proveedor', 'Stock', 'Costo $', 'Precio Detal $', 'Precio Mayor $', 'Min. Mayor']
                        href = exportar_excel(export_df, f"inventario_{datetime.now().strftime('%Y%m%d')}")
                        st.markdown(href, unsafe_allow_html=True)
            
            if not df.empty:
                df_filtrado = df.copy()
                if busqueda:
                    mask_nombre = df_filtrado['nombre'].str.contains(busqueda, case=False, na=False)
                    if 'codigo_barras' in df_filtrado.columns:
                        codigos_str = df_filtrado['codigo_barras'].fillna('').astype(str)
                        mask_codigo = codigos_str.str.contains(busqueda, case=False, na=False)
                        df_filtrado = df_filtrado[mask_nombre | mask_codigo]
                    else:
                        df_filtrado = df_filtrado[mask_nombre]
                if categoria_filtro != "Todas" and 'categoria' in df_filtrado.columns:
                    df_filtrado = df_filtrado[df_filtrado['categoria'] == categoria_filtro]
                if ver_bajo_stock:
                    df_filtrado = df_filtrado[df_filtrado['stock'] < 5]
                    if len(df_filtrado) > 0:
                        st.warning(f"⚠️ Hay {len(df_filtrado)} productos con stock bajo")
                    else:
                        st.success("✅ No hay productos con stock bajo")
                
                def colorear_stock(val):
                    if val < 5:
                        return 'color: red; font-weight: bold; background-color: #ffe6e6'
                    elif val < 10:
                        return 'color: orange; font-weight: bold;'
                    return 'color: green; font-weight: bold;'
                
                columnas_mostrar = ['nombre', 'categoria', 'unidad_medida', 'marca', 'proveedor', 'stock', 'costo', 'precio_detal', 'precio_mayor', 'min_mayor']
                columnas_mostrar = [col for col in columnas_mostrar if col in df_filtrado.columns]
                df_mostrar = df_filtrado[columnas_mostrar].copy()
                df_mostrar.columns = ['Producto', 'Categoría', 'Unidad', 'Marca', 'Proveedor', 'Stock', 'Costo $', 'Detal $', 'Mayor $', 'Mín. Mayor']
                styled_df = df_mostrar.style.map(colorear_stock, subset=['Stock'])
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
                st.caption(f"Mostrando {len(df_filtrado)} de {len(df)} productos")
                
                st.divider()
                st.subheader("✏️ Editar producto")
                if not df_filtrado.empty:
                    producto_editar = st.selectbox("Seleccionar producto", df_filtrado['nombre'].tolist(), key="editar")
                    if producto_editar:
                        prod = df[df['nombre'] == producto_editar].iloc[0]
                        with st.form("form_editar"):
                            col_e1, col_e2 = st.columns(2)
                            with col_e1:
                                nuevo_nombre = st.text_input("Nombre", value=prod['nombre'])
                                nueva_categoria = st.selectbox("Categoría", CATEGORIAS_FERRETERIA, 
                                                              index=CATEGORIAS_FERRETERIA.index(prod.get('categoria', 'Otros')) if prod.get('categoria', 'Otros') in CATEGORIAS_FERRETERIA else 8)
                                nueva_unidad = st.selectbox("Unidad de medida", ["unidad", "metro", "kilo", "litro", "galón", "pieza"], index=["unidad","metro","kilo","litro","galón","pieza"].index(prod.get('unidad_medida','unidad')) if prod.get('unidad_medida') in ["unidad","metro","kilo","litro","galón","pieza"] else 0)
                                nueva_marca = st.text_input("Marca", value=prod.get('marca', ''))
                                nuevo_proveedor = st.text_input("Proveedor", value=prod.get('proveedor', ''))
                                nuevo_stock = st.number_input("Stock", value=float(prod['stock']), min_value=0.0, step=0.1, format="%.2f")
                                nuevo_costo = st.number_input("Costo $", value=float(prod['costo']), min_value=0.0, step=0.01, format="%.2f")
                                nuevo_codigo = st.text_input("Código de barras", value=prod.get('codigo_barras', ''))
                            with col_e2:
                                nuevo_detal = st.number_input("Precio Detal $", value=float(prod['precio_detal']), min_value=0.0, step=0.01, format="%.2f")
                                nuevo_mayor = st.number_input("Precio Mayor $", value=float(prod['precio_mayor']), min_value=0.0, step=0.01, format="%.2f")
                                nuevo_min = st.number_input("Mín. Mayor (unidades)", value=int(prod['min_mayor']), min_value=1, step=1)
                            if st.form_submit_button("💾 Guardar Cambios", use_container_width=True):
                                try:
                                    datos_actualizados = {
                                        "nombre": nuevo_nombre,
                                        "categoria": nueva_categoria,
                                        "unidad_medida": nueva_unidad,
                                        "marca": nueva_marca,
                                        "proveedor": nuevo_proveedor,
                                        "stock": nuevo_stock,
                                        "costo": nuevo_costo,
                                        "precio_detal": nuevo_detal,
                                        "precio_mayor": nuevo_mayor,
                                        "min_mayor": nuevo_min
                                    }
                                    if nuevo_codigo:
                                        datos_actualizados["codigo_barras"] = nuevo_codigo
                                    db.table("inventario").update(datos_actualizados).eq("id", prod['id']).execute()
                                    st.success("✅ Producto actualizado")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                
                st.divider()
                st.subheader("🗑️ Eliminar producto")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    producto_eliminar = st.selectbox("Seleccionar producto", [""] + df['nombre'].tolist(), key="eliminar")
                with col_d2:
                    clave = st.text_input("Clave Admin", type="password", key="clave_eliminar")
                if producto_eliminar and st.button("❌ Eliminar", type="primary", use_container_width=True):
                    if clave == CLAVE_ADMIN:
                        try:
                            db.table("inventario").delete().eq("nombre", producto_eliminar).execute()
                            st.success(f"Producto '{producto_eliminar}' eliminado")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.error("Clave incorrecta")
            else:
                st.info("No hay productos en el inventario")
        
        with tab2:
            with st.form("nuevo_producto", clear_on_submit=True):
                st.markdown("### 📝 Datos del nuevo producto (Ferretería)")
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    nombre = st.text_input("Nombre del producto *").upper()
                    categoria = st.selectbox("Categoría", CATEGORIAS_FERRETERIA)
                    unidad_medida = st.selectbox("Unidad de medida *", ["unidad", "metro", "kilo", "litro", "galón", "pieza"])
                    marca = st.text_input("Marca (opcional)")
                    proveedor = st.text_input("Proveedor (opcional)")
                    stock = st.number_input("Stock inicial *", min_value=0.0, step=0.1, format="%.2f")
                    costo = st.number_input("Costo $ *", min_value=0.0, step=0.01, format="%.2f")
                    codigo_barras = st.text_input("Código de barras (opcional)")
                with col_a2:
                    precio_detal = st.number_input("Precio Detal $ *", min_value=0.0, step=0.01, format="%.2f")
                    precio_mayor = st.number_input("Precio Mayor $ *", min_value=0.0, step=0.01, format="%.2f")
                    min_mayor = st.number_input("Mínimo para Mayor (unidades) *", min_value=1, value=6, step=1)
                if st.form_submit_button("📦 Registrar Producto", use_container_width=True):
                    if not nombre:
                        st.error("El nombre es obligatorio")
                    elif stock < 0 or costo < 0 or precio_detal <= 0:
                        st.error("Verifique los valores ingresados")
                    else:
                        try:
                            existe = db.table("inventario").select("*").eq("nombre", nombre).execute()
                            if existe.data:
                                st.error(f"Ya existe un producto con el nombre '{nombre}'")
                                st.stop()
                            datos_nuevos = {
                                "nombre": nombre,
                                "categoria": categoria,
                                "unidad_medida": unidad_medida,
                                "marca": marca,
                                "proveedor": proveedor,
                                "stock": stock,
                                "costo": costo,
                                "precio_detal": precio_detal,
                                "precio_mayor": precio_mayor,
                                "min_mayor": min_mayor
                            }
                            if codigo_barras:
                                datos_nuevos["codigo_barras"] = codigo_barras
                            db.table("inventario").insert(datos_nuevos).execute()
                            st.success(f"✅ Producto '{nombre}' registrado exitosamente")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al registrar: {e}")
        
        with tab3:
            if not df.empty:
                # Asegurar que 'stock' sea numérico
                df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0)
                valor_inv = (df['stock'] * df['costo']).sum()
                valor_venta = (df['stock'] * df['precio_detal']).sum()
                bajo_stock = len(df[df['stock'] < 5])
                total_productos = len(df)
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Total productos", total_productos)
                col_m2.metric("Valor inventario (costo)", formatear_usd(valor_inv))
                col_m3.metric("Valor venta potencial", formatear_usd(valor_venta))
                col_m4.metric("Stock bajo", bajo_stock, delta_color="inverse")
                ganancia_potencial = valor_venta - valor_inv
                st.metric("💰 Ganancia potencial total", formatear_usd(ganancia_potencial),
                         delta=f"{(ganancia_potencial/valor_inv*100):.1f}%" if valor_inv else "")
                st.subheader("📊 Productos por categoría")
                if 'categoria' in df.columns:
                    cat_stats = df.groupby('categoria').agg({
                        'nombre': 'count',
                        'stock': 'sum',
                        'costo': lambda x: (x * df.loc[x.index, 'stock']).sum()
                    }).round(2)
                    cat_stats.columns = ['Cantidad', 'Stock total', 'Valor total $']
                    st.dataframe(cat_stats, use_container_width=True)
                st.subheader("💰 Top 10 productos por valor en inventario")
                df_temp = df.copy()
                df_temp['valor_total'] = df_temp['stock'] * df_temp['costo']
                df_top = df_temp.nlargest(10, 'valor_total')[['nombre', 'categoria', 'unidad_medida', 'marca', 'stock', 'costo', 'valor_total']]
                df_top.columns = ['Producto', 'Categoría', 'Unidad', 'Marca', 'Stock', 'Costo unitario', 'Valor total']
                st.dataframe(df_top, use_container_width=True, hide_index=True)
                st.subheader("⚠️ Productos con stock bajo (<5)")
                df_bajo = df[df['stock'] < 5][['nombre', 'categoria', 'unidad_medida', 'marca', 'stock', 'costo']]
                if not df_bajo.empty:
                    df_bajo.columns = ['Producto', 'Categoría', 'Unidad', 'Marca', 'Stock', 'Costo unitario']
                    st.dataframe(df_bajo, use_container_width=True, hide_index=True)
                else:
                    st.success("No hay productos con stock bajo")
            else:
                st.info("No hay datos para mostrar estadísticas")
        
        with tab4:
            st.subheader("📥 Respaldo de inventario")
            st.markdown("""
                <div style='background-color: #e7f3ff; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>
                    <p>Desde aquí puedes exportar todo tu inventario para tener un respaldo físico.</p>
                    <p>Recomendación: Haz un respaldo diario antes de cerrar.</p>
                </div>
            """, unsafe_allow_html=True)
            if not df.empty:
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    st.markdown("**📊 Respaldo completo**")
                    if st.button("📥 Exportar inventario completo", use_container_width=True):
                        export_df = df[['nombre', 'categoria', 'unidad_medida', 'marca', 'proveedor', 'stock', 'costo', 'precio_detal', 'precio_mayor', 'min_mayor']].copy()
                        export_df.columns = ['Producto', 'Categoría', 'Unidad', 'Marca', 'Proveedor', 'Stock', 'Costo $', 'Precio Detal $', 'Precio Mayor $', 'Min. Mayor']
                        export_df = export_df.sort_values('Producto')
                        href = exportar_excel(export_df, f"inventario_completo_{datetime.now().strftime('%Y%m%d_%H%M')}")
                        st.markdown(href, unsafe_allow_html=True)
                with col_r2:
                    st.markdown("**📋 Lista de precios**")
                    if st.button("📥 Exportar lista de precios", use_container_width=True):
                        precio_df = df[['nombre', 'categoria', 'unidad_medida', 'precio_detal', 'precio_mayor', 'min_mayor']].copy()
                        precio_df.columns = ['Producto', 'Categoría', 'Unidad', 'Precio Detal $', 'Precio Mayor $', 'Mín. Mayor']
                        precio_df = precio_df.sort_values('Categoría')
                        href = exportar_excel(precio_df, f"lista_precios_{datetime.now().strftime('%Y%m%d')}")
                        st.markdown(href, unsafe_allow_html=True)
                st.divider()
                st.markdown(f"""
                    **📌 Última actualización:** {datetime.now().strftime('%d/%m/%Y %H:%M')}  
                    **📦 Total de productos:** {len(df)}  
                    **🏷️ Categorías:** {df['categoria'].nunique() if 'categoria' in df.columns else 0}
                """)
            else:
                st.info("No hay productos para respaldar")
    except Exception as e:
        st.error(f"Error en inventario: {e}")
        st.exception(e)

# ============================================
# MÓDULO 2: PUNTO DE VENTA (ADAPTADO PARA FERRETERIA)
# ============================================
elif opcion == "🛒 PUNTO DE VENTA":
    requiere_turno()
    requiere_usuario()
    
    id_turno = st.session_state.id_turno
    tasa = st.session_state.tasa_dia
    
    st.markdown("<h1 class='main-header'>🛒 Punto de Venta - Ferreteria Chill</h1>", unsafe_allow_html=True)
    st.markdown(f"""
        <div style='background-color: #e7f3ff; padding: 0.8rem; border-radius: 8px; margin-bottom: 1rem;'>
            <span style='font-weight:600;'>📍 Turno #{id_turno}</span> | 
            <span>💱 Tasa: {tasa:.2f} Bs/$</span> |
            <span>👤 Vendedor: {st.session_state.usuario_actual['nombre']}</span>
        </div>
    """, unsafe_allow_html=True)
    
    # SISTEMA DE MESAS / CUENTAS
    if 'mesas' not in st.session_state:
        st.session_state.mesas = {
            'mesa_1': {'nombre': 'Mesa 1', 'carrito': [], 'activa': True, 'cliente': ''},
            'mesa_2': {'nombre': 'Mesa 2', 'carrito': [], 'activa': True, 'cliente': ''},
            'mesa_3': {'nombre': 'Mesa 3', 'carrito': [], 'activa': True, 'cliente': ''},
            'mesa_4': {'nombre': 'Mesa 4', 'carrito': [], 'activa': True, 'cliente': ''},
            'barra': {'nombre': 'Mostrador', 'carrito': [], 'activa': True, 'cliente': 'Compra en mostrador'},
            'llevar': {'nombre': 'Para llevar', 'carrito': [], 'activa': True, 'cliente': ''}
        }
    
    if 'mesa_actual' not in st.session_state:
        st.session_state.mesa_actual = 'mesa_1'
    
    st.subheader("🍽️ Seleccionar Mesa / Atención")
    col_mesas = st.columns(6)
    idx_mesa = 0
    for mesa_id, mesa_data in st.session_state.mesas.items():
        with col_mesas[idx_mesa]:
            if mesa_id == st.session_state.mesa_actual:
                bg_color = "#28a745"
            elif len(mesa_data['carrito']) > 0:
                bg_color = "#ffc107"
            else:
                bg_color = "#6c757d"
            if st.button(
                f"{mesa_data['nombre']}\n({len(mesa_data['carrito'])} items)",
                key=f"mesa_{mesa_id}",
                use_container_width=True,
                type="primary" if mesa_id == st.session_state.mesa_actual else "secondary"
            ):
                st.session_state.mesa_actual = mesa_id
                st.rerun()
        idx_mesa += 1
    
    mesa_actual = st.session_state.mesas[st.session_state.mesa_actual]
    st.divider()
    
    col_mesa_info1, col_mesa_info2, col_mesa_info3 = st.columns([2, 2, 1])
    with col_mesa_info1:
        st.markdown(f"### 🛠️ {mesa_actual['nombre']}")
    with col_mesa_info2:
        if mesa_actual['nombre'] not in ['Mostrador', 'Para llevar']:
            cliente = st.text_input(
                "Nombre del cliente (opcional)",
                value=mesa_actual.get('cliente', ''),
                key="cliente_mesa",
                placeholder="Ej: Juan Pérez"
            )
            if cliente != mesa_actual.get('cliente', ''):
                st.session_state.mesas[st.session_state.mesa_actual]['cliente'] = cliente
    with col_mesa_info3:
        if len(mesa_actual['carrito']) > 0:
            if st.button("🧹 Limpiar mesa", use_container_width=True):
                st.session_state.mesas[st.session_state.mesa_actual]['carrito'] = []
                st.rerun()
    
    st.divider()
    
    es_tienda = st.checkbox("🏪 Venta en tienda (sin recargo)", help="Precios normales")
    
    with st.popover("🔍 Buscar productos", use_container_width=True):
        busqueda = st.text_input("", placeholder="Escribe nombre del producto...", key="buscar_venta_popover")
        if busqueda:
            try:
                response = db.table("inventario")\
                    .select("*")\
                    .ilike("nombre", f"%{busqueda}%")\
                    .gt("stock", 0)\
                    .order("nombre")\
                    .limit(30)\
                    .execute()
                productos = response.data
                if productos:
                    st.markdown("---")
                    cols_header = st.columns([3, 1, 1, 1, 1])
                    cols_header[0].write("**Producto**")
                    cols_header[1].write("**Unidad**")
                    cols_header[2].write("**Stock**")
                    cols_header[3].write("**Precio USD**")
                    cols_header[4].write("**Precio Bs**")
                    st.markdown("---")
                    for prod in productos:
                        precio_base = float(prod['precio_detal'])
                        precio_unitario = precio_base
                        precio_bs = precio_unitario * tasa
                        unidad = prod.get('unidad_medida', 'unidad')
                        col1, col2, col3, col4, col5, col6 = st.columns([3, 1, 1, 1, 1, 0.5])
                        col1.write(prod['nombre'])
                        col2.write(unidad)
                        col3.write(f"{prod['stock']:.2f}")
                        col4.write(f"${precio_unitario:.2f}")
                        col5.write(f"{precio_bs:,.2f} Bs")
                        if col6.button("➕", key=f"add_pop_{prod['id']}", help="Agregar"):
                            carrito_actual = mesa_actual['carrito']
                            # Determinar si aplica precio mayor
                            nueva_cantidad = 1
                            # Para simplificar, tomamos el precio según la cantidad que haya en carrito +1
                            # Obtenemos cantidad actual
                            cant_actual = 0
                            for item in carrito_actual:
                                if item['id'] == prod['id']:
                                    cant_actual = item['cantidad']
                            nueva_cant_total = cant_actual + 1
                            if nueva_cant_total >= prod['min_mayor']:
                                precio_final = float(prod['precio_mayor'])
                                tipo_precio = " (Mayor)"
                            else:
                                precio_final = precio_base
                                tipo_precio = ""
                            encontrado = False
                            for item in st.session_state.mesas[st.session_state.mesa_actual]['carrito']:
                                if item['id'] == prod['id']:
                                    item['cantidad'] += 1
                                    item['precio'] = precio_final
                                    item['subtotal'] = item['cantidad'] * item['precio']
                                    encontrado = True
                                    break
                            if not encontrado:
                                st.session_state.mesas[st.session_state.mesa_actual]['carrito'].append({
                                    "id": prod['id'],
                                    "nombre": prod['nombre'],
                                    "unidad": prod.get('unidad_medida', 'unidad'),
                                    "cantidad": 1,
                                    "precio": precio_final,
                                    "costo": float(prod['costo']),
                                    "subtotal": precio_final,
                                    "tipo_precio": tipo_precio
                                })
                            st.rerun()
                else:
                    st.info("No se encontraron productos")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.info("Escribe el nombre del producto para buscar")
    
    st.divider()
    
    st.subheader(f"🛒 Carrito - {mesa_actual['nombre']}")
    carrito = mesa_actual['carrito']
    
    if not carrito:
        st.info("Carrito vacío")
    else:
        with st.container():
            st.markdown("""
                <style>
                .carrito-scroll { max-height: 400px; overflow-y: auto; margin-bottom: 1rem; }
                </style>
            """, unsafe_allow_html=True)
            st.markdown('<div class="carrito-scroll">', unsafe_allow_html=True)
            
            cols_head = st.columns([2, 1, 1, 1, 1, 0.5])
            cols_head[0].write("**Producto**")
            cols_head[1].write("**Unidad**")
            cols_head[2].write("**Precio USD**")
            cols_head[3].write("**Precio Bs**")
            cols_head[4].write("**Cantidad**")
            cols_head[5].write("**Eliminar**")
            st.markdown("---")
            
            total_venta_usd = 0
            total_costo = 0
            
            for idx, item in enumerate(carrito):
                cols = st.columns([2, 1, 1, 1, 1, 0.5])
                cols[0].write(item['nombre'])
                cols[1].write(item.get('unidad', 'unidad'))
                cols[2].write(f"${item['precio']:.2f}")
                cols[3].write(f"{(item['precio'] * tasa):,.2f} Bs")
                
                nueva_cant = cols[4].number_input(
                    "",
                    min_value=0.0,
                    max_value=1000.0,
                    value=float(item['cantidad']),
                    step=0.1,
                    format="%.2f",
                    key=f"cant_mesa_lista_{idx}",
                    label_visibility="collapsed"
                )
                if nueva_cant != item['cantidad']:
                    if nueva_cant == 0:
                        st.session_state.mesas[st.session_state.mesa_actual]['carrito'].pop(idx)
                        st.rerun()
                    else:
                        # Recalcular precio si aplica mayorista
                        prod_data = None
                        try:
                            prod_resp = db.table("inventario").select("precio_detal, precio_mayor, min_mayor").eq("id", item['id']).execute()
                            if prod_resp.data:
                                prod_data = prod_resp.data[0]
                        except:
                            pass
                        if prod_data:
                            if nueva_cant >= prod_data['min_mayor']:
                                nuevo_precio = float(prod_data['precio_mayor'])
                                tipo_precio = " (Mayor)"
                            else:
                                nuevo_precio = float(prod_data['precio_detal'])
                                tipo_precio = ""
                            item['precio'] = nuevo_precio
                            item['tipo_precio'] = tipo_precio
                        item['cantidad'] = nueva_cant
                        item['subtotal'] = item['cantidad'] * item['precio']
                        st.rerun()
                
                if cols[5].button("❌", key=f"del_lista_{idx}"):
                    st.session_state.mesas[st.session_state.mesa_actual]['carrito'].pop(idx)
                    st.rerun()
                
                total_venta_usd += item['subtotal']
                total_costo += item['cantidad'] * item['costo']
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        total_venta_bs = total_venta_usd * tasa
        st.divider()
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown(f"### Total calculado USD: ${total_venta_usd:,.2f}")
        with col_t2:
            st.markdown(f"### Total calculado Bs: {total_venta_bs:,.2f}")
        
        total_final_usd = total_venta_usd
        total_final_bs = total_venta_bs
        
        with st.expander("🔧 Ajustar monto final (redondeo)", expanded=False):
            st.markdown("Si deseas redondear el total a cobrar, selecciona una opción e ingresa el monto:")
            opcion_ajuste = st.radio(
                "Ajustar en:",
                ["No ajustar (usar calculado)", "Bolívares (Bs)", "Dólares (USD)"],
                horizontal=True,
                key="opcion_ajuste"
            )
            if opcion_ajuste == "Bolívares (Bs)":
                monto_ajustado_bs = st.number_input(
                    "Monto final en Bs",
                    min_value=0.0,
                    value=float(total_venta_bs),
                    step=10.0,
                    format="%.2f",
                    key="monto_ajustado_bs"
                )
                total_final_bs = monto_ajustado_bs
                total_final_usd = monto_ajustado_bs / tasa if tasa > 0 else 0
                st.info(f"Equivalente en USD: ${total_final_usd:.2f}")
            elif opcion_ajuste == "Dólares (USD)":
                monto_ajustado_usd = st.number_input(
                    "Monto final en USD",
                    min_value=0.0,
                    value=float(total_venta_usd),
                    step=1.0,
                    format="%.2f",
                    key="monto_ajustado_usd"
                )
                total_final_usd = monto_ajustado_usd
                total_final_bs = monto_ajustado_usd * tasa
                st.info(f"Equivalente en Bs: {total_final_bs:,.2f} Bs")
        
        st.divider()
        
        with st.expander("💳 Detalle de pagos", expanded=True):
            st.markdown("**Ingresa los montos recibidos:**")
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.markdown("**💵 Pagos en USD**")
                pago_usd_efectivo = st.number_input("Efectivo USD", min_value=0.0, step=5.0, format="%.2f", key="p_usd_efectivo")
                pago_zelle = st.number_input("Zelle USD", min_value=0.0, step=5.0, format="%.2f", key="p_zelle")
                pago_otros_usd = st.number_input("Otros USD (Binance/Transfer)", min_value=0.0, step=5.0, format="%.2f", key="p_otros_usd")
            with col_p2:
                st.markdown("**💵 Pagos en Bs**")
                pago_bs_efectivo = st.number_input("Efectivo Bs", min_value=0.0, step=100.0, format="%.2f", key="p_bs_efectivo")
                pago_movil = st.number_input("Pago Móvil Bs", min_value=0.0, step=100.0, format="%.2f", key="p_movil")
                pago_punto = st.number_input("Punto de Venta Bs", min_value=0.0, step=100.0, format="%.2f", key="p_punto")
            
            total_usd_recibido = pago_usd_efectivo + pago_zelle + pago_otros_usd
            total_bs_recibido = pago_bs_efectivo + pago_movil + pago_punto
            total_usd_equivalente = total_usd_recibido + (total_bs_recibido / tasa if tasa > 0 else 0)
            esperado_usd = total_final_bs / tasa if tasa > 0 else 0
            vuelto_usd = total_usd_equivalente - esperado_usd
            
            st.divider()
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                st.metric("Pagado USD eq.", f"${total_usd_equivalente:,.2f}")
            with col_r2:
                st.metric("Esperado USD", f"${esperado_usd:,.2f}")
            with col_r3:
                if vuelto_usd >= 0:
                    st.metric("Vuelto USD", f"${vuelto_usd:.2f}")
                else:
                    st.metric("Faltante USD", f"${abs(vuelto_usd):,.2f}", delta_color="inverse")
            
            if vuelto_usd >= -0.01:
                st.success(f"✅ Pago suficiente. Vuelto: ${vuelto_usd:.2f} / {(vuelto_usd * tasa):,.2f} Bs")
            else:
                st.error(f"❌ Faltante: ${abs(vuelto_usd):,.2f} / {(abs(vuelto_usd) * tasa):,.2f} Bs")
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("🔄 Limpiar carrito", use_container_width=True):
                st.session_state.mesas[st.session_state.mesa_actual]['carrito'] = []
                st.rerun()
        with col_btn2:
            venta_valida = vuelto_usd >= -0.01 and len(carrito) > 0
            if st.button("✅ Cobrar y cerrar cuenta", type="primary", use_container_width=True, disabled=not venta_valida):
                try:
                    items_resumen = []
                    for item in carrito:
                        unidad_str = item.get('unidad', '')
                        items_resumen.append(f"{item['cantidad']:.2f} {unidad_str} de {item['nombre']}")
                        stock_actual = db.table("inventario").select("stock").eq("id", item['id']).execute().data[0]['stock']
                        db.table("inventario").update({
                            "stock": stock_actual - item['cantidad']
                        }).eq("id", item['id']).execute()
                    
                    info_cliente = mesa_actual.get('cliente', '')
                    if info_cliente:
                        info_cliente = f" - Cliente: {info_cliente}"
                    
                    venta_data = {
                        "id_cierre": id_turno,
                        "producto": ", ".join(items_resumen),
                        "cantidad": sum(item['cantidad'] for item in carrito),
                        "total_usd": round(total_final_usd, 2),
                        "monto_cobrado_bs": round(total_final_bs, 2),
                        "tasa_cambio": tasa,
                        "pago_divisas": round(pago_usd_efectivo, 2),
                        "pago_zelle": round(pago_zelle, 2),
                        "pago_otros": round(pago_otros_usd, 2),
                        "pago_efectivo": round(pago_bs_efectivo, 2),
                        "pago_movil": round(pago_movil, 2),
                        "pago_punto": round(pago_punto, 2),
                        "costo_venta": round(total_costo, 2),
                        "estado": "Finalizado",
                        "items": json.dumps(carrito),
                        "id_transaccion": str(int(datetime.now().timestamp())),
                        "fecha": datetime.now().isoformat(),
                        "cliente": mesa_actual.get('cliente', '') or f"Mesa: {mesa_actual['nombre']}"
                    }
                    db.table("ventas").insert(venta_data).execute()
                    
                    st.balloons()
                    st.success(f"✅ Venta registrada - {mesa_actual['nombre']}{info_cliente}")
                    
                    with st.popover("🧾 VER TICKET", use_container_width=True):
                        items_html = ""
                        for item in carrito:
                            items_html += f"""
                            <tr>
                                <td style="padding: 6px 8px;">{item['cantidad']:.2f} {item.get('unidad', '')}</td>
                                <td style="padding: 6px 8px;">{item['nombre']}</td>
                                <td style="padding: 6px 8px; text-align: right;">${item['precio']:.2f}</td>
                                <td style="padding: 6px 8px; text-align: right;">${item['subtotal']:.2f}</td>
                            </tr>
                            """
                        factura_html = f"""
                        <div style="background:white; padding:20px; border-radius:10px; border:2px solid #1e3c72; max-width:800px; margin:0 auto; font-family: sans-serif;">
                            <h3 style="text-align:center;">🔧 FERRETERIA CHILL</h3>
                            <p style="text-align:center;">Soluciones en herramientas y materiales</p>
                            <p style="text-align:center;">{datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                            <p style="text-align:center;">Turno #{id_turno} | {mesa_actual['nombre']}{info_cliente}</p>
                            <p style="text-align:center;">Atendido por: {st.session_state.usuario_actual['nombre']}</p>
                            <hr>
                            <table style="width:100%; border-collapse: collapse;">
                                <thead>
                                    <tr style="border-bottom:1px solid #ccc;">
                                        <th style="text-align:left;">Cant</th>
                                        <th style="text-align:left;">Producto</th>
                                        <th style="text-align:right;">Precio</th>
                                        <th style="text-align:right;">Subtotal</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {items_html}
                                </tbody>
                            </table>
                            <hr>
                            <table style="width:100%;">
                                <tr>
                                    <td style="text-align:right;"><b>Total USD:</b></td>
                                    <td style="text-align:right;">${total_final_usd:.2f}</td>
                                </tr>
                                <tr>
                                    <td style="text-align:right;"><b>Total Bs:</b></td>
                                    <td style="text-align:right;">{total_final_bs:,.2f} Bs</td>
                                </tr>
                            </table>
                            <p style="text-align:center; margin-top:20px;">¡Gracias por su compra!</p>
                        </div>
                        """
                        st.markdown(factura_html, unsafe_allow_html=True)
                    
                    st.session_state.mesas[st.session_state.mesa_actual]['carrito'] = []
                    if mesa_actual['nombre'] not in ['Mostrador', 'Para llevar']:
                        st.session_state.mesas[st.session_state.mesa_actual]['cliente'] = ''
                    
                    if st.button("🔄 Cerrar y continuar"):
                        st.rerun()
                except Exception as e:
                    st.error(f"Error al procesar venta: {e}")
        with col_btn3:
            if len(carrito) > 0 and mesa_actual['nombre'] not in ['Mostrador', 'Para llevar']:
                if st.button("⏸️ Dejar pendiente", use_container_width=True):
                    st.session_state.mesa_actual = 'mesa_1'
                    st.rerun()

# ============================================
# MÓDULO 3: GASTOS (SIN CAMBIOS)
# ============================================
elif opcion == "💸 GASTOS":
    requiere_turno()
    requiere_usuario()
    
    id_turno = st.session_state.id_turno
    st.markdown("<h1 class='main-header'>💸 Gestión de Gastos</h1>", unsafe_allow_html=True)
    
    try:
        response = db.table("gastos").select("*").eq("id_cierre", id_turno).order("fecha", desc=True).execute()
        df_gastos = pd.DataFrame(response.data) if response.data else pd.DataFrame()
        
        if not df_gastos.empty:
            st.subheader("📋 Gastos del turno")
            if 'fecha' in df_gastos.columns:
                df_gastos['fecha'] = pd.to_datetime(df_gastos['fecha']).dt.strftime('%d/%m/%Y %H:%M')
            columnas_mostrar = ['fecha', 'descripcion', 'monto_usd']
            if 'categoria' in df_gastos.columns:
                columnas_mostrar.append('categoria')
            if 'estado' in df_gastos.columns:
                columnas_mostrar.append('estado')
            st.dataframe(df_gastos[columnas_mostrar], use_container_width=True, hide_index=True)
            total_gastos = df_gastos['monto_usd'].sum()
            st.metric("💰 Total gastos USD", f"${total_gastos:,.2f}")
            if st.button("📥 Exportar gastos a Excel", use_container_width=True):
                export_df = df_gastos[['fecha', 'descripcion', 'monto_usd', 'categoria']].copy()
                export_df.columns = ['Fecha', 'Descripción', 'Monto USD', 'Categoría']
                href = exportar_excel(export_df, f"gastos_turno_{id_turno}_{datetime.now().strftime('%Y%m%d')}")
                st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No hay gastos registrados en este turno")
    except Exception as e:
        st.error(f"Error cargando gastos: {e}")
    
    st.divider()
    with st.form("nuevo_gasto"):
        st.subheader("➕ Registrar nuevo gasto")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            descripcion = st.text_input("Descripción *", placeholder="Ej: Compra de herramientas, pintura, cables...")
            monto_usd = st.number_input("Monto USD *", min_value=0.01, step=0.01, format="%.2f")
        with col_g2:
            categoria = st.selectbox("Categoría", ["", "Insumos", "Herramientas", "Transporte", "Servicios", "Alimentación", "Otros"])
            monto_bs_extra = st.number_input("Monto extra Bs (opcional)", min_value=0.0, step=10.0, format="%.2f")
        if st.form_submit_button("✅ Registrar gasto", use_container_width=True):
            if descripcion and monto_usd > 0:
                try:
                    gasto_data = {
                        "id_cierre": id_turno,
                        "descripcion": descripcion,
                        "monto_usd": monto_usd,
                        "estado": "activo",
                        "fecha": datetime.now().isoformat()
                    }
                    if categoria:
                        gasto_data["categoria"] = categoria
                    if monto_bs_extra > 0:
                        gasto_data["monto_bs_extra"] = monto_bs_extra
                    db.table("gastos").insert(gasto_data).execute()
                    st.success("✅ Gasto registrado correctamente")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar gasto: {e}")
            else:
                st.warning("⚠️ Complete los campos obligatorios (*)")

# ============================================
# MÓDULO 4: HISTORIAL (SIN CAMBIOS)
# ============================================
elif opcion == "📜 HISTORIAL":
    requiere_usuario()
    
    st.markdown("<h1 class='main-header'>📜 Historial de Ventas</h1>", unsafe_allow_html=True)
    st.markdown(f"""
        <div style='background-color: #e7f3ff; padding: 0.8rem; border-radius: 8px; margin-bottom: 1.5rem;'>
            <span style='font-weight:600;'>👤 Usuario: {st.session_state.usuario_actual['nombre']}</span>
        </div>
    """, unsafe_allow_html=True)
    
    # Selección de carga (turno o fechas)
    st.subheader("🔍 Selecciona qué ventas quieres ver")
    tipo_busqueda = st.radio(
        "Mostrar ventas por:",
        ["🔢 Número de turno", "📅 Rango de fechas"],
        horizontal=True,
        key="tipo_historial"
    )
    
    # Variables de sesión para paginación
    if 'historial_offset' not in st.session_state:
        st.session_state.historial_offset = 0
    LIMITE = 100
    
    # Filtro de estado
    estado_filtro = st.selectbox(
        "Filtrar por estado",
        ["Todos", "Finalizado", "Anulado"],
        key="filtro_estado_historial"
    )
    
    def cargar_ventas(offset, limite):
        if tipo_busqueda == "🔢 Número de turno":
            turno = st.session_state.get('turno_especifico', 0)
            if turno <= 0:
                return []
            return db.table("ventas")\
                .select("*")\
                .eq("id_cierre", turno)\
                .order("fecha", desc=True)\
                .range(offset, offset + limite - 1)\
                .execute().data or []
        else:
            desde = st.session_state.get('fecha_desde', None)
            hasta = st.session_state.get('fecha_hasta', None)
            if not desde or not hasta:
                return []
            desde_str = desde.strftime('%Y-%m-%d')
            hasta_str = hasta.strftime('%Y-%m-%d')
            return db.table("ventas")\
                .select("*")\
                .gte("fecha", desde_str)\
                .lte("fecha", hasta_str)\
                .order("fecha", desc=True)\
                .range(offset, offset + limite - 1)\
                .execute().data or []
    
    if tipo_busqueda == "🔢 Número de turno":
        turno_especifico = st.number_input("Ingresa el número de turno", min_value=1, step=1, key="turno_especifico")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("📊 Cargar ventas de este turno", use_container_width=True):
                st.session_state.historial_offset = 0
                st.session_state.historial_datos_cargados = True
                st.rerun()
        with col_b2:
            if st.button("🔄 Limpiar y volver", use_container_width=True):
                st.session_state.historial_datos_cargados = False
                st.session_state.historial_offset = 0
                st.rerun()
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            fecha_desde = st.date_input("📅 Desde", value=None, key="fecha_desde")
        with col_f2:
            fecha_hasta = st.date_input("📅 Hasta", value=None, key="fecha_hasta")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("📊 Cargar ventas en este rango", use_container_width=True):
                if fecha_desde and fecha_hasta:
                    st.session_state.historial_offset = 0
                    st.session_state.historial_datos_cargados = True
                    st.rerun()
                else:
                    st.warning("Selecciona ambas fechas.")
        with col_b2:
            if st.button("🔄 Limpiar y volver", use_container_width=True):
                st.session_state.historial_datos_cargados = False
                st.session_state.historial_offset = 0
                st.rerun()
    
    if st.session_state.get('historial_datos_cargados', False):
        with st.spinner("Cargando ventas..."):
            ventas = cargar_ventas(st.session_state.historial_offset, LIMITE)
        
        if not ventas:
            st.info("No hay ventas que coincidan con los criterios.")
            if st.button("🔍 Nueva búsqueda"):
                st.session_state.historial_datos_cargados = False
                st.rerun()
        else:
            df = pd.DataFrame(ventas)
            df['fecha_dt'] = pd.to_datetime(df['fecha'])
            df['hora'] = df['fecha_dt'].dt.strftime('%H:%M')
            df['fecha_display'] = df['fecha_dt'].dt.strftime('%d/%m/%Y %H:%M')
            
            def resumen_pagos(row):
                metodos = []
                if row.get('pago_efectivo', 0) > 0:
                    metodos.append(f"Ef. Bs {row['pago_efectivo']:,.0f}")
                if row.get('pago_movil', 0) > 0:
                    metodos.append(f"Pago Móvil {row['pago_movil']:,.0f}")
                if row.get('pago_punto', 0) > 0:
                    metodos.append(f"Punto {row['pago_punto']:,.0f}")
                if row.get('pago_divisas', 0) > 0:
                    metodos.append(f"Ef. USD ${row['pago_divisas']:.2f}")
                if row.get('pago_zelle', 0) > 0:
                    metodos.append(f"Zelle ${row['pago_zelle']:.2f}")
                if row.get('pago_otros', 0) > 0:
                    metodos.append(f"Otros USD ${row['pago_otros']:.2f}")
                return ", ".join(metodos) if metodos else "Efectivo (no registrado)"
            
            df['metodos_pago'] = df.apply(resumen_pagos, axis=1)
            
            if estado_filtro != "Todos":
                df = df[df['estado'] == estado_filtro]
            
            df_activas = df[df['estado'] != 'Anulado']
            total_usd = df_activas['total_usd'].sum() if not df_activas.empty else 0
            total_bs = df_activas['monto_cobrado_bs'].sum() if not df_activas.empty else 0
            cantidad_ventas = len(df_activas)
            promedio_usd = total_usd / cantidad_ventas if cantidad_ventas > 0 else 0
            
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 1rem; border-radius: 10px; color: white; text-align: center;'>
                        <span style='font-size: 0.9rem; opacity: 0.9;'>💰 TOTAL USD</span><br>
                        <span style='font-size: 1.8rem; font-weight: 700;'>${total_usd:,.2f}</span>
                    </div>
                """, unsafe_allow_html=True)
            with col_m2:
                st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                            padding: 1rem; border-radius: 10px; color: white; text-align: center;'>
                        <span style='font-size: 0.9rem; opacity: 0.9;'>💵 TOTAL BS</span><br>
                        <span style='font-size: 1.8rem; font-weight: 700;'>{total_bs:,.0f}</span>
                    </div>
                """, unsafe_allow_html=True)
            with col_m3:
                st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                            padding: 1rem; border-radius: 10px; color: white; text-align: center;'>
                        <span style='font-size: 0.9rem; opacity: 0.9;'>📊 VENTAS</span><br>
                        <span style='font-size: 1.8rem; font-weight: 700;'>{cantidad_ventas}</span>
                    </div>
                """, unsafe_allow_html=True)
            with col_m4:
                st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #5f2c82 0%, #49a09d 100%); 
                            padding: 1rem; border-radius: 10px; color: white; text-align: center;'>
                        <span style='font-size: 0.9rem; opacity: 0.9;'>📈 PROMEDIO</span><br>
                        <span style='font-size: 1.8rem; font-weight: 700;'>${promedio_usd:,.2f}</span>
                    </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Tabla con botones (similar a original pero adaptada)
            headers = st.columns([1, 1, 1.2, 3, 1, 1, 2, 1, 0.8, 0.8])
            headers[0].write("**Turno**")
            headers[1].write("**ID**")
            headers[2].write("**Hora**")
            headers[3].write("**Productos**")
            headers[4].write("**USD**")
            headers[5].write("**Bs**")
            headers[6].write("**Métodos de pago**")
            headers[7].write("**Estado**")
            headers[8].write("**Anular**")
            headers[9].write("**Factura**")
            st.markdown("<hr style='margin:0; margin-bottom:0.5rem;'>", unsafe_allow_html=True)
            
            for idx, venta in df.iterrows():
                es_anulado = venta['estado'] == 'Anulado'
                badge = "ANULADA" if es_anulado else "FINALIZADA"
                productos = venta['producto']
                if len(productos) > 50:
                    productos = productos[:50] + "..."
                
                cols = st.columns([1, 1, 1.2, 3, 1, 1, 2, 1, 0.8, 0.8])
                with cols[0]:
                    st.write(f"#{venta['id_cierre']}")
                with cols[1]:
                    st.write(f"#{venta['id']}")
                with cols[2]:
                    st.write(venta['hora'])
                with cols[3]:
                    st.write(productos)
                with cols[4]:
                    st.write(f"${venta['total_usd']:.2f}")
                with cols[5]:
                    st.write(f"{venta['monto_cobrado_bs']:.0f}")
                with cols[6]:
                    st.write(venta['metodos_pago'])
                with cols[7]:
                    st.write(badge)
                with cols[8]:
                    if not es_anulado:
                        if st.button("🚫", key=f"anular_{venta['id']}", help="Anular venta"):
                            try:
                                items = venta.get('items')
                                if isinstance(items, str):
                                    items = json.loads(items)
                                if items and isinstance(items, list):
                                    for item in items:
                                        if 'id' in item and 'cantidad' in item:
                                            stock_res = db.table("inventario").select("stock").eq("id", item['id']).execute()
                                            if stock_res.data:
                                                stock_actual = stock_res.data[0]['stock']
                                                db.table("inventario").update({
                                                    "stock": stock_actual + item['cantidad']
                                                }).eq("id", item['id']).execute()
                                db.table("ventas").update({"estado": "Anulado"}).eq("id", venta['id']).execute()
                                st.success(f"✅ Venta #{venta['id']} anulada")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al anular: {e}")
                with cols[9]:
                    with st.popover("👁️", help="Ver factura", use_container_width=False):
                        st.markdown("### 🧾 FACTURA DE VENTA")
                        st.markdown(f"""
                            <div style="background:white; padding:15px; border-radius:10px; border:1px solid #ddd;">
                                <p><b>Turno:</b> #{venta['id_cierre']}</p>
                                <p><b>Fecha:</b> {venta['fecha_display']}</p>
                                <p><b>Atendido por:</b> {venta.get('cliente', 'N/A')}</p>
                                <p><b>Cliente:</b> {venta.get('cliente', 'General')}</p>
                                <hr>
                                <table style="width:100%; border-collapse: collapse;">
                                    <thead>
                                        <tr style="border-bottom:1px solid #ccc;">
                                            <th style="text-align:left;">Cant</th>
                                            <th style="text-align:left;">Producto</th>
                                            <th style="text-align:right;">Precio</th>
                                            <th style="text-align:right;">Subtotal</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                        """, unsafe_allow_html=True)
                        items = venta.get('items')
                        if isinstance(items, str):
                            items = json.loads(items)
                        if items and isinstance(items, list):
                            for item in items:
                                unidad = item.get('unidad', '')
                                st.markdown(f"""
                                    <tr>
                                        <td style="padding:4px;">{item.get('cantidad', 0):.2f} {unidad}</td>
                                        <td style="padding:4px;">{item.get('nombre', '')}</td>
                                        <td style="padding:4px; text-align:right;">${item.get('precio', 0):.2f}</td>
                                        <td style="padding:4px; text-align:right;">${item.get('subtotal', 0):.2f}</td>
                                    </tr>
                                """, unsafe_allow_html=True)
                        st.markdown(f"""
                                    </tbody>
                                </table>
                                <hr>
                                <p><b>Total USD:</b> ${venta['total_usd']:.2f}</p>
                                <p><b>Total Bs:</b> {venta['monto_cobrado_bs']:.2f} Bs</p>
                                <hr>
                                <p><b>Pagos:</b></p>
                                <ul>
                        """, unsafe_allow_html=True)
                        if venta.get('pago_efectivo', 0) > 0:
                            st.markdown(f"<li>Efectivo Bs: {venta['pago_efectivo']:,.2f}</li>", unsafe_allow_html=True)
                        if venta.get('pago_movil', 0) > 0:
                            st.markdown(f"<li>Pago Móvil Bs: {venta['pago_movil']:,.2f}</li>", unsafe_allow_html=True)
                        if venta.get('pago_punto', 0) > 0:
                            st.markdown(f"<li>Punto Venta Bs: {venta['pago_punto']:,.2f}</li>", unsafe_allow_html=True)
                        if venta.get('pago_divisas', 0) > 0:
                            st.markdown(f"<li>Efectivo USD: ${venta['pago_divisas']:.2f}</li>", unsafe_allow_html=True)
                        if venta.get('pago_zelle', 0) > 0:
                            st.markdown(f"<li>Zelle USD: ${venta['pago_zelle']:.2f}</li>", unsafe_allow_html=True)
                        if venta.get('pago_otros', 0) > 0:
                            st.markdown(f"<li>Otros USD: ${venta['pago_otros']:.2f}</li>", unsafe_allow_html=True)
                        total_pagado_usd = sum([
                            venta.get('pago_divisas', 0),
                            venta.get('pago_zelle', 0),
                            venta.get('pago_otros', 0),
                            (venta.get('pago_efectivo', 0) + venta.get('pago_movil', 0) + venta.get('pago_punto', 0)) / venta.get('tasa_cambio', 60)
                        ])
                        vuelto = total_pagado_usd - venta['total_usd']
                        st.markdown(f"""
                                </ul>
                                <hr>
                                <p><b>Vuelto:</b> ${vuelto:.2f} / {(vuelto * venta.get('tasa_cambio', 60)):.2f} Bs</p>
                                <p style="text-align:center;">¡Gracias por su compra!</p>
                            </div>
                        """, unsafe_allow_html=True)
                
                if idx < len(df) - 1:
                    st.markdown("<hr style='margin:0.2rem 0; opacity:0.3;'>", unsafe_allow_html=True)
            
            if len(ventas) == LIMITE:
                col_pag1, col_pag2 = st.columns(2)
                with col_pag1:
                    if st.button("⬅️ Anteriores", use_container_width=True):
                        if st.session_state.historial_offset >= LIMITE:
                            st.session_state.historial_offset -= LIMITE
                            st.rerun()
                with col_pag2:
                    if st.button("Siguientes ➡️", use_container_width=True):
                        st.session_state.historial_offset += LIMITE
                        st.rerun()
            elif st.session_state.historial_offset > 0:
                if st.button("⬅️ Anteriores", use_container_width=True):
                    st.session_state.historial_offset -= LIMITE
                    st.rerun()
            
            if st.button("🔍 Nueva búsqueda", use_container_width=True):
                st.session_state.historial_datos_cargados = False
                st.session_state.historial_offset = 0
                st.rerun()

# ============================================
# MÓDULO 5: CIERRE DE CAJA (SIN CAMBIOS)
# ============================================
elif opcion == "📊 CIERRE DE CAJA":
    st.markdown("<h1 class='main-header'>📊 Cierre de Caja</h1>", unsafe_allow_html=True)

    tab_c1, tab_c2 = st.tabs(["🔓 Cierre del turno actual", "📋 Historial de cierres"])

    with tab_c1:
        if not st.session_state.id_turno:
            st.warning("🔓 No hay turno activo. Complete para abrir caja:")
            with st.form("form_apertura"):
                st.subheader("📝 Datos de apertura")
                col1, col2 = st.columns(2)
                with col1:
                    tasa_apertura = st.number_input("💱 Tasa BCV (Bs/$)", min_value=1.0, value=60.0, step=0.5, format="%.2f")
                    fondo_bs = st.number_input("💰 Fondo inicial Bs", min_value=0.0, value=0.0, step=10.0, format="%.2f")
                with col2:
                    fondo_usd = st.number_input("💰 Fondo inicial USD", min_value=0.0, value=0.0, step=5.0, format="%.2f")
                    st.info(f"👤 Abre: {st.session_state.usuario_actual['nombre'] if st.session_state.usuario_actual else 'Anónimo'}")
                if st.form_submit_button("🚀 ABRIR CAJA", type="primary", use_container_width=True):
                    try:
                        data = {
                            "tasa_apertura": tasa_apertura,
                            "fondo_bs": fondo_bs,
                            "fondo_usd": fondo_usd,
                            "monto_apertura": fondo_usd,
                            "estado": "abierto",
                            "fecha_apertura": datetime.now().isoformat(),
                            "usuario_apertura": st.session_state.usuario_actual['nombre'] if st.session_state.usuario_actual else 'Anónimo'
                        }
                        res = db.table("cierres").insert(data).execute()
                        if res.data:
                            st.session_state.id_turno = res.data[0]['id']
                            st.session_state.tasa_dia = tasa_apertura
                            st.session_state.fondo_bs = fondo_bs
                            st.session_state.fondo_usd = fondo_usd
                            st.success(f"✅ Turno #{res.data[0]['id']} abierto")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            st.stop()

        id_turno = st.session_state.id_turno
        tasa = st.session_state.tasa_dia
        fondo_bs_ini = st.session_state.get('fondo_bs', 0)
        fondo_usd_ini = st.session_state.get('fondo_usd', 0)

        turno_info = db.table("cierres").select("*").eq("id", id_turno).execute()
        usuario_apertura = turno_info.data[0].get('usuario_apertura', 'N/A') if turno_info.data else 'N/A'

        col_info1, col_info2, col_info3 = st.columns(3)
        col_info1.success(f"📍 Turno activo: #{id_turno}")
        col_info2.info(f"👤 Abrió: {usuario_apertura}")
        col_info3.info(f"💱 Tasa: {tasa:.2f} Bs/$")

        ventas = db.table("ventas").select("*").eq("id_cierre", id_turno).eq("estado", "Finalizado").execute().data or []
        gastos = db.table("gastos").select("*").eq("id_cierre", id_turno).execute().data or []

        total_ventas_usd = sum(float(v.get('total_usd', 0)) for v in ventas)
        total_costos = sum(float(v.get('costo_venta', 0)) for v in ventas)
        total_gastos = sum(float(g.get('monto_usd', 0)) for g in gastos)

        total_pagos_usd = sum(
            float(v.get('pago_divisas', 0)) +
            float(v.get('pago_zelle', 0)) +
            float(v.get('pago_otros', 0)) for v in ventas
        )
        total_pagos_bs = sum(
            float(v.get('pago_efectivo', 0)) +
            float(v.get('pago_movil', 0)) +
            float(v.get('pago_punto', 0)) for v in ventas
        )

        ganancia_bruta = total_ventas_usd - total_costos
        ganancia_neta = ganancia_bruta - total_gastos
        reposicion = total_costos

        total_efectivo_usd = sum(float(v.get('pago_divisas', 0)) for v in ventas)
        total_zelle = sum(float(v.get('pago_zelle', 0)) for v in ventas)
        total_otros_usd = sum(float(v.get('pago_otros', 0)) for v in ventas)
        total_efectivo_bs = sum(float(v.get('pago_efectivo', 0)) for v in ventas)
        total_movil = sum(float(v.get('pago_movil', 0)) for v in ventas)
        total_punto = sum(float(v.get('pago_punto', 0)) for v in ventas)

        st.subheader("📈 Resumen del turno")
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        col_r1.metric("💰 Ventas totales", f"${total_ventas_usd:,.2f}")
        col_r2.metric("📦 Reposición", f"${reposicion:,.2f}")
        col_r3.metric("💸 Gastos", f"${total_gastos:,.2f}")
        col_r4.metric("📊 Ganancia neta", f"${ganancia_neta:,.2f}")

        with st.expander("💰 Ver desglose por método de pago", expanded=True):
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.markdown("**💵 Pagos en USD**")
                st.metric("Efectivo USD", f"${total_efectivo_usd:,.2f}")
                st.metric("Zelle USD", f"${total_zelle:,.2f}")
                st.metric("Otros USD", f"${total_otros_usd:,.2f}")
            with col_d2:
                st.markdown("**💵 Pagos en Bs**")
                st.metric("Efectivo Bs", f"{total_efectivo_bs:,.2f} Bs")
                st.metric("Pago Móvil Bs", f"{total_movil:,.2f} Bs")
                st.metric("Punto Venta Bs", f"{total_punto:,.2f} Bs")

        st.divider()
        st.subheader("🧮 Ingreso de montos físicos")

        with st.form("form_ingreso_montos"):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                st.markdown("**💰 Bolívares (Bs)**")
                efec_bs = st.number_input("Efectivo Bs", min_value=0.0, value=0.0, step=100.0, format="%.2f", key="bs_efectivo")
                pmovil_bs = st.number_input("Pago Móvil Bs", min_value=0.0, value=0.0, step=100.0, format="%.2f", key="bs_pmovil")
                punto_bs = st.number_input("Punto Venta Bs", min_value=0.0, value=0.0, step=100.0, format="%.2f", key="bs_punto")
            with col_f2:
                st.markdown("**💰 Dólares (USD)**")
                efec_usd = st.number_input("Efectivo USD", min_value=0.0, value=0.0, step=5.0, format="%.2f", key="usd_efectivo")
                zelle_usd = st.number_input("Zelle USD", min_value=0.0, value=0.0, step=5.0, format="%.2f", key="usd_zelle")
                otros_usd = st.number_input("Otros USD", min_value=0.0, value=0.0, step=5.0, format="%.2f", key="usd_otros")

            observaciones = st.text_area("📝 Observaciones (opcional)", placeholder="Ej: Todo en orden...")
            st.markdown("---")
            previsualizar = st.form_submit_button("👁️ PREVISUALIZAR CIERRE", use_container_width=True)

            if previsualizar:
                st.session_state.montos_fisicos = {
                    'efec_bs': efec_bs, 'pmovil_bs': pmovil_bs, 'punto_bs': punto_bs,
                    'efec_usd': efec_usd, 'zelle_usd': zelle_usd, 'otros_usd': otros_usd,
                    'observaciones': observaciones
                }
                st.session_state.montos_calculados = True
                st.rerun()

        if st.session_state.get('montos_calculados', False):
            montos = st.session_state.montos_fisicos
            total_bs_fisico = montos['efec_bs'] + montos['pmovil_bs'] + montos['punto_bs']
            total_usd_fisico = montos['efec_usd'] + montos['zelle_usd'] + montos['otros_usd']

            esperado_bs = fondo_bs_ini + total_pagos_bs - (total_gastos * tasa)
            esperado_usd = fondo_usd_ini + total_pagos_usd - total_gastos

            diff_bs = total_bs_fisico - esperado_bs
            diff_usd = total_usd_fisico - esperado_usd
            diff_total = diff_usd + (diff_bs / tasa if tasa > 0 else 0)

            st.subheader("📊 Comparación Caja vs Sistema")
            col_x1, col_x2 = st.columns(2)
            with col_x1:
                st.markdown("**🇻🇪 Bolívares**")
                st.metric("Esperado", f"{esperado_bs:,.2f} Bs")
                st.metric("Físico", f"{total_bs_fisico:,.2f} Bs")
                st.metric("Diferencia", f"{diff_bs:+,.2f} Bs")
            with col_x2:
                st.markdown("**🇺🇸 Dólares**")
                st.metric("Esperado", f"${esperado_usd:,.2f}")
                st.metric("Físico", f"${total_usd_fisico:,.2f}")
                st.metric("Diferencia", f"${diff_usd:+,.2f}")

            st.metric("DIFERENCIA TOTAL", f"${diff_total:+,.2f}")

            if abs(diff_total) < 0.1:
                st.success("✅ **¡CAJA CUADRADA!** Todo coincide.")
            elif diff_total > 0:
                st.warning(f"🟡 **SOBRANTE:** +${diff_total:,.2f} USD a favor de la caja")
            else:
                st.error(f"🔴 **FALTANTE:** -${abs(diff_total):,.2f} USD en caja")

            st.warning("⚠️ Una vez cerrado, no podrá modificar este turno.")
            confirmar = st.checkbox("✅ Confirmo que los datos del conteo son correctos")

            if st.button("🔒 CONFIRMAR Y CERRAR TURNO", type="primary", use_container_width=True, disabled=not confirmar):
                try:
                    datos_cierre = {
                        "fecha_cierre": datetime.now().isoformat(),
                        "total_ventas": total_ventas_usd,
                        "total_costos": total_costos,
                        "total_ganancias": ganancia_neta,
                        "diferencia": diff_total,
                        "tasa_cierre": tasa,
                        "estado": "cerrado",
                        "usuario_cierre": st.session_state.usuario_actual['nombre'] if st.session_state.usuario_actual else 'Anónimo',
                        "observaciones": montos['observaciones'],
                        "fondo_bs_final": total_bs_fisico,
                        "fondo_usd_final": total_usd_fisico,
                        "efectivo_bs_fisico": montos['efec_bs'],
                        "pmovil_fisico": montos['pmovil_bs'],
                        "punto_fisico": montos['punto_bs'],
                        "efectivo_usd_fisico": montos['efec_usd'],
                        "zelle_fisico": montos['zelle_usd'],
                        "otros_fisico": montos['otros_usd']
                    }

                    db.table("cierres").update(datos_cierre).eq("id", id_turno).execute()
                    db.table("gastos").update({"estado": "cerrado"}).eq("id_cierre", id_turno).execute()

                    st.session_state.id_turno = None
                    st.session_state.montos_calculados = False
                    st.balloons()
                    st.success("✅ Turno cerrado exitosamente!")

                    st.markdown("---")
                    st.subheader("📄 REPORTE DE CIERRE")
                    col_y1, col_y2 = st.columns(2)
                    with col_y1:
                        st.markdown(f"**Turno:** #{id_turno}")
                        st.markdown(f"**Abrió:** {usuario_apertura}")
                        st.markdown(f"**Cerró:** {st.session_state.usuario_actual['nombre'] if st.session_state.usuario_actual else 'Anónimo'}")
                        st.markdown(f"**Fecha:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                    with col_y2:
                        st.markdown(f"**Ventas:** ${total_ventas_usd:,.2f}")
                        st.markdown(f"**Reposición:** ${reposicion:,.2f}")
                        st.markdown(f"**Gastos:** ${total_gastos:,.2f}")
                        st.markdown(f"**Ganancia neta:** ${ganancia_neta:,.2f}")
                    st.markdown(f"**Diferencia total:** ${diff_total:+,.2f}")

                    if st.button("🔄 Volver al inicio"):
                        st.rerun()

                except Exception as e:
                    st.error(f"Error al cerrar: {e}")

            if st.button("✏️ CORREGIR MONTOS", use_container_width=True):
                st.session_state.montos_calculados = False
                st.rerun()

    with tab_c2:
        st.subheader("📋 Historial de turnos cerrados")
        try:
            cierres = db.table("cierres").select("*").eq("estado", "cerrado").order("fecha_cierre", desc=True).execute()
            df_cierres = pd.DataFrame(cierres.data) if cierres.data else pd.DataFrame()

            if not df_cierres.empty:
                df_cierres['fecha_apertura'] = pd.to_datetime(df_cierres['fecha_apertura']).dt.strftime('%d/%m/%Y %H:%M')
                df_cierres['fecha_cierre'] = pd.to_datetime(df_cierres['fecha_cierre']).dt.strftime('%d/%m/%Y %H:%M')

                st.dataframe(
                    df_cierres[['id', 'fecha_apertura', 'fecha_cierre', 'usuario_apertura', 'usuario_cierre',
                                'total_ventas', 'total_ganancias', 'diferencia']],
                    column_config={
                        "id": "Turno",
                        "fecha_apertura": "Apertura",
                        "fecha_cierre": "Cierre",
                        "usuario_apertura": "Abrió",
                        "usuario_cierre": "Cerró",
                        "total_ventas": st.column_config.NumberColumn("Ventas USD", format="$%.2f"),
                        "total_ganancias": st.column_config.NumberColumn("Ganancias USD", format="$%.2f"),
                        "diferencia": st.column_config.NumberColumn("Diferencia USD", format="$%.2f")
                    },
                    use_container_width=True,
                    hide_index=True
                )

                if st.button("📥 Exportar historial a Excel", use_container_width=True):
                    export_df = df_cierres[['id', 'fecha_apertura', 'fecha_cierre', 'usuario_apertura', 'usuario_cierre',
                                            'total_ventas', 'total_ganancias', 'diferencia']].copy()
                    export_df.columns = ['Turno', 'Apertura', 'Cierre', 'Abrió', 'Cerró',
                                         'Ventas USD', 'Ganancias USD', 'Diferencia USD']
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        export_df.to_excel(writer, index=False, sheet_name='Cierres')
                    excel_data = output.getvalue()
                    b64 = base64.b64encode(excel_data).decode()
                    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="historial_cierres.xlsx">📥 Descargar Excel</a>'
                    st.markdown(href, unsafe_allow_html=True)
            else:
                st.info("No hay turnos cerrados registrados.")
        except Exception as e:
            st.error(f"Error cargando historial de cierres: {e}")

# ============================================
# MÓDULO 6: ADMINISTRACIÓN (solo admin)
# ============================================
elif opcion == "👥 ADMINISTRACIÓN":
    st.markdown("<h1 class='main-header'>👥 Administración de Usuarios</h1>", unsafe_allow_html=True)
    
    if not es_admin():
        st.error("No tienes permisos para acceder a esta sección.")
        st.stop()
    
    usuarios = cargar_usuarios()
    
    with st.expander("➕ Agregar nueva empleada", expanded=False):
        with st.form("nuevo_usuario"):
            col1, col2 = st.columns(2)
            with col1:
                nuevo_nombre = st.text_input("Nombre *")
                nueva_clave = st.text_input("Clave *", type="password")
            with col2:
                nuevo_rol = st.selectbox("Rol", ["empleado", "admin"])
                nuevo_activo = st.checkbox("Activo", value=True)
            if st.form_submit_button("Crear usuario"):
                if nuevo_nombre and nueva_clave:
                    existe = db.table("usuarios").select("*").eq("nombre", nuevo_nombre).execute()
                    if existe.data:
                        st.error("Ya existe un usuario con ese nombre.")
                    else:
                        db.table("usuarios").insert({
                            "nombre": nuevo_nombre,
                            "clave": nueva_clave,
                            "rol": nuevo_rol,
                            "activo": nuevo_activo
                        }).execute()
                        st.success(f"Usuario {nuevo_nombre} creado.")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.warning("Nombre y clave son obligatorios.")
    
    st.subheader("📋 Usuarios del sistema")
    if usuarios:
        for user in usuarios:
            with st.container(border=True):
                col1, col2, col3, col4, col5, col6 = st.columns([2, 1.5, 1, 1, 1, 1])
                col1.write(f"**{user['nombre']}**")
                col2.write(f"Rol: {user['rol']}")
                col3.write("✅ Activo" if user['activo'] else "❌ Inactivo")
                with col4:
                    if st.button("✏️ Editar", key=f"edit_{user['id']}"):
                        st.session_state.edit_usuario = user
                        st.rerun()
                with col5:
                    if user['rol'] != 'admin':
                        if st.button("🗑️ Eliminar", key=f"del_{user['id']}"):
                            db.table("usuarios").delete().eq("id", user['id']).execute()
                            st.success(f"Usuario {user['nombre']} eliminado.")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.markdown("_Protegido_")
                with col6:
                    if user['id'] == st.session_state.usuario_actual['id'] and user['rol'] == 'admin':
                        st.markdown("*(tú)*")
        st.markdown("---")
        
        if 'edit_usuario' in st.session_state:
            user = st.session_state.edit_usuario
            st.subheader(f"Editando: {user['nombre']}")
            with st.form("edit_usuario_form"):
                nuevo_nombre = st.text_input("Nombre", value=user['nombre'])
                nueva_clave = st.text_input("Nueva clave (dejar vacío para no cambiar)", type="password")
                nuevo_rol = st.selectbox("Rol", ["empleado", "admin"], index=0 if user['rol']=='empleado' else 1)
                nuevo_activo = st.checkbox("Activo", value=user['activo'])
                if st.form_submit_button("Guardar cambios"):
                    update_data = {"nombre": nuevo_nombre, "rol": nuevo_rol, "activo": nuevo_activo}
                    if nueva_clave:
                        update_data["clave"] = nueva_clave
                    db.table("usuarios").update(update_data).eq("id", user['id']).execute()
                    if user['id'] == st.session_state.usuario_actual['id']:
                        st.session_state.usuario_actual.update(update_data)
                    st.success("Usuario actualizado")
                    del st.session_state.edit_usuario
                    time.sleep(1)
                    st.rerun()
            if st.button("Cancelar"):
                del st.session_state.edit_usuario
                st.rerun()
        
        st.markdown("---")
        st.subheader("🔑 Cambiar mi clave")
        with st.form("cambiar_clave_admin"):
            nueva_clave_admin = st.text_input("Nueva clave", type="password")
            confirmar_clave = st.text_input("Confirmar nueva clave", type="password")
            if st.form_submit_button("Actualizar mi clave"):
                if nueva_clave_admin and nueva_clave_admin == confirmar_clave:
                    db.table("usuarios").update({"clave": nueva_clave_admin}).eq("id", st.session_state.usuario_actual['id']).execute()
                    st.session_state.usuario_actual['clave'] = nueva_clave_admin
                    st.success("Clave actualizada. Vuelve a iniciar sesión para aplicar cambios.")
                    time.sleep(2)
                    logout()
                else:
                    st.error("Las claves no coinciden o están vacías.")
    else:
        st.info("No hay usuarios registrados.")
