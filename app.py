# -*- coding: utf-8 -*-
"""
app.py - Aplicación Streamlit para estadísticas de Voleibol
Sistema de informes interactivo para el club
VERSIÓN 2: Con análisis de rotaciones, distribución colocador y errores
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import create_engine, text
import os

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Colores del club
COLOR_ROJO = "#C8102E"
COLOR_BLANCO = "#FFFFFF"
COLOR_NEGRO = "#000000"
COLOR_AMARILLO = "#F4D000"
COLOR_GRIS = "#F2F2F2"
COLOR_VERDE = "#4CAF50"
COLOR_NARANJA = "#FF9800"

# Configuración de página
st.set_page_config(
    page_title="🏐 Voleibol Stats",
    page_icon="🏐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado con colores del club
st.markdown(f"""
<style>
    .main-header {{
        background: linear-gradient(90deg, {COLOR_ROJO} 0%, #8B0000 100%);
        padding: 1rem 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }}
    .main-header h1 {{
        color: {COLOR_BLANCO};
        margin: 0;
        font-size: 2rem;
    }}
    .stat-card {{
        background: {COLOR_BLANCO};
        border-left: 4px solid {COLOR_ROJO};
        padding: 1rem;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    .metric-good {{ color: {COLOR_VERDE}; font-weight: bold; }}
    .metric-warning {{ color: {COLOR_NARANJA}; font-weight: bold; }}
    .metric-bad {{ color: {COLOR_ROJO}; font-weight: bold; }}
    .stSelectbox label {{ font-weight: bold; }}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# CONEXIÓN A BASE DE DATOS
# =============================================================================

@st.cache_resource
def get_engine():
    """Crea conexión a la base de datos"""
    # Usar secrets de Streamlit Cloud si existen
    if "database" in st.secrets:
        return create_engine(st.secrets["database"]["url"])
    else:
        # Fallback para desarrollo local
        return create_engine(
            "postgresql+psycopg2://postgres:navi6573@localhost:5432/voleibol"
        )

def get_connection():
    """Obtiene una conexión activa"""
    return get_engine().connect()

# =============================================================================
# FUNCIONES DE DATOS
# =============================================================================

@st.cache_data(ttl=300)
def cargar_equipos():
    """Carga lista de equipos"""
    with get_engine().connect() as conn:
        df = pd.read_sql(text("""
            SELECT id, nombre, equipo_letra 
            FROM equipos 
            ORDER BY nombre, equipo_letra
        """), conn)
        df['nombre_completo'] = df.apply(
            lambda x: f"{x['nombre']} {x['equipo_letra']}" if x['equipo_letra'] else x['nombre'], 
            axis=1
        )
        return df

@st.cache_data(ttl=300)
def cargar_temporadas():
    """Carga lista de temporadas"""
    with get_engine().connect() as conn:
        return pd.read_sql(text("""
            SELECT id, nombre, activa 
            FROM temporadas 
            ORDER BY nombre DESC
        """), conn)

@st.cache_data(ttl=300)
def cargar_fases(temporada_id):
    """Carga fases de una temporada"""
    with get_engine().connect() as conn:
        return pd.read_sql(text("""
            SELECT id, nombre 
            FROM fases 
            WHERE temporada_id = :tid
            ORDER BY nombre
        """), conn, params={"tid": temporada_id})

@st.cache_data(ttl=300)
def cargar_partidos(equipo_id, temporada_id, fase_id=None):
    """Carga partidos según filtros"""
    with get_engine().connect() as conn:
        query = """
            SELECT 
                p.id, 
                p.rival, 
                p.local,
                p.fecha,
                p.resultado,
                f.nombre as fase
            FROM partidos_new p
            LEFT JOIN fases f ON p.fase_id = f.id
            WHERE p.equipo_id = :eid AND p.temporada_id = :tid
        """
        params = {"eid": equipo_id, "tid": temporada_id}
        
        if fase_id:
            query += " AND p.fase_id = :fid"
            params["fid"] = fase_id
        
        query += " ORDER BY p.fecha DESC, p.id DESC"
        
        return pd.read_sql(text(query), conn, params=params)

@st.cache_data(ttl=300)
def cargar_jugadores(equipo_id):
    """Carga jugadores de un equipo"""
    with get_engine().connect() as conn:
        df = pd.read_sql(text("""
            SELECT id, apellido, nombre, dorsal, posicion
            FROM jugadores
            WHERE equipo_id = :eid AND activo = true
            ORDER BY apellido
        """), conn, params={"eid": equipo_id})
        
        # Crear nombre completo en formato "Nombre Apellido"
        df['nombre_completo'] = df.apply(
            lambda x: f"{x['nombre']} {x['apellido']}" if x['nombre'] else x['apellido'],
            axis=1
        )
        return df

@st.cache_data(ttl=60)
def obtener_estadisticas_partido(partido_id):
    """Obtiene estadísticas completas de un partido"""
    with get_engine().connect() as conn:
        # Estadísticas por jugador y tipo de acción
        df = pd.read_sql(text("""
            SELECT 
                j.apellido as jugador,
                j.id as jugador_id,
                a.tipo_accion,
                a.marca,
                COUNT(*) as cantidad
            FROM acciones_new a
            JOIN jugadores j ON a.jugador_id = j.id
            WHERE a.partido_id = :pid
            GROUP BY j.apellido, j.id, a.tipo_accion, a.marca
            ORDER BY j.apellido, a.tipo_accion
        """), conn, params={"pid": partido_id})
        
        return df

@st.cache_data(ttl=60)
def obtener_resumen_acciones(partido_id):
    """Obtiene resumen de todas las acciones del partido"""
    with get_engine().connect() as conn:
        df = pd.read_sql(text("""
            SELECT 
                tipo_accion,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE marca = '#') as puntos,
                COUNT(*) FILTER (WHERE marca = '+') as positivos,
                COUNT(*) FILTER (WHERE marca = '!') as neutros,
                COUNT(*) FILTER (WHERE marca = '-') as negativos,
                COUNT(*) FILTER (WHERE marca = '/') as errores_forzados,
                COUNT(*) FILTER (WHERE marca = '=') as errores
            FROM acciones_new
            WHERE partido_id = :pid
            GROUP BY tipo_accion
            ORDER BY tipo_accion
        """), conn, params={"pid": partido_id})
        
        # Calcular eficacia y eficiencia
        df['eficacia'] = ((df['puntos'] + df['positivos']) / df['total'] * 100).round(1)
        df['eficiencia'] = ((df['puntos'] - df['errores']) / df['total'] * 100).round(1)
        
        return df

@st.cache_data(ttl=60)
def obtener_resumen_acciones_multi(partido_ids):
    """Obtiene resumen de todas las acciones de múltiples partidos"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                tipo_accion,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE marca = '#') as puntos,
                COUNT(*) FILTER (WHERE marca = '+') as positivos,
                COUNT(*) FILTER (WHERE marca = '!') as neutros,
                COUNT(*) FILTER (WHERE marca = '-') as negativos,
                COUNT(*) FILTER (WHERE marca = '/') as errores_forzados,
                COUNT(*) FILTER (WHERE marca = '=') as errores
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            GROUP BY tipo_accion
            ORDER BY tipo_accion
        """), conn)
        
        # Calcular eficacia y eficiencia
        df['eficacia'] = ((df['puntos'] + df['positivos']) / df['total'] * 100).round(1)
        df['eficiencia'] = ((df['puntos'] - df['errores']) / df['total'] * 100).round(1)
        
        return df

@st.cache_data(ttl=60)
def obtener_estadisticas_jugadores_partido(partido_ids):
    """Obtiene estadísticas detalladas por jugador para un partido"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                CASE 
                    WHEN j.nombre IS NOT NULL AND j.nombre != '' 
                    THEN j.nombre || ' ' || j.apellido 
                    ELSE j.apellido 
                END AS jugador,
                a.tipo_accion,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE a.marca = '#') as puntos,
                COUNT(*) FILTER (WHERE a.marca = '+') as positivos,
                COUNT(*) FILTER (WHERE a.marca = '!') as neutros,
                COUNT(*) FILTER (WHERE a.marca = '-') as negativos,
                COUNT(*) FILTER (WHERE a.marca = '/') as errores_forzados,
                COUNT(*) FILTER (WHERE a.marca = '=') as errores
            FROM acciones_new a
            JOIN jugadores j ON a.jugador_id = j.id
            WHERE a.partido_id IN ({ids_str})
            AND a.tipo_accion IN ('atacar', 'recepción', 'saque', 'bloqueo')
            GROUP BY j.nombre, j.apellido, a.tipo_accion
            ORDER BY j.apellido, a.tipo_accion
        """), conn)
        
        if not df.empty:
            df['eficacia'] = ((df['puntos'] + df['positivos']) / df['total'] * 100).round(1)
            df['eficiencia'] = ((df['puntos'] - df['errores']) / df['total'] * 100).round(1)
        
        return df

@st.cache_data(ttl=60)
def obtener_estadisticas_jugador(partido_ids, jugador_id):
    """Obtiene estadísticas de un jugador para varios partidos"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                tipo_accion,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE marca = '#') as puntos,
                COUNT(*) FILTER (WHERE marca = '+') as positivos,
                COUNT(*) FILTER (WHERE marca = '!') as neutros,
                COUNT(*) FILTER (WHERE marca = '-') as negativos,
                COUNT(*) FILTER (WHERE marca = '/') as errores_forzados,
                COUNT(*) FILTER (WHERE marca = '=') as errores
            FROM acciones_new
            WHERE partido_id IN ({ids_str}) AND jugador_id = :jid
            GROUP BY tipo_accion
            ORDER BY tipo_accion
        """), conn, params={"jid": jugador_id})
        
        if not df.empty:
            df['eficacia'] = ((df['puntos'] + df['positivos']) / df['total'] * 100).round(1)
            df['eficiencia'] = ((df['puntos'] - df['errores']) / df['total'] * 100).round(1)
        
        return df

@st.cache_data(ttl=60)
def obtener_evolucion_jugador(partido_ids, jugador_id):
    """Obtiene la evolución del jugador partido a partido"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                p.id as partido_id,
                p.rival,
                p.local,
                p.fecha,
                a.tipo_accion,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE a.marca = '#') as puntos,
                COUNT(*) FILTER (WHERE a.marca = '+') as positivos,
                COUNT(*) FILTER (WHERE a.marca = '=') as errores
            FROM acciones_new a
            JOIN partidos_new p ON a.partido_id = p.id
            WHERE a.partido_id IN ({ids_str}) AND a.jugador_id = :jid
            GROUP BY p.id, p.rival, p.local, p.fecha, a.tipo_accion
            ORDER BY p.fecha, p.id
        """), conn, params={"jid": jugador_id})
        
        if not df.empty:
            df['eficacia'] = ((df['puntos'] + df['positivos']) / df['total'] * 100).round(1)
            df['eficiencia'] = ((df['puntos'] - df['errores']) / df['total'] * 100).round(1)
            df['partido_display'] = df.apply(
                lambda x: f"vs {x['rival']} ({'L' if x['local'] else 'V'})", axis=1
            )
        
        return df

@st.cache_data(ttl=60)
def obtener_media_equipo(partido_ids):
    """Obtiene la media del equipo para comparar con jugador individual"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                tipo_accion,
                ROUND((COUNT(*) FILTER (WHERE marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 1) as eficacia_media,
                ROUND(((COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))::decimal / NULLIF(COUNT(*),0))*100, 1) as eficiencia_media
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND tipo_accion IN ('atacar', 'recepción', 'saque', 'bloqueo')
            GROUP BY tipo_accion
        """), conn)
        
        return df

@st.cache_data(ttl=60)
def obtener_ranking_equipo(partido_ids, tipo_accion):
    """Obtiene el ranking de jugadores del equipo para una acción específica"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                j.id as jugador_id,
                CASE 
                    WHEN j.nombre IS NOT NULL AND j.nombre != '' 
                    THEN j.nombre || ' ' || j.apellido 
                    ELSE j.apellido 
                END AS jugador,
                COUNT(*) as total,
                ROUND((COUNT(*) FILTER (WHERE a.marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 1) as eficacia
            FROM acciones_new a
            JOIN jugadores j ON a.jugador_id = j.id
            WHERE a.partido_id IN ({ids_str})
            AND a.tipo_accion = :tipo
            GROUP BY j.id, j.nombre, j.apellido
            HAVING COUNT(*) >= 5
            ORDER BY eficacia DESC
        """), conn, params={"tipo": tipo_accion})
        
        if not df.empty:
            df['ranking'] = range(1, len(df) + 1)
        
        return df

@st.cache_data(ttl=60)
def obtener_sideout_contraataque(partido_ids):
    """Obtiene estadísticas de side-out vs contraataque"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            WITH acciones_ordenadas AS (
                SELECT 
                    id,
                    tipo_accion,
                    marca,
                    partido_id,
                    LAG(tipo_accion) OVER (PARTITION BY partido_id ORDER BY id) as accion_previa,
                    LAG(tipo_accion, 2) OVER (PARTITION BY partido_id ORDER BY id) as accion_previa_2
                FROM acciones_new
                WHERE partido_id IN ({ids_str})
                AND tipo_accion IN ('recepción', 'atacar', 'colocación')
            ),
            ataques_clasificados AS (
                SELECT 
                    marca,
                    CASE 
                        WHEN tipo_accion = 'atacar' AND accion_previa = 'recepción' THEN 'Side-out'
                        WHEN tipo_accion = 'atacar' AND accion_previa = 'colocación' AND accion_previa_2 = 'recepción' THEN 'Side-out'
                        WHEN tipo_accion = 'atacar' THEN 'Contraatac'
                        ELSE NULL
                    END AS fase
                FROM acciones_ordenadas
                WHERE tipo_accion = 'atacar'
            )
            SELECT 
                fase,
                COUNT(*) AS total,
                ROUND((COUNT(*) FILTER (WHERE marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficacia,
                ROUND(((COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficiencia
            FROM ataques_clasificados
            WHERE fase IS NOT NULL
            GROUP BY fase
            ORDER BY fase DESC
        """), conn)
        
        return df

@st.cache_data(ttl=60)
def obtener_top_jugadores(partido_ids):
    """Obtiene ranking de jugadores por puntos directos"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                CASE 
                    WHEN j.nombre IS NOT NULL AND j.nombre != '' 
                    THEN j.nombre || ' ' || j.apellido 
                    ELSE j.apellido 
                END AS jugador,
                COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar' AND a.marca = '#') AS ataque,
                COUNT(*) FILTER (WHERE a.tipo_accion = 'saque' AND a.marca = '#') AS saque,
                COUNT(*) FILTER (WHERE a.tipo_accion = 'bloqueo' AND a.marca = '#') AS bloqueo,
                COUNT(*) FILTER (WHERE a.marca = '#' AND a.tipo_accion IN ('atacar', 'saque', 'bloqueo')) AS total
            FROM acciones_new a
            JOIN jugadores j ON a.jugador_id = j.id
            WHERE a.partido_id IN ({ids_str})
            AND a.tipo_accion IN ('atacar', 'saque', 'bloqueo')
            AND a.marca = '#'
            GROUP BY j.nombre, j.apellido
            HAVING COUNT(*) > 0
            ORDER BY total DESC
            LIMIT 10
        """), conn)
        
        return df

@st.cache_data(ttl=60)
def obtener_distribucion_colocador(partido_ids):
    """Obtiene distribución de colocaciones por zona"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            WITH total_ataques AS (
                SELECT COUNT(*) as total
                FROM acciones_new
                WHERE partido_id IN ({ids_str})
                AND tipo_accion = 'atacar'
                AND zona_jugador IS NOT NULL
            )
            SELECT 
                UPPER(zona_jugador) AS zona,
                COUNT(*) as colocaciones,
                ROUND((COUNT(*)::decimal / NULLIF((SELECT total FROM total_ataques), 0)) * 100, 1) as porcentaje,
                ROUND((COUNT(*) FILTER (WHERE marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficacia
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND tipo_accion = 'atacar'
            AND zona_jugador IS NOT NULL
            GROUP BY zona_jugador
            ORDER BY colocaciones DESC
        """), conn)
        
        return df

# =============================================================================
# NUEVAS FUNCIONES DE DATOS - ANÁLISIS AVANZADO
# =============================================================================

@st.cache_data(ttl=60)
def obtener_ataque_por_rotacion(partido_ids):
    """Obtiene estadísticas de ataque por rotación (P1-P6)"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                UPPER(zona_colocador) AS rotacion,
                COUNT(*) AS total,
                ROUND((COUNT(*) FILTER (WHERE marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficacia,
                ROUND(((COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficiencia
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND tipo_accion = 'atacar'
            AND zona_colocador IS NOT NULL
            GROUP BY zona_colocador
            ORDER BY zona_colocador
        """), conn)
        
        return df

@st.cache_data(ttl=60)
def obtener_analisis_errores(partido_ids):
    """Obtiene análisis de errores forzados vs no forzados"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                tipo_accion,
                COUNT(*) FILTER (WHERE marca = '=' AND tipo_accion = 'defensa') AS errores_forzados,
                COUNT(*) FILTER (WHERE marca = '=' AND tipo_accion != 'defensa') +
                COUNT(*) FILTER (WHERE marca = '/' AND tipo_accion = 'bloqueo') AS errores_no_forzados,
                COUNT(*) FILTER (WHERE marca IN ('=', '/')) AS total_errores
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND marca IN ('=', '/')
            GROUP BY tipo_accion
            HAVING COUNT(*) FILTER (WHERE marca IN ('=', '/')) > 0
            ORDER BY COUNT(*) FILTER (WHERE marca IN ('=', '/')) DESC
        """), conn)
        
        if not df.empty:
            df['pct_forzados'] = (df['errores_forzados'] / df['total_errores'] * 100).round(1)
            df['pct_no_forzados'] = (df['errores_no_forzados'] / df['total_errores'] * 100).round(1)
        
        return df

@st.cache_data(ttl=60)
def obtener_errores_por_jugador(partido_ids):
    """Obtiene errores desglosados por jugador"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                CASE 
                    WHEN j.nombre IS NOT NULL AND j.nombre != '' 
                    THEN j.nombre || ' ' || j.apellido 
                    ELSE j.apellido 
                END AS jugador,
                COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar' AND a.marca = '=') AS err_ataque,
                COUNT(*) FILTER (WHERE a.tipo_accion = 'saque' AND a.marca = '=') AS err_saque,
                COUNT(*) FILTER (WHERE a.tipo_accion = 'recepción' AND a.marca = '=') AS err_recepcion,
                COUNT(*) FILTER (WHERE a.tipo_accion = 'bloqueo' AND a.marca IN ('=', '/')) AS err_bloqueo,
                COUNT(*) FILTER (WHERE a.marca IN ('=', '/')) AS total_errores
            FROM acciones_new a
            JOIN jugadores j ON a.jugador_id = j.id
            WHERE a.partido_id IN ({ids_str})
            AND a.marca IN ('=', '/')
            GROUP BY j.nombre, j.apellido
            HAVING COUNT(*) FILTER (WHERE a.marca IN ('=', '/')) > 0
            ORDER BY total_errores DESC
        """), conn)
        
        return df

@st.cache_data(ttl=60)
def obtener_jugadores_partido(partido_ids):
    """Obtiene lista de jugadores que participaron en los partidos"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT DISTINCT
                j.id,
                CASE 
                    WHEN j.nombre IS NOT NULL AND j.nombre != '' 
                    THEN j.nombre || ' ' || j.apellido 
                    ELSE j.apellido 
                END AS jugador,
                j.dorsal,
                j.posicion,
                COUNT(*) as acciones
            FROM acciones_new a
            JOIN jugadores j ON a.jugador_id = j.id
            WHERE a.partido_id IN ({ids_str})
            GROUP BY j.id, j.nombre, j.apellido, j.dorsal, j.posicion
            ORDER BY acciones DESC
        """), conn)
        
        return df

@st.cache_data(ttl=60)
def obtener_ficha_jugador(partido_ids, jugador_id):
    """Obtiene todos los datos para la ficha de un jugador"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        # Estadísticas de ataque
        ataque = conn.execute(text(f"""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE marca = '#') as puntos,
                ROUND((COUNT(*) FILTER (WHERE marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 1) as eficacia,
                ROUND(((COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))::decimal / NULLIF(COUNT(*),0))*100, 1) as eficiencia
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND jugador_id = :jid
            AND tipo_accion = 'atacar'
        """), {"jid": jugador_id}).fetchone()
        
        # Mejor rotación
        mejor_rot = conn.execute(text(f"""
            SELECT 
                UPPER(zona_colocador) as rotacion,
                COUNT(*) FILTER (WHERE marca = '#') as puntos,
                COUNT(*) as total
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND jugador_id = :jid
            AND tipo_accion = 'atacar'
            AND zona_colocador IS NOT NULL
            GROUP BY zona_colocador
            ORDER BY puntos DESC
            LIMIT 1
        """), {"jid": jugador_id}).fetchone()
        
        # Mejor zona
        mejor_zona = conn.execute(text(f"""
            SELECT 
                UPPER(zona_jugador) as zona,
                COUNT(*) FILTER (WHERE marca = '#') as puntos,
                COUNT(*) as total
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND jugador_id = :jid
            AND tipo_accion = 'atacar'
            AND zona_jugador IS NOT NULL
            GROUP BY zona_jugador
            ORDER BY puntos DESC
            LIMIT 1
        """), {"jid": jugador_id}).fetchone()
        
        # Errores principales
        errores = pd.read_sql(text(f"""
            SELECT 
                tipo_accion,
                COUNT(*) as errores
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND jugador_id = :jid
            AND (
                (tipo_accion = 'bloqueo' AND marca IN ('=', '/'))
                OR (tipo_accion != 'bloqueo' AND marca = '=')
            )
            GROUP BY tipo_accion
            ORDER BY errores DESC
            LIMIT 3
        """), conn, params={"jid": jugador_id})
        
        # Otras estadísticas
        otras = conn.execute(text(f"""
            SELECT 
                COUNT(*) FILTER (WHERE tipo_accion = 'saque' AND marca = '#') as aces,
                COUNT(*) FILTER (WHERE tipo_accion = 'bloqueo' AND marca = '#') as bloqueos,
                COUNT(*) FILTER (WHERE tipo_accion = 'recepción' AND marca IN ('#', '+')) as recepciones,
                COUNT(*) FILTER (WHERE tipo_accion IN ('atacar', 'saque', 'bloqueo') AND marca = '#') as puntos_directos
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND jugador_id = :jid
        """), {"jid": jugador_id}).fetchone()
        
        # Valoración total
        valor = conn.execute(text(f"""
            SELECT
                (
                    COUNT(*) FILTER (WHERE tipo_accion = 'atacar' AND marca = '#')
                  + COUNT(*) FILTER (WHERE tipo_accion = 'saque' AND marca = '#')
                  + COUNT(*) FILTER (WHERE tipo_accion = 'bloqueo' AND marca = '#')
                  - COUNT(*) FILTER (WHERE tipo_accion = 'recepción' AND marca = '=')
                  - COUNT(*) FILTER (WHERE tipo_accion = 'atacar' AND marca = '=')
                  - COUNT(*) FILTER (WHERE tipo_accion = 'saque' AND marca = '=')
                  - COUNT(*) FILTER (WHERE tipo_accion = 'bloqueo' AND marca = '/')
                ) AS valor_total
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND jugador_id = :jid
        """), {"jid": jugador_id}).fetchone()
        
        return {
            'ataque': {
                'total': ataque[0] if ataque else 0,
                'puntos': ataque[1] if ataque else 0,
                'eficacia': ataque[2] if ataque else 0,
                'eficiencia': ataque[3] if ataque else 0
            },
            'mejor_rotacion': {
                'nombre': mejor_rot[0] if mejor_rot else 'N/A',
                'puntos': mejor_rot[1] if mejor_rot else 0,
                'total': mejor_rot[2] if mejor_rot else 0
            },
            'mejor_zona': {
                'nombre': mejor_zona[0] if mejor_zona else 'N/A',
                'puntos': mejor_zona[1] if mejor_zona else 0,
                'total': mejor_zona[2] if mejor_zona else 0
            },
            'errores': errores,
            'otras': {
                'aces': otras[0] if otras else 0,
                'bloqueos': otras[1] if otras else 0,
                'recepciones': otras[2] if otras else 0,
                'puntos_directos': otras[3] if otras else 0
            },
            'valor_total': valor[0] if valor else 0
        }

# =============================================================================
# FUNCIONES DE VISUALIZACIÓN
# =============================================================================

def color_eficacia(valor):
    """Retorna color según eficacia"""
    if valor >= 60:
        return COLOR_VERDE
    elif valor >= 40:
        return COLOR_NARANJA
    else:
        return COLOR_ROJO

def crear_grafico_acciones(df_resumen):
    """Crea gráfico de barras de acciones"""
    fig = go.Figure()
    
    tipos = df_resumen['tipo_accion'].tolist()
    
    fig.add_trace(go.Bar(
        name='Puntos (#)',
        x=tipos,
        y=df_resumen['puntos'],
        marker_color=COLOR_VERDE
    ))
    
    fig.add_trace(go.Bar(
        name='Positivos (+)',
        x=tipos,
        y=df_resumen['positivos'],
        marker_color='#81C784'
    ))
    
    fig.add_trace(go.Bar(
        name='Neutros (!)',
        x=tipos,
        y=df_resumen['neutros'],
        marker_color=COLOR_AMARILLO
    ))
    
    fig.add_trace(go.Bar(
        name='Negativos (-)',
        x=tipos,
        y=df_resumen['negativos'],
        marker_color=COLOR_NARANJA
    ))
    
    fig.add_trace(go.Bar(
        name='Errores (=)',
        x=tipos,
        y=df_resumen['errores'],
        marker_color=COLOR_ROJO
    ))
    
    fig.update_layout(
        barmode='stack',
        title='Distribució d\'Accions',
        xaxis_title='Tipus d\'Acció',
        yaxis_title='Quantitat',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400
    )
    
    return fig

def crear_grafico_eficacia(df_resumen):
    """Crea gráfico de eficacia por acción"""
    fig = go.Figure()
    
    tipos = df_resumen['tipo_accion'].tolist()
    colores = [color_eficacia(e) for e in df_resumen['eficacia']]
    
    fig.add_trace(go.Bar(
        name='Eficàcia',
        x=tipos,
        y=df_resumen['eficacia'],
        marker_color=colores,
        text=df_resumen['eficacia'].apply(lambda x: f'{x}%'),
        textposition='outside'
    ))
    
    # Líneas de referencia
    fig.add_hline(y=60, line_dash="dash", line_color=COLOR_VERDE, 
                  annotation_text="Bo (60%)")
    fig.add_hline(y=40, line_dash="dash", line_color=COLOR_NARANJA,
                  annotation_text="Regular (40%)")
    
    fig.update_layout(
        title='Eficàcia per Tipus d\'Acció',
        xaxis_title='Tipus d\'Acció',
        yaxis_title='Eficàcia (%)',
        height=400,
        yaxis=dict(range=[0, 100])
    )
    
    return fig

def crear_grafico_sideout(df_sideout):
    """Crea gráfico de side-out vs contraataque"""
    fig = make_subplots(rows=1, cols=2, subplot_titles=['Eficàcia', 'Eficiència'])
    
    fig.add_trace(
        go.Bar(x=df_sideout['fase'], y=df_sideout['eficacia'], 
               marker_color=[COLOR_ROJO, COLOR_NEGRO],
               text=df_sideout['eficacia'].apply(lambda x: f'{x}%'),
               textposition='outside'),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(x=df_sideout['fase'], y=df_sideout['eficiencia'],
               marker_color=[COLOR_ROJO, COLOR_NEGRO],
               text=df_sideout['eficiencia'].apply(lambda x: f'{x}%'),
               textposition='outside'),
        row=1, col=2
    )
    
    fig.update_layout(
        title='Side-out vs Contraatac',
        showlegend=False,
        height=350
    )
    
    return fig

def crear_grafico_radar_jugador(df_jugador):
    """Crea gráfico radar con el perfil del jugador"""
    if df_jugador.empty:
        return None
    
    # Preparar datos para el radar
    categorias = []
    valores = []
    
    acciones_map = {
        'atacar': 'Atac',
        'saque': 'Saque',
        'recepción': 'Recepció',
        'bloqueo': 'Bloqueig',
        'defensa': 'Defensa',
        'colocación': 'Col·locació'
    }
    
    for accion, nombre in acciones_map.items():
        fila = df_jugador[df_jugador['tipo_accion'] == accion]
        if not fila.empty:
            categorias.append(nombre)
            valores.append(float(fila['eficacia'].iloc[0]))
    
    if not categorias:
        return None
    
    # Cerrar el radar
    categorias.append(categorias[0])
    valores.append(valores[0])
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=valores,
        theta=categorias,
        fill='toself',
        fillcolor=f'rgba(200, 16, 46, 0.3)',
        line_color=COLOR_ROJO,
        name='Eficàcia'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )
        ),
        title='Perfil del Jugador (Eficàcia %)',
        height=400
    )
    
    return fig

def crear_podio(df_top, titulo="🏆 Top Anotadors"):
    """Crea visualización de podio"""
    if df_top.empty:
        st.info("No hi ha dades per mostrar el podi")
        return
    
    st.subheader(titulo)
    
    # Mostrar top 3 con medallas
    cols = st.columns(3)
    medallas = ["🥇", "🥈", "🥉"]
    
    for idx, col in enumerate(cols):
        if idx < len(df_top):
            jugador = df_top.iloc[idx]
            with col:
                st.markdown(f"""
                <div style="text-align: center; padding: 1rem; 
                            background: linear-gradient(135deg, {COLOR_GRIS} 0%, white 100%);
                            border-radius: 10px; margin: 0.5rem;">
                    <h2>{medallas[idx]}</h2>
                    <h3 style="color: {COLOR_ROJO};">{jugador['jugador']}</h3>
                    <p style="font-size: 2rem; font-weight: bold;">{int(jugador['total'])} pts</p>
                    <p>🔥 {int(jugador['ataque'])} | 🎯 {int(jugador['saque'])} | 🧱 {int(jugador['bloqueo'])}</p>
                </div>
                """, unsafe_allow_html=True)

# =============================================================================
# NUEVAS FUNCIONES DE VISUALIZACIÓN - ANÁLISIS AVANZADO
# =============================================================================

def crear_grafico_rotaciones(df_rotaciones):
    """Crea gráfico de eficacia por rotación"""
    if df_rotaciones.empty:
        return None
    
    # Ordenar por rotación P1-P6
    orden = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6']
    df_rotaciones['rotacion'] = pd.Categorical(df_rotaciones['rotacion'], categories=orden, ordered=True)
    df_rotaciones = df_rotaciones.sort_values('rotacion')
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='Eficàcia',
        x=df_rotaciones['rotacion'],
        y=df_rotaciones['eficacia'],
        marker_color=COLOR_ROJO,
        text=df_rotaciones['eficacia'].apply(lambda x: f'{x}%'),
        textposition='outside'
    ))
    
    fig.add_trace(go.Bar(
        name='Eficiència',
        x=df_rotaciones['rotacion'],
        y=df_rotaciones['eficiencia'],
        marker_color=COLOR_NEGRO,
        text=df_rotaciones['eficiencia'].apply(lambda x: f'{x}%'),
        textposition='outside'
    ))
    
    fig.add_hline(y=60, line_dash="dash", line_color=COLOR_VERDE, 
                  annotation_text="Bo (60%)", annotation_position="right")
    fig.add_hline(y=40, line_dash="dash", line_color=COLOR_NARANJA,
                  annotation_text="Regular (40%)", annotation_position="right")
    
    fig.update_layout(
        title="Eficiència d'Atac per Rotació",
        xaxis_title="Rotació (Posició del Col·locador)",
        yaxis_title="%",
        barmode='group',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    return fig

def crear_grafico_distribucion_colocador(df_dist):
    """Crea visualización de distribución del colocador en formato campo 3x2"""
    if df_dist.empty:
        return None
    
    # Crear diccionario de datos por zona
    datos_zona = {}
    for _, row in df_dist.iterrows():
        zona = row['zona'].upper() if row['zona'] else 'N/A'
        datos_zona[zona] = {
            'colocaciones': row['colocaciones'],
            'porcentaje': row['porcentaje'],
            'eficacia': row['eficacia']
        }
    
    # Orden del campo: P4 P3 P2 (arriba), P5 P6 P1 (abajo)
    zonas_campo = [
        ['P4', 'P3', 'P2'],
        ['P5', 'P6', 'P1']
    ]
    
    fig = go.Figure()
    
    # Crear la cuadrícula del campo
    for fila_idx, fila in enumerate(zonas_campo):
        for col_idx, zona in enumerate(fila):
            x_pos = col_idx * 1.5  # Más espaciado horizontal
            y_pos = (1 - fila_idx) * 1.2  # Más espaciado vertical
            
            # Obtener datos de la zona
            if zona in datos_zona:
                pct = datos_zona[zona]['porcentaje']
                efic = datos_zona[zona]['eficacia']
                col_count = datos_zona[zona]['colocaciones']
            else:
                pct = 0
                efic = 0
                col_count = 0
            
            # Añadir rectángulo de zona - FONDO BLANCO
            fig.add_shape(
                type="rect",
                x0=x_pos - 0.65, y0=y_pos - 0.5,
                x1=x_pos + 0.65, y1=y_pos + 0.5,
                fillcolor=COLOR_BLANCO,
                line=dict(color=COLOR_NEGRO, width=2),
            )
            
            # Texto de la zona
            fig.add_annotation(
                x=x_pos, y=y_pos + 0.28,
                text=f"<b>{zona}</b>",
                showarrow=False,
                font=dict(size=14, color=COLOR_NEGRO)
            )
            
            # Porcentaje grande
            fig.add_annotation(
                x=x_pos, y=y_pos,
                text=f"<b>{pct}%</b>",
                showarrow=False,
                font=dict(size=22, color=COLOR_ROJO)
            )
            
            # Eficacia pequeña
            fig.add_annotation(
                x=x_pos, y=y_pos - 0.28,
                text=f"Efic: {efic}%",
                showarrow=False,
                font=dict(size=10, color=COLOR_NEGRO)
            )
    
    # Añadir indicador de red - ARRIBA DE TODO
    fig.add_shape(
        type="line",
        x0=-0.8, y0=2.0,
        x1=3.8, y1=2.0,
        line=dict(color=COLOR_NEGRO, width=4, dash="solid"),
    )
    
    fig.add_annotation(
        x=1.5, y=2.2,
        text="<b>XARXA</b>",
        showarrow=False,
        font=dict(size=12, color=COLOR_NEGRO)
    )
    
    fig.update_layout(
        title="Distribució del Col·locador per Zona",
        xaxis=dict(visible=False, range=[-1, 4]),
        yaxis=dict(visible=False, range=[-0.8, 2.5], scaleanchor="x"),
        height=450,
        showlegend=False,
        plot_bgcolor='white'
    )
    
    return fig

def crear_grafico_errores(df_errores):
    """Crea gráfico de análisis de errores"""
    if df_errores.empty:
        return None
    
    # Renombrar acciones
    nombres_cat = {
        'atacar': 'Atac',
        'recepción': 'Recepció',
        'saque': 'Saque',
        'bloqueo': 'Bloqueig',
        'defensa': 'Defensa'
    }
    df_errores['tipo_accion'] = df_errores['tipo_accion'].map(nombres_cat).fillna(df_errores['tipo_accion'])
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='Errors Forçats',
        x=df_errores['tipo_accion'],
        y=df_errores['errores_forzados'],
        marker_color=COLOR_NARANJA
    ))
    
    fig.add_trace(go.Bar(
        name='Errors No Forçats',
        x=df_errores['tipo_accion'],
        y=df_errores['errores_no_forzados'],
        marker_color=COLOR_ROJO
    ))
    
    fig.update_layout(
        title="Anàlisi d'Errors per Tipus d'Acció",
        xaxis_title="Acció",
        yaxis_title="Nombre d'Errors",
        barmode='stack',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    return fig

def crear_grafico_errores_jugador(df_errores_jug):
    """Crea gráfico de errores por jugador"""
    if df_errores_jug.empty:
        return None
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='Atac',
        x=df_errores_jug['jugador'],
        y=df_errores_jug['err_ataque'],
        marker_color=COLOR_ROJO
    ))
    
    fig.add_trace(go.Bar(
        name='Saque',
        x=df_errores_jug['jugador'],
        y=df_errores_jug['err_saque'],
        marker_color=COLOR_NARANJA
    ))
    
    fig.add_trace(go.Bar(
        name='Recepció',
        x=df_errores_jug['jugador'],
        y=df_errores_jug['err_recepcion'],
        marker_color=COLOR_AMARILLO
    ))
    
    fig.add_trace(go.Bar(
        name='Bloqueig',
        x=df_errores_jug['jugador'],
        y=df_errores_jug['err_bloqueo'],
        marker_color=COLOR_NEGRO
    ))
    
    fig.update_layout(
        title="Errors per Jugador",
        xaxis_title="Jugador",
        yaxis_title="Nombre d'Errors",
        barmode='stack',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    return fig

# =============================================================================
# PÁGINAS DE LA APLICACIÓN
# =============================================================================

def pagina_inicio():
    """Página principal de bienvenida"""
    st.markdown("""
    <div class="main-header">
        <h1>🏐 Sistema d'Estadístiques de Voleibol</h1>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    ### Benvingut al sistema d'anàlisi estadístic!
    
    Utilitza el menú lateral per seleccionar el context de treball i navegar entre les diferents seccions:
    
    - **📊 Partit**: Estadístiques completes d'un partit
    - **👤 Jugador**: Anàlisi individual de jugadors
    - **📈 Comparativa**: Compara dos partits
    
    ---
    
    #### Com començar:
    1. Selecciona l'**equip** al menú lateral
    2. Selecciona la **temporada** i opcionalment la **fase**
    3. Navega a la secció que vulguis analitzar
    """)
    
    # Mostrar estadísticas rápidas si hay contexto
    if 'equipo_id' in st.session_state and st.session_state.equipo_id:
        st.markdown("---")
        st.subheader("📊 Resum ràpid")
        
        partidos = cargar_partidos(
            st.session_state.equipo_id,
            st.session_state.temporada_id,
            st.session_state.get('fase_id')
        )
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Partits", len(partidos))
        col2.metric("Equip", st.session_state.get('equipo_nombre', '-'))
        col3.metric("Temporada", st.session_state.get('temporada_nombre', '-'))

def pagina_partido():
    """Página de análisis de partido"""
    st.markdown("""
    <div class="main-header">
        <h1>📊 Informe de Partit</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Verificar contexto
    if not st.session_state.get('equipo_id') or not st.session_state.get('temporada_id'):
        st.warning("⚠️ Selecciona primer un equip i temporada al menú lateral")
        return
    
    # Cargar partidos disponibles
    partidos = cargar_partidos(
        st.session_state.equipo_id,
        st.session_state.temporada_id,
        st.session_state.get('fase_id')
    )
    
    if partidos.empty:
        st.info("No hi ha partits disponibles amb els filtres seleccionats")
        return
    
    # Selector de partido con opción "Tots els partits"
    partidos['display'] = partidos.apply(
        lambda x: f"vs {x['rival']} ({'Local' if x['local'] else 'Visitant'}) - {x.get('fase', '')}", 
        axis=1
    )
    
    opciones_partido = ["tots"] + partidos['id'].tolist()
    partido_seleccionado = st.selectbox(
        "Selecciona un partit:",
        options=opciones_partido,
        format_func=lambda x: f"📊 Tots els partits ({len(partidos)})" if x == "tots"
            else partidos[partidos['id'] == x]['display'].iloc[0]
    )
    
    # Determinar qué partidos analizar
    if partido_seleccionado == "tots":
        partido_ids = partidos['id'].tolist()
        titulo_partido = f"Resum de {len(partido_ids)} partits"
        info_extra = f"**Partits analitzats:** {len(partido_ids)}"
    else:
        partido_ids = [partido_seleccionado]
        info_partido = partidos[partidos['id'] == partido_seleccionado].iloc[0]
        titulo_partido = f"vs {info_partido['rival']}"
        info_extra = f"""**Tipus:** {'Local' if info_partido['local'] else 'Visitant'} | 
        **Fase:** {info_partido.get('fase', '-')} |
        **Resultat:** {info_partido.get('resultado', '-')}"""
    
    st.markdown(f"### 🏐 {titulo_partido}")
    st.markdown(info_extra)
    
    st.markdown("---")
    
    # Cargar datos (usando lista de IDs)
    df_resumen = obtener_resumen_acciones_multi(partido_ids)
    df_sideout = obtener_sideout_contraataque(partido_ids)
    df_top = obtener_top_jugadores(partido_ids)
    df_rotaciones = obtener_ataque_por_rotacion(partido_ids)
    df_distribucion = obtener_distribucion_colocador(partido_ids)
    df_errores = obtener_analisis_errores(partido_ids)
    df_errores_jug = obtener_errores_por_jugador(partido_ids)
    
    # === MÉTRICAS PRINCIPALES ===
    st.subheader("📈 Resum General")
    
    cols = st.columns(4)
    
    # Ataque
    ataque = df_resumen[df_resumen['tipo_accion'] == 'atacar']
    if not ataque.empty:
        cols[0].metric(
            "🔥 Atac",
            f"{ataque['eficacia'].iloc[0]}%",
            f"Eficiència: {ataque['eficiencia'].iloc[0]}%"
        )
    
    # Recepción
    recepcion = df_resumen[df_resumen['tipo_accion'] == 'recepción']
    if not recepcion.empty:
        cols[1].metric(
            "🎯 Recepció",
            f"{recepcion['eficacia'].iloc[0]}%",
            f"Total: {recepcion['total'].iloc[0]}"
        )
    
    # Saque
    saque = df_resumen[df_resumen['tipo_accion'] == 'saque']
    if not saque.empty:
        cols[2].metric(
            "🚀 Saque",
            f"{saque['eficacia'].iloc[0]}%",
            f"Aces: {saque['puntos'].iloc[0]}"
        )
    
    # Bloqueo
    bloqueo = df_resumen[df_resumen['tipo_accion'] == 'bloqueo']
    if not bloqueo.empty:
        cols[3].metric(
            "🧱 Bloqueig",
            f"{bloqueo['eficacia'].iloc[0]}%",
            f"Punts: {bloqueo['puntos'].iloc[0]}"
        )
    
    # === TABS DE ANÁLISIS ===
    st.markdown("---")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Accions", 
        "⚔️ Side-out", 
        "🔄 Rotacions",
        "🎯 Distribució",
        "⚠️ Errors"
    ])
    
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(crear_grafico_acciones(df_resumen), use_container_width=True, config={'staticPlot': True})
        with col2:
            st.plotly_chart(crear_grafico_eficacia(df_resumen), use_container_width=True, config={'staticPlot': True})
        
        # Tabla detallada
        st.subheader("📋 Detall per Acció")
        df_display = df_resumen.rename(columns={
            'tipo_accion': 'Acció',
            'total': 'Total',
            'puntos': '#',
            'positivos': '+',
            'neutros': '!',
            'negativos': '-',
            'errores': '=',
            'eficacia': 'Eficàcia (%)',
            'eficiencia': 'Eficiència (%)'
        })
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Tabla detallada por jugador
        st.subheader("👥 Detall per Jugador")
        
        df_jugadores_stats = obtener_estadisticas_jugadores_partido(partido_ids)
        
        if not df_jugadores_stats.empty:
            # Pivotar para tener una fila por jugador con todas las acciones
            acciones = ['atacar', 'recepción', 'saque', 'bloqueo']
            nombres_cat = {'atacar': 'Atac', 'recepción': 'Recepció', 'saque': 'Saque', 'bloqueo': 'Bloqueig'}
            
            # Crear tabla pivotada
            jugadores_unicos = df_jugadores_stats['jugador'].unique()
            
            tabla_data = []
            for jugador in jugadores_unicos:
                fila = {'Jugador': jugador}
                df_jug = df_jugadores_stats[df_jugadores_stats['jugador'] == jugador]
                
                for accion in acciones:
                    df_acc = df_jug[df_jug['tipo_accion'] == accion]
                    nombre = nombres_cat[accion]
                    
                    if not df_acc.empty:
                        row = df_acc.iloc[0]
                        fila[f'{nombre}_#'] = int(row['puntos'])
                        fila[f'{nombre}_+'] = int(row['positivos'])
                        fila[f'{nombre}_!'] = int(row['neutros'])
                        fila[f'{nombre}_-'] = int(row['negativos'])
                        fila[f'{nombre}_/'] = int(row['errores_forzados'])
                        fila[f'{nombre}_='] = int(row['errores'])
                        fila[f'{nombre}_Efc'] = row['eficacia']
                        fila[f'{nombre}_Efn'] = row['eficiencia']
                    else:
                        fila[f'{nombre}_#'] = ''
                        fila[f'{nombre}_+'] = ''
                        fila[f'{nombre}_!'] = ''
                        fila[f'{nombre}_-'] = ''
                        fila[f'{nombre}_/'] = ''
                        fila[f'{nombre}_='] = ''
                        fila[f'{nombre}_Efc'] = ''
                        fila[f'{nombre}_Efn'] = ''
                
                tabla_data.append(fila)
            
            df_tabla_jugadores = pd.DataFrame(tabla_data)
            
            # Crear columnas multinivel
            columnas_multinivel = [('', 'Jugador')]
            for accion in ['Atac', 'Recepció', 'Saque', 'Bloqueig']:
                for simbolo in ['#', '+', '!', '-', '/', '=', 'Efc', 'Efn']:
                    columnas_multinivel.append((accion, simbolo))
            
            df_tabla_jugadores.columns = pd.MultiIndex.from_tuples(columnas_multinivel)
            
            # Mostrar con estilo HTML para encabezados multinivel
            st.markdown(df_tabla_jugadores.to_html(index=False), unsafe_allow_html=True)
            
            # Añadir estilo CSS para la tabla
            st.markdown("""
            <style>
            table {
                border-collapse: collapse;
                width: 100%;
                font-size: 12px;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 4px;
                text-align: center;
            }
            th {
                background-color: #C8102E;
                color: white;
            }
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            </style>
            """, unsafe_allow_html=True)
        else:
            st.info("No hi ha dades de jugadors")
    
    with tab2:
        if not df_sideout.empty:
            st.plotly_chart(crear_grafico_sideout(df_sideout), use_container_width=True, config={'staticPlot': True})
            
            # Tabla side-out
            col1, col2 = st.columns(2)
            for idx, row in df_sideout.iterrows():
                target_col = col1 if row['fase'] == 'Side-out' else col2
                with target_col:
                    st.markdown(f"""
                    <div style="background: {COLOR_GRIS}; padding: 1rem; border-radius: 10px; text-align: center;">
                        <h3>{row['fase']}</h3>
                        <p><strong>Total:</strong> {row['total']} atacs</p>
                        <p><strong>Eficàcia:</strong> {row['eficacia']}%</p>
                        <p><strong>Eficiència:</strong> {row['eficiencia']}%</p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No hi ha dades de side-out/contraatac")
    
    with tab3:
        st.subheader("🔄 Anàlisi per Rotació")
        if not df_rotaciones.empty:
            st.plotly_chart(crear_grafico_rotaciones(df_rotaciones), use_container_width=True, config={'staticPlot': True})
            
            # Tabla de rotaciones
            st.subheader("📋 Detall per Rotació")
            df_rot_display = df_rotaciones.rename(columns={
                'rotacion': 'Rotació',
                'total': 'Total Atacs',
                'eficacia': 'Eficàcia (%)',
                'eficiencia': 'Eficiència (%)'
            })
            st.dataframe(df_rot_display, use_container_width=True, hide_index=True)
            
            # Mejor y peor rotación
            mejor = df_rotaciones.loc[df_rotaciones['eficacia'].idxmax()]
            peor = df_rotaciones.loc[df_rotaciones['eficacia'].idxmin()]
            
            col1, col2 = st.columns(2)
            with col1:
                st.success(f"✅ **Millor rotació:** {mejor['rotacion']} ({mejor['eficacia']}% eficàcia)")
            with col2:
                st.error(f"⚠️ **Pitjor rotació:** {peor['rotacion']} ({peor['eficacia']}% eficàcia)")
        else:
            st.info("No hi ha dades de rotacions")
    
    with tab4:
        st.subheader("🎯 Distribució del Col·locador")
        if not df_distribucion.empty:
            st.plotly_chart(crear_grafico_distribucion_colocador(df_distribucion), use_container_width=True, config={'staticPlot': True})
            
            # Tabla de distribución
            st.subheader("📋 Detall per Zona")
            df_dist_display = df_distribucion.rename(columns={
                'zona': 'Zona',
                'colocaciones': 'Col·locacions',
                'porcentaje': '% Total',
                'eficacia': 'Eficàcia Atac (%)'
            })
            st.dataframe(df_dist_display, use_container_width=True, hide_index=True)
            
            # Análisis de equilibrio
            max_zona = df_distribucion.loc[df_distribucion['porcentaje'].idxmax()]
            st.info(f"📊 **Zona més utilitzada:** {max_zona['zona']} ({max_zona['porcentaje']}% del total)")
            
            if max_zona['porcentaje'] > 30:
                st.warning("⚠️ Alta dependència d'una zona. Considera diversificar la distribució.")
        else:
            st.info("No hi ha dades de distribució")
    
    with tab5:
        st.subheader("⚠️ Anàlisi d'Errors")
        if not df_errores.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.plotly_chart(crear_grafico_errores(df_errores), use_container_width=True, config={'staticPlot': True})
            
            with col2:
                if not df_errores_jug.empty:
                    st.plotly_chart(crear_grafico_errores_jugador(df_errores_jug), use_container_width=True, config={'staticPlot': True})
            
            # Tabla de errores por jugador
            st.subheader("📋 Errors per Jugador")
            df_err_display = df_errores_jug.rename(columns={
                'jugador': 'Jugador',
                'err_ataque': 'Atac',
                'err_saque': 'Saque',
                'err_recepcion': 'Recepció',
                'err_bloqueo': 'Bloqueig',
                'total_errores': 'Total'
            })
            st.dataframe(df_err_display, use_container_width=True, hide_index=True)
            
            # Resumen
            total_errores = df_errores['total_errores'].sum()
            st.metric("Total Errors", total_errores)
        else:
            st.info("No hi ha dades d'errors")
    
    # === RANKINGS ===
    st.markdown("---")
    crear_podio(df_top, "🏆 Top Anotadors")
    
    if not df_top.empty:
        with st.expander("📋 Veure detall complet"):
            st.dataframe(df_top.rename(columns={
                'jugador': 'Jugador',
                'ataque': 'Atac',
                'saque': 'Saque',
                'bloqueo': 'Bloqueig',
                'total': 'Total'
            }), use_container_width=True, hide_index=True)
    
    # === JUGADORES DEL PARTIDO ===
    st.markdown("---")
    st.subheader("👥 Jugadors Participants")
    
    df_jugadores_partido = obtener_jugadores_partido(partido_ids)
    
    if not df_jugadores_partido.empty:
        # Mostrar en formato más visual
        cols = st.columns(4)
        for idx, row in df_jugadores_partido.iterrows():
            col_idx = idx % 4
            with cols[col_idx]:
                dorsal_str = f"#{row['dorsal']}" if row['dorsal'] else ""
                posicion_str = f"({row['posicion']})" if row['posicion'] else ""
                st.markdown(f"""
                <div style="background: {COLOR_GRIS}; padding: 0.5rem; border-radius: 5px; margin: 0.25rem 0; text-align: center;">
                    <strong>{row['jugador']}</strong> {dorsal_str}<br>
                    <small>{posicion_str} - {row['acciones']} accions</small>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No hi ha dades de jugadors")

def pagina_jugador():
    """Página de análisis de jugador"""
    st.markdown("""
    <div class="main-header">
        <h1>👤 Informe de Jugador</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Verificar contexto
    if not st.session_state.get('equipo_id') or not st.session_state.get('temporada_id'):
        st.warning("⚠️ Selecciona primer un equip i temporada al menú lateral")
        return
    
    # Cargar jugadores
    jugadores = cargar_jugadores(st.session_state.equipo_id)
    
    if jugadores.empty:
        st.info("No hi ha jugadors en aquest equip")
        return
    
    # Selector de jugador
    col1, col2 = st.columns([2, 1])
    
    with col1:
        jugador_options = [None] + jugadores['id'].tolist()
        jugador_id = st.selectbox(
            "Selecciona un jugador:",
            options=jugador_options,
            format_func=lambda x: "Selecciona un jugador..." if x is None
                else f"{jugadores[jugadores['id'] == x]['nombre_completo'].iloc[0]} (#{jugadores[jugadores['id'] == x]['dorsal'].iloc[0] or '-'})"
        )
    
    with col2:
        # Opción: todos los partidos o uno específico
        partidos = cargar_partidos(
            st.session_state.equipo_id,
            st.session_state.temporada_id,
            st.session_state.get('fase_id')
        )
        
        partidos['display'] = partidos.apply(
            lambda x: f"vs {x['rival']} ({'L' if x['local'] else 'V'})", axis=1
        )
        
        opciones_partido = ["Tots els partits"] + partidos['id'].tolist()
        partido_seleccionado = st.selectbox(
            "Partit:",
            options=opciones_partido,
            format_func=lambda x: "Tots els partits" if x == "Tots els partits" 
                else partidos[partidos['id'] == x]['display'].iloc[0]
        )
    
    if jugador_id:
        jugador_info = jugadores[jugadores['id'] == jugador_id].iloc[0]
        
        st.markdown(f"""
        ### {jugador_info['nombre_completo']}
        **Dorsal:** #{jugador_info['dorsal'] or '-'} | 
        **Posició:** {jugador_info['posicion'] or '-'}
        """)
        
        st.markdown("---")
        
        # Determinar partidos a analizar
        if partido_seleccionado == "Tots els partits":
            partido_ids = partidos['id'].tolist()
            contexto_txt = f"Tots els partits ({len(partido_ids)})"
        else:
            partido_ids = [partido_seleccionado]
            info_p = partidos[partidos['id'] == partido_seleccionado].iloc[0]
            contexto_txt = f"vs {info_p['rival']}"
        
        st.caption(f"📊 Analitzant: {contexto_txt}")
        
        # Cargar estadísticas
        df_jugador = obtener_estadisticas_jugador(partido_ids, jugador_id)
        
        if df_jugador.empty:
            st.warning("No hi ha dades per aquest jugador en els partits seleccionats")
            return
        
        # === MÉTRICAS ===
        cols = st.columns(4)
        
        acciones = ['atacar', 'recepción', 'saque', 'bloqueo']
        iconos = ['🔥', '🎯', '🚀', '🧱']
        nombres = ['Atac', 'Recepció', 'Saque', 'Bloqueig']
        
        for col, accion, icono, nombre in zip(cols, acciones, iconos, nombres):
            fila = df_jugador[df_jugador['tipo_accion'] == accion]
            if not fila.empty:
                col.metric(
                    f"{icono} {nombre}",
                    f"{fila['eficacia'].iloc[0]}%",
                    f"Total: {fila['total'].iloc[0]}"
                )
            else:
                col.metric(f"{icono} {nombre}", "-", "Sense dades")
        
        # === GRÁFICOS ===
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico radar
            fig_radar = crear_grafico_radar_jugador(df_jugador)
            if fig_radar:
                st.plotly_chart(fig_radar, use_container_width=True, config={'staticPlot': True})
        
        with col2:
            # Gráfico de barras - Acciones en X, Marcas como series
            fig = go.Figure()
            
            # Renombrar acciones a catalán
            nombres_acciones = {
                'atacar': 'Atac',
                'bloqueo': 'Bloc',
                'defensa': 'Defensa',
                'recepción': 'Recepció',
                'saque': 'Saque',
                'colocación': 'Col·locació'
            }
            
            # Preparar datos por marca
            marcas = ['#', '+', '!', '-', '/', '=']
            colores_marcas = [COLOR_VERDE, '#81C784', COLOR_AMARILLO, COLOR_NARANJA, '#FF7043', COLOR_ROJO]
            campos_marcas = ['puntos', 'positivos', 'neutros', 'negativos', 'errores_forzados', 'errores']
            
            # Ordenar acciones
            df_ordenado = df_jugador.copy()
            df_ordenado['accion_cat'] = df_ordenado['tipo_accion'].map(nombres_acciones).fillna(df_ordenado['tipo_accion'])
            
            for marca, color, campo in zip(marcas, colores_marcas, campos_marcas):
                fig.add_trace(go.Bar(
                    name=marca,
                    x=df_ordenado['accion_cat'],
                    y=df_ordenado[campo],
                    marker_color=color
                ))
            
            fig.update_layout(
                title='Distribució per Marca',
                xaxis_title='Acció',
                yaxis_title='Quantitat',
                barmode='group',
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})
        
        # === TABLA DETALLADA ===
        st.subheader("📋 Estadístiques Detallades")
        
        df_display = df_jugador.rename(columns={
            'tipo_accion': 'Acció',
            'total': 'Total',
            'puntos': '#',
            'positivos': '+',
            'neutros': '!',
            'negativos': '-',
            'errores_forzados': '/',
            'errores': '=',
            'eficacia': 'Eficàcia (%)',
            'eficiencia': 'Eficiència (%)'
        })
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # === EVOLUCIÓN PERSONAL ===
        st.markdown("---")
        st.subheader("📈 Evolució Personal")
        
        # Solo mostrar si hay más de un partido
        if len(partido_ids) > 1:
            df_evolucion = obtener_evolucion_jugador(partido_ids, jugador_id)
            
            if not df_evolucion.empty:
                # Selector de acción para ver evolución
                accion_evol = st.selectbox(
                    "Selecciona acció:",
                    options=['atacar', 'recepción', 'saque', 'bloqueo'],
                    format_func=lambda x: {'atacar': 'Atac', 'recepción': 'Recepció', 'saque': 'Saque', 'bloqueo': 'Bloqueig'}[x],
                    key='evolucion_accion'
                )
                
                df_accion = df_evolucion[df_evolucion['tipo_accion'] == accion_evol]
                
                if not df_accion.empty:
                    fig = go.Figure()
                    
                    # Línea de eficacia
                    fig.add_trace(go.Scatter(
                        x=df_accion['partido_display'],
                        y=df_accion['eficacia'],
                        mode='lines+markers+text',
                        name='Eficàcia',
                        line=dict(color=COLOR_ROJO, width=3),
                        marker=dict(size=10),
                        text=df_accion['eficacia'].apply(lambda x: f'{x}%'),
                        textposition='top center'
                    ))
                    
                    # Línea de eficiencia
                    fig.add_trace(go.Scatter(
                        x=df_accion['partido_display'],
                        y=df_accion['eficiencia'],
                        mode='lines+markers+text',
                        name='Eficiència',
                        line=dict(color=COLOR_NEGRO, width=3),
                        marker=dict(size=10),
                        text=df_accion['eficiencia'].apply(lambda x: f'{x}%'),
                        textposition='bottom center'
                    ))
                    
                    # Líneas de referencia
                    fig.add_hline(y=60, line_dash="dash", line_color=COLOR_VERDE, 
                                  annotation_text="Bo (60%)")
                    fig.add_hline(y=40, line_dash="dash", line_color=COLOR_NARANJA,
                                  annotation_text="Regular (40%)")
                    
                    nombres_acciones_evol = {'atacar': 'Atac', 'recepción': 'Recepció', 'saque': 'Saque', 'bloqueo': 'Bloqueig'}
                    
                    fig.update_layout(
                        title=f"Evolució de {nombres_acciones_evol[accion_evol]}",
                        xaxis_title="Partit",
                        yaxis_title="%",
                        height=400,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                        yaxis=dict(range=[min(-10, df_accion['eficiencia'].min() - 10), 
                                         max(100, df_accion['eficacia'].max() + 10)])
                    )
                    
                    st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})
                    
                    # Indicador de tendencia
                    if len(df_accion) >= 2:
                        primera = df_accion['eficacia'].iloc[0]
                        ultima = df_accion['eficacia'].iloc[-1]
                        diferencia = ultima - primera
                        
                        if diferencia > 5:
                            st.success(f"📈 **Tendència positiva!** Has millorat un {diferencia:.1f}% en eficàcia")
                        elif diferencia < -5:
                            st.error(f"📉 **Tendència negativa.** Has baixat un {abs(diferencia):.1f}% en eficàcia")
                        else:
                            st.info(f"➡️ **Rendiment estable.** Variació de {diferencia:+.1f}%")
                else:
                    st.info(f"No hi ha dades d'aquesta acció per aquest jugador")
            else:
                st.info("No hi ha dades d'evolució")
        else:
            st.info("Selecciona 'Tots els partits' per veure l'evolució")
        
        # === COMPARATIVA AMB MITJANA DE L'EQUIP ===
        st.markdown("---")
        st.subheader("🎯 Comparativa amb l'Equip")
        
        df_media_equipo = obtener_media_equipo(partido_ids)
        
        if not df_media_equipo.empty and not df_jugador.empty:
            nombres_acc = {'atacar': 'Atac', 'recepción': 'Recepció', 'saque': 'Saque', 'bloqueo': 'Bloqueig'}
            
            comparativa_data = []
            for accion in ['atacar', 'recepción', 'saque', 'bloqueo']:
                media_row = df_media_equipo[df_media_equipo['tipo_accion'] == accion]
                jugador_row = df_jugador[df_jugador['tipo_accion'] == accion]
                
                if not media_row.empty and not jugador_row.empty:
                    efic_media = float(media_row['eficacia_media'].iloc[0])
                    efic_jugador = float(jugador_row['eficacia'].iloc[0])
                    diferencia = efic_jugador - efic_media
                    
                    comparativa_data.append({
                        'accion': nombres_acc[accion],
                        'jugador': efic_jugador,
                        'media': efic_media,
                        'diferencia': diferencia
                    })
            
            if comparativa_data:
                # Gráfico de barras comparativo
                fig = go.Figure()
                
                acciones_nombres = [d['accion'] for d in comparativa_data]
                efic_jugador_vals = [d['jugador'] for d in comparativa_data]
                efic_media_vals = [d['media'] for d in comparativa_data]
                
                fig.add_trace(go.Bar(
                    name=jugador_info['nombre_completo'],
                    x=acciones_nombres,
                    y=efic_jugador_vals,
                    marker_color=COLOR_ROJO,
                    text=[f"{v}%" for v in efic_jugador_vals],
                    textposition='outside'
                ))
                
                fig.add_trace(go.Bar(
                    name='Mitjana Equip',
                    x=acciones_nombres,
                    y=efic_media_vals,
                    marker_color=COLOR_NEGRO,
                    text=[f"{v}%" for v in efic_media_vals],
                    textposition='outside'
                ))
                
                fig.update_layout(
                    title="Eficàcia: Jugador vs Mitjana de l'Equip",
                    xaxis_title="Acció",
                    yaxis_title="Eficàcia (%)",
                    barmode='group',
                    height=400,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    yaxis=dict(range=[0, max(max(efic_jugador_vals), max(efic_media_vals)) + 15])
                )
                
                st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})
                
                # Resumen por acción
                cols = st.columns(len(comparativa_data))
                for idx, data in enumerate(comparativa_data):
                    with cols[idx]:
                        diff = data['diferencia']
                        if diff > 5:
                            color = COLOR_VERDE
                            icono = "↑"
                        elif diff < -5:
                            color = COLOR_ROJO
                            icono = "↓"
                        else:
                            color = COLOR_NARANJA
                            icono = "→"
                        
                        st.markdown(f"""
                        <div style="text-align: center; padding: 0.5rem; background: {COLOR_GRIS}; border-radius: 10px;">
                            <strong>{data['accion']}</strong><br>
                            <span style="font-size: 1.5rem; color: {color};">{icono} {diff:+.1f}%</span><br>
                            <small>vs mitjana</small>
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("No hi ha dades suficients per comparar")
        
        # === RANKING DE L'EQUIP ===
        st.markdown("---")
        st.subheader("🏆 Rànquing de l'Equip")
        
        nombres_acc = {'atacar': 'Atac', 'recepción': 'Recepció', 'saque': 'Saque', 'bloqueo': 'Bloqueig'}
        
        ranking_cols = st.columns(4)
        
        for idx, (accion, nombre) in enumerate(nombres_acc.items()):
            with ranking_cols[idx]:
                df_ranking = obtener_ranking_equipo(partido_ids, accion)
                
                if not df_ranking.empty:
                    # Buscar posición del jugador actual
                    jugador_ranking = df_ranking[df_ranking['jugador_id'] == jugador_id]
                    
                    if not jugador_ranking.empty:
                        posicion = int(jugador_ranking['ranking'].iloc[0])
                        total_jugadores = len(df_ranking)
                        eficacia = jugador_ranking['eficacia'].iloc[0]
                        
                        # Color según posición
                        if posicion == 1:
                            color = "#FFD700"  # Oro
                            emoji = "🥇"
                        elif posicion == 2:
                            color = "#C0C0C0"  # Plata
                            emoji = "🥈"
                        elif posicion == 3:
                            color = "#CD7F32"  # Bronce
                            emoji = "🥉"
                        elif posicion <= total_jugadores // 2:
                            color = COLOR_VERDE
                            emoji = "✓"
                        else:
                            color = COLOR_NARANJA
                            emoji = "↗"
                        
                        st.markdown(f"""
                        <div style="text-align: center; padding: 1rem; background: {COLOR_GRIS}; border-radius: 10px; border-left: 4px solid {color};">
                            <strong>{nombre}</strong><br>
                            <span style="font-size: 2rem;">{emoji}</span><br>
                            <span style="font-size: 1.5rem; font-weight: bold;">{posicion}º</span><br>
                            <small>de {total_jugadores} jugadors</small><br>
                            <small style="color: {COLOR_ROJO};">{eficacia}% efic.</small>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style="text-align: center; padding: 1rem; background: {COLOR_GRIS}; border-radius: 10px;">
                            <strong>{nombre}</strong><br>
                            <small>Mínim 5 accions</small>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="text-align: center; padding: 1rem; background: {COLOR_GRIS}; border-radius: 10px;">
                        <strong>{nombre}</strong><br>
                        <small>Sense dades</small>
                    </div>
                    """, unsafe_allow_html=True)

def pagina_comparativa():
    """Página de comparación de partidos"""
    st.markdown("""
    <div class="main-header">
        <h1>📈 Comparativa de Partits</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Verificar contexto
    if not st.session_state.get('equipo_id') or not st.session_state.get('temporada_id'):
        st.warning("⚠️ Selecciona primer un equip i temporada al menú lateral")
        return
    
    partidos = cargar_partidos(
        st.session_state.equipo_id,
        st.session_state.temporada_id,
        st.session_state.get('fase_id')
    )
    
    if len(partidos) < 2:
        st.info("Es necessiten almenys 2 partits per fer una comparativa")
        return
    
    partidos['display'] = partidos.apply(
        lambda x: f"vs {x['rival']} ({'L' if x['local'] else 'V'})", axis=1
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        partido1_options = [None] + partidos['id'].tolist()
        partido1 = st.selectbox(
            "Partit 1:",
            options=partido1_options,
            format_func=lambda x: "Selecciona Partit 1..." if x is None
                else partidos[partidos['id'] == x]['display'].iloc[0],
            key='partido1'
        )
    
    with col2:
        partido2_options = [None] + partidos['id'].tolist()
        partido2 = st.selectbox(
            "Partit 2:",
            options=partido2_options,
            format_func=lambda x: "Selecciona Partit 2..." if x is None
                else partidos[partidos['id'] == x]['display'].iloc[0],
            key='partido2'
        )
    
    if partido1 and partido2 and partido1 != partido2:
        info1 = partidos[partidos['id'] == partido1].iloc[0]
        info2 = partidos[partidos['id'] == partido2].iloc[0]
        
        # Crear nombres con L/V
        rival1_display = f"{info1['rival']} ({'L' if info1['local'] else 'V'})"
        rival2_display = f"{info2['rival']} ({'L' if info2['local'] else 'V'})"
        
        st.markdown("---")
        
        # Cargar datos
        df1 = obtener_resumen_acciones(partido1)
        df2 = obtener_resumen_acciones(partido2)
        
        # Comparar eficacias
        st.subheader("⚔️ Comparativa d'Eficàcia")
        
        acciones = ['atacar', 'recepción', 'saque', 'bloqueo', 'defensa']
        nombres = ['Atac', 'Recepció', 'Saque', 'Bloqueig', 'Defensa']
        
        fig = go.Figure()
        
        eficacias1 = []
        eficacias2 = []
        
        for accion in acciones:
            e1 = df1[df1['tipo_accion'] == accion]['eficacia']
            e2 = df2[df2['tipo_accion'] == accion]['eficacia']
            eficacias1.append(float(e1.iloc[0]) if not e1.empty else 0)
            eficacias2.append(float(e2.iloc[0]) if not e2.empty else 0)
        
        fig.add_trace(go.Bar(
            name=f"vs {rival1_display}",
            x=nombres,
            y=eficacias1,
            marker_color=COLOR_ROJO,
            text=[f'{e}%' for e in eficacias1],
            textposition='outside'
        ))
        
        fig.add_trace(go.Bar(
            name=f"vs {rival2_display}",
            x=nombres,
            y=eficacias2,
            marker_color=COLOR_NEGRO,
            text=[f'{e}%' for e in eficacias2],
            textposition='outside'
        ))
        
        fig.update_layout(
            barmode='group',
            yaxis=dict(range=[0, 100]),
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})
        
        # Tabla comparativa con tendencias
        st.subheader("📋 Taula Comparativa amb Tendències")
        
        comparativa = []
        for accion, nombre in zip(acciones, nombres):
            fila1 = df1[df1['tipo_accion'] == accion]
            fila2 = df2[df2['tipo_accion'] == accion]
            
            e1 = float(fila1['eficacia'].iloc[0]) if not fila1.empty else 0
            e2 = float(fila2['eficacia'].iloc[0]) if not fila2.empty else 0
            diff = e2 - e1
            
            # Determinar tendencia
            if diff > 5:
                tendencia = "✅ Millora"
            elif diff < -5:
                tendencia = "❌ Empitjora"
            else:
                tendencia = "➡️ Similar"
            
            comparativa.append({
                'Acció': nombre,
                f'vs {rival1_display}': f'{e1}%',
                f'vs {rival2_display}': f'{e2}%',
                'Diferència': f'{diff:+.1f}%',
                'Tendència': tendencia
            })
        
        st.dataframe(pd.DataFrame(comparativa), use_container_width=True, hide_index=True)
        
        # Leyenda
        st.caption("✅ Millora (+5%) | ➡️ Similar (±5%) | ❌ Empitjora (-5%)")
        
        # === DISTRIBUCIÓN DEL COLOCADOR COMPARATIVA ===
        st.markdown("---")
        st.subheader("🎯 Comparativa Distribució del Col·locador")
        
        df_dist1 = obtener_distribucion_colocador(partido1)
        df_dist2 = obtener_distribucion_colocador(partido2)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**vs {rival1_display}**")
            if not df_dist1.empty:
                st.plotly_chart(crear_grafico_distribucion_colocador(df_dist1), use_container_width=True, config={'staticPlot': True})
            else:
                st.info("No hi ha dades de distribució")
        
        with col2:
            st.markdown(f"**vs {rival2_display}**")
            if not df_dist2.empty:
                st.plotly_chart(crear_grafico_distribucion_colocador(df_dist2), use_container_width=True, config={'staticPlot': True})
            else:
                st.info("No hi ha dades de distribució")
        
        # === JUGADORES DE CADA PARTIDO ===
        st.markdown("---")
        st.subheader("👥 Jugadors Participants")
        
        df_jug1 = obtener_jugadores_partido(partido1)
        df_jug2 = obtener_jugadores_partido(partido2)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**vs {rival1_display}** ({len(df_jug1)} jugadors)")
            if not df_jug1.empty:
                for _, row in df_jug1.iterrows():
                    dorsal_str = f"#{row['dorsal']}" if row['dorsal'] else ""
                    st.markdown(f"• **{row['jugador']}** {dorsal_str} - {row['acciones']} accions")
            else:
                st.info("No hi ha dades")
        
        with col2:
            st.markdown(f"**vs {rival2_display}** ({len(df_jug2)} jugadors)")
            if not df_jug2.empty:
                for _, row in df_jug2.iterrows():
                    dorsal_str = f"#{row['dorsal']}" if row['dorsal'] else ""
                    st.markdown(f"• **{row['jugador']}** {dorsal_str} - {row['acciones']} accions")
            else:
                st.info("No hi ha dades")
    
    elif partido1 and partido2 and partido1 == partido2:
        st.warning("Selecciona dos partits diferents per comparar")

def pagina_fichas():
    """Página de fichas individuales de jugadores"""
    st.markdown("""
    <div class="main-header">
        <h1>🎴 Fitxes de Jugadors</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Verificar contexto
    if not st.session_state.get('equipo_id') or not st.session_state.get('temporada_id'):
        st.warning("⚠️ Selecciona primer un equip i temporada al menú lateral")
        return
    
    # Cargar partidos y jugadores
    partidos = cargar_partidos(
        st.session_state.equipo_id,
        st.session_state.temporada_id,
        st.session_state.get('fase_id')
    )
    
    if partidos.empty:
        st.info("No hi ha partits disponibles")
        return
    
    jugadores = cargar_jugadores(st.session_state.equipo_id)
    
    if jugadores.empty:
        st.info("No hi ha jugadors en aquest equip")
        return
    
    # Selectores
    col1, col2 = st.columns(2)
    
    with col1:
        jugador_options = [None] + jugadores['id'].tolist()
        jugador_id = st.selectbox(
            "Selecciona un jugador:",
            options=jugador_options,
            format_func=lambda x: "Selecciona un jugador..." if x is None
                else f"{jugadores[jugadores['id'] == x]['nombre_completo'].iloc[0]} (#{jugadores[jugadores['id'] == x]['dorsal'].iloc[0] or '-'})",
            key='ficha_jugador'
        )
    
    with col2:
        partidos['display'] = partidos.apply(
            lambda x: f"vs {x['rival']} ({'L' if x['local'] else 'V'})", axis=1
        )
        
        opciones_partido = ["tots"] + partidos['id'].tolist()
        partido_seleccionado = st.selectbox(
            "Partit:",
            options=opciones_partido,
            format_func=lambda x: f"Tots els partits ({len(partidos)})" if x == "tots"
                else partidos[partidos['id'] == x]['display'].iloc[0],
            key='ficha_partido'
        )
    
    if jugador_id:
        jugador_info = jugadores[jugadores['id'] == jugador_id].iloc[0]
        
        # Determinar partidos
        if partido_seleccionado == "tots":
            partido_ids = partidos['id'].tolist()
            contexto_partido = f"Tots els partits ({len(partido_ids)})"
        else:
            partido_ids = [partido_seleccionado]
            info_p = partidos[partidos['id'] == partido_seleccionado].iloc[0]
            contexto_partido = f"vs {info_p['rival']} ({'L' if info_p['local'] else 'V'})"
        
        # Obtener datos de la ficha
        ficha = obtener_ficha_jugador(partido_ids, jugador_id)
        
        st.markdown("---")
        
        # === HEADER DE LA FICHA ===
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, {COLOR_ROJO} 0%, #8B0000 100%); 
                    padding: 1.5rem; border-radius: 10px; text-align: center; margin-bottom: 1rem;">
            <h1 style="color: white; margin: 0;">{jugador_info['nombre_completo'].upper()}</h1>
            <p style="color: white; margin: 0.5rem 0 0 0; opacity: 0.9;">
                #{jugador_info['dorsal'] or '-'} | {jugador_info['posicion'] or '-'} | {contexto_partido}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # === SECCIÓN ATAQUE ===
        col1, col2, col3 = st.columns(3)
        
        eficacia = ficha['ataque']['eficacia'] or 0
        if eficacia >= 60:
            color_efic = COLOR_VERDE
        elif eficacia >= 40:
            color_efic = COLOR_NARANJA
        else:
            color_efic = COLOR_ROJO
        
        with col1:
            st.markdown(f"""
            <div style="background: {COLOR_GRIS}; padding: 1.5rem; border-radius: 10px; text-align: center;">
                <h4 style="color: {COLOR_ROJO}; margin: 0;">EFICÀCIA ATAC</h4>
                <p style="font-size: 3rem; font-weight: bold; color: {color_efic}; margin: 0.5rem 0;">{eficacia}%</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style="background: {COLOR_GRIS}; padding: 1.5rem; border-radius: 10px; text-align: center;">
                <h4 style="color: {COLOR_ROJO}; margin: 0;">PUNTS ATAC</h4>
                <p style="font-size: 3rem; font-weight: bold; color: {COLOR_ROJO}; margin: 0.5rem 0;">{ficha['ataque']['puntos'] or 0}</p>
                <small>de {ficha['ataque']['total'] or 0} intents</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            valor = ficha['valor_total'] or 0
            color_valor = COLOR_VERDE if valor > 0 else COLOR_ROJO
            signo = "+" if valor > 0 else ""
            st.markdown(f"""
            <div style="background: {COLOR_NEGRO}; padding: 1.5rem; border-radius: 10px; text-align: center;">
                <h4 style="color: white; margin: 0;">VALORACIÓ TOTAL</h4>
                <p style="font-size: 3rem; font-weight: bold; color: {color_valor}; margin: 0.5rem 0;">{signo}{valor}</p>
                <small style="color: {COLOR_GRIS};">punts - errors</small>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # === DESTACATS ===
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            <div style="background: {COLOR_AMARILLO}; padding: 1rem; border-radius: 10px;">
                <h4 style="margin: 0;">⭐ MILLOR ROTACIÓ</h4>
                <p style="font-size: 2rem; font-weight: bold; color: {COLOR_ROJO}; margin: 0.5rem 0;">
                    {ficha['mejor_rotacion']['nombre']}
                </p>
                <small>{ficha['mejor_rotacion']['puntos']} punts en {ficha['mejor_rotacion']['total']} atacs</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style="background: #E3F2FD; padding: 1rem; border-radius: 10px;">
                <h4 style="margin: 0;">🎯 ZONA MÉS PRODUCTIVA</h4>
                <p style="font-size: 2rem; font-weight: bold; color: {COLOR_ROJO}; margin: 0.5rem 0;">
                    {ficha['mejor_zona']['nombre']}
                </p>
                <small>{ficha['mejor_zona']['puntos']} punts en {ficha['mejor_zona']['total']} atacs</small>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # === ALTRES ACCIONS ===
        st.subheader("📊 Altres Accions")
        
        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric("🎯 Aces", ficha['otras']['aces'])
        col2.metric("🧱 Bloquejos #", ficha['otras']['bloqueos'])
        col3.metric("🏐 Recepcions +/#", ficha['otras']['recepciones'])
        col4.metric("⚡ Punts Directes", ficha['otras']['puntos_directos'])
        
        # === ERRORS ===
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("⚠️ Principals Errors")
        
        if not ficha['errores'].empty:
            nombres_acc = {
                'atacar': 'Atac', 
                'recepción': 'Recepció', 
                'saque': 'Saque', 
                'bloqueo': 'Bloqueig', 
                'defensa': 'Defensa'
            }
            
            cols = st.columns(len(ficha['errores']))
            for idx, (_, row) in enumerate(ficha['errores'].iterrows()):
                nombre_cat = nombres_acc.get(row['tipo_accion'], row['tipo_accion'])
                with cols[idx]:
                    st.markdown(f"""
                    <div style="background: #FFEBEE; padding: 1rem; border-radius: 10px; text-align: center;">
                        <p style="margin: 0; font-weight: bold;">{nombre_cat}</p>
                        <p style="font-size: 2rem; color: {COLOR_ROJO}; font-weight: bold; margin: 0;">{row['errores']}</p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.success("✅ Cap error registrat!")

# =============================================================================
# SIDEBAR Y NAVEGACIÓN
# =============================================================================

def sidebar_contexto():
    """Sidebar con selección de contexto"""
    st.sidebar.markdown(f"""
    <div style="text-align: center; padding: 1rem;">
        <h2 style="color: {COLOR_ROJO};">🏐 Volei Stats</h2>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Context de Treball")
    
    # Cargar datos
    equipos = cargar_equipos()
    temporadas = cargar_temporadas()
    
    # Selector de equipo con placeholder
    equipo_options = [None] + equipos['id'].tolist()
    equipo_id = st.sidebar.selectbox(
        "Equip:",
        options=equipo_options,
        format_func=lambda x: "Selecciona l'equip..." if x is None 
            else equipos[equipos['id'] == x]['nombre_completo'].iloc[0],
        key='select_equipo'
    )
    
    if equipo_id:
        st.session_state.equipo_id = equipo_id
        st.session_state.equipo_nombre = equipos[equipos['id'] == equipo_id]['nombre_completo'].iloc[0]
        
        # Selector de temporada con placeholder
        temporada_options = [None] + temporadas['id'].tolist()
        temporada_id = st.sidebar.selectbox(
            "Temporada:",
            options=temporada_options,
            format_func=lambda x: "Selecciona la temporada..." if x is None
                else temporadas[temporadas['id'] == x]['nombre'].iloc[0],
            key='select_temporada'
        )
        
        if temporada_id:
            st.session_state.temporada_id = temporada_id
            st.session_state.temporada_nombre = temporadas[temporadas['id'] == temporada_id]['nombre'].iloc[0]
            
            # Cargar fases
            fases = cargar_fases(temporada_id)
            
            if not fases.empty:
                fase_options = [None] + fases['id'].tolist()
                fase_id = st.sidebar.selectbox(
                    "Fase (opcional):",
                    options=fase_options,
                    format_func=lambda x: "Totes les fases" if x is None 
                        else fases[fases['id'] == x]['nombre'].iloc[0],
                    key='select_fase'
                )
                st.session_state.fase_id = fase_id
            else:
                st.session_state.fase_id = None
        else:
            st.session_state.temporada_id = None
            st.session_state.temporada_nombre = None
            st.session_state.fase_id = None
    else:
        st.session_state.equipo_id = None
        st.session_state.equipo_nombre = None
        st.session_state.temporada_id = None
        st.session_state.temporada_nombre = None
        st.session_state.fase_id = None
    
    st.sidebar.markdown("---")
    
    # Navegación
    st.sidebar.subheader("📍 Navegació")
    
    pagina = st.sidebar.radio(
        "Selecciona secció:",
        options=["🏠 Inici", "📊 Partit", "👤 Jugador", "🎴 Fitxes", "📈 Comparativa"],
        key='navegacion'
    )
    
    return pagina

# =============================================================================
# MAIN
# =============================================================================

def main():
    """Función principal"""
    # Sidebar y navegación
    pagina = sidebar_contexto()
    
    # Routing
    if pagina == "🏠 Inici":
        pagina_inicio()
    elif pagina == "📊 Partit":
        pagina_partido()
    elif pagina == "👤 Jugador":
        pagina_jugador()
    elif pagina == "🎴 Fitxes":
        pagina_fichas()
    elif pagina == "📈 Comparativa":
        pagina_comparativa()

if __name__ == "__main__":
    main()
