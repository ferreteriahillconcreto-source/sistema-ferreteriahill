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
URL = "https://dhkunafosiyvofunehsd.supabase.co"
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
# MÓDULO 1: INVENTARIO (VERSIÓN RÁPIDA, LIMPIA Y PROFESIONAL)
# ============================================
if opcion == "📦 INVENTARIO":
    st.markdown("<h1 class='main-header'>📦 Gestión de Inventario - Ferreteria Chill</h1>", unsafe_allow_html=True)
    
    CATEGORIAS_FERRETERIA = [
        "Herramientas", "Pinturas", "Electricidad", "Plomería",
        "Ferretería general", "Construcción", "Jardinería", "Seguridad", "Otros"
    ]
    
    UNIDADES = ["unidad", "metro", "kilo", "litro", "galón", "pieza"]
    
    # Cargar datos (con range para obtener todos los registros)
    try:
        response = db.table("inventario").select("*").order("nombre").range(0, 10000).execute()
        df = pd.DataFrame(response.data) if response.data else pd.DataFrame()
        
        if not df.empty:
            if 'categoria' not in df.columns:
                df['categoria'] = 'Otros'
            if 'codigo_barras' not in df.columns:
                df['codigo_barras'] = ''
            for col in ['unidad_medida', 'marca', 'proveedor']:
                if col not in df.columns:
                    df[col] = ''
            # Asegurar tipos numéricos
            for col in ['stock', 'costo', 'precio_detal', 'precio_mayor', 'min_mayor']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        st.stop()
    
    # Función para formatear números (entero sin decimales, decimal con 2)
    def fmt_num(x):
        if pd.isna(x):
            return ""
        if isinstance(x, (int, float)):
            if x == int(x):
                return str(int(x))
            else:
                return f"{x:.2f}"
        return str(x)
    
    # ============================================
    # PESTAÑA PRINCIPAL: VER INVENTARIO
    # ============================================
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Ver Inventario", "➕ Agregar Producto", "📊 Estadísticas", "📥 Respaldos", "📤 Importar Masivo"])
    
    with tab1:
        st.subheader("🔍 Búsqueda y filtros")
        col_f1, col_f2, col_f3, col_f4 = st.columns([3, 1, 1, 1])
        with col_f1:
            busqueda_global = st.text_input("Buscar (nombre, código, marca, proveedor)", placeholder="Ej: Martillo, 123456, Stanley...")
        with col_f2:
            categoria_filtro = st.selectbox("Categoría", ["Todas"] + CATEGORIAS_FERRETERIA)
        with col_f3:
            ver_bajo_stock = st.checkbox("⚠️ Solo stock bajo (<5)")
        with col_f4:
            if st.button("🧹 Limpiar filtros", use_container_width=True):
                st.query_params.clear()
                st.rerun()
        
        # Aplicar filtros
        df_filtrado = df.copy() if not df.empty else df
        if not df_filtrado.empty:
            if busqueda_global:
                busq = busqueda_global.strip().lower()
                mask = (
                    df_filtrado['nombre'].str.lower().str.contains(busq, na=False) |
                    df_filtrado['codigo_barras'].astype(str).str.lower().str.contains(busq, na=False) |
                    df_filtrado['marca'].str.lower().str.contains(busq, na=False) |
                    df_filtrado['proveedor'].str.lower().str.contains(busq, na=False)
                )
                df_filtrado = df_filtrado[mask]
            if categoria_filtro != "Todas":
                df_filtrado = df_filtrado[df_filtrado['categoria'] == categoria_filtro]
            if ver_bajo_stock:
                df_filtrado = df_filtrado[df_filtrado['stock'] < 5]
        
        if df_filtrado.empty:
            st.info("No hay productos que coincidan con los filtros.")
        else:
            # Paginación
            total_filas = len(df_filtrado)
            page_size = st.selectbox("Productos por página", [25, 50, 100, 200], index=1, key="page_size_inv")
            total_paginas = (total_filas + page_size - 1) // page_size
            
            if 'pagina_actual' not in st.session_state:
                st.session_state.pagina_actual = 1
            if st.session_state.pagina_actual > total_paginas:
                st.session_state.pagina_actual = total_paginas
            
            col_pag1, col_pag2, col_pag3 = st.columns([1, 2, 1])
            with col_pag1:
                if st.button("◀ Anterior", disabled=(st.session_state.pagina_actual == 1)):
                    st.session_state.pagina_actual -= 1
                    st.rerun()
            with col_pag2:
                st.markdown(f"<div style='text-align: center;'>Página {st.session_state.pagina_actual} de {total_paginas} (Total: {total_filas} productos)</div>", unsafe_allow_html=True)
                ir_a = st.number_input("Ir a página", min_value=1, max_value=total_paginas, value=st.session_state.pagina_actual, step=1, label_visibility="collapsed")
                if ir_a != st.session_state.pagina_actual:
                    st.session_state.pagina_actual = ir_a
                    st.rerun()
            with col_pag3:
                if st.button("Siguiente ▶", disabled=(st.session_state.pagina_actual == total_paginas)):
                    st.session_state.pagina_actual += 1
                    st.rerun()
            
            inicio = (st.session_state.pagina_actual - 1) * page_size
            fin = inicio + page_size
            df_pagina = df_filtrado.iloc[inicio:fin].copy()
            
            # Preparar DataFrame para mostrar (con formato de números)
            df_mostrar = df_pagina[['nombre', 'categoria', 'unidad_medida', 'stock', 'precio_detal', 'precio_mayor']].copy()
            df_mostrar.columns = ['Producto', 'Categoría', 'Unidad', 'Stock', 'Precio Detal $', 'Precio Mayor $']
            for col in ['Stock', 'Precio Detal $', 'Precio Mayor $']:
                df_mostrar[col] = df_mostrar[col].apply(fmt_num)
            
            # Mostrar tabla
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
            
            # Exportar resultados filtrados
            if st.button("📤 Exportar resultados a Excel", use_container_width=True):
                export_df = df_filtrado[['nombre', 'categoria', 'unidad_medida', 'marca', 'proveedor', 'stock', 'costo', 'precio_detal', 'precio_mayor', 'min_mayor', 'codigo_barras']].copy()
                export_df.columns = ['Producto', 'Categoría', 'Unidad', 'Marca', 'Proveedor', 'Stock', 'Costo $', 'Precio Detal $', 'Precio Mayor $', 'Min. Mayor', 'Código Barras']
                href = exportar_excel(export_df, f"inventario_filtrado_{datetime.now().strftime('%Y%m%d_%H%M')}")
                st.markdown(href, unsafe_allow_html=True)
            
            st.divider()
            
            # ============================================
            # EDICIÓN DE PRODUCTO (selectbox + formulario)
            # ============================================
            st.subheader("✏️ Editar producto")
            productos_nombres = df_filtrado['nombre'].tolist()
            producto_editar = st.selectbox("Seleccionar producto", [""] + productos_nombres, key="editar_select")
            if producto_editar:
                prod = df[df['nombre'] == producto_editar].iloc[0]
                with st.form("form_editar"):
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        nuevo_nombre = st.text_input("Nombre", value=prod['nombre'])
                        nueva_categoria = st.selectbox("Categoría", CATEGORIAS_FERRETERIA, 
                                                      index=CATEGORIAS_FERRETERIA.index(prod.get('categoria', 'Otros')) if prod.get('categoria', 'Otros') in CATEGORIAS_FERRETERIA else 8)
                        nueva_unidad = st.selectbox("Unidad de medida", UNIDADES, 
                                                    index=UNIDADES.index(prod.get('unidad_medida','unidad')) if prod.get('unidad_medida') in UNIDADES else 0)
                        nueva_marca = st.text_input("Marca", value=prod.get('marca', ''))
                        nuevo_proveedor = st.text_input("Proveedor", value=prod.get('proveedor', ''))
                        nuevo_stock = st.number_input("Stock", value=float(prod['stock']), min_value=-9999.0, step=0.1, format="%.2f")
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
                                "min_mayor": nuevo_min,
                                "codigo_barras": nuevo_codigo
                            }
                            db.table("inventario").update(datos_actualizados).eq("id", prod['id']).execute()
                            st.success("✅ Producto actualizado")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
            
            st.divider()
            
            # ============================================
            # ELIMINAR PRODUCTO
            # ============================================
            st.subheader("🗑️ Eliminar producto")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                producto_eliminar = st.selectbox("Seleccionar producto", [""] + productos_nombres, key="eliminar_select")
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
    
    # ==================================================
    # PESTAÑA 2: AGREGAR PRODUCTO
    # ==================================================
    with tab2:
        with st.form("nuevo_producto", clear_on_submit=True):
            st.markdown("### 📝 Datos del nuevo producto (Ferretería)")
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                nombre = st.text_input("Nombre del producto *").upper()
                categoria = st.selectbox("Categoría", CATEGORIAS_FERRETERIA)
                unidad_medida = st.selectbox("Unidad de medida *", UNIDADES)
                marca = st.text_input("Marca (opcional)")
                proveedor = st.text_input("Proveedor (opcional)")
                stock = st.number_input("Stock inicial *", min_value=-9999.0, step=0.1, format="%.2f")
                costo = st.number_input("Costo $ *", min_value=0.0, step=0.01, format="%.2f")
                codigo_barras = st.text_input("Código de barras (opcional)")
            with col_a2:
                precio_detal = st.number_input("Precio Detal $ *", min_value=0.0, step=0.01, format="%.2f")
                precio_mayor = st.number_input("Precio Mayor $ *", min_value=0.0, step=0.01, format="%.2f")
                min_mayor = st.number_input("Mínimo para Mayor (unidades) *", min_value=1, value=6, step=1)
            if st.form_submit_button("📦 Registrar Producto", use_container_width=True):
                if not nombre:
                    st.error("El nombre es obligatorio")
                elif costo < 0 or precio_detal <= 0:
                    st.error("Costo y precio detal deben ser positivos")
                else:
                    try:
                        existe = db.table("inventario").select("*").eq("nombre", nombre).execute()
                        if existe.data:
                            st.error(f"Ya existe un producto con el nombre '{nombre}'")
                        else:
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
                                "min_mayor": min_mayor,
                                "codigo_barras": codigo_barras if codigo_barras else ''
                            }
                            db.table("inventario").insert(datos_nuevos).execute()
                            st.success(f"✅ Producto '{nombre}' registrado exitosamente")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar: {e}")
    
    # ==================================================
    # PESTAÑA 3: ESTADÍSTICAS
    # ==================================================
    with tab3:
        if not df.empty:
            df_stats = df.copy()
            df_stats['stock'] = pd.to_numeric(df_stats['stock'], errors='coerce').fillna(0)
            valor_inv = (df_stats['stock'] * df_stats['costo']).sum()
            valor_venta = (df_stats['stock'] * df_stats['precio_detal']).sum()
            bajo_stock = len(df_stats[df_stats['stock'] < 5])
            total_productos = len(df_stats)
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Total productos", total_productos)
            col_m2.metric("Valor inventario (costo)", f"${valor_inv:,.2f}")
            col_m3.metric("Valor venta potencial", f"${valor_venta:,.2f}")
            col_m4.metric("Stock bajo", bajo_stock, delta_color="inverse")
            ganancia_potencial = valor_venta - valor_inv
            st.metric("💰 Ganancia potencial total", f"${ganancia_potencial:,.2f}",
                     delta=f"{(ganancia_potencial/valor_inv*100):.1f}%" if valor_inv else "")
            
            st.subheader("📊 Productos por categoría")
            if 'categoria' in df_stats.columns:
                cat_stats = df_stats.groupby('categoria').agg({
                    'nombre': 'count',
                    'stock': 'sum',
                    'costo': lambda x: (x * df_stats.loc[x.index, 'stock']).sum()
                }).round(2)
                cat_stats.columns = ['Cantidad', 'Stock total', 'Valor total $']
                st.dataframe(cat_stats, use_container_width=True)
            
            st.subheader("💰 Top 10 productos por valor en inventario")
            df_temp = df_stats.copy()
            df_temp['valor_total'] = df_temp['stock'] * df_temp['costo']
            df_top = df_temp.nlargest(10, 'valor_total')[['nombre', 'categoria', 'unidad_medida', 'marca', 'stock', 'costo', 'valor_total']]
            df_top.columns = ['Producto', 'Categoría', 'Unidad', 'Marca', 'Stock', 'Costo unitario', 'Valor total']
            st.dataframe(df_top, use_container_width=True, hide_index=True)
            
            st.subheader("⚠️ Productos con stock bajo (<5) o negativo")
            df_bajo = df_stats[df_stats['stock'] < 5][['nombre', 'categoria', 'unidad_medida', 'marca', 'stock', 'costo']]
            if not df_bajo.empty:
                df_bajo.columns = ['Producto', 'Categoría', 'Unidad', 'Marca', 'Stock', 'Costo unitario']
                st.dataframe(df_bajo, use_container_width=True, hide_index=True)
            else:
                st.success("No hay productos con stock bajo ni negativo")
        else:
            st.info("No hay datos para mostrar estadísticas")
    
    # ==================================================
    # PESTAÑA 4: RESPALDOS
    # ==================================================
    with tab4:
        st.subheader("📥 Respaldo de inventario")
        st.markdown("Exporta el inventario completo o lista de precios en Excel.")
        if not df.empty:
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                if st.button("📥 Exportar inventario completo", use_container_width=True):
                    export_df = df[['nombre', 'categoria', 'unidad_medida', 'marca', 'proveedor', 'stock', 'costo', 'precio_detal', 'precio_mayor', 'min_mayor', 'codigo_barras']].copy()
                    export_df.columns = ['Producto', 'Categoría', 'Unidad', 'Marca', 'Proveedor', 'Stock', 'Costo $', 'Precio Detal $', 'Precio Mayor $', 'Min. Mayor', 'Código Barras']
                    href = exportar_excel(export_df, f"inventario_completo_{datetime.now().strftime('%Y%m%d_%H%M')}")
                    st.markdown(href, unsafe_allow_html=True)
            with col_r2:
                if st.button("📥 Exportar lista de precios", use_container_width=True):
                    precio_df = df[['nombre', 'categoria', 'unidad_medida', 'precio_detal', 'precio_mayor', 'min_mayor']].copy()
                    precio_df.columns = ['Producto', 'Categoría', 'Unidad', 'Precio Detal $', 'Precio Mayor $', 'Mín. Mayor']
                    href = exportar_excel(precio_df, f"lista_precios_{datetime.now().strftime('%Y%m%d')}")
                    st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No hay productos para respaldar")
    
    # ==================================================
    # PESTAÑA 5: IMPORTACIÓN MASIVA (FLEXIBLE)
    # ==================================================
    with tab5:
        st.subheader("📤 Importación masiva desde Cristal Plus (flexible)")
        st.markdown("""
            **El sistema detectará automáticamente las columnas** aunque tengan tildes, mayúsculas o espacios.
            Las columnas necesarias son: `Código`, `Nombre`, `Precio Máximo` (y opcionales: `Departamento`, `Unidad`, `Costo Calculado`, `Existencia`).
            Puedes subir tu archivo directamente sin modificar nada.
        """)
        
        def normalizar_columna(nombre):
            import unicodedata
            nombre = unicodedata.normalize('NFKD', nombre).encode('ASCII', 'ignore').decode('utf-8')
            return nombre.strip().lower().replace(' ', '_')
        
        mapeo_columnas = {
            'codigo': 'codigo_barras',
            'nombre': 'nombre',
            'departamento': 'categoria',
            'unidad': 'unidad_medida',
            'costo_calculado': 'costo',
            'existencia': 'stock',
            'precio_maximo': 'precio_detal'
        }
        
        col_imp1, col_imp2 = st.columns(2)
        with col_imp1:
            if st.button("📥 Descargar plantilla (formato recomendado)", use_container_width=True):
                plantilla = pd.DataFrame({
                    'Código': ['123456', '789012'],
                    'Nombre': ['MARTILLO', 'PINTURA BLANCA'],
                    'Departamento': ['Herramientas', 'Pinturas'],
                    'Unidad': ['unidad', 'litro'],
                    'Costo Calculado': [5.0, 8.0],
                    'Existencia': [10, 5.5],
                    'Precio Máximo': [15.0, 20.0]
                })
                href = exportar_excel(plantilla, "plantilla_importacion_cristal")
                st.markdown(href, unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader("Selecciona el archivo Excel de Cristal Plus (.xlsx)", type=['xlsx'])
        if uploaded_file is not None:
            try:
                df_import_raw = pd.read_excel(uploaded_file)
                with st.expander("🔍 Ver columnas detectadas en el archivo", expanded=False):
                    st.write("Columnas originales:", list(df_import_raw.columns))
                
                columnas_norm = {col: normalizar_columna(col) for col in df_import_raw.columns}
                rename_dict = {}
                for col, norm in columnas_norm.items():
                    if norm in mapeo_columnas:
                        rename_dict[col] = mapeo_columnas[norm]
                
                if not rename_dict:
                    st.error("No se pudo identificar ninguna columna requerida.")
                    st.stop()
                
                df_import = df_import_raw.rename(columns=rename_dict)
                obligatorias = ['nombre', 'precio_detal']
                faltan = [col for col in obligatorias if col not in df_import.columns]
                if faltan:
                    st.error(f"Faltan columnas: {faltan}. Detectadas: {list(df_import.columns)}")
                    st.stop()
                
                df_import['categoria'] = df_import.get('categoria', 'Otros').fillna('Otros')
                df_import['unidad_medida'] = df_import.get('unidad_medida', 'unidad').fillna('unidad')
                df_import['unidad_medida'] = df_import['unidad_medida'].apply(lambda x: x if x in UNIDADES else 'unidad')
                df_import['costo'] = pd.to_numeric(df_import.get('costo', 0), errors='coerce').fillna(0)
                df_import['stock'] = pd.to_numeric(df_import.get('stock', 0), errors='coerce').fillna(0)
                df_import['precio_detal'] = pd.to_numeric(df_import['precio_detal'], errors='coerce')
                df_import['precio_mayor'] = df_import['precio_detal']
                df_import['min_mayor'] = 6
                df_import['marca'] = ''
                df_import['proveedor'] = ''
                df_import['codigo_barras'] = df_import.get('codigo_barras', '').fillna('').astype(str)
                
                df_import = df_import.dropna(subset=['nombre', 'precio_detal'])
                df_import = df_import[df_import['precio_detal'] > 0]
                df_import['nombre'] = df_import['nombre'].astype(str).str.upper().str.strip()
                
                if df_import.empty:
                    st.error("No hay datos válidos para importar.")
                else:
                    st.success(f"✅ Se encontraron {len(df_import)} productos listos para importar/actualizar.")
                    st.dataframe(df_import[['nombre', 'categoria', 'precio_detal', 'stock']], use_container_width=True)
                    if st.button("🚀 Confirmar importación", use_container_width=True):
                        insertados = 0
                        actualizados = 0
                        errores = []
                        for idx, row in df_import.iterrows():
                            try:
                                nombre = row['nombre']
                                codigo = row['codigo_barras'] if row['codigo_barras'] else None
                                existe = None
                                if codigo and codigo != '':
                                    existe = db.table("inventario").select("id").eq("codigo_barras", codigo).execute().data
                                if not existe:
                                    existe = db.table("inventario").select("id").eq("nombre", nombre).execute().data
                                
                                datos = {k: row[k] for k in ['nombre', 'categoria', 'unidad_medida', 'marca', 'proveedor', 'stock', 'costo', 'precio_detal', 'precio_mayor', 'min_mayor', 'codigo_barras']}
                                datos['stock'] = float(datos['stock'])
                                datos['costo'] = float(datos['costo'])
                                datos['precio_detal'] = float(datos['precio_detal'])
                                datos['precio_mayor'] = float(datos['precio_mayor'])
                                datos['min_mayor'] = int(datos['min_mayor'])
                                
                                if existe:
                                    db.table("inventario").update(datos).eq("id", existe[0]['id']).execute()
                                    actualizados += 1
                                else:
                                    db.table("inventario").insert(datos).execute()
                                    insertados += 1
                            except Exception as e:
                                errores.append(f"Fila {idx+2}: {str(e)[:100]}")
                        if errores:
                            st.error(f"Errores en {len(errores)} filas. Ej: {errores[0]}")
                        st.success(f"✅ Importación completada: {insertados} nuevos, {actualizados} actualizados.")
                        time.sleep(2)
                        st.rerun()
            except Exception as e:
                st.error(f"Error al leer archivo: {e}")

# ============================================
# MÓDULO 2: PUNTO DE VENTA (CON LIMPIEZA DE RESULTADOS AL AGREGAR)
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
    
    # Inicializar clientes
    if 'clientes' not in st.session_state:
        st.session_state.clientes = {
            'cliente_1': {'nombre': 'Cliente 1', 'carrito': [], 'cliente_nombre': ''},
            'cliente_2': {'nombre': 'Cliente 2', 'carrito': [], 'cliente_nombre': ''}
        }
    if 'cliente_actual' not in st.session_state:
        st.session_state.cliente_actual = 'cliente_1'
    
    # Selector de cliente
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        if st.button("🧑 Cliente 1", use_container_width=True, type="primary" if st.session_state.cliente_actual == 'cliente_1' else "secondary"):
            st.session_state.cliente_actual = 'cliente_1'
            st.rerun()
    with col_sel2:
        if st.button("👩 Cliente 2", use_container_width=True, type="primary" if st.session_state.cliente_actual == 'cliente_2' else "secondary"):
            st.session_state.cliente_actual = 'cliente_2'
            st.rerun()
    
    cliente_data = st.session_state.clientes[st.session_state.cliente_actual]
    carrito = cliente_data['carrito']
    
    # Nombre del cliente
    nombre_cliente = st.text_input(
        "Nombre del cliente (opcional)",
        value=cliente_data.get('cliente_nombre', ''),
        key="nombre_cliente_input",
        placeholder="Ej: Juan Pérez, Constructora XYZ"
    )
    if nombre_cliente != cliente_data.get('cliente_nombre', ''):
        st.session_state.clientes[st.session_state.cliente_actual]['cliente_nombre'] = nombre_cliente
    
    st.markdown("---")
    
    # ============================================
    # BUSCADORES (pestañas)
    # ============================================
    tab_codigo, tab_nombre = st.tabs(["📷 Escanear código de barras", "🔎 Buscar producto por nombre"])
    
    # Pestaña código de barras
    with tab_codigo:
        codigo = st.chat_input("Escanea el código de barras aquí...")
        if codigo:
            codigo = codigo.strip()
            try:
                response = db.table("inventario").select("*").eq("codigo_barras", codigo).execute()
                prod = response.data[0] if response.data else None
                if not prod:
                    st.warning("❌ Código no encontrado")
                elif prod['stock'] <= 0:
                    st.error(f"⚠️ Producto '{prod['nombre']}' sin stock disponible.")
                else:
                    carrito_actual = st.session_state.clientes[st.session_state.cliente_actual]['carrito']
                    cant_actual = sum(item['cantidad'] for item in carrito_actual if item['id'] == prod['id'])
                    nueva_cant = cant_actual + 1
                    if nueva_cant > prod['stock']:
                        st.error(f"⚠️ Stock insuficiente: solo {prod['stock']} {prod.get('unidad_medida', 'unidades')}.")
                    else:
                        precio = prod['precio_mayor'] if nueva_cant >= prod['min_mayor'] else prod['precio_detal']
                        encontrado = False
                        for item in carrito_actual:
                            if item['id'] == prod['id']:
                                item['cantidad'] += 1
                                item['precio'] = float(precio)
                                item['subtotal'] = item['cantidad'] * item['precio']
                                encontrado = True
                                break
                        if not encontrado:
                            carrito_actual.append({
                                "id": prod['id'],
                                "nombre": prod['nombre'],
                                "unidad": prod.get('unidad_medida', 'unidad'),
                                "cantidad": 1,
                                "precio": float(precio),
                                "costo": float(prod['costo']),
                                "subtotal": float(precio),
                                "tipo_precio": " (Mayor)" if nueva_cant >= prod['min_mayor'] else ""
                            })
                        st.success(f"✅ Agregado: {prod['nombre']} (x1)")
                        st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    
    # Pestaña búsqueda por nombre
    with tab_nombre:
        if 'resultados_busqueda' not in st.session_state:
            st.session_state.resultados_busqueda = []
        
        with st.form(key="buscar_nombre_form"):
            busqueda = st.text_input("Escribe el nombre del producto", placeholder="Ej: Martillo, Pintura...")
            submitted = st.form_submit_button("🔍 Buscar", use_container_width=False)
        
        if submitted and busqueda:
            try:
                response = db.table("inventario")\
                    .select("*")\
                    .ilike("nombre", f"%{busqueda}%")\
                    .gt("stock", 0)\
                    .order("nombre")\
                    .limit(20)\
                    .execute()
                st.session_state.resultados_busqueda = response.data if response.data else []
                if not st.session_state.resultados_busqueda:
                    st.warning(f"No se encontraron productos con '{busqueda}'")
            except Exception as e:
                st.error(f"Error en búsqueda: {e}")
        
        if st.session_state.resultados_busqueda:
            st.markdown("**Resultados de la búsqueda:**")
            for idx, prod in enumerate(st.session_state.resultados_busqueda):
                cols = st.columns([3, 1, 1, 1.5, 1])
                cols[0].write(f"**{prod['nombre']}** ({prod.get('unidad_medida', 'unidad')})")
                cols[1].write(f"${prod['precio_detal']:.2f}")
                cols[2].write(f"Stock: {prod['stock']:.2f}")
                cols[3].write(f"Mayoría: {prod['min_mayor']} uds")
                if cols[4].button("➕ Agregar", key=f"add_result_{prod['id']}_{idx}"):
                    carrito_actual = st.session_state.clientes[st.session_state.cliente_actual]['carrito']
                    cant_actual = sum(item['cantidad'] for item in carrito_actual if item['id'] == prod['id'])
                    nueva_cant = cant_actual + 1
                    if nueva_cant > prod['stock']:
                        st.error(f"⚠️ Stock insuficiente: solo {prod['stock']} {prod.get('unidad_medida', 'unidades')}.")
                    else:
                        precio = prod['precio_mayor'] if nueva_cant >= prod['min_mayor'] else prod['precio_detal']
                        encontrado = False
                        for item in carrito_actual:
                            if item['id'] == prod['id']:
                                item['cantidad'] += 1
                                item['precio'] = float(precio)
                                item['subtotal'] = item['cantidad'] * item['precio']
                                encontrado = True
                                break
                        if not encontrado:
                            carrito_actual.append({
                                "id": prod['id'],
                                "nombre": prod['nombre'],
                                "unidad": prod.get('unidad_medida', 'unidad'),
                                "cantidad": 1,
                                "precio": float(precio),
                                "costo": float(prod['costo']),
                                "subtotal": float(precio),
                                "tipo_precio": " (Mayor)" if nueva_cant >= prod['min_mayor'] else ""
                            })
                        st.success(f"✅ Agregado: {prod['nombre']}")
                        # LIMPIAR RESULTADOS DESPUÉS DE AGREGAR
                        st.session_state.resultados_busqueda = []
                        st.rerun()
            st.markdown("---")
    
    st.divider()
    
    # ============================================
    # CARRITO DE COMPRAS (CON BORDES Y SUBTOTAL EN USD+Bs)
    # ============================================
    st.subheader(f"🛒 Carrito de compras - {cliente_data['nombre']}")
    
    if not carrito:
        st.info("Carrito vacío. Agrega productos escaneando códigos o buscando por nombre.")
    else:
        # Estilos CSS para la tabla con bordes
        st.markdown("""
            <style>
            .tabla-carrito {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 1rem;
            }
            .tabla-carrito th, .tabla-carrito td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            .tabla-carrito th {
                background-color: #f2f2f2;
                font-weight: bold;
            }
            .tabla-carrito tr:hover {
                background-color: #f5f5f5;
            }
            </style>
        """, unsafe_allow_html=True)
        
        # Cabeceras de la tabla (usamos st.columns pero con estilo visual)
        cols_head = st.columns([2.5, 1, 1.2, 1.2, 1.2, 1.2, 1.5, 0.6], gap="small")
        cols_head[0].write("**Producto**")
        cols_head[1].write("**Unidad**")
        cols_head[2].write("**Precio USD**")
        cols_head[3].write("**Precio Bs**")
        cols_head[4].write("**Cantidad**")
        cols_head[5].write("**Subtotal USD**")
        cols_head[6].write("**Subtotal Bs**")
        cols_head[7].write("**✖️**")
        
        total_venta_usd = 0
        total_costo = 0
        
        for idx, item in enumerate(carrito):
            cols = st.columns([2.5, 1, 1.2, 1.2, 1.2, 1.2, 1.5, 0.6], gap="small")
            cols[0].write(item['nombre'])
            cols[1].write(item.get('unidad', 'unidad'))
            cols[2].write(f"${item['precio']:.2f}")
            cols[3].write(f"{(item['precio'] * tasa):,.2f}")
            
            nueva_cant = cols[4].number_input(
                "",
                min_value=0.0,
                value=float(item['cantidad']),
                step=0.1,
                format="%.2f",
                key=f"cant_{st.session_state.cliente_actual}_{idx}_{item['id']}",
                label_visibility="collapsed"
            )
            if nueva_cant != item['cantidad']:
                if nueva_cant == 0:
                    carrito.pop(idx)
                    st.rerun()
                else:
                    try:
                        prod_resp = db.table("inventario").select("precio_detal, precio_mayor, min_mayor").eq("id", item['id']).execute()
                        if prod_resp.data:
                            prod_data = prod_resp.data[0]
                            if nueva_cant >= prod_data['min_mayor']:
                                nuevo_precio = float(prod_data['precio_mayor'])
                            else:
                                nuevo_precio = float(prod_data['precio_detal'])
                            item['precio'] = nuevo_precio
                    except:
                        pass
                    item['cantidad'] = nueva_cant
                    item['subtotal'] = item['cantidad'] * item['precio']
                    st.rerun()
            
            subtotal_usd = item['subtotal']
            subtotal_bs = subtotal_usd * tasa
            cols[5].write(f"${subtotal_usd:.2f}")
            cols[6].write(f"{subtotal_bs:,.2f}")
            if cols[7].button("🗑️", key=f"del_{st.session_state.cliente_actual}_{idx}_{item['id']}"):
                carrito.pop(idx)
                st.rerun()
            
            total_venta_usd += subtotal_usd
            total_costo += item['cantidad'] * item['costo']
        
        # Totales
        total_venta_bs = total_venta_usd * tasa
        st.markdown("---")
        col_total1, col_total2 = st.columns(2)
        col_total1.markdown(f"### Total USD: ${total_venta_usd:,.2f}")
        col_total2.markdown(f"### Total Bs: {total_venta_bs:,.2f}")
        
        # Ajuste de redondeo
        with st.expander("🔧 Ajustar monto final (redondeo)"):
            opcion_ajuste = st.radio(
                "Ajustar en:",
                ["No ajustar", "Bolívares (Bs)", "Dólares (USD)"],
                horizontal=True,
                key="opcion_ajuste"
            )
            total_final_usd = total_venta_usd
            total_final_bs = total_venta_bs
            if opcion_ajuste == "Bolívares (Bs)":
                monto_ajustado_bs = st.number_input("Monto final en Bs", value=float(total_venta_bs), step=10.0, format="%.2f", key="monto_bs")
                total_final_bs = monto_ajustado_bs
                total_final_usd = monto_ajustado_bs / tasa if tasa > 0 else 0
            elif opcion_ajuste == "Dólares (USD)":
                monto_ajustado_usd = st.number_input("Monto final en USD", value=float(total_venta_usd), step=1.0, format="%.2f", key="monto_usd")
                total_final_usd = monto_ajustado_usd
                total_final_bs = monto_ajustado_usd * tasa
        
        # Pagos
        with st.expander("💳 Detalle de pagos", expanded=True):
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                pago_usd_efectivo = st.number_input("Efectivo USD", min_value=0.0, step=5.0, format="%.2f", key="p_usd")
                pago_zelle = st.number_input("Zelle USD", min_value=0.0, step=5.0, format="%.2f", key="p_zelle")
                pago_otros_usd = st.number_input("Otros USD", min_value=0.0, step=5.0, format="%.2f", key="p_otros")
            with col_p2:
                pago_bs_efectivo = st.number_input("Efectivo Bs", min_value=0.0, step=100.0, format="%.2f", key="p_bs")
                pago_movil = st.number_input("Pago Móvil Bs", min_value=0.0, step=100.0, format="%.2f", key="p_movil")
                pago_punto = st.number_input("Punto de Venta Bs", min_value=0.0, step=100.0, format="%.2f", key="p_punto")
            
            total_usd_recibido = pago_usd_efectivo + pago_zelle + pago_otros_usd
            total_bs_recibido = pago_bs_efectivo + pago_movil + pago_punto
            total_usd_equivalente = total_usd_recibido + (total_bs_recibido / tasa if tasa > 0 else 0)
            esperado_usd = total_final_bs / tasa if tasa > 0 else 0
            vuelto_usd = total_usd_equivalente - esperado_usd
            
            st.metric("Pagado USD equivalente", f"${total_usd_equivalente:.2f}")
            if vuelto_usd >= 0:
                st.success(f"Vuelto: ${vuelto_usd:.2f} / {(vuelto_usd * tasa):,.2f} Bs")
            else:
                st.error(f"Faltante: ${abs(vuelto_usd):.2f} / {(abs(vuelto_usd) * tasa):,.2f} Bs")
        
        # Botones de acción
        col_acc1, col_acc2, col_acc3 = st.columns(3)
        with col_acc1:
            if st.button("🔄 Limpiar carrito", use_container_width=True):
                st.session_state.clientes[st.session_state.cliente_actual]['carrito'] = []
                st.rerun()
        with col_acc2:
            venta_valida = vuelto_usd >= -0.01 and len(carrito) > 0
            if st.button("✅ Cobrar y finalizar", type="primary", use_container_width=True, disabled=not venta_valida):
                try:
                    for item in carrito:
                        stock_actual = db.table("inventario").select("stock").eq("id", item['id']).execute().data[0]['stock']
                        if item['cantidad'] > stock_actual:
                            st.error(f"Stock insuficiente para {item['nombre']}. Solo hay {stock_actual} {item.get('unidad', 'unidades')}.")
                            st.stop()
                    
                    items_resumen = []
                    for item in carrito:
                        unidad_str = item.get('unidad', '')
                        items_resumen.append(f"{item['cantidad']:.2f} {unidad_str} de {item['nombre']}")
                        stock_actual = db.table("inventario").select("stock").eq("id", item['id']).execute().data[0]['stock']
                        db.table("inventario").update({"stock": stock_actual - item['cantidad']}).eq("id", item['id']).execute()
                    
                    info_cliente = cliente_data.get('cliente_nombre', '') or cliente_data['nombre']
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
                        "cliente": info_cliente
                    }
                    db.table("ventas").insert(venta_data).execute()
                    
                    st.balloons()
                    st.success(f"✅ Venta registrada - {info_cliente}")
                    
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
                        <div style="background:white; padding:20px; border-radius:10px; border:2px solid #1e3c72;">
                            <h3 style="text-align:center;">🔧 FERRETERIA CHILL</h3>
                            <p style="text-align:center;">{datetime.now().strftime('%d/%m/%Y %H:%M')} | Turno #{id_turno}</p>
                            <p>Cliente: {info_cliente} | Atendido: {st.session_state.usuario_actual['nombre']}</p>
                            <hr>
                            <table style="width:100%; border-collapse: collapse;">
                                <thead><tr style="border-bottom:1px solid #ccc;"><th>Cant</th><th>Producto</th><th>Precio</th><th>Subtotal</th></tr></thead>
                                <tbody>{items_html}</tbody>
                            </table>
                            <hr>
                            <p><b>Total USD:</b> ${total_final_usd:.2f} | <b>Total Bs:</b> {total_final_bs:,.2f} Bs</p>
                            <p style="text-align:center;">¡Gracias por su compra!</p>
                            <button onclick="window.print()" style="background:#007bff; color:white; border:none; padding:5px 10px; border-radius:5px;">🖨️ Imprimir</button>
                        </div>
                        """
                        st.markdown(factura_html, unsafe_allow_html=True)
                    
                    st.session_state.clientes[st.session_state.cliente_actual]['carrito'] = []
                    st.session_state.clientes[st.session_state.cliente_actual]['cliente_nombre'] = ''
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al procesar venta: {e}")
        with col_acc3:
            if st.button("🆕 Nueva venta", use_container_width=True):
                st.session_state.clientes[st.session_state.cliente_actual]['carrito'] = []
                st.session_state.clientes[st.session_state.cliente_actual]['cliente_nombre'] = ''
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
