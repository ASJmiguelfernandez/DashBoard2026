import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from thefuzz import process, fuzz
import io
import base64
import os as _os

try:
    import pyodbc
    _PYODBC_OK = True
except ImportError:
    _PYODBC_OK = False

def cargar_carga_desde_sql():
    """Carga los datos de Carga de Trabajo desde SQL Server.
    Se llama una sola vez por sesión y el resultado se guarda en session_state.
    Devuelve (DataFrame, None) si tiene éxito, o (None, mensaje_error) si falla."""
    if not _PYODBC_OK:
        return None, "pyodbc no instalado"
    try:
        cfg = st.secrets.get("sqlserver", {})
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={cfg.get('server', '')};"
            f"DATABASE={cfg.get('database', '')};"
            f"UID={cfg.get('username', '')};"
            f"PWD={cfg.get('password', '')};"
            f"Connection Timeout=30;"
        )
        conn = pyodbc.connect(conn_str)
        query = """
            select Gestor   as RECURSO,
                   Entidad  as CLIENTE,
                   COUNT(*) as OPERACIONES
            from acue_view_operaciones
            where ITINTERVINIENTE_PRINCIPAL = 'S'
              and ITFUERA_GESTION = 0
            group by Entidad, Gestor
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df, None
    except Exception as e:
        return None, str(e)

# ================================
# CONFIGURACIÓN DE PÁGINA
# ================================
_login_logo_path = _os.path.join(_os.path.dirname(__file__), "logo-login.png")
try:
    with open(_login_logo_path, "rb") as _f:
        _login_logo_b64 = base64.b64encode(_f.read()).decode()
    _login_logo_html = f"<img src='data:image/png;base64,{_login_logo_b64}' style='height:80px;margin-bottom:20px;'/>"
    _page_icon = f"data:image/png;base64,{_login_logo_b64}"
except Exception:
    _login_logo_html = "### ⚖️ Acuerdo"
    _page_icon = "⚖️"

st.set_page_config(page_title="Acuerdo Servicios Jurídicos", page_icon=_page_icon, layout="wide")

# ================================
# AUTENTICACIÓN
# ================================
def _check_login_db(usuario, password):
    """Valida las credenciales contra la tabla CDM_Usuarios de la base de datos."""
    if not _PYODBC_OK:
        return False, "pyodbc no instalado"
    try:
        cfg = st.secrets.get("sqlserver", {})
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={cfg.get('server', '')};"
            f"DATABASE={cfg.get('database', '')};"
            f"UID={cfg.get('username', '')};"
            f"PWD={cfg.get('password', '')};"
            f"Connection Timeout=30;"
        )
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        # Primero comprobamos qué columnas tiene la tabla
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='CDM_Usuarios'")
        cols = [r[0] for r in cursor.fetchall()]
        # Buscamos la columna de contraseña por aproximación (por si la ñ da problemas)
        col_pass = next((c for c in cols if 'ontra' in c), None)
        if col_pass is None:
            conn.close()
            return False, f"No se encontró columna de contraseña. Columnas: {cols}"
        query = f"SELECT TOP 1 ID FROM CDM_Usuarios WHERE UsuarioID = ? AND [{col_pass}] = ?"
        cursor.execute(query, (usuario, password))
        row = cursor.fetchone()
        conn.close()
        return (row is not None), None
    except Exception as e:
        return False, str(e)

def _check_login(usuario, password):
    # 1. Intentar validar contra base de datos
    success, err = _check_login_db(usuario, password)
    if success:
        return True, None
    
    # 2. Fallback a secrets.toml (para usuarios administradores o emergencia)
    usuarios_secrets = st.secrets.get("usuarios", {})
    if usuarios_secrets.get(usuario) == password:
        return True, None
    
    return False, err

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_login, _ = st.columns([1, 2])
    with col_login:
        st.markdown(_login_logo_html, unsafe_allow_html=True)
        st.markdown("### Acuerdo Servicios Jurídicos")
        st.markdown("Introduce tus credenciales para acceder.")
        usuario_input  = st.text_input("Usuario")
        password_input = st.text_input("Contraseña", type="password")
        if st.button("Entrar", use_container_width=True, type="primary"):
            is_ok, login_err = _check_login(usuario_input, password_input)
            if is_ok:
                st.session_state.logged_in = True
                st.rerun()
            else:
                if login_err:
                    st.error(f"Error de conexión a la base de datos: {login_err}")
                else:
                    st.error("Usuario o contraseña incorrectos.")
    st.stop()

# Header con logo
_logo_path = _os.path.join(_os.path.dirname(__file__), "logo-acuerdo.svg")
try:
    with open(_logo_path, "rb") as _f:
        _logo_b64 = base64.b64encode(_f.read()).decode()
    _logo_html = f"<img src='data:image/svg+xml;base64,{_logo_b64}' style='height:56px;'/>"
except Exception:
    _logo_html = "<span style='font-size:1.5rem;font-weight:bold;'>ACUERDO</span>"

st.markdown(f"""
<div style='display:flex;align-items:center;gap:20px;padding:8px 0 16px 0;
            border-bottom:2px solid #e0e0e0;margin-bottom:8px;'>
    {_logo_html}
    <div>
        <h1 style='margin:0;font-size:1.8rem;line-height:1.2;'>Acuerdo Servicios Jurídicos.</h1>
        <p style='margin:0;color:rgb(163,168,184);font-size:0.9rem;'>
            Rendimiento de facturación frente a objetivos por Responsable e ITEM/Cliente
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

# ================================
# BARRA LATERAL (SIDEBAR)
# ================================
st.sidebar.header("📁 1. Cargar Archivos Excel")

_ruta_red = r"\\asjdc.asj.land\ASJ\Aplicaciones\AppCuadroDeMandos"
_obj_red  = _os.path.join(_ruta_red, "OBJETIVOSyEQUIPOS.xlsx")
_fact_red = _os.path.join(_ruta_red, "FACTURAS ASJ de 2019 a 2026.xlsx")
_obj_encontrado  = _os.path.exists(_obj_red)
_fact_encontrado = _os.path.exists(_fact_red)

st.sidebar.markdown("**📂 Ficheros en red:**")
st.sidebar.markdown(
    f"{'✅' if _obj_encontrado  else '❌'} OBJETIVOSyEQUIPOS.xlsx\n\n"
    f"{'✅' if _fact_encontrado else '❌'} FACTURAS ASJ...xlsx"
)
st.sidebar.markdown("*Sube manualmente si no se detectan:*")
obj_file  = st.sidebar.file_uploader("Subir Excel de OBJETIVOS Y EQUIPOS", type=['xlsx', 'xls'])
fact_file = st.sidebar.file_uploader("Subir Excel de FACTURAS", type=['xlsx', 'xls'])
# Carga de Trabajo se obtiene de la base de datos

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 2. Configuración")
año_analisis = st.sidebar.number_input("Año de Análisis", min_value=2000, max_value=2100, value=2026)

divisor_meses = st.sidebar.number_input("Divisor de Presupuesto Anual (Facturación)", min_value=1, max_value=12, value=12, help="Se usa para calcular el objetivo de facturación mensual. Usualmente 12, pero se puede bajar a 11 para amortiguar vacaciones.")

mes_actual_sugerido = datetime.datetime.now().month
mes_corte = st.sidebar.slider("Mes actual (para objetivo acumulado y coste recursos)", min_value=1, max_value=12, value=mes_actual_sugerido)

st.sidebar.markdown("---")

meses_str = {1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL', 5: 'MAYO', 6: 'JUNIO', 
             7: 'JULIO', 8: 'AGOSTO', 9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'}

meses_columnas_obj = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']

def get_best_match(query, choices, threshold=80, scorer=None):
    if not isinstance(query, str) or pd.isna(query):
        return None
    _scorer = scorer if scorer is not None else fuzz.token_sort_ratio
    res = process.extractOne(query, choices, scorer=_scorer)
    if res and res[1] >= threshold:
        return res[0]
    return None

def fmt_eur(value):
    """Formatea un número con formato europeo: punto como separador de miles, coma como decimal."""
    try:
        v = float(value)
        formatted = f"{v:,.2f}"  # 1,234.56
        formatted = formatted.replace(',', 'X').replace('.', ',').replace('X', '.')  # 1.234,56
        return f"€ {formatted}"
    except (TypeError, ValueError):
        return ""

def color_estado(pct):
    """Devuelve el estilo CSS de celda según el % de cumplimiento."""
    try:
        v = float(pct)
    except:
        return ''
    if v >= 95:   return 'background-color:#00b300;color:white;font-weight:bold'
    elif v >= 85: return 'background-color:#ccaa00;color:white;font-weight:bold'
    elif v >= 70: return 'background-color:#e05000;color:white;font-weight:bold'
    else:         return 'background-color:#cc0000;color:white;font-weight:bold'

def color_gauge(pct):
    """Devuelve el color principal del gauge según el % de cumplimiento."""
    if pct >= 95:  return "#00b300"
    elif pct >= 85: return "#ccaa00"
    elif pct >= 70: return "#e05000"
    else:           return "#cc0000"

def badge_peso_equipo(pct, pct_fmt):
    """Devuelve HTML de badge coloreado según el peso del equipo sobre la facturación."""
    if pct < 40:
        bg, color = "#d4edda", "#155724"
    elif pct <= 55:
        bg, color = "#ffe8cc", "#a04000"
    else:
        bg, color = "#f8d7da", "#721c24"
    return (f"<span style='display:inline-block;background:{bg};color:{color};"
            f"border-radius:6px;padding:2px 10px;font-size:0.875rem;font-weight:bold;'>"
            f"{pct_fmt}% s/fact.</span>")

def html_metric(label, value, sub_html=""):
    """Renderiza un bloque métrico con el mismo estilo visual que st.metric."""
    return (f"<div style='padding:0.25rem 0 0.5rem 0;'>"
            f"<p style='font-size:0.8rem;color:rgb(163,168,184);margin:0 0 2px 0;font-weight:400;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{label}</p>"
            f"<p style='font-size:1.35rem;font-weight:700;margin:0 0 5px 0;line-height:1.2;white-space:nowrap;'>{value}</p>"
            f"{sub_html}"
            f"</div>")

# ================================
# PROCESAMIENTO
# ================================
import os

ruta_obj_defecto   = _obj_red
ruta_fact_defecto  = _fact_red

usar_rutas_defecto = not obj_file and not fact_file and os.path.exists(ruta_obj_defecto) and os.path.exists(ruta_fact_defecto)

# Asignar a las variables a usar
archivo_obj_a_leer   = obj_file   if obj_file   else (ruta_obj_defecto   if usar_rutas_defecto else None)
archivo_fact_a_leer  = fact_file  if fact_file  else (ruta_fact_defecto  if usar_rutas_defecto else None)

if archivo_obj_a_leer and archivo_fact_a_leer:
    try:
        # Leer CLIENTES del Excel de Objetivos
        df_clientes = pd.read_excel(archivo_obj_a_leer, sheet_name="CLIENTES", skiprows=3)
        # Limpiar nombres de columnas
        df_clientes.columns = df_clientes.columns.astype(str).str.strip()
        
        # Leer EQUIPOS del Excel de Objetivos
        df_equipos = pd.read_excel(archivo_obj_a_leer, sheet_name="EQUIPOS", skiprows=3)
        df_equipos.columns = df_equipos.columns.astype(str).str.strip()
        
        # Leer FACTURAS del año
        df_facturas = pd.read_excel(archivo_fact_a_leer, sheet_name=str(año_analisis), skiprows=1)
        df_facturas.columns = df_facturas.columns.astype(str).str.strip()
        
    except Exception as e:
        st.error(f"Hubo un problema al leer los archivos. Asegúrate de que las pestañas (CLIENTES, EQUIPOS, {año_analisis}) existen: {e}")
        st.stop()
else:
    st.info("👆 Por favor sube los **tres archivos Excel** en el menú de la izquierda para comenzar el análisis.")
    st.stop()

with st.spinner("Procesando y cruzando datos..."):
    try:
        # 1. TRATAMIENTO DE OBJETIVOS (CLIENTES)
        col_cliente_obj = 'CLIENTES'
        col_presupuesto_obj = 'PRESUPUESTO 2026'
        col_responsable_obj = 'RESPONSABLE'
        # Usamos regex para encontrar la columna de facturacion mensual ya que puede tener espacios u otros caracteres
        col_fact_mensual_obj = [c for c in df_clientes.columns if 'facturacion mensual' in c.lower()][0]
        
        df_clientes = df_clientes.dropna(subset=[col_cliente_obj])
        df_clientes[col_presupuesto_obj] = pd.to_numeric(df_clientes[col_presupuesto_obj], errors='coerce').fillna(0)
        
        # Recalcular la facturación mensual basada en el divisor seleccionado en UI
        df_clientes[col_fact_mensual_obj] = df_clientes[col_presupuesto_obj] / divisor_meses
        
        lista_clientes_objetivos = df_clientes[col_cliente_obj].dropna().unique().tolist()
        
        # 2. MATCHING DE FACTURAS
        # Fecha en col E (indice 4), Cliente en F y G (indices 5 y 6), Importe Base en J (indice 9)
        col_fecha_fact = df_facturas.columns[4]
        col_cliente_f_fact = df_facturas.columns[5]
        col_cliente_g_fact = df_facturas.columns[6]
        col_base_fact = df_facturas.columns[9]
        
        df_facturas = df_facturas.dropna(subset=[col_base_fact])
        # Excluir facturas de tipo SUP y WIP (columna C = índice 2)
        col_serie_fact = df_facturas.columns[2]
        df_facturas = df_facturas[~df_facturas[col_serie_fact].astype(str).str.strip().str.upper().isin(['SUP', 'WIP'])]
        df_facturas[col_fecha_fact] = pd.to_datetime(df_facturas[col_fecha_fact], errors='coerce')
        df_facturas = df_facturas.dropna(subset=[col_fecha_fact])
        
        # Fuzzy matching con F y G
        def match_cliente(row):
            cliente_f = str(row[col_cliente_f_fact]) if pd.notna(row[col_cliente_f_fact]) else ""
            cliente_g = str(row[col_cliente_g_fact]) if pd.notna(row[col_cliente_g_fact]) else ""
            match_f = get_best_match(cliente_f, lista_clientes_objetivos)
            if match_f: return match_f
            match_g = get_best_match(cliente_g, lista_clientes_objetivos)
            if match_g: return match_g
            return None # No se encontró match
            
        df_facturas['CLIENTE_MATCHED'] = df_facturas.apply(match_cliente, axis=1)
        
        # Solo quedarnos con facturas de clientes que están en Objetivos
        df_facturas_validas = df_facturas.dropna(subset=['CLIENTE_MATCHED']).copy()
        df_facturas_validas['Mes'] = df_facturas_validas[col_fecha_fact].dt.month
        
        # 3. RELLENAR IMPORTES MENSUALES EN CLIENTES
        agrupado_meses = df_facturas_validas.groupby(['CLIENTE_MATCHED', 'Mes'])[col_base_fact].sum().reset_index()
        
        # Limpiar las columnas de meses en el dataframe original para sobreescribirlas
        for m in meses_columnas_obj:
            if m in df_clientes.columns:
                df_clientes[m] = 0.0
                
        # Iterar para rellenar
        for idx, row in agrupado_meses.iterrows():
            cliente = row['CLIENTE_MATCHED']
            mes_num = int(row['Mes'])
            if mes_num in meses_str:
                mes_nombre = meses_str[mes_num]
                # Buscar la columna que contenga el nombre del mes (ya están .strip() entonces match exacto o parcial)
                matched_cols = [c for c in df_clientes.columns if mes_nombre in c.upper()]
                if matched_cols:
                    col_nombre = matched_cols[0]
                    # Sumar por si hay un valor preexistente, aunque lo acabamos de limpiar
                    df_clientes.loc[df_clientes[col_cliente_obj] == cliente, col_nombre] += row[col_base_fact]
                
        # 4. RATIOS y FACTURACIÓN ACUMULADA CLIENTES (PARA DASHBOARD)
        # Meses computados: siempre mes_corte - 1 (meses completos transcurridos), independiente de facturas
        meses_transcurridos = max(mes_corte - 1, 0)
        df_clientes['Meses Computados'] = meses_transcurridos

        # Facturación Acumulada: suma de todos los meses en el dataframe de clientes
        df_clientes['Facturación Acumulada'] = df_clientes.apply(
            lambda row: sum(
                row[matched_cols[0]]
                for i in range(1, 13)
                if i in meses_str
                and (matched_cols := [c for c in df_clientes.columns if meses_str[i] in c.upper()])
                and pd.notna(row[matched_cols[0]])
            ), axis=1
        )

        # Objetivo Acumulado = Facturación Mensual * meses transcurridos (igual para todos)
        df_clientes['Objetivo Acumulado'] = df_clientes[col_fact_mensual_obj] * meses_transcurridos

        df_clientes['% Cumplimiento'] = df_clientes.apply(
            lambda row: (row['Facturación Acumulada'] / row['Objetivo Acumulado'] * 100) if row['Objetivo Acumulado'] > 0 else 0, axis=1
        )
        
        # 5. TRATAMIENTO DE EQUIPOS
        col_recurso_eq = df_equipos.columns[0] # 'RECURSO'
        col_presupuesto_eq = df_equipos.columns[1] # 'PRESUPUESTO 2026'
        
        df_equipos = df_equipos.dropna(subset=[col_recurso_eq])
        df_equipos[col_presupuesto_eq] = pd.to_numeric(df_equipos[col_presupuesto_eq], errors='coerce').fillna(0)
        
        # Coste mensual = Anual / 12
        df_equipos['COSTE_MENSUAL'] = df_equipos[col_presupuesto_eq] / 12.0
        
        # Asegurar que los meses pasados sean numéricos (se leen del Excel tal cual, sin sobreescribir)
        for i in range(1, mes_corte):
            matched_cols = [c for c in df_equipos.columns if meses_str[i] in c.upper()]
            if matched_cols:
                df_equipos[matched_cols[0]] = pd.to_numeric(df_equipos[matched_cols[0]], errors='coerce').fillna(0)
                
        for i in range(mes_corte, 13):
            mes_nombre = meses_str[i]
            matched_cols = [c for c in df_equipos.columns if mes_nombre in c.upper()]
            if matched_cols:
                col_nombre = matched_cols[0]
                df_equipos[col_nombre] = None

        # ================================
        # CARGA DE TRABAJO
        # ================================
        lista_recursos_eq = df_equipos[col_recurso_eq].dropna().unique().tolist()
        dict_expedientes = {}      # recurso_eq → total expedientes (fuzzy matched)
        recursos_sin_carga = []    # recursos de equipos sin match en carga de trabajo
        df_carga = None
        col_rec_carga = col_exp_carga = col_cli_carga = None

        # --- Carga de Trabajo: desde SQL Server, una sola vez por sesión ---
        if 'df_carga_sesion' not in st.session_state:
            _df_sql_carga, _sql_err = cargar_carga_desde_sql()
            st.session_state['df_carga_sesion'] = _df_sql_carga
            st.session_state['df_carga_err']    = _sql_err
        else:
            _df_sql_carga = st.session_state['df_carga_sesion']
            _sql_err      = st.session_state['df_carga_err']

        col_rec_carga = 'RECURSO'
        col_cli_carga = 'CLIENTE'
        col_exp_carga = 'OPERACIONES'

        if _df_sql_carga is not None and not _df_sql_carga.empty:
            df_carga = _df_sql_carga.copy()
            df_carga[col_exp_carga] = pd.to_numeric(df_carga[col_exp_carga], errors='coerce').fillna(0)
            st.sidebar.caption(f"🟢 Carga de trabajo: {len(df_carga)} registros")
        else:
            if _sql_err:
                st.sidebar.caption(f"⚠️ Carga de trabajo no disponible: {_sql_err[:60]}")

        if df_carga is not None:
            lista_recursos_carga = df_carga[col_rec_carga].dropna().unique().tolist()
            exp_por_recurso_carga = df_carga.groupby(col_rec_carga)[col_exp_carga].sum().to_dict()
            for rec in lista_recursos_eq:
                match = get_best_match(str(rec), lista_recursos_carga)
                if match:
                    dict_expedientes[rec] = int(exp_por_recurso_carga.get(match, 0))
                else:
                    recursos_sin_carga.append(rec)
        else:
            recursos_sin_carga = list(lista_recursos_eq)

        # ================================
        # DATOS DE ANOMALÍAS
        # ================================
        # 1. Facturas sin cliente asociado
        df_anom_facturas = df_facturas[df_facturas['CLIENTE_MATCHED'].isna()][[
            col_fecha_fact, col_serie_fact, col_cliente_f_fact, col_cliente_g_fact, col_base_fact
        ]].copy()
        df_anom_facturas.columns = ['Fecha', 'Serie', 'Cliente (col F)', 'Cliente (col G)', 'Importe Base']

        # 2. Recursos sin responsable
        col_resp_eq = next((c for c in df_equipos.columns if 'responsable' in c.lower()), None)
        if col_resp_eq:
            df_anom_recursos = df_equipos[
                df_equipos[col_resp_eq].isna() | (df_equipos[col_resp_eq].astype(str).str.strip() == '')
            ][[col_recurso_eq, col_presupuesto_eq]].copy()
            df_anom_recursos.columns = ['Recurso', 'Presupuesto Anual']
        else:
            df_anom_recursos = pd.DataFrame(columns=['Recurso', 'Presupuesto Anual'])

        # 3. Clientes sin responsable
        df_anom_clientes = df_clientes[
            df_clientes[col_responsable_obj].isna() | (df_clientes[col_responsable_obj].astype(str).str.strip() == '')
        ][[col_cliente_obj, col_presupuesto_obj]].copy()
        df_anom_clientes.columns = ['Cliente', 'Presupuesto Anual']

        st.success("✅ ¡Datos procesados correctamente!")
        
        # ================================
        # EXPORTACIÓN DE EXCEL
        # ================================
        # Generar Excel final en memoria
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Seleccionar y reordenar columnas tal como venían (excepto las de cálculo visual)
            # Volcamos las calculadas a las pestañas
            cols_clientes_export = list(df_clientes.columns[:len(df_clientes.columns)-4]) # Quitar calculadas visuales
            df_clientes[cols_clientes_export].to_excel(writer, sheet_name='CLIENTES_ACTUALIZADO', index=False)
            
            cols_equipos_export = [c for c in df_equipos.columns if c != 'COSTE_MENSUAL']
            df_equipos[cols_equipos_export].to_excel(writer, sheet_name='EQUIPOS_ACTUALIZADO', index=False)
            
        output.seek(0)
        
        st.download_button(
            label="📥 Descargar Excel Actualizado",
            data=output,
            file_name=f"OBJETIVOS_Y_EQUIPOS_ACTUALIZADO_{año_analisis}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
        
    except Exception as e:
        st.error(f"Error procesando los datos: {e}")
        st.stop()


# ================================
# PRESENTACIÓN VISUAL / DASHBOARD
# ================================
import plotly.graph_objects as go

if 'vista_actual' not in st.session_state:
    st.session_state.vista_actual = 'Global'
if 'responsable_seleccionado' not in st.session_state:
    st.session_state.responsable_seleccionado = None
if 'cliente_seleccionado' not in st.session_state:
    st.session_state.cliente_seleccionado = None
if 'responsable_de_cliente' not in st.session_state:
    st.session_state.responsable_de_cliente = None

n_anom = len(df_anom_facturas) + len(df_anom_recursos) + len(df_anom_clientes) + len(recursos_sin_carga)
_badge = f" 🔴 {n_anom}" if n_anom > 0 else " ✅ 0"
st.sidebar.markdown("---")
if st.sidebar.button(f"⚠️ Anomalías{_badge}", use_container_width=True):
    st.session_state.vista_actual = 'Anomalias'
    st.rerun()

st.header(f"📈 Resultados (hasta {meses_str[mes_corte]} {año_analisis})")

# Limpiar responsables nulos o vacíos
lista_todos_resp = df_clientes[(df_clientes[col_responsable_obj].notna()) & (df_clientes[col_responsable_obj] != "")][col_responsable_obj].unique().tolist()
lista_todos_resp = sorted(lista_todos_resp)

if st.session_state.vista_actual == 'Global':
    st.subheader("🌐 Vista Global")
    
    # Global Totals
    g_total_obj_anual = df_clientes[col_presupuesto_obj].sum()
    g_total_obj_acumulado = df_clientes['Objetivo Acumulado'].sum()
    g_total_fact = df_clientes['Facturación Acumulada'].sum()
    g_pct_cumplimiento = (g_total_fact / g_total_obj_acumulado * 100) if g_total_obj_acumulado > 0 else 0
    g_diferencia = g_total_fact - g_total_obj_acumulado
    
    # Coste Equipos global
    _cols_eq_g = [c for i in range(1, mes_corte) for c in df_equipos.columns if meses_str[i] in c.upper()]
    g_coste_total_equipos = df_equipos[_cols_eq_g].sum().sum() if _cols_eq_g else 0.0
    
    c1, c2, c3, c4, c5 = st.columns(5)
    g_dif_fmt = fmt_eur(abs(g_diferencia))
    g_peso_pct = (g_coste_total_equipos / g_total_fact * 100) if g_total_fact > 0 else 0
    g_peso_fmt = f"{g_peso_pct:.1f}".replace('.', ',')
    _dc = "#cc0000" if g_diferencia < 0 else "#00b300"
    _da = "↓" if g_diferencia < 0 else "↑"
    _dv = f"-{g_dif_fmt}" if g_diferencia < 0 else g_dif_fmt
    g_pct_fmt = f"{g_pct_cumplimiento:.1f}".replace('.', ',')
    g_pct_color = color_gauge(g_pct_cumplimiento)

    c1.markdown(html_metric("Global: Obj. Anual", fmt_eur(g_total_obj_anual)), unsafe_allow_html=True)
    c2.markdown(html_metric("Global: Obj. Acumulado", fmt_eur(g_total_obj_acumulado)), unsafe_allow_html=True)
    c3.markdown(html_metric("Global: Fact. Acumulada", fmt_eur(g_total_fact),
        f"<p style='font-size:0.8rem;color:{_dc};margin:0;'>{_da} {_dv}</p>"), unsafe_allow_html=True)
    c4.markdown(html_metric("Global: Coste Equipos", fmt_eur(g_coste_total_equipos),
        badge_peso_equipo(g_peso_pct, g_peso_fmt)), unsafe_allow_html=True)
    c5.markdown(html_metric("Global: % Cumplimiento",
        f"<span style='color:{g_pct_color};'>{g_pct_fmt}%</span>"), unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("👥 Estado por Responsable")
    
    # Mostrar gráficos tipo termómetro (gauge) en grid
    cols_per_row = 3
    for i in range(0, len(lista_todos_resp), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j < len(lista_todos_resp):
                resp = lista_todos_resp[i + j]
                df_resp_g = df_clientes[df_clientes[col_responsable_obj] == resp]
                r_obj_acum = df_resp_g['Objetivo Acumulado'].sum()
                r_fact = df_resp_g['Facturación Acumulada'].sum()
                r_pct = (r_fact / r_obj_acum * 100) if r_obj_acum > 0 else 0

                max_gauge_val = max(100, r_pct) * 1.2

                # Color de la barra del gauge según cumplimiento (umbrales 95/85/70)
                bar_color = color_gauge(r_pct)
                if r_pct >= 95:
                    step_colors = [
                        {'range': [0, 70],  'color': "#ffdddd"},
                        {'range': [70, 85], 'color': "#ffe8cc"},
                        {'range': [85, 95], 'color': "#ffee99"},
                        {'range': [95, max_gauge_val], 'color': "#b3ffb3"}
                    ]
                elif r_pct >= 85:
                    step_colors = [
                        {'range': [0, 70],  'color': "#ffdddd"},
                        {'range': [70, 85], 'color': "#ffe8cc"},
                        {'range': [85, max_gauge_val], 'color': "#ffee55"}
                    ]
                elif r_pct >= 70:
                    step_colors = [
                        {'range': [0, 70],  'color': "#ffdddd"},
                        {'range': [70, max_gauge_val], 'color': "#ffbb66"}
                    ]
                else:
                    step_colors = [
                        {'range': [0, max_gauge_val], 'color': "#ff8080"}
                    ]

                fig = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = r_pct,
                    title = {'text': resp, 'font': {'size': 18, 'color': bar_color}},
                    number = {'suffix': "%", 'valueformat': ".1f", 'font': {'color': bar_color, 'size': 30}},
                    gauge = {
                        'axis': {'range': [None, max_gauge_val], 'tickwidth': 1},
                        'bar': {'color': bar_color, 'thickness': 0.3},
                        'bgcolor': 'white',
                        'borderwidth': 2,
                        'bordercolor': '#cccccc',
                        'steps': step_colors,
                        'threshold': {
                            'line': {'color': "#333333", 'width': 4},
                            'thickness': 0.85,
                            'value': 100
                        }
                    }
                ))
                fig.update_layout(height=260, margin=dict(l=10, r=10, t=50, b=10),
                                  paper_bgcolor='rgba(0,0,0,0)')

                with col:
                    st.plotly_chart(fig, use_container_width=True)
                    if st.button(f"🔍 Ver Detalle de {resp}", key=f"btn_{resp}", use_container_width=True):
                        st.session_state.responsable_seleccionado = resp
                        st.session_state.vista_actual = 'Detalle'
                        st.rerun()

    # Tabla resumen por responsable
    st.markdown("---")
    st.subheader("📋 Resumen por Responsable")
    resumen_rows = []
    for resp_r in lista_todos_resp:
        df_r = df_clientes[df_clientes[col_responsable_obj] == resp_r]
        r_obj_anual = df_r[col_presupuesto_obj].sum()
        r_obj_acum = df_r['Objetivo Acumulado'].sum()
        r_fact = df_r['Facturación Acumulada'].sum()
        r_pct = (r_fact / r_obj_acum * 100) if r_obj_acum > 0 else 0
        r_dif = r_fact - r_obj_acum
        r_dif_fmt = fmt_eur(abs(r_dif))
        resumen_rows.append({
            'Responsable': resp_r,
            'Obj. Anual': fmt_eur(r_obj_anual),
            'Obj. Acumulado': fmt_eur(r_obj_acum),
            'Fact. Acumulada': fmt_eur(r_fact),
            'Diferencia': r_dif_fmt if r_dif >= 0 else f"-{r_dif_fmt}",
            '% Cumplimiento': r_pct,
        })
    df_resumen = pd.DataFrame(resumen_rows)

    df_resumen_styled = df_resumen.style\
        .format({'% Cumplimiento': lambda v: f"{v:,.1f} %".replace(',', 'X').replace('.', ',').replace('X', '.')})\
        .map(color_estado, subset=['% Cumplimiento'])
    st.dataframe(df_resumen_styled, use_container_width=True, hide_index=True)

elif st.session_state.vista_actual == 'Detalle':
    if st.button("⬅️ Volver a Vista Global"):
        st.session_state.vista_actual = 'Global'
        st.session_state.responsable_seleccionado = None
        st.rerun()
        
    resp = st.session_state.responsable_seleccionado
    
    df_resp = df_clientes[df_clientes[col_responsable_obj] == resp].copy()
    
    # Totales Clientes
    total_obj_anual = df_resp[col_presupuesto_obj].sum()
    total_obj_acumulado = df_resp['Objetivo Acumulado'].sum()
    total_fact = df_resp['Facturación Acumulada'].sum()
    
    pct_cumplimiento = (total_fact / total_obj_acumulado * 100) if total_obj_acumulado > 0 else 0
    diferencia = total_fact - total_obj_acumulado
    
    # Coste Equipos del responsable
    df_equipos_resp = df_equipos[df_equipos['RESPONSABLE'] == resp]
    # Coste acumulado = recursos * coste_mensual * (mes_corte - 1)
    _cols_eq_r = [c for i in range(1, mes_corte) for c in df_equipos_resp.columns if meses_str[i] in c.upper()]
    coste_total_equipos = df_equipos_resp[_cols_eq_r].sum().sum() if _cols_eq_r else 0.0
    
    beneficio_bruto = total_fact - coste_total_equipos

    # Indicador de termómetro (umbrales 95/85/70)
    bar_color_det = color_gauge(pct_cumplimiento)
    if pct_cumplimiento >= 95:
        termometro_icono = "🟩"
    elif pct_cumplimiento >= 85:
        termometro_icono = "🟨"
    elif pct_cumplimiento >= 70:
        termometro_icono = "🟧"
    else:
        termometro_icono = "🟥"

    pct_fmt = f"{pct_cumplimiento:.1f}".replace('.', ',')
    st.markdown("---")
    resumen_html = f"<h3 style='margin-bottom:0;'>👤 {resp} &nbsp;&nbsp;|&nbsp;&nbsp; 🌡️ <span style='color:{bar_color_det};'>{pct_fmt}% {termometro_icono}</span></h3>"
    st.markdown(resumen_html, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Tarjetas Métricas
    c1, c2, c3, c4, c5 = st.columns(5)
    dif_fmt = fmt_eur(abs(diferencia))
    peso_pct = (coste_total_equipos / total_fact * 100) if total_fact > 0 else 0
    peso_fmt = f"{peso_pct:.1f}".replace('.', ',')
    _dc = "#cc0000" if diferencia < 0 else "#00b300"
    _da = "↓" if diferencia < 0 else "↑"
    _dv = f"-{dif_fmt}" if diferencia < 0 else dif_fmt

    c1.markdown(html_metric("Objetivo Anual", fmt_eur(total_obj_anual)), unsafe_allow_html=True)
    c2.markdown(html_metric("Objetivo Acumulado (Meta)", fmt_eur(total_obj_acumulado)), unsafe_allow_html=True)
    c3.markdown(html_metric("Facturado Acumulado", fmt_eur(total_fact),
        f"<p style='font-size:0.8rem;color:{_dc};margin:0;'>{_da} {_dv}</p>"), unsafe_allow_html=True)
    c4.markdown(html_metric("Coste Disp. Equipos", fmt_eur(coste_total_equipos),
        badge_peso_equipo(peso_pct, peso_fmt)), unsafe_allow_html=True)
    c5.markdown(html_metric("% Cumplimiento Global",
        f"<span style='color:{bar_color_det};'>{pct_fmt}%</span>"), unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

    # --- Gráfico de burbujas PRIMERO ---
    df_chart = df_resp.copy()
    if not df_chart.empty:
        df_chart['Tamaño'] = df_chart['Objetivo Acumulado'].fillna(0).apply(lambda x: x if x > 0 else 1)

        def asignar_estado_color(pct):
            if pct >= 95:  return 'Alcanzado (≥95%)'
            elif pct >= 85: return 'En Progreso (85-94%)'
            elif pct >= 70: return 'Bajo (70-84%)'
            else:           return 'Crítico (<70%)'

        df_chart['Estado'] = df_chart['% Cumplimiento'].apply(asignar_estado_color)
        df_chart = df_chart.sort_values('Objetivo Acumulado', ascending=False)

        # Orden fijo de categorías para leyenda (Verde→Amarillo→Naranja→Rojo)
        orden_estados = ['Alcanzado (≥95%)', 'En Progreso (85-94%)', 'Bajo (70-84%)', 'Crítico (<70%)']

        mapa_colores = {
            'Alcanzado (≥95%)':      '#00b300',
            'En Progreso (85-94%)':  '#ccaa00',
            'Bajo (70-84%)':         '#e05000',
            'Crítico (<70%)':        '#cc0000'
        }

        # X-axis ordenado de mayor a menor objetivo acumulado (izq → der)
        x_order = df_chart[col_cliente_obj].tolist()

        fig_burbuja = px.scatter(
            df_chart,
            x=col_cliente_obj,
            y='Facturación Acumulada',
            size='Tamaño',
            color='Estado',
            hover_name=col_cliente_obj,
            hover_data={'Tamaño': False, 'Objetivo Acumulado': ':,.2f', 'Facturación Acumulada': ':,.2f', '% Cumplimiento': ':.1f'},
            color_discrete_map=mapa_colores,
            size_max=40,
            category_orders={'Estado': orden_estados, col_cliente_obj: x_order},
            title=f"Facturación vs Objetivo (Tamaño de burbuja = Objetivo Acumulado)"
        )
        fig_burbuja.update_layout(xaxis_title="Cliente", yaxis_title="Facturación Acumulada (€)", margin=dict(l=20, r=20, t=40, b=20))
        st.caption("💡 Haz clic en una burbuja para ver el detalle del cliente.")
        ev = st.plotly_chart(fig_burbuja, use_container_width=True, on_select="rerun", key=f"burbuja_{resp}")
        if ev and ev.selection and ev.selection.points:
            _pt = ev.selection.points[0]
            _cliente_click = _pt.get('x') or _pt.get('hovertext')
            if _cliente_click:
                st.session_state.cliente_seleccionado = _cliente_click
                st.session_state.responsable_de_cliente = resp
                st.session_state.vista_actual = 'Cliente'
                st.rerun()

    # --- Detalle de Clientes (expandible) ---
    with st.expander("📋 Detalle de Clientes", expanded=False):
        columnas_meses_presentes = [c for c in meses_columnas_obj if c in df_resp.columns]
        cols_mostrar = [
            col_cliente_obj,
            col_presupuesto_obj,
            col_fact_mensual_obj,
            'Meses Computados',
            'Objetivo Acumulado',
            'Facturación Acumulada',
            '% Cumplimiento'
        ] + columnas_meses_presentes

        format_dict = {
            col_presupuesto_obj: "€ {:,.2f}",
            col_fact_mensual_obj: "€ {:,.2f}",
            'Meses Computados': "{:,.0f}",
            'Objetivo Acumulado': "€ {:,.2f}",
            'Facturación Acumulada': "€ {:,.2f}",
            '% Cumplimiento': "{:.1f} %"
        }
        for m in columnas_meses_presentes:
            format_dict[m] = "€ {:,.2f}"

        try:
            df_mostrar = df_resp[cols_mostrar].sort_values('Objetivo Acumulado', ascending=False)
            styled_df = df_mostrar.style.format(format_dict).map(color_estado, subset=['% Cumplimiento'])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        except:
            st.dataframe(df_resp[cols_mostrar].sort_values('Objetivo Acumulado', ascending=False), use_container_width=True, hide_index=True)

    # --- Recursos del equipo (expandible) ---
    with st.expander("👥 Recursos del Equipo", expanded=False):
        if df_equipos_resp.empty:
            st.info("No hay recursos asignados a este responsable.")
        else:
            col_recurso_eq = df_equipos_resp.columns[0]
            col_ppto_eq_name = df_equipos_resp.columns[1]

            # Columnas de meses transcurridos (hasta mes anterior)
            cols_meses_eq = []
            for i in range(1, mes_corte):
                matched = [c for c in df_equipos_resp.columns if meses_str[i] in c.upper()]
                if matched:
                    cols_meses_eq.append(matched[0])

            df_eq = df_equipos_resp[[col_recurso_eq, col_ppto_eq_name] + cols_meses_eq + ['COSTE_MENSUAL']].copy()
            df_eq['Coste Acumulado'] = df_eq[cols_meses_eq].apply(
                lambda row: sum(v for v in row if pd.notna(v)), axis=1) if cols_meses_eq else 0.0
            df_eq['Presupuesto Acumulado'] = df_eq['COSTE_MENSUAL'] * meses_transcurridos
            df_eq['Desviación %'] = df_eq.apply(
                lambda row: ((row['Coste Acumulado'] - row['Presupuesto Acumulado']) / row['Presupuesto Acumulado'] * 100)
                if row['Presupuesto Acumulado'] > 0 else 0.0, axis=1)

            df_eq = df_eq.rename(columns={col_recurso_eq: 'Recurso', col_ppto_eq_name: 'Presupuesto Anual'})
            df_eq = df_eq.drop(columns=['COSTE_MENSUAL'])

            # Expedientes de carga de trabajo (usando nombre original antes de renombrar)
            df_eq['Expedientes'] = df_eq['Recurso'].map(dict_expedientes).fillna(0).astype(int)

            fmt_eq = {'Presupuesto Anual': lambda x: fmt_eur(x) if pd.notna(x) else "",
                      'Coste Acumulado': lambda x: fmt_eur(x),
                      'Presupuesto Acumulado': lambda x: fmt_eur(x),
                      'Desviación %': lambda x: f"{x:+.1f}%".replace('.', ','),
                      'Expedientes': lambda x: f"{int(x):,}".replace(',', '.')}
            for c in cols_meses_eq:
                fmt_eq[c] = lambda x: fmt_eur(x) if pd.notna(x) else "-"

            def color_desv(val):
                try:
                    return 'color:#cc0000;font-weight:bold' if float(val) > 0 else 'color:#155724;font-weight:bold'
                except:
                    return ''

            cols_display = ['Recurso', 'Presupuesto Anual', 'Presupuesto Acumulado', 'Coste Acumulado', 'Desviación %', 'Expedientes'] + cols_meses_eq
            styled_eq = df_eq[cols_display].style.format(fmt_eq).map(color_desv, subset=['Desviación %'])
            st.dataframe(styled_eq, use_container_width=True, hide_index=True)
            st.caption(f"Coste total acumulado del equipo hasta mes anterior: **{fmt_eur(coste_total_equipos)}**")

elif st.session_state.vista_actual == 'Anomalias':
    if st.button("⬅️ Volver a Vista Global"):
        st.session_state.vista_actual = 'Global'
        st.rerun()

    st.header("⚠️ Informe de Anomalías")
    st.markdown("Revisa estos datos para depurar los archivos Excel antes del próximo análisis.")

    # --- 1. Facturas sin cliente asociado ---
    st.markdown("---")
    n1 = len(df_anom_facturas)
    st.subheader(f"🧾 Facturas sin cliente asociado ({n1})")
    if n1 == 0:
        st.success("No hay facturas sin asociar. ✅")
    else:
        st.warning(f"{n1} facturas no pudieron asociarse a ningún cliente del Excel de Objetivos (umbral fuzzy matching < 80%).")
        fmt_fact = {'Importe Base': lambda x: fmt_eur(x) if pd.notna(x) else ""}
        st.dataframe(
            df_anom_facturas.style.format(fmt_fact),
            use_container_width=True, hide_index=True
        )

    # --- 2. Recursos sin responsable ---
    st.markdown("---")
    n2 = len(df_anom_recursos)
    st.subheader(f"👤 Recursos sin responsable asignado ({n2})")
    if n2 == 0:
        st.success("Todos los recursos tienen responsable asignado. ✅")
    else:
        st.warning(f"{n2} recursos en la hoja EQUIPOS no tienen responsable. Su coste no aparecerá en ningún panel.")
        st.dataframe(
            df_anom_recursos.style.format({'Presupuesto Anual': lambda x: fmt_eur(x) if pd.notna(x) else ""}),
            use_container_width=True, hide_index=True
        )

    # --- 3. Clientes sin responsable ---
    st.markdown("---")
    n3 = len(df_anom_clientes)
    st.subheader(f"🏢 Clientes sin responsable asignado ({n3})")
    if n3 == 0:
        st.success("Todos los clientes tienen responsable asignado. ✅")
    else:
        st.warning(f"{n3} clientes en la hoja CLIENTES no tienen responsable. Su facturación no aparecerá en ningún panel.")
        st.dataframe(
            df_anom_clientes.style.format({'Presupuesto Anual': lambda x: fmt_eur(x) if pd.notna(x) else ""}),
            use_container_width=True, hide_index=True
        )

    # --- 4. Recursos sin match en Carga de Trabajo ---

    st.markdown("---")
    n4 = len(recursos_sin_carga)
    st.subheader(f"📋 Recursos sin datos en Carga de Trabajo ({n4})")
    if df_carga is None:
        st.info("No hay datos de Carga de Trabajo disponibles (error de conexión a la BD).")
    elif n4 == 0:
        st.success("Todos los recursos tienen datos de carga de trabajo. ✅")
    else:
        st.warning(f"{n4} recursos del equipo no se encontraron en la Carga de Trabajo (fuzzy matching < 80%). Su número de operaciones aparecerá como 0.")
        st.dataframe(pd.DataFrame({'Recurso': recursos_sin_carga}), use_container_width=True, hide_index=True)

elif st.session_state.vista_actual == 'Cliente':
    cliente_sel = st.session_state.cliente_seleccionado
    resp_origen = st.session_state.responsable_de_cliente

    if st.button(f"⬅️ Volver a {resp_origen}"):
        st.session_state.vista_actual = 'Detalle'
        st.session_state.responsable_seleccionado = resp_origen
        st.rerun()

    df_cli = df_clientes[df_clientes[col_cliente_obj] == cliente_sel]
    if df_cli.empty:
        st.warning(f"No se encontraron datos para el cliente '{cliente_sel}'.")
    else:
        row_cli = df_cli.iloc[0]
        cli_obj_anual  = row_cli[col_presupuesto_obj]
        cli_obj_acum   = row_cli['Objetivo Acumulado']
        cli_fact       = row_cli['Facturación Acumulada']
        cli_pct        = row_cli['% Cumplimiento']
        cli_dif        = cli_fact - cli_obj_acum
        cli_color      = color_gauge(cli_pct)
        cli_pct_fmt    = f"{cli_pct:.1f}".replace('.', ',')
        cli_icono      = "🟩" if cli_pct >= 95 else "🟨" if cli_pct >= 85 else "🟧" if cli_pct >= 70 else "🟥"

        st.markdown("---")
        st.markdown(f"<h3 style='margin-bottom:0;'>🏢 {cliente_sel} &nbsp;&nbsp;|&nbsp;&nbsp; 🌡️ "
                    f"<span style='color:{cli_color};'>{cli_pct_fmt}% {cli_icono}</span></h3>",
                    unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # --- Pre-cálculo del coste proporcional del equipo para este cliente ---
        cli_coste_equipo = 0.0
        if df_carga is not None and col_cli_carga is not None:
            _lista_cli_tmp = df_carga[col_cli_carga].dropna().unique().tolist()
            _match_cli_tmp = get_best_match(cliente_sel, _lista_cli_tmp,
                                            scorer=fuzz.partial_ratio, threshold=70)
            if _match_cli_tmp:
                _df_cc_tmp = df_carga[df_carga[col_cli_carga] == _match_cli_tmp]
                _lista_eq_tmp = df_equipos[col_recurso_eq].dropna().unique().tolist()
                _cols_acum_tmp = [c for i in range(1, mes_corte) for c in df_equipos.columns if meses_str[i] in c.upper()]
                _exp_tot_tmp = df_carga.groupby(col_rec_carga)[col_exp_carga].sum().to_dict()
                for _, _cr in _df_cc_tmp.iterrows():
                    _rn = _cr[col_rec_carga]
                    _exp_c = float(_cr[col_exp_carga]) if pd.notna(_cr[col_exp_carga]) else 0.0
                    _exp_t = _exp_tot_tmp.get(_rn, 0)
                    _ratio = (_exp_c / _exp_t) if _exp_t > 0 else 0.0
                    _meq = get_best_match(str(_rn), _lista_eq_tmp)
                    if _meq:
                        _eq_r = df_equipos[df_equipos[col_recurso_eq] == _meq].iloc[0]
                        _acum = float(_eq_r[_cols_acum_tmp].sum()) if _cols_acum_tmp else float(_eq_r['COSTE_MENSUAL']) * meses_transcurridos
                        cli_coste_equipo += _acum * _ratio

        cli_dif_fmt = fmt_eur(abs(cli_dif))
        _dc = "#cc0000" if cli_dif < 0 else "#00b300"
        _da = "↓" if cli_dif < 0 else "↑"
        _dv = f"-{cli_dif_fmt}" if cli_dif < 0 else cli_dif_fmt

        cli_peso_pct = (cli_coste_equipo / cli_fact * 100) if cli_fact > 0 else 0.0
        cli_peso_fmt = f"{cli_peso_pct:.1f}".replace('.', ',')

        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(html_metric("Obj. Anual", fmt_eur(cli_obj_anual)), unsafe_allow_html=True)
        c2.markdown(html_metric("Obj. Acumulado", fmt_eur(cli_obj_acum)), unsafe_allow_html=True)
        c3.markdown(html_metric("Fact. Acumulada", fmt_eur(cli_fact),
            f"<p style='font-size:0.8rem;color:{_dc};margin:0;'>{_da} {_dv}</p>"), unsafe_allow_html=True)
        c4.markdown(html_metric("Coste Equipo (proporcional)", fmt_eur(cli_coste_equipo),
            badge_peso_equipo(cli_peso_pct, cli_peso_fmt)), unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("👥 Recursos relacionados con este cliente")

        if df_carga is not None and col_cli_carga is not None:
            lista_cli_carga = df_carga[col_cli_carga].dropna().unique().tolist()
            # Usar partial_ratio con umbral 70: maneja typos y nombres con palabras extra
            # (ej. "volkswagen" matchea con "vollkswagen Financial services")
            match_cli_carga = get_best_match(cliente_sel, lista_cli_carga,
                                             scorer=fuzz.partial_ratio, threshold=70)

            if match_cli_carga:
                df_carga_cli = df_carga[df_carga[col_cli_carga] == match_cli_carga]
                lista_eq_all = df_equipos[col_recurso_eq].dropna().unique().tolist()
                _cols_acum = [c for i in range(1, mes_corte) for c in df_equipos.columns if meses_str[i] in c.upper()]

                # Expedientes totales por recurso (en todos los clientes) para calcular proporciones
                exp_totales_por_recurso = df_carga.groupby(col_rec_carga)[col_exp_carga].sum().to_dict()

                rows_rec = []
                for _, cr in df_carga_cli.iterrows():
                    rec_name = cr[col_rec_carga]
                    exp_cli  = int(cr[col_exp_carga]) if pd.notna(cr[col_exp_carga]) else 0

                    # Proporción: expedientes en este cliente / expedientes totales del recurso
                    exp_total_rec = exp_totales_por_recurso.get(rec_name, 0)
                    ratio = (exp_cli / exp_total_rec) if exp_total_rec > 0 else 0.0

                    match_eq = get_best_match(str(rec_name), lista_eq_all)
                    if match_eq:
                        eq_row     = df_equipos[df_equipos[col_recurso_eq] == match_eq].iloc[0]
                        coste_mens_total = float(eq_row['COSTE_MENSUAL'])
                        coste_acum_total = float(eq_row[_cols_acum].sum()) if _cols_acum else coste_mens_total * meses_transcurridos
                        # Aplicar proporción
                        coste_mens = coste_mens_total * ratio
                        coste_acum = coste_acum_total * ratio
                    else:
                        coste_mens = coste_acum = 0.0
                    rows_rec.append({'Recurso': rec_name, 'Expedientes': exp_cli,
                                     'Exp. Totales Recurso': exp_total_rec,
                                     '% s/Total Recurso': ratio * 100,
                                     'Coste Mensual': coste_mens, 'Coste Acumulado': coste_acum})

                if rows_rec:
                    df_rec_cli = pd.DataFrame(rows_rec).sort_values('Coste Acumulado', ascending=False)

                    # % peso de cada recurso en el cliente según expedientes (sobre el total del cliente)
                    total_exp = df_rec_cli['Expedientes'].sum()
                    df_rec_cli['% s/Expedientes'] = (
                        df_rec_cli['Expedientes'] / total_exp * 100
                        if total_exp > 0 else 0.0
                    )

                    # Fila de totales (la proporción no se suma, se deja en blanco)
                    total_row = {
                        'Recurso':               'TOTAL',
                        'Expedientes':           int(df_rec_cli['Expedientes'].sum()),
                        'Exp. Totales Recurso':  '',
                        '% s/Total Recurso':     float('nan'),
                        '% s/Expedientes':       df_rec_cli['% s/Expedientes'].sum(),
                        'Coste Mensual':         df_rec_cli['Coste Mensual'].sum(),
                        'Coste Acumulado':       df_rec_cli['Coste Acumulado'].sum(),
                    }
                    df_rec_cli = pd.concat([df_rec_cli, pd.DataFrame([total_row])], ignore_index=True)

                    fmt_rec = {
                        'Coste Mensual':       lambda x: fmt_eur(x),
                        'Coste Acumulado':     lambda x: fmt_eur(x),
                        'Expedientes':         lambda x: f"{int(x):,}".replace(',', '.'),
                        'Exp. Totales Recurso': lambda x: f"{int(x):,}".replace(',', '.') if pd.notna(x) and x != '' else '',
                        '% s/Total Recurso':   lambda x: f"{x:.1f}%".replace('.', ',') if pd.notna(x) else '',
                        '% s/Expedientes':     lambda x: f"{x:.1f}%".replace('.', ','),
                    }

                    cols_rec_display = ['Recurso', 'Expedientes', 'Exp. Totales Recurso', '% s/Total Recurso', '% s/Expedientes', 'Coste Mensual', 'Coste Acumulado']
                    _idx_exp = cols_rec_display.index('Exp. Totales Recurso')

                    def _style_table(row):
                        is_total = row['Recurso'] == 'TOTAL'
                        base = 'font-weight:bold;background-color:#f0f0f0;' if is_total else ''
                        result = [base] * len(row)
                        result[_idx_exp] = base + 'text-align:right'
                        return result

                    st.caption("ℹ️ El **Coste Mensual** y **Coste Acumulado** son proporcionales a los expedientes del recurso en este cliente respecto a su total de expedientes (columna *% s/Total Recurso*).")
                    styled_rec = (df_rec_cli[cols_rec_display]
                                  .style.format(fmt_rec)
                                  .apply(_style_table, axis=1))
                    st.dataframe(styled_rec, use_container_width=True, hide_index=True)
                else:
                    st.info("No se encontraron recursos para este cliente en la Carga de Trabajo.")
            else:
                st.info(f"No se encontraron datos de Carga de Trabajo para '{cliente_sel}'.")
        else:
            st.info("Carga el Excel de Carga de Trabajo para ver los recursos asociados al cliente.")
