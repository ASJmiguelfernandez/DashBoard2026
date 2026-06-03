# CLAUDE.md — Comparador de Excels / Cuadro de Mandos "Acuerdo Servicios Jurídicos"

Guía de contexto para cualquier sesión de Claude que trabaje en este proyecto.
Escribe y conversa en **español**.

## Qué es

Aplicación web interna (**cuadro de mandos**) para Acuerdo Servicios Jurídicos (ASJ).
Cruza datos de **objetivos/facturación** (Excels) con la **carga de trabajo** (SQL Server)
para mostrar el estado por responsable, cliente y recurso, detectar anomalías y
visualizar el cumplimiento de presupuesto.

Originalmente desarrollada con la herramienta **Antigravity** (Google); ahora se continúa con Claude.

## Stack

- **Python 3.12** + **Streamlit** (interfaz web).
- **pandas** (datos), **openpyxl** (lectura de Excel).
- **plotly** (gráficos), **thefuzz** + **python-Levenshtein** (emparejado aproximado de nombres).
- **pyodbc** → **SQL Server** (driver `ODBC Driver 17 for SQL Server`).

> ⚠️ Está instalado **pandas 3.0.x** en el venv; la app se escribió pensada para pandas 2.x.
> Vigilar posibles incompatibilidades (`pd.read_sql`, tipos, etc.).

## Estructura

- `app.py` — **toda la aplicación** (≈64 KB, un único archivo). Login, sidebar, vistas y lógica.
- `requirements.txt` — dependencias.
- `.streamlit/secrets.toml` — credenciales (SQL Server y usuarios). **NO subir al repo** (gitignored).
- `logo-login.png`, `logo-acuerdo.svg` — recursos gráficos.
- Scripts de apoyo (no forman parte de la app en producción):
  - `generar_mock.py` — genera datos de prueba.
  - `read_excel_structure.py` / `explorar_bd.py` — inspección de Excels / BD.
  - `test_*.py` — pruebas de parsing.

## Cómo arrancar (local, Windows)

```powershell
cd C:\Proyectos\comparador_excels
# Primera vez:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Arrancar:
.\.venv\Scripts\streamlit run app.py
```
App en **http://localhost:8501**. Pantalla inicial: **login**.

## Datos de entrada

### SQL Server (carga de trabajo y login)
- Conexión configurada en `.streamlit/secrets.toml`, sección `[sqlserver]`
  (`server`, `database`, `username`, `password`).
- Carga de trabajo: tabla `ACUE_SALDO` + joins con `ACUE_GESTORES_COLABORADORES`,
  `ACUE_ENTIDAD_DEUDA_SERVICIO`, `ACUE_ENTIDAD_DEUDA` (ver `cargar_carga_desde_sql()`).
- Login: valida contra tabla `CDM_Usuarios`; fallback a usuarios definidos en `secrets.toml` (`[usuarios]`).

### Ficheros Excel en red (`\\asjdc.asj.land\ASJ\Aplicaciones\AppCuadroDeMandos`)
- `OBJETIVOSyEQUIPOS.xlsx` — objetivos y equipos.
- `FACTURAS ASJ de 2019 a 2026.xlsx` — facturación.
- `NomenclaturaFacturacionVersusCargaTrabajo.xlsx` — mapeo nombres de clientes.
- `NomenclaturaRecursosVersusCargaTrabajo.xlsx` — mapeo nombres de recursos.
- Si la ruta de red no está disponible, hay carga manual de Excels desde el sidebar.

## Funcionalidad principal (vistas)

- **Vista Global** — resumen general de facturación vs objetivo.
- **Estado por Responsable** — métricas y gráficos por responsable.
- **Resumen por Responsable** — detalle tabular.
- **Informe de Anomalías** — facturas sin cliente, recursos sin responsable,
  clientes sin responsable, recursos sin datos de carga de trabajo.
- Sidebar: selección de meses, año de análisis, divisor de presupuesto, estado de ficheros.

Lógica clave: emparejado difuso de nombres (`get_best_match`, `match_recurso_en_carga`,
`match_cliente_en_carga`) porque los nombres no coinciden exactamente entre Excel y BD.

## Despliegue / producción

- Ruta de producción conocida: `\\172.16.128.203\miguel.fernandez\comparador_excels`.
- Carpeta de trabajo (desarrollo): `C:\Proyectos\comparador_excels`.
- **No editar directamente producción**; desarrollar en local y desplegar después.

## Git

- Repositorio con remoto `origin` (rama `main`).
- `.gitignore` excluye: `secrets.toml`, Excels reales (`*.xlsx/*.xls/*.csv`),
  `__pycache__`, entornos virtuales y scripts de test.

## Convenciones para trabajar aquí

- Responder y comentar el código en **español**.
- La app es un único `app.py` muy grande: al editar, localizar la sección con búsqueda
  y hacer cambios acotados.
- Al añadir dependencias, actualizar `requirements.txt`.
- No exponer ni subir credenciales (`secrets.toml`).
