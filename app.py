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
import streamlit.components.v1 as components
from datetime import date
import bcrypt
import os
import secrets

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Colores del club
COLOR_ROJO = "#C8102E"
COLOR_BLANCO = "#FFFFFF"
COLOR_NEGRO = "#000000"
COLOR_AMARILLO = "#F4D000"
COLOR_GRIS = "#F2F2F2"
COLOR_GRISOSCURO = "#31333f"
COLOR_VERDE = "#4CAF50"
COLOR_NARANJA = "#FF9800"

# Configuración de página
st.set_page_config(
    page_title="Voleibol Stats",
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

def encriptar_password(password):
    """Encripta una contraseña con bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_password(password, password_hash):
    """Verifica si una contraseña coincide con su hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

@st.cache_resource
def get_engine():
    """Crea conexión a la base de datos"""
    # Primero: Usar variable de entorno (Railway, Render, etc.)
    if os.environ.get("DATABASE_URL"):
        return create_engine(os.environ.get("DATABASE_URL"))
    # Segundo: Usar secrets de Streamlit Cloud si existen
    try:
        if "database" in st.secrets:
            return create_engine(st.secrets["database"]["url"])
    except:
        pass
    # Fallback para desarrollo local
    return create_engine(
        "postgresql+psycopg2://postgres:navi6573@localhost:5432/voleibol"
    )
def get_connection():
    """Obtiene una conexión activa"""
    return get_engine().connect()

# =============================================================================
# SISTEMA DE LOGIN
# =============================================================================

def verificar_login(username, password):
    """Verifica credenciales y devuelve info del usuario"""
    with get_engine().connect() as conn:
        resultado = conn.execute(text("""
            SELECT id, username, password, equipo_id, es_admin
            FROM usuarios
            WHERE username = :username AND activo = TRUE
        """), {"username": username}).fetchone()
        
        if resultado:
            password_hash = resultado[2]
            
            # Verificar contraseña (soporta hash bcrypt y texto plano para migración)
            password_valida = False
            
            # Si empieza por $2b$ es bcrypt
            if password_hash.startswith('$2b$'):
                password_valida = verificar_password(password, password_hash)
            else:
                # Texto plano (usuarios antiguos) - comparación directa
                password_valida = (password == password_hash)
            
            if password_valida:
                return {
                    'id': resultado[0],
                    'username': resultado[1],
                    'equipo_id': resultado[3],
                    'es_admin': resultado[4]
                }
        
        return None

def crear_sesion(usuario_id):
    """Crea una sesión persistente para el usuario"""
    token = secrets.token_hex(32)
    try:
        with get_engine().begin() as conn:
            # Eliminar sesiones antiguas del usuario
            conn.execute(text("DELETE FROM sesiones WHERE usuario_id = :usuario_id"), {"usuario_id": usuario_id})
            # Crear nueva sesión
            conn.execute(text("""
                INSERT INTO sesiones (usuario_id, token)
                VALUES (:usuario_id, :token)
            """), {"usuario_id": usuario_id, "token": token})
        return token
    except:
        return None

def verificar_sesion(token):
    """Verifica si un token de sesión es válido y devuelve el usuario"""
    if not token:
        return None
    try:
        with get_engine().connect() as conn:
            resultado = conn.execute(text("""
                SELECT u.id, u.username, u.equipo_id, u.es_admin
                FROM sesiones s
                JOIN usuarios u ON s.usuario_id = u.id
                WHERE s.token = :token
                AND s.fecha_expiracion > CURRENT_TIMESTAMP
                AND u.activo = TRUE
            """), {"token": token}).fetchone()
            
            if resultado:
                return {
                    'id': resultado[0],
                    'username': resultado[1],
                    'equipo_id': resultado[2],
                    'es_admin': resultado[3]
                }
        return None
    except:
        return None

def eliminar_sesion(token):
    """Elimina una sesión"""
    try:
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM sesiones WHERE token = :token"), {"token": token})
    except:
        pass

def registrar_acceso(usuario_id, username, exitoso):
    """Registra un intento de acceso en la base de datos"""
    try:
        with get_engine().begin() as conn:
            conn.execute(text("""
                INSERT INTO registro_accesos (usuario_id, username, exitoso)
                VALUES (:usuario_id, :username, :exitoso)
            """), {
                "usuario_id": usuario_id,
                "username": username,
                "exitoso": exitoso
            })
    except Exception as e:
        # No fallar si hay error en el registro
        pass

def pagina_login():
    """Página de login"""
    st.title("🏐 Voleibol Stats")
    st.subheader("Inicia sessió per continuar")
    
    username = st.text_input("Usuari:")
    password = st.text_input("Contrasenya:", type="password")
    
    if st.button("🔐 Entrar", type="primary"):
        if username and password:
            usuario = verificar_login(username, password)
            
            if usuario:
                st.session_state.logged_in = True
                st.session_state.usuario = usuario
                st.session_state.es_admin = usuario['es_admin']
                
                if not usuario['es_admin'] and usuario['equipo_id']:
                    st.session_state.equipo_id = usuario['equipo_id']
                    equipos = cargar_equipos()
                    equipo_info = equipos[equipos['id'] == usuario['equipo_id']]
                    if not equipo_info.empty:
                        st.session_state.equipo_nombre = equipo_info['nombre_completo'].iloc[0]
                
                st.success(f"✅ Benvingut, {usuario['username']}!")
                st.rerun()
            else:
                st.error("❌ Usuari o contrasenya incorrectes")
        else:
            st.warning("⚠️ Introdueix usuari i contrasenya")

def logout():
    """Cierra la sesión del usuario"""
    # Eliminar sesión de BD
    if 'session_token' in st.session_state:
        eliminar_sesion(st.session_state.session_token)
    
    # Limpiar query params
    if 'session' in st.query_params:
        del st.query_params['session']
    
    # Limpiar session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]

def mostrar_login_inline():
    """Muestra formulario de login en la página actual"""
    st.markdown("---")
    st.subheader("🔐 Iniciar sessió")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        username = st.text_input("Usuari:", key="login_inline_user")
        password = st.text_input("Contrasenya:", type="password", key="login_inline_pass")
        
        if st.button("🔐 Entrar", type="primary", use_container_width=True, key="login_inline_btn"):
            if username and password:
                usuario = verificar_login(username, password)
                
                if usuario:
                    st.session_state.logged_in = True
                    st.session_state.usuario = usuario
                    st.session_state.es_admin = usuario['es_admin']
                    
                    if not usuario['es_admin'] and usuario['equipo_id']:
                        st.session_state.equipo_id = usuario['equipo_id']
                        equipos = cargar_equipos()
                        equipo_info = equipos[equipos['id'] == usuario['equipo_id']]
                        if not equipo_info.empty:
                            st.session_state.equipo_nombre = equipo_info['nombre_completo'].iloc[0]
                    
                    st.success(f"✅ Benvingut, {usuario['username']}!")
                    st.rerun()
                else:
                    st.error("❌ Usuari o contrasenya incorrectes")
            else:
                st.warning("⚠️ Introdueix usuari i contrasenya")

def pagina_inicio_publica():
    """Página de inicio para visitantes"""
    st.title("🏐 Voleibol Stats")
    st.markdown("### Benvingut!")
    st.markdown("""
    Aquesta aplicació permet consultar estadístiques de voleibol.
    
    **Com a visitant pots veure:**
    - 🏐 Informació dels equips
    - 👥 Jugadors de cada equip
    - 📅 Resultats dels partits
    
    **Inicia sessió** per accedir a estadístiques avançades i anàlisis detallats.
    """)
    
    st.markdown("---")
    
    # Mostrar resumen de equipos
    st.subheader("🏐 Equips")
    equipos = cargar_equipos()
    
    if not equipos.empty:
        cols = st.columns(3)
        for idx, (_, equipo) in enumerate(equipos.iterrows()):
            col_idx = idx % 3
            with cols[col_idx]:
                st.markdown(f"""
                <div style="background: #f5f5f5; padding: 1rem; border-radius: 10px; text-align: center; margin: 0.5rem 0;">
                    <h4 style="margin: 0;">{equipo['nombre_completo']}</h4>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No hi ha equips disponibles")
    
    # Mostrar login si se ha pulsado el botón
    if st.session_state.get('mostrar_login'):
        mostrar_login_inline()

    return

def pagina_equipos_publica():
    """Página de equipos para visitantes"""
    st.title("🏐 Equips")
    
    equipos = cargar_equipos()
    
    if equipos.empty:
        st.info("No hi ha equips disponibles")
        return
    
    # Selector de equipo
    equipo_sel = st.selectbox(
        "Selecciona un equip:",
        options=equipos['id'].tolist(),
        format_func=lambda x: equipos[equipos['id'] == x]['nombre_completo'].iloc[0]
    )
    
    if equipo_sel:
        equipo_info = equipos[equipos['id'] == equipo_sel].iloc[0]
        
        st.markdown(f"## {equipo_info['nombre_completo']}")
        
        # === ESTADÍSTICAS GENERALES ===
        st.markdown("---")
        st.subheader("📊 Estadístiques")
        
        with get_engine().connect() as conn:
            # Obtener estadísticas de partidos
            stats = conn.execute(text("""
                SELECT 
                    COUNT(*) as partidos,
                    COUNT(*) FILTER (WHERE 
                        (local = true AND SPLIT_PART(resultado, '-', 1)::int > SPLIT_PART(resultado, '-', 2)::int) OR
                        (local = false AND SPLIT_PART(resultado, '-', 2)::int > SPLIT_PART(resultado, '-', 1)::int)
                    ) as victorias,
                    SUM(SPLIT_PART(resultado, '-', 1)::int) as sets_favor,
                    SUM(SPLIT_PART(resultado, '-', 2)::int) as sets_contra
                FROM partidos_new
                WHERE equipo_id = :equipo_id
                AND resultado IS NOT NULL
                AND resultado LIKE '%-%'
            """), {"equipo_id": equipo_sel}).fetchone()
        
        partidos = stats[0] or 0
        victorias = stats[1] or 0
        derrotas = partidos - victorias
        sets_favor = int(stats[2] or 0)
        sets_contra = int(stats[3] or 0)
        pct_victorias = round((victorias / partidos * 100), 1) if partidos > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Partits", partidos)
        col2.metric("Victòries", victorias, f"{pct_victorias}%")
        col3.metric("Derrotes", derrotas)
        col4.metric("Sets", f"{sets_favor}-{sets_contra}")
        
        # === RACHA ACTUAL ===
        with get_engine().connect() as conn:
            ultimos = pd.read_sql(text("""
                SELECT resultado, local
                FROM partidos_new
                WHERE equipo_id = :equipo_id
                AND resultado IS NOT NULL
                ORDER BY fecha DESC
                LIMIT 10
            """), conn, params={"equipo_id": equipo_sel})
        
        if not ultimos.empty:
            racha = 0
            tipo_racha = None
            
            for _, p in ultimos.iterrows():
                try:
                    sets = p['resultado'].split('-')
                    if p['local']:
                        victoria = int(sets[0]) > int(sets[1])
                    else:
                        victoria = int(sets[1]) > int(sets[0])
                    
                    if tipo_racha is None:
                        tipo_racha = victoria
                        racha = 1
                    elif victoria == tipo_racha:
                        racha += 1
                    else:
                        break
                except:
                    break
            
            if racha >= 2:
                if tipo_racha:
                    st.success(f"🔥 **Ratxa actual:** {racha} victòries seguides!")
                else:
                    st.warning(f"💪 **Ratxa actual:** {racha} derrotes seguides")
        
        # === ÚLTIMO PARTIDO ===
        st.markdown("---")
        st.subheader("📅 Últim Partit")
        
        with get_engine().connect() as conn:
            ultimo = pd.read_sql(text("""
                SELECT rival, local, fecha, resultado
                FROM partidos_new
                WHERE equipo_id = :equipo_id
                ORDER BY fecha DESC
                LIMIT 1
            """), conn, params={"equipo_id": equipo_sel})
        
        if not ultimo.empty:
            p = ultimo.iloc[0]
            tipo = "🏠 Local" if p['local'] else "✈️ Visitant"
            fecha = p['fecha'].strftime("%d/%m/%Y") if p['fecha'] else "-"
            
            try:
                sets = p['resultado'].split('-')
                if p['local']:
                    victoria = int(sets[0]) > int(sets[1])
                else:
                    victoria = int(sets[1]) > int(sets[0])
                color = "#4CAF50" if victoria else "#F44336"
                resultado_texto = "✅ Victòria" if victoria else "❌ Derrota"
            except:
                color = "#888"
                resultado_texto = ""
            
            st.markdown(f"""
            <div style="background: #f5f5f5; padding: 1rem; border-radius: 10px; border-left: 4px solid {color};">
                <h3 style="margin: 0;">vs {p['rival']}</h3>
                <p style="margin: 0.5rem 0;">{tipo} · {fecha}</p>
                <p style="font-size: 1.5rem; font-weight: bold; margin: 0;">{p['resultado']} {resultado_texto}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # === MEJOR VICTORIA ===
        st.markdown("---")
        st.subheader("🏆 Millor Victòria")
        
        with get_engine().connect() as conn:
            mejor = pd.read_sql(text("""
                SELECT rival, local, fecha, resultado
                FROM partidos_new
                WHERE equipo_id = :equipo_id
                AND resultado IS NOT NULL
                AND (
                    (local = true AND SPLIT_PART(resultado, '-', 1)::int > SPLIT_PART(resultado, '-', 2)::int) OR
                    (local = false AND SPLIT_PART(resultado, '-', 2)::int > SPLIT_PART(resultado, '-', 1)::int)
                )
                ORDER BY 
                    CASE WHEN local THEN SPLIT_PART(resultado, '-', 1)::int - SPLIT_PART(resultado, '-', 2)::int
                         ELSE SPLIT_PART(resultado, '-', 2)::int - SPLIT_PART(resultado, '-', 1)::int END DESC
                LIMIT 1
            """), conn, params={"equipo_id": equipo_sel})
        
        if not mejor.empty:
            p = mejor.iloc[0]
            tipo = "🏠" if p['local'] else "✈️"
            fecha = p['fecha'].strftime("%d/%m/%Y") if p['fecha'] else "-"
            
            st.markdown(f"""
            <div style="background: #E8F5E9; padding: 1rem; border-radius: 10px; border-left: 4px solid #4CAF50;">
                <h3 style="margin: 0;">{tipo} vs {p['rival']}</h3>
                <p style="margin: 0.5rem 0;">{fecha}</p>
                <p style="font-size: 1.5rem; font-weight: bold; margin: 0; color: #4CAF50;">{p['resultado']} 🏆</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Encara no hi ha victòries registrades")
        
        # === TOP 5 ANOTADORES ===
        st.markdown("---")
        st.subheader("⭐ Top 5 Anotadors")
        
        with get_engine().connect() as conn:
            top_anotadores = pd.read_sql(text("""
                SELECT 
                    j.apellido as jugador,
                    COUNT(*) FILTER (WHERE a.marca = '#') as puntos
                FROM acciones_new a
                JOIN jugadores j ON a.jugador_id = j.id
                JOIN partidos_new p ON a.partido_id = p.id
                WHERE p.equipo_id = :equipo_id
                AND a.tipo_accion IN ('atacar', 'saque', 'bloqueo')
                GROUP BY j.id, j.apellido
                ORDER BY puntos DESC
                LIMIT 5
            """), conn, params={"equipo_id": equipo_sel})
        
        if not top_anotadores.empty:
            for idx, (_, row) in enumerate(top_anotadores.iterrows()):
                medalla = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][idx]
                st.markdown(f"""
                <div style="background: #f5f5f5; padding: 0.5rem 1rem; border-radius: 5px; margin: 0.25rem 0; display: flex; justify-content: space-between; align-items: center;">
                    <span>{medalla} <strong>{row['jugador']}</strong></span>
                    <span style="font-weight: bold; color: #D32F2F;">{int(row['puntos'])} punts</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No hi ha dades d'anotadors")

        # === GRÀFIC DE RANKINGS ===
        st.markdown("---")
        st.subheader("📈 Comparativa de Jugadors")
        
        df_rankings = obtener_rankings_todas_acciones(equipo_sel)
        
        if not df_rankings.empty:
            # Selector de jugador
            jugadores_disponibles = sorted(df_rankings['jugador'].unique())
            
            jugador_sel = st.selectbox(
                "Selecciona un jugador per destacar-lo:",
                options=[None] + jugadores_disponibles,
                format_func=lambda x: "Cap seleccionat (tots en gris)" if x is None else x,
                key="selector_jugador_ranking"
            )
            
            # Crear y mostrar gráfico
            fig_ranking = crear_grafico_ranking_jugadores(df_rankings, jugador_sel)
            
            if fig_ranking:
                st.plotly_chart(fig_ranking, use_container_width=True, config={'staticPlot': True})
                
                # Mostrar leyenda/explicación
                st.caption("El gràfic mostra la posició de cada jugador al ranking d'eficàcia per cada acció. Posició 1 = millor del equip.")
        else:
            st.info("No hi ha prou dades per mostrar el gràfic de rankings")
        
        # === JUGADORES ===
        st.markdown("---")
        st.subheader("👥 Plantilla")
        
        with get_engine().connect() as conn:
            jugadores = pd.read_sql(text("""
                SELECT apellido, posicion, dorsal
                FROM jugadores
                WHERE equipo_id = :equipo_id AND activo = true
                ORDER BY apellido
            """), conn, params={"equipo_id": equipo_sel})
        
        if not jugadores.empty:
            cols = st.columns(4)
            for idx, (_, jug) in enumerate(jugadores.iterrows()):
                with cols[idx % 4]:
                    dorsal = f"#{jug['dorsal']}" if jug['dorsal'] else ""
                    posicion = f"({jug['posicion']})" if jug['posicion'] else ""
                    st.markdown(f"""
                    <div style="background: #f5f5f5; padding: 0.5rem; border-radius: 5px; text-align: center; margin: 0.25rem 0;">
                        <strong>{jug['apellido']}</strong> {dorsal}<br>
                        <small>{posicion}</small>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No hi ha jugadors registrats")
        
        # === HISTORIAL DE PARTIDOS ===
        st.markdown("---")
        st.subheader("📋 Historial de Partits")
        
        with get_engine().connect() as conn:
            partidos = pd.read_sql(text("""
                SELECT rival, local, fecha, resultado
                FROM partidos_new
                WHERE equipo_id = :equipo_id
                ORDER BY fecha DESC
            """), conn, params={"equipo_id": equipo_sel})
        
        if not partidos.empty:
            for _, partido in partidos.iterrows():
                tipo = "🏠" if partido['local'] else "✈️"
                fecha = partido['fecha'].strftime("%d/%m/%Y") if partido['fecha'] else "-"
                resultado = partido['resultado'] or "-"
                
                # Color según resultado
                if resultado and resultado != "-":
                    try:
                        sets = resultado.split("-")
                        if partido['local']:
                            victoria = int(sets[0]) > int(sets[1])
                        else:
                            victoria = int(sets[1]) > int(sets[0])
                        color = "#4CAF50" if victoria else "#F44336"
                    except:
                        color = "#888"
                else:
                    color = "#888"
                
                st.markdown(f"""
                <div style="background: #f5f5f5; padding: 0.5rem 1rem; border-radius: 5px; margin: 0.25rem 0; border-left: 4px solid {color};">
                    {tipo} <strong>vs {partido['rival']}</strong> · {fecha} · <strong>{resultado}</strong>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No hi ha partits registrats")
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
def obtener_estadisticas_jugadores_por_set(partido_ids, set_numero):
    """Obtiene estadísticas detalladas por jugador para un set específico"""
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
            AND a.set_numero = :set_numero
            AND a.tipo_accion IN ('atacar', 'recepción', 'saque', 'bloqueo')
            GROUP BY j.nombre, j.apellido, a.tipo_accion
            ORDER BY j.apellido, a.tipo_accion
        """), conn, params={"set_numero": set_numero})
        
        if not df.empty:
            df['eficacia'] = ((df['puntos'] + df['positivos']) / df['total'] * 100).round(1)
            df['eficiencia'] = ((df['puntos'] - df['errores']) / df['total'] * 100).round(1)
        
        return df

@st.cache_data(ttl=60)
def obtener_distribucion_por_rotacion_set(partido_ids, set_numero):
    """Obtiene distribución de colocaciones por zona y rotación para un set específico (solo ataques después de colocación)"""
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
                    zona_jugador,
                    zona_colocador,
                    LAG(tipo_accion) OVER (ORDER BY id) as accion_previa
                FROM acciones_new
                WHERE partido_id IN ({ids_str})
                AND set_numero = :set_numero
            )
            SELECT 
                zona_colocador as rotacion,
                UPPER(zona_jugador) AS zona,
                COUNT(*) as colocaciones,
                ROUND((COUNT(*) FILTER (WHERE marca = '#')::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficacia,
                COUNT(*) FILTER (WHERE marca = '#') as puntos,
                COUNT(*) FILTER (WHERE marca = '=') as errores
            FROM acciones_ordenadas
            WHERE tipo_accion = 'atacar'
            AND accion_previa = 'colocación'
            AND zona_jugador IS NOT NULL
            AND zona_colocador IS NOT NULL
            GROUP BY zona_colocador, zona_jugador
            ORDER BY zona_colocador, colocaciones DESC
        """), conn, params={"set_numero": set_numero})
        
        return df

@st.cache_data(ttl=60)
def obtener_distribucion_colocador_por_set(partido_ids, set_numero):
    """Obtiene distribución de colocaciones por zona para un set específico (solo ataques después de colocación)"""
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
                    zona_jugador,
                    LAG(tipo_accion) OVER (ORDER BY id) as accion_previa
                FROM acciones_new
                WHERE partido_id IN ({ids_str})
                AND set_numero = :set_numero
            ),
            ataques_colocados AS (
                SELECT *
                FROM acciones_ordenadas
                WHERE tipo_accion = 'atacar'
                AND accion_previa = 'colocación'
                AND zona_jugador IS NOT NULL
            ),
            total_ataques AS (
                SELECT COUNT(*) as total
                FROM ataques_colocados
            )
            SELECT 
                UPPER(zona_jugador) AS zona,
                COUNT(*) as colocaciones,
                ROUND((COUNT(*)::decimal / NULLIF((SELECT total FROM total_ataques), 0)) * 100, 1) as porcentaje,
                ROUND((COUNT(*) FILTER (WHERE marca = '#')::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficacia,
                COUNT(*) FILTER (WHERE marca = '#') as puntos
            FROM ataques_colocados
            GROUP BY zona_jugador
            ORDER BY colocaciones DESC
        """), conn, params={"set_numero": set_numero})
        
        return df


@st.cache_data(ttl=60)
def obtener_sideout_por_set(partido_ids, set_numero):
    """Obtiene side-out y contraataque para un set específico"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            WITH acciones_ordenadas AS (
                SELECT 
                    a.id,
                    a.tipo_accion,
                    a.marca,
                    LAG(a.tipo_accion) OVER (ORDER BY a.id) as accion_previa,
                    LAG(a.tipo_accion, 2) OVER (ORDER BY a.id) as accion_previa_2
                FROM acciones_new a
                WHERE a.partido_id IN ({ids_str})
                AND a.set_numero = :set_numero
            )
            SELECT 
                -- Side-out (ataque después de recepción)
                COUNT(*) FILTER (WHERE tipo_accion = 'atacar' AND (accion_previa = 'recepción' OR (accion_previa = 'colocación' AND accion_previa_2 = 'recepción'))) as total_sideout,
                COUNT(*) FILTER (WHERE tipo_accion = 'atacar' AND (accion_previa = 'recepción' OR (accion_previa = 'colocación' AND accion_previa_2 = 'recepción')) AND marca IN ('#', '+')) as sideout_positivo,
                COUNT(*) FILTER (WHERE tipo_accion = 'atacar' AND (accion_previa = 'recepción' OR (accion_previa = 'colocación' AND accion_previa_2 = 'recepción')) AND marca = '#') as sideout_puntos,
                
                -- Contraataque (ataque después de defensa)
                COUNT(*) FILTER (WHERE tipo_accion = 'atacar' AND (accion_previa = 'defensa' OR (accion_previa = 'colocación' AND accion_previa_2 = 'defensa'))) as total_contraataque,
                COUNT(*) FILTER (WHERE tipo_accion = 'atacar' AND (accion_previa = 'defensa' OR (accion_previa = 'colocación' AND accion_previa_2 = 'defensa')) AND marca IN ('#', '+')) as contraataque_positivo,
                COUNT(*) FILTER (WHERE tipo_accion = 'atacar' AND (accion_previa = 'defensa' OR (accion_previa = 'colocación' AND accion_previa_2 = 'defensa')) AND marca = '#') as contraataque_puntos
            FROM acciones_ordenadas
        """), conn, params={"set_numero": set_numero})
        
        return df


@st.cache_data(ttl=60)
def obtener_distribucion_por_rotacion(partido_ids):
    """Obtiene distribución de colocaciones por zona y rotación (solo ataques después de colocación)"""
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
                    zona_jugador,
                    zona_colocador,
                    LAG(tipo_accion) OVER (ORDER BY id) as accion_previa
                FROM acciones_new
                WHERE partido_id IN ({ids_str})
            )
            SELECT 
                zona_colocador as rotacion,
                UPPER(zona_jugador) AS zona,
                COUNT(*) as colocaciones,
                ROUND((COUNT(*) FILTER (WHERE marca = '#')::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficacia,
                COUNT(*) FILTER (WHERE marca = '#') as puntos,
                COUNT(*) FILTER (WHERE marca = '=') as errores
            FROM acciones_ordenadas
            WHERE tipo_accion = 'atacar'
            AND accion_previa = 'colocación'
            AND zona_jugador IS NOT NULL
            AND zona_colocador IS NOT NULL
            GROUP BY zona_colocador, zona_jugador
            ORDER BY zona_colocador, colocaciones DESC
        """), conn)
        
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
def obtener_rankings_todas_acciones(equipo_id):
    """Obtiene el ranking de todos los jugadores en todas las acciones"""
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text("""
            WITH stats AS (
                SELECT 
                    j.id as jugador_id,
                    CASE 
                        WHEN j.nombre IS NOT NULL AND j.nombre != '' 
                        THEN j.nombre || ' ' || j.apellido 
                        ELSE j.apellido 
                    END AS jugador,
                    a.tipo_accion,
                    COUNT(*) as total,
                    ROUND((COUNT(*) FILTER (WHERE a.marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 1) as eficacia
                FROM acciones_new a
                JOIN jugadores j ON a.jugador_id = j.id
                JOIN partidos_new p ON a.partido_id = p.id
                WHERE p.equipo_id = :equipo_id
                AND a.tipo_accion IN ('recepción', 'atacar', 'saque', 'bloqueo')
                GROUP BY j.id, j.nombre, j.apellido, a.tipo_accion
                HAVING COUNT(*) >= 5
            ),
            rankings AS (
                SELECT 
                    jugador_id,
                    jugador,
                    tipo_accion,
                    eficacia,
                    ROW_NUMBER() OVER (PARTITION BY tipo_accion ORDER BY eficacia DESC) as ranking
                FROM stats
            )
            SELECT * FROM rankings
            ORDER BY jugador, tipo_accion
        """), conn, params={"equipo_id": equipo_id})
        
        return df

@st.cache_data(ttl=60)
def obtener_rendimiento_rotacion_jugador(partido_ids, jugador_id):
    """Obtiene el rendimiento del jugador por rotación"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                UPPER(zona_colocador) as rotacion,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE marca = '#') as puntos,
                COUNT(*) FILTER (WHERE marca IN ('#','+')) as positivos,
                COUNT(*) FILTER (WHERE marca = '=') as errores,
                ROUND((COUNT(*) FILTER (WHERE marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 1) as eficacia,
                ROUND(((COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))::decimal / NULLIF(COUNT(*),0))*100, 1) as eficiencia
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND jugador_id = :jid
            AND tipo_accion = 'atacar'
            AND zona_colocador IS NOT NULL
            GROUP BY zona_colocador
            ORDER BY zona_colocador
        """), conn, params={"jid": jugador_id})
        
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
    """Obtiene distribución de colocaciones por zona (solo ataques después de colocación)"""
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
                    zona_jugador,
                    LAG(tipo_accion) OVER (ORDER BY id) as accion_previa
                FROM acciones_new
                WHERE partido_id IN ({ids_str})
            ),
            ataques_colocados AS (
                SELECT *
                FROM acciones_ordenadas
                WHERE tipo_accion = 'atacar'
                AND accion_previa = 'colocación'
                AND zona_jugador IS NOT NULL
            ),
            total_ataques AS (
                SELECT COUNT(*) as total
                FROM ataques_colocados
            )
            SELECT 
                UPPER(zona_jugador) AS zona,
                COUNT(*) as colocaciones,
                ROUND((COUNT(*)::decimal / NULLIF((SELECT total FROM total_ataques), 0)) * 100, 1) as porcentaje,
                ROUND((COUNT(*) FILTER (WHERE marca = '#')::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficacia,
                COUNT(*) FILTER (WHERE marca = '#') as puntos
            FROM ataques_colocados
            GROUP BY zona_jugador
            ORDER BY colocaciones DESC
        """), conn)
        
        return df

@st.cache_data(ttl=60)
def obtener_distribucion_por_rotacion(partido_ids):
    """Obtiene distribución de colocaciones por zona y rotación"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                zona_colocador as rotacion,
                UPPER(zona_jugador) AS zona,
                COUNT(*) as colocaciones,
                ROUND((COUNT(*) FILTER (WHERE marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficacia,
                COUNT(*) FILTER (WHERE marca = '#') as puntos
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND tipo_accion = 'atacar'
            AND zona_jugador IS NOT NULL
            AND zona_colocador IS NOT NULL
            GROUP BY zona_colocador, zona_jugador
            ORDER BY zona_colocador, colocaciones DESC
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

@st.cache_data(ttl=60)
def obtener_badges_equipo(equipo_id, temporada_id, fase_id=None):
    """Obtiene los badges/logros del equipo"""
    
    # Cargar partidos
    partidos = cargar_partidos(equipo_id, temporada_id, fase_id)
    
    if partidos.empty:
        return []
    
    partido_ids = partidos['id'].tolist()
    badges = []
    
    with get_engine().connect() as conn:
        # Para cada partido, buscar logros
        for _, partido in partidos.iterrows():
            pid = partido['id']
            rival = partido['rival']
            fecha = partido['fecha']
            local = partido['local']
            
            # === MEJOR ATACANTE DEL PARTIDO ===
            mejor_atacante = conn.execute(text("""
                SELECT 
                    CASE WHEN j.nombre IS NOT NULL AND j.nombre != '' 
                         THEN j.nombre || ' ' || j.apellido 
                         ELSE j.apellido END AS jugador,
                    COUNT(*) as total,
                    ROUND((COUNT(*) FILTER (WHERE a.marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 1) as eficacia
                FROM acciones_new a
                JOIN jugadores j ON a.jugador_id = j.id
                WHERE a.partido_id = :pid AND a.tipo_accion = 'atacar'
                GROUP BY j.nombre, j.apellido
                HAVING COUNT(*) >= 5
                ORDER BY eficacia DESC
                LIMIT 1
            """), {"pid": pid}).fetchone()
            
            if mejor_atacante and mejor_atacante[2] and mejor_atacante[2] >= 50:
                badges.append({
                    'tipo': 'gold',
                    'icono': '🏆',
                    'titulo': 'Millor Atacant',
                    'descripcion': f"{mejor_atacante[0]} - {mejor_atacante[2]}% eficàcia vs {rival}",
                    'fecha': fecha,
                    'partido_id': pid
                })
            
            # === RÉCORD DE ACES (3+) ===
            aces_record = conn.execute(text("""
                SELECT 
                    CASE WHEN j.nombre IS NOT NULL AND j.nombre != '' 
                         THEN j.nombre || ' ' || j.apellido 
                         ELSE j.apellido END AS jugador,
                    COUNT(*) as aces
                FROM acciones_new a
                JOIN jugadores j ON a.jugador_id = j.id
                WHERE a.partido_id = :pid AND a.tipo_accion = 'saque' AND a.marca = '#'
                GROUP BY j.nombre, j.apellido
                HAVING COUNT(*) >= 3
                ORDER BY aces DESC
                LIMIT 1
            """), {"pid": pid}).fetchone()
            
            if aces_record:
                badges.append({
                    'tipo': 'fire',
                    'icono': '🔥',
                    'titulo': 'Màquina de Aces',
                    'descripcion': f"{aces_record[0]} - {aces_record[1]} aces vs {rival}!",
                    'fecha': fecha,
                    'partido_id': pid
                })
            
            # === 10+ PUNTOS DIRECTOS ===
            puntos_record = conn.execute(text("""
                SELECT 
                    CASE WHEN j.nombre IS NOT NULL AND j.nombre != '' 
                         THEN j.nombre || ' ' || j.apellido 
                         ELSE j.apellido END AS jugador,
                    COUNT(*) as puntos
                FROM acciones_new a
                JOIN jugadores j ON a.jugador_id = j.id
                WHERE a.partido_id = :pid 
                AND a.tipo_accion IN ('atacar', 'saque', 'bloqueo') 
                AND a.marca = '#'
                GROUP BY j.nombre, j.apellido
                HAVING COUNT(*) >= 10
                ORDER BY puntos DESC
                LIMIT 1
            """), {"pid": pid}).fetchone()
            
            if puntos_record:
                badges.append({
                    'tipo': 'gold',
                    'icono': '⭐',
                    'titulo': '10+ Punts',
                    'descripcion': f"{puntos_record[0]} - {puntos_record[1]} punts directes vs {rival}!",
                    'fecha': fecha,
                    'partido_id': pid
                })
            
            # === PARTIDO PERFECTO (0 errores, mínimo 10 acciones) ===
            partido_perfecto = conn.execute(text("""
                SELECT 
                    CASE WHEN j.nombre IS NOT NULL AND j.nombre != '' 
                         THEN j.nombre || ' ' || j.apellido 
                         ELSE j.apellido END AS jugador,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE a.marca = '=') as errores
                FROM acciones_new a
                JOIN jugadores j ON a.jugador_id = j.id
                WHERE a.partido_id = :pid
                GROUP BY j.nombre, j.apellido
                HAVING COUNT(*) >= 10 AND COUNT(*) FILTER (WHERE a.marca = '=') = 0
            """), {"pid": pid}).fetchall()
            
            for jugador in partido_perfecto:
                badges.append({
                    'tipo': 'perfect',
                    'icono': '💯',
                    'titulo': 'Partit Perfecte',
                    'descripcion': f"{jugador[0]} - 0 errors en {jugador[1]} accions vs {rival}!",
                    'fecha': fecha,
                    'partido_id': pid
                })
            
            # === MUR DE BLOC (3+ bloqueos punto) ===
            mur_bloc = conn.execute(text("""
                SELECT 
                    CASE WHEN j.nombre IS NOT NULL AND j.nombre != '' 
                         THEN j.nombre || ' ' || j.apellido 
                         ELSE j.apellido END AS jugador,
                    COUNT(*) as blocs
                FROM acciones_new a
                JOIN jugadores j ON a.jugador_id = j.id
                WHERE a.partido_id = :pid AND a.tipo_accion = 'bloqueo' AND a.marca = '#'
                GROUP BY j.nombre, j.apellido
                HAVING COUNT(*) >= 3
                ORDER BY blocs DESC
                LIMIT 1
            """), {"pid": pid}).fetchone()
            
            if mur_bloc:
                badges.append({
                    'tipo': 'fire',
                    'icono': '🧱',
                    'titulo': 'El Muro',
                    'descripcion': f"{mur_bloc[0]} - {mur_bloc[1]} blocs punt vs {rival}!",
                    'fecha': fecha,
                    'partido_id': pid
                })
            
            # === MEJOR RECEPCIÓN (60%+ con mínimo 10 recepciones) ===
            mejor_receptor = conn.execute(text("""
                SELECT 
                    CASE WHEN j.nombre IS NOT NULL AND j.nombre != '' 
                         THEN j.nombre || ' ' || j.apellido 
                         ELSE j.apellido END AS jugador,
                    COUNT(*) as total,
                    ROUND((COUNT(*) FILTER (WHERE a.marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 1) as eficacia
                FROM acciones_new a
                JOIN jugadores j ON a.jugador_id = j.id
                WHERE a.partido_id = :pid AND a.tipo_accion = 'recepción'
                GROUP BY j.nombre, j.apellido
                HAVING COUNT(*) >= 10
                ORDER BY eficacia DESC
                LIMIT 1
            """), {"pid": pid}).fetchone()
            
            if mejor_receptor and mejor_receptor[2] and mejor_receptor[2] >= 60:
                badges.append({
                    'tipo': 'perfect',
                    'icono': '🎯',
                    'titulo': 'Recepció d\'Or',
                    'descripcion': f"{mejor_receptor[0]} - {mejor_receptor[2]}% eficàcia vs {rival}",
                    'fecha': fecha,
                    'partido_id': pid
                })
    
    # Ordenar por fecha (más recientes primero)
    from datetime import date
    badges.sort(key=lambda x: x['fecha'] if x['fecha'] else date.min, reverse=True)
    
    return badges

@st.cache_data(ttl=60)
def obtener_distribucion_por_recepcion(partido_ids):
    """Obtiene la distribución de colocación según zona de recepción y rotación"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    # Mapeo: rotación -> {posición jugador -> zona recepción}
    mapeo_recepcion = {
        'p1': {'p2': 'Z1', 'p6': 'Z6', 'p5': 'Z5'},
        'p2': {'p1': 'Z1', 'p6': 'Z6', 'p3': 'Z5'},
        'p3': {'p1': 'Z1', 'p5': 'Z6', 'p4': 'Z5'},
        'p4': {'p6': 'Z1', 'p5': 'Z6', 'p2': 'Z5'},
        'p5': {'p1': 'Z1', 'p6': 'Z6', 'p3': 'Z5'},
        'p6': {'p1': 'Z1', 'p5': 'Z6', 'p4': 'Z5'},
    }
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            WITH acciones_ordenadas AS (
                SELECT 
                    id,
                    partido_id,
                    tipo_accion,
                    marca,
                    zona_jugador,
                    zona_colocador,
                    LEAD(tipo_accion) OVER (PARTITION BY partido_id ORDER BY id) as siguiente_accion,
                    LEAD(tipo_accion, 2) OVER (PARTITION BY partido_id ORDER BY id) as siguiente_accion_2,
                    LEAD(zona_jugador, 2) OVER (PARTITION BY partido_id ORDER BY id) as zona_ataque,
                    LEAD(marca, 2) OVER (PARTITION BY partido_id ORDER BY id) as marca_ataque
                FROM acciones_new
                WHERE partido_id IN ({ids_str})
            )
            SELECT 
                zona_jugador as posicion_receptor,
                zona_colocador as rotacion,
                zona_ataque,
                marca_ataque,
                COUNT(*) as cantidad
            FROM acciones_ordenadas
            WHERE tipo_accion = 'recepción'
            AND siguiente_accion = 'colocación'
            AND siguiente_accion_2 = 'atacar'
            AND zona_jugador IS NOT NULL
            AND zona_colocador IS NOT NULL
            AND zona_ataque IS NOT NULL
            GROUP BY zona_jugador, zona_colocador, zona_ataque, marca_ataque
            ORDER BY zona_colocador, zona_jugador, zona_ataque
        """), conn)
    
    if df.empty:
        return pd.DataFrame()
    
    def calcular_zona_recepcion(row):
        rotacion = row['rotacion'].lower() if row['rotacion'] else None
        posicion = row['posicion_receptor'].lower() if row['posicion_receptor'] else None
        
        if rotacion and posicion and rotacion in mapeo_recepcion:
            return mapeo_recepcion[rotacion].get(posicion, 'Altres')
        return 'Altres'
    
    df['zona_recepcion'] = df.apply(calcular_zona_recepcion, axis=1)
    df['zona_ataque'] = df['zona_ataque'].str.upper()
    df['rotacion'] = df['rotacion'].str.upper()
    
    return df

@st.cache_data(ttl=60)
def obtener_estadisticas_por_set(partido_ids):
    """Obtiene estadísticas desglosadas por set"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        # Estadísticas generales por acción
        df = pd.read_sql(text(f"""
            SELECT 
                set_numero as numero_set,
                tipo_accion,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE marca = '#') as puntos,
                COUNT(*) FILTER (WHERE marca = '+') as positivos,
                COUNT(*) FILTER (WHERE marca = '=') as errores
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND set_numero IS NOT NULL
            GROUP BY set_numero, tipo_accion
            ORDER BY set_numero, tipo_accion
        """), conn)
        
        # Errores específicos (solo recepción, atacar, saque con = y error genérico)
        df_errores = pd.read_sql(text(f"""
            SELECT 
                set_numero as numero_set,
                COUNT(*) as errores_reales
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND set_numero IS NOT NULL
            AND (
                (tipo_accion IN ('recepción', 'atacar', 'saque') AND marca = '=')
                OR tipo_accion = 'error genérico'
            )
            GROUP BY set_numero
            ORDER BY set_numero
        """), conn)
        
        if not df.empty:
            df['eficacia'] = ((df['puntos'] + df['positivos']) / df['total'] * 100).round(1)
        
        # Añadir errores reales al df
        df = df.merge(df_errores, on='numero_set', how='left')
        df['errores_reales'] = df['errores_reales'].fillna(0).astype(int)
        
        return df

@st.cache_data(ttl=60)
def obtener_puntos_por_set(partido_ids):
    """Obtiene el marcador final de cada set (sumando +1 al ganador)"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                partido_id,
                set_numero as numero_set,
                MAX(puntos_local) as puntos_local,
                MAX(puntos_visitante) as puntos_visitante
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND set_numero IS NOT NULL
            GROUP BY partido_id, set_numero
            ORDER BY partido_id, set_numero
        """), conn)
        
        # Sumar +1 al ganador de cada set (el Excel no incluye el último punto)
        if not df.empty:
            for idx, row in df.iterrows():
                p_local = int(row['puntos_local'] or 0)
                p_visit = int(row['puntos_visitante'] or 0)
                num_set = int(row['numero_set'])
                
                # Set 5 se juega a 15, los demás a 25
                puntos_minimos = 15 if num_set == 5 else 25
                
                if p_local > p_visit:
                    # Solo sumar si no ha llegado al mínimo o están empatados cerca del final
                    if p_local < puntos_minimos or (p_local >= puntos_minimos - 1 and p_local - p_visit < 2):
                        df.at[idx, 'puntos_local'] = p_local + 1
                elif p_visit > p_local:
                    if p_visit < puntos_minimos or (p_visit >= puntos_minimos - 1 and p_visit - p_local < 2):
                        df.at[idx, 'puntos_visitante'] = p_visit + 1
        
        return df

@st.cache_data(ttl=60)
def obtener_tendencias_equipo(equipo_id, temporada_id, fase_id=None):
    """Obtiene estadísticas del equipo partido a partido para ver tendencias"""
    
    with get_engine().connect() as conn:
        # Construir query base
        fase_filter = "AND p.fase_id = :fase_id" if fase_id else ""
        params = {"equipo_id": equipo_id, "temporada_id": temporada_id}
        if fase_id:
            params["fase_id"] = fase_id
        
        df = pd.read_sql(text(f"""
            SELECT 
                p.id as partido_id,
                p.rival,
                p.local,
                p.fecha,
                p.resultado,
                
                -- Ataque
                COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar') as ataques_total,
                ROUND((COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar' AND a.marca IN ('#','+'))::decimal / 
                    NULLIF(COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar'), 0)) * 100, 1) as eficacia_ataque,
                
                -- Recepción
                COUNT(*) FILTER (WHERE a.tipo_accion = 'recepción') as recepciones_total,
                ROUND((COUNT(*) FILTER (WHERE a.tipo_accion = 'recepción' AND a.marca IN ('#','+'))::decimal / 
                    NULLIF(COUNT(*) FILTER (WHERE a.tipo_accion = 'recepción'), 0)) * 100, 1) as eficacia_recepcion,
                
                -- Puntos directos
                COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar' AND a.marca = '#') as puntos_ataque,
                COUNT(*) FILTER (WHERE a.tipo_accion = 'saque' AND a.marca = '#') as puntos_saque,
                COUNT(*) FILTER (WHERE a.tipo_accion = 'bloqueo' AND a.marca = '#') as puntos_bloqueo,
                
                -- Errores (solo recepción, ataque, saque = y error genérico)
                COUNT(*) FILTER (WHERE 
                    (a.tipo_accion IN ('recepción', 'atacar', 'saque') AND a.marca = '=')
                    OR a.tipo_accion = 'error genérico'
                ) as errores
                
            FROM partidos_new p
            LEFT JOIN acciones_new a ON p.id = a.partido_id
            WHERE p.equipo_id = :equipo_id 
            AND p.temporada_id = :temporada_id
            {fase_filter}
            GROUP BY p.id, p.rival, p.local, p.fecha, p.resultado
            ORDER BY p.fecha ASC, p.id ASC
        """), conn, params=params)
        
        if not df.empty:
            # Calcular puntos directos totales
            df['puntos_directos'] = df['puntos_ataque'] + df['puntos_saque'] + df['puntos_bloqueo']
            
            # Crear etiqueta del partido
            df['partido_display'] = df.apply(
                lambda x: f"vs {x['rival']} ({'L' if x['local'] else 'V'})", axis=1
            )
            
            # Determinar victoria/derrota
            def es_victoria(resultado):
                if not resultado:
                    return None
                try:
                    partes = resultado.split('-')
                    return int(partes[0]) > int(partes[1])
                except:
                    return None
            
            df['victoria'] = df['resultado'].apply(es_victoria)
        
        return df

@st.cache_data(ttl=60)
def obtener_sideout_por_partido(equipo_id, temporada_id, fase_id=None):
    """Obtiene el % de side-out partido a partido"""
    
    with get_engine().connect() as conn:
        fase_filter = "AND p.fase_id = :fase_id" if fase_id else ""
        params = {"equipo_id": equipo_id, "temporada_id": temporada_id}
        if fase_id:
            params["fase_id"] = fase_id
        
        df = pd.read_sql(text(f"""
            WITH acciones_ordenadas AS (
                SELECT 
                    p.id as partido_id,
                    p.rival,
                    p.fecha,
                    a.tipo_accion,
                    a.marca,
                    LAG(a.tipo_accion) OVER (PARTITION BY p.id ORDER BY a.id) as accion_previa,
                    LAG(a.tipo_accion, 2) OVER (PARTITION BY p.id ORDER BY a.id) as accion_previa_2
                FROM partidos_new p
                JOIN acciones_new a ON p.id = a.partido_id
                WHERE p.equipo_id = :equipo_id 
                AND p.temporada_id = :temporada_id
                {fase_filter}
            ),
            ataques_sideout AS (
                SELECT 
                    partido_id,
                    COUNT(*) as total_sideout,
                    COUNT(*) FILTER (WHERE marca IN ('#', '+')) as sideout_positivo
                FROM acciones_ordenadas
                WHERE tipo_accion = 'atacar'
                AND (accion_previa = 'recepción' OR 
                     (accion_previa = 'colocación' AND accion_previa_2 = 'recepción'))
                GROUP BY partido_id
            )
            SELECT 
                p.id as partido_id,
                p.rival,
                p.fecha,
                COALESCE(s.total_sideout, 0) as total_sideout,
                ROUND((s.sideout_positivo::decimal / NULLIF(s.total_sideout, 0)) * 100, 1) as eficacia_sideout
            FROM partidos_new p
            LEFT JOIN ataques_sideout s ON p.id = s.partido_id
            WHERE p.equipo_id = :equipo_id 
            AND p.temporada_id = :temporada_id
            {fase_filter}
            ORDER BY p.fecha ASC, p.id ASC
        """), conn, params=params)
        
        return df

@st.cache_data(ttl=60)
def obtener_momentos_criticos(partido_ids):
    """Obtiene estadísticas en momentos críticos del partido"""
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    with get_engine().connect() as conn:
        df = pd.read_sql(text(f"""
            SELECT 
                set_numero,
                puntos_local,
                puntos_visitante,
                tipo_accion,
                marca,
                ABS(puntos_local - puntos_visitante) as diferencia,
                GREATEST(puntos_local, puntos_visitante) as punto_mayor
            FROM acciones_new
            WHERE partido_id IN ({ids_str})
            AND puntos_local IS NOT NULL
            AND puntos_visitante IS NOT NULL
        """), conn)
        
        if df.empty:
            return pd.DataFrame(), {}
        
        def calcular_stats(df_filtrado):
            """Calcula estadísticas para un conjunto de acciones"""
            stats = {}
            
            # Ataque
            ataque = df_filtrado[df_filtrado['tipo_accion'] == 'atacar']
            if len(ataque) > 0:
                stats['eficacia_ataque'] = round(len(ataque[ataque['marca'].isin(['#', '+'])]) / len(ataque) * 100, 1)
                stats['puntos_ataque'] = len(ataque[ataque['marca'] == '#'])
                stats['total_ataques'] = len(ataque)
            else:
                stats['eficacia_ataque'] = 0
                stats['puntos_ataque'] = 0
                stats['total_ataques'] = 0
            
            # Recepción
            recepcion = df_filtrado[df_filtrado['tipo_accion'] == 'recepción']
            if len(recepcion) > 0:
                stats['eficacia_recepcion'] = round(len(recepcion[recepcion['marca'].isin(['#', '+'])]) / len(recepcion) * 100, 1)
                stats['total_recepciones'] = len(recepcion)
            else:
                stats['eficacia_recepcion'] = 0
                stats['total_recepciones'] = 0
            
            # Saque
            saque = df_filtrado[df_filtrado['tipo_accion'] == 'saque']
            if len(saque) > 0:
                stats['eficacia_saque'] = round(len(saque[saque['marca'].isin(['#', '+'])]) / len(saque) * 100, 1)
                stats['puntos_saque'] = len(saque[saque['marca'] == '#'])
                stats['total_saques'] = len(saque)
            else:
                stats['eficacia_saque'] = 0
                stats['puntos_saque'] = 0
                stats['total_saques'] = 0
            
            # Bloqueo
            bloqueo = df_filtrado[df_filtrado['tipo_accion'] == 'bloqueo']
            if len(bloqueo) > 0:
                stats['eficacia_bloqueo'] = round(len(bloqueo[bloqueo['marca'].isin(['#', '+'])]) / len(bloqueo) * 100, 1)
                stats['puntos_bloqueo'] = len(bloqueo[bloqueo['marca'] == '#'])
                stats['total_bloqueos'] = len(bloqueo)
            else:
                stats['eficacia_bloqueo'] = 0
                stats['puntos_bloqueo'] = 0
                stats['total_bloqueos'] = 0
            
            # Errores (solo recepción, ataque, saque con =)
            errores = len(df_filtrado[(df_filtrado['tipo_accion'].isin(['atacar', 'saque', 'recepción'])) & (df_filtrado['marca'] == '=')])
            stats['errores'] = errores
            
            # Puntos directos totales
            stats['puntos_directos'] = stats['puntos_ataque'] + stats['puntos_saque'] + stats['puntos_bloqueo']
            
            return stats
        
        resultados = {}
        
        # 1. Puntos ajustados (diferencia <= 2 y al menos 18 puntos)
        df_ajustados = df[(df['diferencia'] <= 2) & (df['punto_mayor'] >= 18)]
        if not df_ajustados.empty:
            resultados['ajustados'] = calcular_stats(df_ajustados)
        
        # 2. Final de set (>= 20 puntos el que más tiene)
        df_final = df[df['punto_mayor'] >= 20]
        if not df_final.empty:
            resultados['final_set'] = calcular_stats(df_final)
        
        # 3. Inicio de set (<= 5 puntos el que más tiene)
        df_inicio = df[df['punto_mayor'] <= 5]
        if not df_inicio.empty:
            resultados['inicio_set'] = calcular_stats(df_inicio)
        
        # 4. Estadísticas generales
        resultados['general'] = calcular_stats(df)
        
        return df, resultados
        
def obtener_rival(nombre_archivo):
    """Extrae el nombre del rival del nombre del archivo"""
    nombre = nombre_archivo.replace(".xlsx", "")
    if "_vs_" in nombre.lower():
        partes = nombre.split("_vs_")
        if len(partes) > 1:
            rival_y_tipo = partes[1].split("_")
            rival = rival_y_tipo[0]
            return rival.strip()
    return nombre.strip()

def es_local(nombre_archivo):
    """Detecta si el partido es local o visitante según el sufijo"""
    nombre = nombre_archivo.lower()
    if "home" in nombre:
        return True
    elif "guest" in nombre or "away" in nombre:
        return False
    return True

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

def crear_grafico_ranking_jugadores(df_rankings, jugador_seleccionado=None):
    """Crea gráfico de líneas paralelas con rankings por acción"""
    
    if df_rankings.empty:
        return None
    
    # Pivotar datos para tener una fila por jugador
    acciones_orden = ['recepción', 'atacar', 'saque', 'bloqueo']
    acciones_nombres = ['Recepció', 'Atac', 'Saque', 'Bloqueig']
    
    jugadores = df_rankings['jugador'].unique()
    
    fig = go.Figure()
    
    # Encontrar el máximo ranking para invertir el eje Y
    max_ranking = df_rankings['ranking'].max()
    
    # Dibujar línea de cada jugador
    for jugador in jugadores:
        df_jug = df_rankings[df_rankings['jugador'] == jugador]
        
        # Obtener ranking en cada acción (en orden)
        rankings = []
        for accion in acciones_orden:
            rank_accion = df_jug[df_jug['tipo_accion'] == accion]['ranking'].values
            if len(rank_accion) > 0:
                rankings.append(rank_accion[0])
            else:
                rankings.append(None)
        
        # Determinar si es el jugador seleccionado
        es_seleccionado = jugador == jugador_seleccionado
        
        # Color y grosor según si está seleccionado
        if es_seleccionado:
            color = '#D32F2F'
            width = 4
            opacity = 1
        else:
            color = '#CCCCCC'
            width = 1.5
            opacity = 0.5
        
        # Añadir línea
        fig.add_trace(go.Scatter(
            x=acciones_nombres,
            y=rankings,
            mode='lines+markers',
            name=jugador,
            line=dict(color=color, width=width),
            marker=dict(size=10 if es_seleccionado else 6, color=color),
            opacity=opacity,
            hovertemplate=f'<b>{jugador}</b><br>%{{x}}: #%{{y}}<extra></extra>'
        ))
    
    # Si hay jugador seleccionado, moverlo al frente (dibujarlo último)
    if jugador_seleccionado:
        # Reordenar traces para que el seleccionado esté al final
        traces = list(fig.data)
        for i, trace in enumerate(traces):
            if trace.name == jugador_seleccionado:
                traces.append(traces.pop(i))
                break
        fig.data = traces
    
    fig.update_layout(
        title="📊 Ranking de Jugadors per Acció",
        xaxis=dict(
            title="",
            tickfont=dict(size=14, color='black'),
        ),
        yaxis=dict(
            title="Posició al Ranking",
            autorange='reversed',  # 1 arriba, números altos abajo
            tickmode='linear',
            tick0=1,
            dtick=1,
            range=[0.5, max_ranking + 0.5]
        ),
        height=450,
        showlegend=False,
        hovermode='closest',
        plot_bgcolor='white'
    )
    
    # Añadir líneas de grid verticales
    for i, accion in enumerate(acciones_nombres):
        fig.add_vline(x=i, line_dash="dot", line_color="#EEEEEE")
    
    return fig

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
            'eficacia': row['eficacia'],
            'puntos': row['puntos'] if 'puntos' in row else 0
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
            x_pos = col_idx * 1.5
            y_pos = (1 - fila_idx) * 1.2
            
            # Obtener datos de la zona
            if zona in datos_zona:
                pct = datos_zona[zona]['porcentaje']
                efic = datos_zona[zona]['eficacia']
                col_count = datos_zona[zona]['colocaciones']
                puntos = datos_zona[zona]['puntos']
            else:
                pct = 0
                efic = 0
                col_count = 0
                puntos = 0
            
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
                font=dict(size=12, color=COLOR_NEGRO)
            )
            
            # Porcentaje grande
            fig.add_annotation(
                x=x_pos, y=y_pos,
                text=f"<b>{pct}%</b>",
                showarrow=False,
                font=dict(size=18, color=COLOR_ROJO)
            )
            
            # Eficacia y puntos pequeños
            fig.add_annotation(
                x=x_pos, y=y_pos - 0.3,
                text=f"Ef:{efic}% #{int(puntos)}",
                showarrow=False,
                font=dict(size=8, color=COLOR_NEGRO)
            )
    
    # Añadir indicador de red - ARRIBA DE TODO (ajustado)
    fig.add_shape(
        type="line",
        x0=-0.8, y0=1.85,
        x1=3.8, y1=1.85,
        line=dict(color=COLOR_NEGRO, width=4, dash="solid"),
    )
    
    fig.add_annotation(
        x=1.5, y=2.0,
        text="<b>XARXA</b>",
        showarrow=False,
        font=dict(size=10, color=COLOR_NEGRO)
    )
    
    fig.update_layout(
        title="Distribució del Col·locador per Zona",
        xaxis=dict(visible=False, range=[-1, 4]),
        yaxis=dict(visible=False, range=[-0.7, 2.2], scaleanchor="x"),
        height=400,
        showlegend=False,
        plot_bgcolor='white',
        margin=dict(l=10, r=10, t=40, b=10)
    )
    
    return fig
        
def crear_mini_grafico_rotacion(df_rotacion, rotacion):
    """Crea mini visualización de distribución para una rotación específica"""
    
    # Crear diccionario de datos por zona
    datos_zona = {}
    total_ataques = df_rotacion['colocaciones'].sum() if not df_rotacion.empty else 0
    
    for _, row in df_rotacion.iterrows():
        zona = row['zona'].upper() if row['zona'] else 'N/A'
        pct = round((row['colocaciones'] / total_ataques * 100), 1) if total_ataques > 0 else 0
        
        # Calcular eficiencia: (puntos - errores) / total
        puntos = row['puntos'] if 'puntos' in row else 0
        errores = row['errores'] if 'errores' in row else 0
        total = row['colocaciones'] if row['colocaciones'] > 0 else 1
        eficiencia = round(((puntos - errores) / total) * 100, 1)
        
        datos_zona[zona] = {
            'colocaciones': row['colocaciones'],
            'porcentaje': pct,
            'eficacia': row['eficacia'],
            'puntos': puntos,
            'eficiencia': eficiencia
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
            x_pos = col_idx * 1.2
            y_pos = (1 - fila_idx) * 1.0
            
            # Obtener datos de la zona
            if zona in datos_zona:
                pct = datos_zona[zona]['porcentaje']
                efic = datos_zona[zona]['eficacia']
                puntos = datos_zona[zona]['puntos']
                eficiencia = datos_zona[zona]['eficiencia']
            else:
                pct = 0
                efic = 0
                puntos = 0
                eficiencia = 0
            
            # Color de fondo según porcentaje
            if pct >= 30:
                bg_color = "rgba(244, 67, 54, 0.3)"  # Rojo claro
            elif pct >= 15:
                bg_color = "rgba(255, 193, 7, 0.3)"  # Amarillo claro
            else:
                bg_color = COLOR_BLANCO
            
            # Añadir rectángulo de zona
            fig.add_shape(
                type="rect",
                x0=x_pos - 0.5, y0=y_pos - 0.4,
                x1=x_pos + 0.5, y1=y_pos + 0.4,
                fillcolor=bg_color,
                line=dict(color=COLOR_NEGRO, width=1),
            )
            
            # Texto de la zona
            fig.add_annotation(
                x=x_pos, y=y_pos + 0.22,
                text=f"<b>{zona}</b>",
                showarrow=False,
                font=dict(size=10, color=COLOR_NEGRO)
            )
            
            # Porcentaje
            fig.add_annotation(
                x=x_pos, y=y_pos,
                text=f"<b>{pct}%</b>",
                showarrow=False,
                font=dict(size=16, color=COLOR_ROJO)
            )
            
            # Puntos y eficiencia
            fig.add_annotation(
                x=x_pos, y=y_pos - 0.25,
                text=f"#{int(puntos)} ({eficiencia}%)",
                showarrow=False,
                font=dict(size=9, color=COLOR_NEGRO)
            )
    
    fig.update_layout(
        title=f"Rotació {rotacion} ({total_ataques} atacs)",
        xaxis=dict(visible=False, range=[-0.8, 3.2]),
        yaxis=dict(visible=False, range=[-0.6, 1.5], scaleanchor="x"),
        height=220,
        margin=dict(l=5, r=5, t=35, b=5),
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
    
    # Mostrar contenido si hay contexto
    if 'equipo_id' in st.session_state and st.session_state.equipo_id:
        
        # Obtener badges
        badges = obtener_badges_equipo(
            st.session_state.equipo_id,
            st.session_state.temporada_id,
            st.session_state.get('fase_id')
        )
        
        # Notificación si hay badges nuevos (del último partido)
        if badges:
            partidos = cargar_partidos(
                st.session_state.equipo_id,
                st.session_state.temporada_id,
                st.session_state.get('fase_id')
            )
            
            if not partidos.empty:
                ultimo_partido_id = partidos.iloc[0]['id']
                badges_nuevos = [b for b in badges if b['partido_id'] == ultimo_partido_id]
                
                if badges_nuevos:
                    st.markdown(f"""
                    <div style="background: linear-gradient(90deg, #4CAF50 0%, #45a049 100%); 
                                color: white; padding: 1rem 1.5rem; border-radius: 10px; 
                                margin-bottom: 1.5rem; display: flex; align-items: center;">
                        <span style="font-size: 2rem; margin-right: 1rem;">🎉</span>
                        <div>
                            <h3 style="margin: 0; color: white;">Nous assoliments desbloquejats!</h3>
                            <p style="margin: 0; opacity: 0.9;">{len(badges_nuevos)} badges nous a l'últim partit</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
        # Resumen rápido
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
        
        # Sección de Badges
        if badges:
            st.markdown("---")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader("🏆 Últims Assoliments de l'Equip")
            with col2:
                st.markdown(f"""
                <div style="background: #C8102E; color: white; padding: 0.3rem 0.8rem; 
                            border-radius: 20px; text-align: center; margin-top: 0.5rem;">
                    {len(badges)} totals
                </div>
                """, unsafe_allow_html=True)
            
            # Mostrar badges en grid (máximo 6)
            badges_mostrar = badges[:6]
            
            cols = st.columns(2)
            for idx, badge in enumerate(badges_mostrar):
                with cols[idx % 2]:
                    # Determinar color según tipo
                    if badge['tipo'] == 'gold':
                        bg_color = "linear-gradient(135deg, #fff9e6 0%, #ffe066 100%)"
                        border_color = "#FFD700"
                    elif badge['tipo'] == 'fire':
                        bg_color = "linear-gradient(135deg, #ffe5e5 0%, #ffcccc 100%)"
                        border_color = "#ff4444"
                    elif badge['tipo'] == 'perfect':
                        bg_color = "linear-gradient(135deg, #e5ffe5 0%, #ccffcc 100%)"
                        border_color = "#44ff44"
                    else:
                        bg_color = "linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%)"
                        border_color = "#C8102E"
                    
                    # Calcular si es nuevo (del último partido)
                    es_nuevo = badge['partido_id'] == partidos.iloc[0]['id'] if not partidos.empty else False
                    nuevo_tag = '<span style="background: #C8102E; color: white; font-size: 0.7rem; padding: 0.2rem 0.5rem; border-radius: 10px; margin-left: 0.5rem;">NOU!</span>' if es_nuevo else ''
                    
                    # Formatear fecha
                    if badge['fecha']:
                        from datetime import datetime, date
                        if isinstance(badge['fecha'], str):
                            fecha_badge = datetime.strptime(badge['fecha'], '%Y-%m-%d').date()
                        else:
                            fecha_badge = badge['fecha']
                        
                        dias = (date.today() - fecha_badge).days
                        if dias == 0:
                            fecha_texto = "Avui"
                        elif dias == 1:
                            fecha_texto = "Ahir"
                        elif dias < 7:
                            fecha_texto = f"Fa {dias} dies"
                        elif dias < 14:
                            fecha_texto = "Fa 1 setmana"
                        else:
                            fecha_texto = f"Fa {dias // 7} setmanes"
                    else:
                        fecha_texto = ""
                    
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; padding: 1rem; 
                                border-radius: 10px; background: {bg_color}; 
                                border-left: 4px solid {border_color}; margin-bottom: 0.5rem;">
                        <span style="font-size: 2rem; margin-right: 1rem;">{badge['icono']}</span>
                        <div>
                            <h4 style="margin: 0; font-size: 0.95rem;">{badge['titulo']} {nuevo_tag}</h4>
                            <p style="margin: 0.2rem 0; font-size: 0.85rem; color: #666;">{badge['descripcion']}</p>
                            <span style="font-size: 0.75rem; color: #999;">{fecha_texto}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            if len(badges) > 6:
                st.info(f"📜 I {len(badges) - 6} assoliments més...")
        
        else:
            st.markdown("---")
            st.info("🏆 Encara no hi ha assoliments. Juga partits per desbloquejar badges!")
    
    else:
        # Sin contexto seleccionado
        st.markdown("""
        ### Benvingut al sistema d'anàlisi estadístic!
        
        Utilitza el menú lateral per seleccionar el context de treball i navegar entre les diferents seccions:
        
        - **📊 Partit**: Estadístiques completes d'un partit
        - **👤 Jugador**: Anàlisi individual de jugadors
        - **🎴 Fitxes**: Fitxa ràpida de jugadors
        - **📈 Comparativa**: Compara partits o jugadors
        
        ---
        
        #### Com començar:
        1. Selecciona l'**equip** al menú lateral
        2. Selecciona la **temporada** i opcionalment la **fase**
        3. Navega a la secció que vulguis analitzar
        """)

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
        resultado = info_partido.get('resultado')
        resultado_txt = resultado if resultado else '-'
        info_extra = f"""**Tipus:** {'Local' if info_partido['local'] else 'Visitant'} | 
        **Fase:** {info_partido.get('fase', '-')} |
        **Resultat:** {resultado_txt}"""
    
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
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Accions", 
        "⚔️ Side-out", 
        "🔄 Rotacions",
        "🎯 Distribució",
        "⚠️ Errors",
        "📈 Sets"
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
        
        # Sub-tabs dentro de Distribució
        subtab1, subtab2 = st.tabs(["📊 Per Zona", "🏐 Segons Recepció"])
        
        with subtab1:
            # Contenido original de distribución por zona
            if not df_distribucion.empty:
                st.plotly_chart(crear_grafico_distribucion_colocador(df_distribucion), use_container_width=True, config={'staticPlot': True})
                
                st.markdown("##### 📋 Detall per Zona")
                df_dist_display = df_distribucion.rename(columns={
                    'zona': 'Zona',
                    'colocaciones': 'Col·locacions',
                    'porcentaje': '% Total',
                    'eficacia': 'Eficàcia Atac (%)',
                    'puntos': 'Punts (#)'
                })
                st.dataframe(df_dist_display, use_container_width=True, hide_index=True)
                
                max_zona = df_distribucion.loc[df_distribucion['porcentaje'].idxmax()]
                st.info(f"📊 **Zona més utilitzada:** {max_zona['zona']} ({max_zona['porcentaje']}% del total)")
                
                if max_zona['porcentaje'] > 40:
                    st.warning("⚠️ Alta dependència d'una zona. Considera diversificar la distribució.")
                
                # === DISTRIBUCIÓ PER ROTACIÓ ===
            st.markdown("---")
            st.markdown("##### 🔄 Distribució per Rotació")
            
            df_rot_set = obtener_distribucion_por_rotacion(partido_ids)
            
            if not df_rot_set.empty:
                # Mostrar rotaciones en filas de 2
                for fila in range(0, 6, 2):
                    cols = st.columns(2)
                    for col_idx, col in enumerate(cols):
                        rot_num = fila + col_idx + 1
                        rotacion_key = f"p{rot_num}"
                        df_rot = df_rot_set[df_rot_set['rotacion'] == rotacion_key]
                        
                        with col:
                            if not df_rot.empty:
                                fig_rot = crear_mini_grafico_rotacion(df_rot, rotacion_key)
                                st.plotly_chart(fig_rot, use_container_width=True, config={'staticPlot': True})
                            else:
                                st.markdown(f"**Rotació {rotacion_key}**")
                                st.info("Sense dades")
                
                # Tabla resumen por rotación
                with st.expander("📋 Taula resum per rotació"):
                    df_resumen_rot = df_rot_set.groupby('rotacion').agg({
                        'colocaciones': 'sum',
                        'puntos': 'sum'
                    }).reset_index()
                    df_resumen_rot['eficacia'] = df_rot_set.groupby('rotacion').apply(
                        lambda x: round((x['puntos'].sum() / x['colocaciones'].sum() * 100), 1) if x['colocaciones'].sum() > 0 else 0
                    ).values
                    df_resumen_rot = df_resumen_rot.rename(columns={
                        'rotacion': 'Rotació',
                        'colocaciones': 'Atacs',
                        'puntos': 'Punts (#)',
                        'eficacia': 'Eficàcia (%)'
                    })
                    st.dataframe(df_resumen_rot, use_container_width=True, hide_index=True)
            else:
                st.info("No hi ha dades de rotació per aquest set")
        
        with subtab2:
            st.markdown("""
            Anàlisi de com distribueix el col·locador segons **des d'on es rep** i en quina **rotació** estem.
            """)
            
            df_rec_dist = obtener_distribucion_por_recepcion(partido_ids)
            
            if df_rec_dist.empty:
                st.info("No hi ha dades suficients per aquest anàlisi")
            else:
                # Filtros
                col1, col2 = st.columns(2)
                
                with col1:
                    rotaciones_disponibles = ['Totes'] + sorted(df_rec_dist['rotacion'].unique().tolist())
                    rotacion_filtro = st.selectbox(
                        "Filtrar per rotació:",
                        options=rotaciones_disponibles,
                        key="filtro_rotacion_rec"
                    )
                
                with col2:
                    zonas_recepcion = ['Totes'] + sorted(df_rec_dist['zona_recepcion'].unique().tolist())
                    zona_rec_filtro = st.selectbox(
                        "Filtrar per zona de recepció:",
                        options=zonas_recepcion,
                        key="filtro_zona_rec"
                    )
                
                # Aplicar filtros
                df_filtrado = df_rec_dist.copy()
                if rotacion_filtro != 'Totes':
                    df_filtrado = df_filtrado[df_filtrado['rotacion'] == rotacion_filtro]
                if zona_rec_filtro != 'Totes':
                    df_filtrado = df_filtrado[df_filtrado['zona_recepcion'] == zona_rec_filtro]
                
                if df_filtrado.empty:
                    st.warning("No hi ha dades amb aquests filtres")
                else:
                    # Agrupar por zona de ataque
                    dist_zona_ataque = df_filtrado.groupby('zona_ataque').agg({
                        'cantidad': 'sum'
                    }).reset_index()
                    
                    total = dist_zona_ataque['cantidad'].sum()
                    dist_zona_ataque['porcentaje'] = (dist_zona_ataque['cantidad'] / total * 100).round(1)
                    
                    # Calcular eficacia por zona
                    eficacia_zona = df_filtrado.groupby('zona_ataque').apply(
                        lambda x: round((x[x['marca_ataque'].isin(['#', '+'])]['cantidad'].sum() / x['cantidad'].sum()) * 100, 1)
                    ).reset_index()
                    eficacia_zona.columns = ['zona_ataque', 'eficacia']
                    
                    dist_zona_ataque = dist_zona_ataque.merge(eficacia_zona, on='zona_ataque', how='left')
                    dist_zona_ataque = dist_zona_ataque.sort_values('porcentaje', ascending=False)
                    
                    # Gráfico de barras
                    fig = go.Figure()
                    
                    colores = [COLOR_ROJO if p == dist_zona_ataque['porcentaje'].max() else COLOR_NEGRO 
                              for p in dist_zona_ataque['porcentaje']]
                    
                    fig.add_trace(go.Bar(
                        x=dist_zona_ataque['zona_ataque'],
                        y=dist_zona_ataque['porcentaje'],
                        marker_color=colores,
                        text=dist_zona_ataque['porcentaje'].apply(lambda x: f'{x}%'),
                        textposition='outside'
                    ))
                    
                    fig.update_layout(
                        title=f"On col·loca? (Total: {total} atacs)",
                        xaxis_title="Zona d'Atac",
                        yaxis_title="% de Col·locacions",
                        height=350,
                        yaxis=dict(range=[0, max(dist_zona_ataque['porcentaje']) + 15])
                    )
                    
                    st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})
                    
                    # Tabla resumen
                    st.markdown("##### 📋 Detall per Zona")
                    df_display = dist_zona_ataque.rename(columns={
                        'zona_ataque': 'Zona Atac',
                        'cantidad': 'Col·locacions',
                        'porcentaje': '% Total',
                        'eficacia': 'Eficàcia Atac (%)'
                    })
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                    
                    # Detalle por rotación y zona de recepción
                    st.markdown("---")
                    st.markdown("##### 🔄 Detall per Rotació i Zona de Recepció")
                    
                    tabla_cruzada = df_rec_dist.groupby(['rotacion', 'zona_recepcion', 'zona_ataque']).agg({
                        'cantidad': 'sum'
                    }).reset_index()
                    
                    for rotacion in sorted(df_rec_dist['rotacion'].unique()):
                        with st.expander(f"📍 Rotació {rotacion}"):
                            df_rot = tabla_cruzada[tabla_cruzada['rotacion'] == rotacion]
                            
                            if not df_rot.empty:
                                for zona_rec in sorted(df_rot['zona_recepcion'].unique()):
                                    df_zona = df_rot[df_rot['zona_recepcion'] == zona_rec]
                                    total_zona = df_zona['cantidad'].sum()
                                    
                                    st.markdown(f"**Recepció des de {zona_rec}** ({total_zona} accions)")
                                    
                                    cols = st.columns(len(df_zona))
                                    for idx, (_, row) in enumerate(df_zona.iterrows()):
                                        pct = round(row['cantidad'] / total_zona * 100, 1)
                                        with cols[idx]:
                                            st.metric(
                                                row['zona_ataque'],
                                                f"{pct}%",
                                                f"{int(row['cantidad'])} col."
                                            )
                                    
                                    st.markdown("")
                            else:
                                st.info("No hi ha dades")
                    
                    # Insights
                    st.markdown("---")
                    st.markdown("##### 💡 Conclusions")
                    
                    zona_preferida = dist_zona_ataque.iloc[0]
                    zona_eficaz = dist_zona_ataque.loc[dist_zona_ataque['eficacia'].idxmax()]
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.success(f"🎯 **Zona preferida:** {zona_preferida['zona_ataque']} ({zona_preferida['porcentaje']}%)")
                    with col2:
                        st.success(f"✅ **Més efectiva:** {zona_eficaz['zona_ataque']} ({zona_eficaz['eficacia']}% efic.)")
    
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

    with tab6:
        st.subheader("📈 Anàlisi per Sets")
        
        df_sets = obtener_estadisticas_por_set(partido_ids)
        df_puntos_sets = obtener_puntos_por_set(partido_ids)
        
        if df_sets.empty:
            st.info("No hi ha dades de sets disponibles")
        else:
            # Detectar si hay múltiples partidos
            es_multiple = isinstance(partido_ids, list) and len(partido_ids) > 1
            
            if es_multiple:
                st.info(f"📊 Mostrant **mitjanes** de {len(partido_ids)} partits seleccionats")
            
            # Selector de set
            sets_disponibles = sorted(df_sets['numero_set'].unique())
            
            set_seleccionado = st.selectbox(
                "Selecciona el set:",
                options=sets_disponibles,
                format_func=lambda x: f"Set {int(x)}" + (" (mitjana)" if es_multiple else ""),
                key="selector_set_analisis"
            )
            
            # Mostrar resultado del set seleccionado
            if not df_puntos_sets.empty:
                set_info = df_puntos_sets[df_puntos_sets['numero_set'] == set_seleccionado]
                
                if es_multiple and not set_info.empty:
                    # Calcular medias y totales para múltiples partidos
                    p_local_media = set_info['puntos_local'].mean()
                    p_visit_media = set_info['puntos_visitante'].mean()
                    sets_ganados = len(set_info[set_info['puntos_local'] > set_info['puntos_visitante']])
                    sets_perdidos = len(set_info[set_info['puntos_local'] < set_info['puntos_visitante']])
                    total_sets = len(set_info)
                    
                    if sets_ganados > sets_perdidos:
                        color_resultado = COLOR_VERDE
                    elif sets_ganados < sets_perdidos:
                        color_resultado = COLOR_ROJO
                    else:
                        color_resultado = COLOR_NARANJA
                    
                    st.markdown(f"""
                    <div style="background: {COLOR_GRIS}; padding: 1rem; border-radius: 10px; text-align: center; border-left: 4px solid {color_resultado}; margin-bottom: 1rem;">
                        <strong style="font-size: 1.2rem;">Set {int(set_seleccionado)} - Mitjana: {p_local_media:.1f} - {p_visit_media:.1f}</strong><br>
                        <span style="font-size: 0.9rem;">✅ {sets_ganados} guanyats · ❌ {sets_perdidos} perduts · Total: {total_sets} sets</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                elif not set_info.empty:
                    # Partido único
                    p_local = int(set_info['puntos_local'].iloc[0]) if set_info['puntos_local'].iloc[0] else 0
                    p_visit = int(set_info['puntos_visitante'].iloc[0]) if set_info['puntos_visitante'].iloc[0] else 0
                    
                    if p_local > p_visit:
                        color_resultado = COLOR_VERDE
                        icono = "✅ Guanyat"
                    elif p_local < p_visit:
                        color_resultado = COLOR_ROJO
                        icono = "❌ Perdut"
                    else:
                        color_resultado = COLOR_NARANJA
                        icono = "➡️"
                    
                    st.markdown(f"""
                    <div style="background: {COLOR_GRIS}; padding: 1rem; border-radius: 10px; text-align: center; border-left: 4px solid {color_resultado}; margin-bottom: 1rem;">
                        <strong style="font-size: 1.2rem;">Set {int(set_seleccionado)}: {p_local} - {p_visit}</strong>
                        <span style="margin-left: 1rem;">{icono}</span>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # === ESTADÍSTICAS GENERALES DEL SET ===
            if es_multiple:
                st.markdown("##### 📊 Estadístiques del Set (Mitjanes)")
            else:
                st.markdown("##### 📊 Estadístiques del Set")
            
            df_set = df_sets[df_sets['numero_set'] == int(set_seleccionado)]
            
            if es_multiple:
                # Calcular medias agrupando por tipo_accion
                ataque = df_set[df_set['tipo_accion'] == 'atacar']
                efic_ataque = float(ataque['eficacia'].mean()) if not ataque.empty else 0
                
                recepcion = df_set[df_set['tipo_accion'] == 'recepción']
                efic_recepcion = float(recepcion['eficacia'].mean()) if not recepcion.empty else 0
                
                saque = df_set[df_set['tipo_accion'] == 'saque']
                puntos_saque = float(saque['puntos'].mean()) if not saque.empty else 0
                
                bloqueo = df_set[df_set['tipo_accion'] == 'bloqueo']
                puntos_bloqueo = float(bloqueo['puntos'].mean()) if not bloqueo.empty else 0
                
                errores_total = float(df_set['errores_reales'].mean()) if 'errores_reales' in df_set.columns and not df_set.empty else 0
                
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Efic. Atac", f"{efic_ataque:.1f}%")
                col2.metric("Efic. Recep.", f"{efic_recepcion:.1f}%")
                col3.metric("Aces (mitj.)", f"{puntos_saque:.1f}")
                col4.metric("Blocs (mitj.)", f"{puntos_bloqueo:.1f}")
                col5.metric("Errors (mitj.)", f"{errores_total:.1f}")
            else:
                # Partido único - valores exactos
                ataque = df_set[df_set['tipo_accion'] == 'atacar']
                efic_ataque = float(ataque['eficacia'].iloc[0]) if not ataque.empty else 0
                
                recepcion = df_set[df_set['tipo_accion'] == 'recepción']
                efic_recepcion = float(recepcion['eficacia'].iloc[0]) if not recepcion.empty else 0
                
                saque = df_set[df_set['tipo_accion'] == 'saque']
                puntos_saque = int(saque['puntos'].iloc[0]) if not saque.empty else 0
                
                bloqueo = df_set[df_set['tipo_accion'] == 'bloqueo']
                puntos_bloqueo = int(bloqueo['puntos'].iloc[0]) if not bloqueo.empty else 0
                
                errores_total = df_set['errores_reales'].iloc[0] if 'errores_reales' in df_set.columns and not df_set.empty else 0
                
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Efic. Atac", f"{efic_ataque}%")
                col2.metric("Efic. Recep.", f"{efic_recepcion}%")
                col3.metric("Aces", puntos_saque)
                col4.metric("Blocs", puntos_bloqueo)
                col5.metric("Errors", int(errores_total))
            
            # === SIDE-OUT I CONTRAATAC ===
            st.markdown("---")
            st.markdown("##### ⚔️ Side-out i Contraatac" + (" (Mitjanes)" if es_multiple else ""))
            
            df_sideout = obtener_sideout_por_set(partido_ids, int(set_seleccionado))
            
            if not df_sideout.empty:
                row = df_sideout.iloc[0]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    total_so = int(row['total_sideout']) if row['total_sideout'] else 0
                    positivo_so = int(row['sideout_positivo']) if row['sideout_positivo'] else 0
                    puntos_so = int(row['sideout_puntos']) if row['sideout_puntos'] else 0
                    efic_so = round((positivo_so / total_so * 100), 1) if total_so > 0 else 0
                    
                    st.markdown(f"""
                    <div style="background: #E3F2FD; padding: 1rem; border-radius: 10px; text-align: center;">
                        <h4 style="margin: 0;">🏐 Side-out</h4>
                        <p style="font-size: 2rem; font-weight: bold; margin: 0.5rem 0; color: {COLOR_ROJO};">{efic_so}%</p>
                        <p style="margin: 0;">{positivo_so}/{total_so} positius · {puntos_so} punts</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    total_ca = int(row['total_contraataque']) if row['total_contraataque'] else 0
                    positivo_ca = int(row['contraataque_positivo']) if row['contraataque_positivo'] else 0
                    puntos_ca = int(row['contraataque_puntos']) if row['contraataque_puntos'] else 0
                    efic_ca = round((positivo_ca / total_ca * 100), 1) if total_ca > 0 else 0
                    
                    st.markdown(f"""
                    <div style="background: #FFF3E0; padding: 1rem; border-radius: 10px; text-align: center;">
                        <h4 style="margin: 0;">⚡ Contraatac</h4>
                        <p style="font-size: 2rem; font-weight: bold; margin: 0.5rem 0; color: {COLOR_ROJO};">{efic_ca}%</p>
                        <p style="margin: 0;">{positivo_ca}/{total_ca} positius · {puntos_ca} punts</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No hi ha dades de side-out/contraatac per aquest set")
            
            # === DISTRIBUCIÓ DEL COL·LOCADOR ===
            st.markdown("---")
            st.markdown("##### 🎯 Distribució del Col·locador" + (" (Agregat)" if es_multiple else ""))
            
            df_dist_set = obtener_distribucion_colocador_por_set(partido_ids, int(set_seleccionado))
            
            if not df_dist_set.empty:
                # Gráfico de distribución
                fig_dist = crear_grafico_distribucion_colocador(df_dist_set)
                if fig_dist:
                    st.plotly_chart(fig_dist, use_container_width=True, config={'staticPlot': True})
                
                # Tabla de detalle
                with st.expander("📋 Detall per zona"):
                    df_dist_display = df_dist_set.rename(columns={
                        'zona': 'Zona',
                        'colocaciones': 'Atacs',
                        'porcentaje': '% Total',
                        'eficacia': 'Eficàcia (%)',
                        'puntos': 'Punts (#)'
                    })
                    st.dataframe(df_dist_display, use_container_width=True, hide_index=True)
            else:
                st.info("No hi ha dades de distribució per aquest set")
            
            # === DISTRIBUCIÓ PER ROTACIÓ ===
            st.markdown("---")
            st.markdown("##### 🔄 Distribució per Rotació" + (" (Agregat)" if es_multiple else ""))
            
            df_rot_set = obtener_distribucion_por_rotacion_set(partido_ids, int(set_seleccionado))
            
            if not df_rot_set.empty:
                rotaciones = sorted(df_rot_set['rotacion'].unique())
                
                # Crear 2 filas de 3 columnas
                for fila in range(0, len(rotaciones), 3):
                    cols = st.columns(3)
                    for col_idx, col in enumerate(cols):
                        rot_idx = fila + col_idx
                        if rot_idx < len(rotaciones):
                            rotacion = rotaciones[rot_idx]
                            df_rot = df_rot_set[df_rot_set['rotacion'] == rotacion]
                            
                            with col:
                                fig_rot = crear_mini_grafico_rotacion(df_rot, rotacion)
                                st.plotly_chart(fig_rot, use_container_width=True, config={'staticPlot': True})
            else:
                st.info("No hi ha dades de rotació per aquest set")
            
            # === DETALL PER JUGADOR ===
            st.markdown("---")
            st.markdown("##### 👥 Detall per Jugador")
            
            df_jugadores_set = obtener_estadisticas_jugadores_por_set(partido_ids, int(set_seleccionado))
            
            if not df_jugadores_set.empty:
                # Pivotar datos
                jugadores_unicos = df_jugadores_set['jugador'].unique()
                acciones = ['atacar', 'recepción', 'saque', 'bloqueo']
                
                data_rows = []
                for jugador in jugadores_unicos:
                    df_jug = df_jugadores_set[df_jugadores_set['jugador'] == jugador]
                    
                    row = {'Jugador': jugador}
                    
                    for accion in acciones:
                        df_acc = df_jug[df_jug['tipo_accion'] == accion]
                        
                        if accion == 'atacar':
                            prefix = 'Atac'
                        elif accion == 'recepción':
                            prefix = 'Recep'
                        elif accion == 'saque':
                            prefix = 'Saque'
                        else:
                            prefix = 'Bloc'
                        
                        if not df_acc.empty:
                            row[f'{prefix} #'] = int(df_acc['puntos'].iloc[0])
                            row[f'{prefix} +'] = int(df_acc['positivos'].iloc[0])
                            row[f'{prefix} !'] = int(df_acc['neutros'].iloc[0])
                            row[f'{prefix} -'] = int(df_acc['negativos'].iloc[0])
                            row[f'{prefix} /'] = int(df_acc['errores_forzados'].iloc[0])
                            row[f'{prefix} ='] = int(df_acc['errores'].iloc[0])
                            row[f'{prefix} Efc'] = df_acc['eficacia'].iloc[0]
                            row[f'{prefix} Efn'] = df_acc['eficiencia'].iloc[0]
                        else:
                            row[f'{prefix} #'] = None
                            row[f'{prefix} +'] = None
                            row[f'{prefix} !'] = None
                            row[f'{prefix} -'] = None
                            row[f'{prefix} /'] = None
                            row[f'{prefix} ='] = None
                            row[f'{prefix} Efc'] = None
                            row[f'{prefix} Efn'] = None
                    
                    data_rows.append(row)
                
                df_tabla = pd.DataFrame(data_rows)
                
                # Usar st.dataframe con scroll
                st.dataframe(df_tabla, use_container_width=True, hide_index=True, height=400)
            else:
                st.info("No hi ha dades de jugadors per aquest set")
            
            # === MOMENTS CRÍTICS DEL SET ===
            if not es_multiple:
                st.markdown("---")
                st.markdown("##### 🎯 Moments Crítics del Set")
                
                _, momentos = obtener_momentos_criticos(partido_ids)
                
                if momentos:
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown(f"""
                        <div style="background: #E3F2FD; padding: 1rem; border-radius: 10px; text-align: center;">
                            <h4 style="margin: 0;">🚀 Inici de Set</h4>
                            <p style="font-size: 0.8rem; color: #666;">(0-5 punts)</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if 'inicio_set' in momentos:
                            datos = momentos['inicio_set']
                            st.metric("Efic. Atac", f"{datos['eficacia_ataque']}%")
                            st.metric("Efic. Recep.", f"{datos['eficacia_recepcion']}%")
                        else:
                            st.info("Sense dades")
                    
                    with col2:
                        st.markdown(f"""
                        <div style="background: #FFF3E0; padding: 1rem; border-radius: 10px; text-align: center;">
                            <h4 style="margin: 0;">⚔️ Punts Ajustats</h4>
                            <p style="font-size: 0.8rem; color: #666;">(diferència ≤2, +18 pts)</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if 'ajustados' in momentos:
                            datos = momentos['ajustados']
                            st.metric("Efic. Atac", f"{datos['eficacia_ataque']}%")
                            st.metric("Efic. Recep.", f"{datos['eficacia_recepcion']}%")
                        else:
                            st.info("Sense dades")
                    
                    with col3:
                        st.markdown(f"""
                        <div style="background: #FFEBEE; padding: 1rem; border-radius: 10px; text-align: center;">
                            <h4 style="margin: 0;">🏁 Final de Set</h4>
                            <p style="font-size: 0.8rem; color: #666;">(+20 punts)</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if 'final_set' in momentos:
                            datos = momentos['final_set']
                            st.metric("Efic. Atac", f"{datos['eficacia_ataque']}%")
                            st.metric("Efic. Recep.", f"{datos['eficacia_recepcion']}%")
                        else:
                            st.info("Sense dades")
                else:
                    st.info("No hi ha dades suficients de punts per analitzar moments crítics")
            
    
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
                dorsal_str = f"#{int(row['dorsal'])}" if pd.notna(row['dorsal']) else ""
                posicion_str = f"({row['posicion']})" if row['posicion'] else ""
                st.markdown(f"""
                <div style="background: {COLOR_GRIS}; padding: 0.5rem; border-radius: 5px; margin: 0.25rem 0; text-align: center;">
                    <strong>{row['jugador']}</strong> {dorsal_str}<br>
                    <small>{posicion_str} - {row['acciones']} accions</small>
                </div>
                """, unsafe_allow_html=True)
        
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

        # === RACHA ACTUAL ===
        if partido_seleccionado == "Tots els partits" and len(partido_ids) >= 2:
            st.subheader("🔥 Ratxa Actual")
            
            # Obtener evolución para analizar rachas
            df_evolucion = obtener_evolucion_jugador(partido_ids, jugador_id)
            
            if not df_evolucion.empty:
                rachas = []
                
                # Analizar cada acción
                for accion, nombre in [('atacar', 'Atac'), ('recepción', 'Recepció'), ('saque', 'Saque')]:
                    df_accion = df_evolucion[df_evolucion['tipo_accion'] == accion].sort_values('fecha')
                    
                    if len(df_accion) >= 2:
                        # Contar racha de mejora
                        racha_mejora = 0
                        eficacias = df_accion['eficacia'].tolist()
                        
                        for i in range(len(eficacias) - 1, 0, -1):
                            if eficacias[i] >= eficacias[i-1]:
                                racha_mejora += 1
                            else:
                                break
                        
                        if racha_mejora >= 2:
                            rachas.append(f"📈 Portes **{racha_mejora} partits** millorant en **{nombre.lower()}**!")
                        
                        # Mejor partido
                        mejor_partido = df_accion.loc[df_accion['eficacia'].idxmax()]
                        if mejor_partido['eficacia'] >= 50:
                            rachas.append(f"⭐ Millor partit en {nombre.lower()}: **vs {mejor_partido['rival']}** ({mejor_partido['eficacia']}%)")
                        
                        # Tendencia temporada
                        primer_partido = eficacias[0]
                        ultimo_partido = eficacias[-1]
                        diferencia = ultimo_partido - primer_partido
                        
                        if diferencia >= 10:
                            rachas.append(f"🚀 Has pujat **{diferencia:.0f}%** en {nombre.lower()} aquesta temporada!")
                        elif diferencia <= -10:
                            rachas.append(f"💪 Pots millorar en {nombre.lower()}: has baixat {abs(diferencia):.0f}% des del primer partit")
                
                # Calcular puntos totales
                puntos_totales = 0
                for accion in ['atacar', 'saque', 'bloqueo']:
                    df_acc = df_evolucion[df_evolucion['tipo_accion'] == accion]
                    if not df_acc.empty:
                        puntos_totales += df_acc['puntos'].sum()
                
                if puntos_totales > 0:
                    rachas.insert(0, f"⚡ **{int(puntos_totales)} punts directes** aquesta temporada!")
                
                # Mostrar rachas
                if rachas:
                    cols = st.columns(2)
                    for idx, racha in enumerate(rachas[:4]):  # Máximo 4 rachas
                        with cols[idx % 2]:
                            st.info(racha)
                else:
                    st.info("📊 Juga més partits per veure les teves ratxes!")
            
            st.markdown("---")
        
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
        
        # === PUNTS FORTS I FEBLES ===
        st.markdown("---")
        st.subheader("💪 Punts Forts i Febles")
        
        if not df_jugador.empty and not df_media_equipo.empty:
            # Calcular diferencias con la media para cada acción
            analisis = []
            nombres_acc = {'atacar': 'Atac', 'recepción': 'Recepció', 'saque': 'Saque', 'bloqueo': 'Bloqueig'}
            
            for accion in ['atacar', 'recepción', 'saque', 'bloqueo']:
                jugador_row = df_jugador[df_jugador['tipo_accion'] == accion]
                media_row = df_media_equipo[df_media_equipo['tipo_accion'] == accion]
                
                if not jugador_row.empty and not media_row.empty:
                    efic_jugador = float(jugador_row['eficacia'].iloc[0])
                    efic_media = float(media_row['eficacia_media'].iloc[0])
                    total = int(jugador_row['total'].iloc[0])
                    diferencia = efic_jugador - efic_media
                    
                    if total >= 5:  # Solo considerar si tiene suficientes acciones
                        analisis.append({
                            'accion': accion,
                            'nombre': nombres_acc[accion],
                            'eficacia': efic_jugador,
                            'diferencia': diferencia,
                            'total': total
                        })
            
            if analisis:
                # Ordenar por diferencia
                analisis_ordenado = sorted(analisis, key=lambda x: x['diferencia'], reverse=True)
                
                col1, col2 = st.columns(2)
                
                # Puntos fuertes (diferencia positiva)
                with col1:
                    punts_forts = [a for a in analisis_ordenado if a['diferencia'] > 0]
                    
                    st.markdown(f"""
                    <div style="background: #E8F5E9; padding: 1rem; border-radius: 10px; border-left: 4px solid {COLOR_VERDE};">
                        <h4 style="color: {COLOR_VERDE}; margin: 0;">✅ Punts Forts</h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if punts_forts:
                        for pf in punts_forts:
                            st.markdown(f"""
                            <div style="padding: 0.5rem; margin: 0.5rem 0; background: white; border-radius: 5px;">
                                <strong>{pf['nombre']}</strong>: {pf['eficacia']}% 
                                <span style="color: {COLOR_VERDE};">(+{pf['diferencia']:.1f}% vs equip)</span>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.markdown("<p style='padding: 0.5rem;'>Cap acció destaca per sobre la mitjana</p>", unsafe_allow_html=True)
                
                # Puntos a mejorar (diferencia negativa)
                with col2:
                    punts_febles = [a for a in analisis_ordenado if a['diferencia'] < 0]
                    
                    st.markdown(f"""
                    <div style="background: #FFEBEE; padding: 1rem; border-radius: 10px; border-left: 4px solid {COLOR_ROJO};">
                        <h4 style="color: {COLOR_ROJO}; margin: 0;">⚠️ A Millorar</h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if punts_febles:
                        for pf in punts_febles:
                            st.markdown(f"""
                            <div style="padding: 0.5rem; margin: 0.5rem 0; background: white; border-radius: 5px;">
                                <strong>{pf['nombre']}</strong>: {pf['eficacia']}% 
                                <span style="color: {COLOR_ROJO};">({pf['diferencia']:.1f}% vs equip)</span>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.markdown("<p style='padding: 0.5rem;'>Totes les accions estan a la mitjana o per sobre!</p>", unsafe_allow_html=True)
                
                # Resumen general
                if analisis_ordenado:
                    mejor = analisis_ordenado[0]
                    peor = analisis_ordenado[-1]
                    
                    st.markdown("---")
                    st.markdown(f"""
                    <div style="background: {COLOR_GRIS}; padding: 1rem; border-radius: 10px; text-align: center;">
                        <h4>📊 Resum</h4>
                        <p><strong>El teu punt fort és {mejor['nombre'].lower()}</strong> ({mejor['eficacia']}% eficàcia)</p>
                        <p><strong>Pots millorar en {peor['nombre'].lower()}</strong> ({peor['eficacia']}% eficàcia)</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Necessites mínim 5 accions per veure l'anàlisi")
        else:
            st.info("No hi ha dades suficients per l'anàlisi")
        
        # === RENDIMENT PER ROTACIÓ ===
        st.markdown("---")
        st.subheader("🔄 Rendiment per Rotació (Atac)")
        
        df_rotacion = obtener_rendimiento_rotacion_jugador(partido_ids, jugador_id)
        
        if not df_rotacion.empty:
            # Ordenar rotaciones P1-P6
            orden_rot = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6']
            df_rotacion['rotacion'] = pd.Categorical(df_rotacion['rotacion'], categories=orden_rot, ordered=True)
            df_rotacion = df_rotacion.sort_values('rotacion')
            
            # Gráfico de barras por rotación
            fig = go.Figure()
            
            colores = [COLOR_VERDE if e >= 60 else COLOR_NARANJA if e >= 40 else COLOR_ROJO 
                      for e in df_rotacion['eficacia']]
            
            fig.add_trace(go.Bar(
                x=df_rotacion['rotacion'],
                y=df_rotacion['eficacia'],
                marker_color=colores,
                text=df_rotacion['eficacia'].apply(lambda x: f'{x}%'),
                textposition='outside'
            ))
            
            fig.add_hline(y=60, line_dash="dash", line_color=COLOR_VERDE, 
                          annotation_text="Bo (60%)")
            fig.add_hline(y=40, line_dash="dash", line_color=COLOR_NARANJA,
                          annotation_text="Regular (40%)")
            
            fig.update_layout(
                title="Eficàcia d'Atac per Rotació",
                xaxis_title="Rotació (Posició del Col·locador)",
                yaxis_title="Eficàcia (%)",
                height=350,
                yaxis=dict(range=[0, max(100, df_rotacion['eficacia'].max() + 15)])
            )
            
            st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})
            
            # Mostrar mejor y peor rotación
            mejor_rot = df_rotacion.loc[df_rotacion['eficacia'].idxmax()]
            peor_rot = df_rotacion.loc[df_rotacion['eficacia'].idxmin()]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"""
                <div style="background: #E8F5E9; padding: 1rem; border-radius: 10px; text-align: center; border-left: 4px solid {COLOR_VERDE};">
                    <h4 style="color: {COLOR_VERDE}; margin: 0;">⭐ Millor Rotació</h4>
                    <p style="font-size: 2rem; font-weight: bold; margin: 0.5rem 0;">{mejor_rot['rotacion']}</p>
                    <p style="margin: 0;">{mejor_rot['eficacia']}% eficàcia</p>
                    <small>{int(mejor_rot['puntos'])} punts en {int(mejor_rot['total'])} atacs</small>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div style="background: #FFEBEE; padding: 1rem; border-radius: 10px; text-align: center; border-left: 4px solid {COLOR_ROJO};">
                    <h4 style="color: {COLOR_ROJO}; margin: 0;">⚠️ A Treballar</h4>
                    <p style="font-size: 2rem; font-weight: bold; margin: 0.5rem 0;">{peor_rot['rotacion']}</p>
                    <p style="margin: 0;">{peor_rot['eficacia']}% eficàcia</p>
                    <small>{int(peor_rot['puntos'])} punts en {int(peor_rot['total'])} atacs</small>
                </div>
                """, unsafe_allow_html=True)
            
            # Tabla detallada
            with st.expander("📋 Veure detall per rotació"):
                df_rot_display = df_rotacion[['rotacion', 'total', 'puntos', 'eficacia', 'eficiencia']].rename(columns={
                    'rotacion': 'Rotació',
                    'total': 'Total Atacs',
                    'puntos': 'Punts (#)',
                    'eficacia': 'Eficàcia (%)',
                    'eficiencia': 'Eficiència (%)'
                })
                st.dataframe(df_rot_display, use_container_width=True, hide_index=True)
        else:
            st.info("No hi ha dades d'atac per rotació per aquest jugador")

def pagina_comparativa():
    """Página de comparación de partidos y jugadores"""
    st.markdown("""
    <div class="main-header">
        <h1>📈 Comparativa</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Verificar contexto
    if not st.session_state.get('equipo_id') or not st.session_state.get('temporada_id'):
        st.warning("⚠️ Selecciona primer un equip i temporada al menú lateral")
        return
    
    tab1, tab2, tab3 = st.tabs(["⚔️ Comparar Partits", "👥 Comparar Jugadors", "📈 Tendències Equip"])
    
    # =================================
    # TAB 1: COMPARAR PARTIDOS
    # =================================
    with tab1:
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
            
            rival1_display = f"{info1['rival']} ({'L' if info1['local'] else 'V'})"
            rival2_display = f"{info2['rival']} ({'L' if info2['local'] else 'V'})"
            
            st.markdown("---")
            
            df1 = obtener_resumen_acciones(partido1)
            df2 = obtener_resumen_acciones(partido2)
            
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
            
            st.caption("✅ Millora (+5%) | ➡️ Similar (±5%) | ❌ Empitjora (-5%)")
            
            # Distribución del colocador comparativa
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
            
            # Jugadores de cada partido
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
    
    # =================================
    # TAB 2: COMPARAR JUGADORES
    # =================================
    with tab2:
        st.subheader("👥 Comparativa entre Jugadors")
        
        # Cargar partidos para el contexto
        partidos = cargar_partidos(
            st.session_state.equipo_id,
            st.session_state.temporada_id,
            st.session_state.get('fase_id')
        )
        
        if partidos.empty:
            st.info("No hi ha partits disponibles")
            return
        
        partido_ids = partidos['id'].tolist()
        
        # Cargar jugadores que han participado
        jugadores_participantes = obtener_jugadores_partido(partido_ids)
        
        if len(jugadores_participantes) < 2:
            st.info("Es necessiten almenys 2 jugadors per fer una comparativa")
            return
        
        st.info(f"📊 Comparant estadístiques de {len(partidos)} partits")
        
        col1, col2 = st.columns(2)
        
        with col1:
            jugador1_options = [None] + jugadores_participantes['id'].tolist()
            jugador1_id = st.selectbox(
                "Jugador 1:",
                options=jugador1_options,
                format_func=lambda x: "Selecciona Jugador 1..." if x is None
                    else jugadores_participantes[jugadores_participantes['id'] == x]['jugador'].iloc[0],
                key='comp_jugador1'
            )
        
        with col2:
            jugador2_options = [None] + jugadores_participantes['id'].tolist()
            jugador2_id = st.selectbox(
                "Jugador 2:",
                options=jugador2_options,
                format_func=lambda x: "Selecciona Jugador 2..." if x is None
                    else jugadores_participantes[jugadores_participantes['id'] == x]['jugador'].iloc[0],
                key='comp_jugador2'
            )
        
        if jugador1_id and jugador2_id and jugador1_id != jugador2_id:
            jugador1_nombre = jugadores_participantes[jugadores_participantes['id'] == jugador1_id]['jugador'].iloc[0]
            jugador2_nombre = jugadores_participantes[jugadores_participantes['id'] == jugador2_id]['jugador'].iloc[0]
            
            st.markdown("---")
            
            # Obtener estadísticas de ambos jugadores
            df_jug1 = obtener_estadisticas_jugador(partido_ids, jugador1_id)
            df_jug2 = obtener_estadisticas_jugador(partido_ids, jugador2_id)
            
            # === MÉTRICAS PRINCIPALES ===
            st.subheader("📊 Comparativa General")
            
            acciones = ['atacar', 'recepción', 'saque', 'bloqueo']
            nombres = ['Atac', 'Recepció', 'Saque', 'Bloqueig']
            iconos = ['🔥', '🎯', '🚀', '🧱']
            
            # Gráfico de barras comparativo
            fig = go.Figure()
            
            eficacias1 = []
            eficacias2 = []
            
            for accion in acciones:
                e1 = df_jug1[df_jug1['tipo_accion'] == accion]['eficacia']
                e2 = df_jug2[df_jug2['tipo_accion'] == accion]['eficacia']
                eficacias1.append(float(e1.iloc[0]) if not e1.empty else 0)
                eficacias2.append(float(e2.iloc[0]) if not e2.empty else 0)
            
            fig.add_trace(go.Bar(
                name=jugador1_nombre,
                x=nombres,
                y=eficacias1,
                marker_color=COLOR_ROJO,
                text=[f'{e}%' for e in eficacias1],
                textposition='outside'
            ))
            
            fig.add_trace(go.Bar(
                name=jugador2_nombre,
                x=nombres,
                y=eficacias2,
                marker_color=COLOR_NEGRO,
                text=[f'{e}%' for e in eficacias2],
                textposition='outside'
            ))
            
            fig.add_hline(y=60, line_dash="dash", line_color=COLOR_VERDE, 
                          annotation_text="Bo (60%)")
            fig.add_hline(y=40, line_dash="dash", line_color=COLOR_NARANJA,
                          annotation_text="Regular (40%)")
            
            fig.update_layout(
                title="Eficàcia per Acció",
                barmode='group',
                yaxis=dict(range=[0, 100]),
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            
            st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})
            
            # === TABLA DETALLADA ===
            st.markdown("---")
            st.subheader("📋 Detall per Acció")
            
            comparativa_data = []
            
            for accion, nombre, icono in zip(acciones, nombres, iconos):
                fila1 = df_jug1[df_jug1['tipo_accion'] == accion]
                fila2 = df_jug2[df_jug2['tipo_accion'] == accion]
                
                total1 = int(fila1['total'].iloc[0]) if not fila1.empty else 0
                total2 = int(fila2['total'].iloc[0]) if not fila2.empty else 0
                puntos1 = int(fila1['puntos'].iloc[0]) if not fila1.empty else 0
                puntos2 = int(fila2['puntos'].iloc[0]) if not fila2.empty else 0
                efic1 = float(fila1['eficacia'].iloc[0]) if not fila1.empty else 0
                efic2 = float(fila2['eficacia'].iloc[0]) if not fila2.empty else 0
                
                diff = efic1 - efic2
                if diff > 5:
                    guanyador = f"🏆 {jugador1_nombre}"
                elif diff < -5:
                    guanyador = f"🏆 {jugador2_nombre}"
                else:
                    guanyador = "🤝 Empat"
                
                comparativa_data.append({
                    'Acció': f"{icono} {nombre}",
                    f'{jugador1_nombre} Total': total1,
                    f'{jugador1_nombre} #': puntos1,
                    f'{jugador1_nombre} Efic.': f"{efic1}%",
                    f'{jugador2_nombre} Total': total2,
                    f'{jugador2_nombre} #': puntos2,
                    f'{jugador2_nombre} Efic.': f"{efic2}%",
                    'Millor': guanyador
                })
            
            st.dataframe(pd.DataFrame(comparativa_data), use_container_width=True, hide_index=True)
            
            # === RADAR COMPARATIVO ===
            st.markdown("---")
            st.subheader("🎯 Perfil Comparatiu")
            
            # Crear radar con ambos jugadores
            categorias = []
            valores1 = []
            valores2 = []
            
            for accion, nombre in zip(acciones, nombres):
                fila1 = df_jug1[df_jug1['tipo_accion'] == accion]
                fila2 = df_jug2[df_jug2['tipo_accion'] == accion]
                
                if not fila1.empty or not fila2.empty:
                    categorias.append(nombre)
                    valores1.append(float(fila1['eficacia'].iloc[0]) if not fila1.empty else 0)
                    valores2.append(float(fila2['eficacia'].iloc[0]) if not fila2.empty else 0)
            
            if categorias:
                # Cerrar el radar
                categorias_radar = categorias + [categorias[0]]
                valores1_radar = valores1 + [valores1[0]]
                valores2_radar = valores2 + [valores2[0]]
                
                fig_radar = go.Figure()
                
                fig_radar.add_trace(go.Scatterpolar(
                    r=valores1_radar,
                    theta=categorias_radar,
                    fill='toself',
                    fillcolor=f'rgba(200, 16, 46, 0.3)',
                    line_color=COLOR_ROJO,
                    name=jugador1_nombre
                ))
                
                fig_radar.add_trace(go.Scatterpolar(
                    r=valores2_radar,
                    theta=categorias_radar,
                    fill='toself',
                    fillcolor=f'rgba(0, 0, 0, 0.2)',
                    line_color=COLOR_NEGRO,
                    name=jugador2_nombre
                ))
                
                fig_radar.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 100]
                        )
                    ),
                    title="Comparativa de Perfils (Eficàcia %)",
                    height=450,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2)
                )
                
                st.plotly_chart(fig_radar, use_container_width=True, config={'staticPlot': True})

            # === RADAR COLOCADORES ===
            # Verificar si alguno tiene colocaciones
            df_col1 = df_jug1[df_jug1['tipo_accion'] == 'colocación']
            df_col2 = df_jug2[df_jug2['tipo_accion'] == 'colocación']
            
            if not df_col1.empty or not df_col2.empty:
                st.markdown("---")
                st.subheader("🎯 Comparativa de Col·locació")
                
                # Obtener datos de colocación
                marcas = ['#', '+', '!', '-', '=']
                nombres_marcas = ['1v0 (#)', '1v1 (+)', '1v2/3 (!)', 'Negatiu (-)', 'Error (=)']
                campos = ['puntos', 'positivos', 'neutros', 'negativos', 'errores']
                
                valores_col1 = []
                valores_col2 = []
                
                total1 = int(df_col1['total'].iloc[0]) if not df_col1.empty else 1
                total2 = int(df_col2['total'].iloc[0]) if not df_col2.empty else 1
                
                for campo in campos:
                    v1 = int(df_col1[campo].iloc[0]) if not df_col1.empty else 0
                    v2 = int(df_col2[campo].iloc[0]) if not df_col2.empty else 0
                    # Convertir a porcentaje
                    valores_col1.append(round(v1 / total1 * 100, 1))
                    valores_col2.append(round(v2 / total2 * 100, 1))
                
                # Cerrar el radar
                nombres_marcas_radar = nombres_marcas + [nombres_marcas[0]]
                valores_col1_radar = valores_col1 + [valores_col1[0]]
                valores_col2_radar = valores_col2 + [valores_col2[0]]
                
                fig_col = go.Figure()
                
                fig_col.add_trace(go.Scatterpolar(
                    r=valores_col1_radar,
                    theta=nombres_marcas_radar,
                    fill='toself',
                    fillcolor=f'rgba(200, 16, 46, 0.3)',
                    line_color=COLOR_ROJO,
                    name=f"{jugador1_nombre} ({total1} col.)"
                ))
                
                fig_col.add_trace(go.Scatterpolar(
                    r=valores_col2_radar,
                    theta=nombres_marcas_radar,
                    fill='toself',
                    fillcolor=f'rgba(0, 0, 0, 0.2)',
                    line_color=COLOR_NEGRO,
                    name=f"{jugador2_nombre} ({total2} col.)"
                ))
                
                fig_col.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 100]
                        )
                    ),
                    title="Distribució de Marques en Col·locació (%)",
                    height=450,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2)
                )
                
                st.plotly_chart(fig_col, use_container_width=True, config={'staticPlot': True})
                
                # Métricas de colocación
                col1, col2 = st.columns(2)
                
                efic_col1 = float(df_col1['eficacia'].iloc[0]) if not df_col1.empty else 0
                efic_col2 = float(df_col2['eficacia'].iloc[0]) if not df_col2.empty else 0
                
                with col1:
                    st.metric(
                        f"🎯 {jugador1_nombre}",
                        f"{efic_col1}% eficàcia",
                        f"{total1} col·locacions"
                    )
                
                with col2:
                    st.metric(
                        f"🎯 {jugador2_nombre}",
                        f"{efic_col2}% eficàcia",
                        f"{total2} col·locacions"
                    )
            
            # === PUNTOS DIRECTOS ===
            st.markdown("---")
            st.subheader("⚡ Punts Directes")
            
            col1, col2 = st.columns(2)
            
            # Calcular puntos directos de cada jugador
            puntos1_ataque = int(df_jug1[df_jug1['tipo_accion'] == 'atacar']['puntos'].iloc[0]) if not df_jug1[df_jug1['tipo_accion'] == 'atacar'].empty else 0
            puntos1_saque = int(df_jug1[df_jug1['tipo_accion'] == 'saque']['puntos'].iloc[0]) if not df_jug1[df_jug1['tipo_accion'] == 'saque'].empty else 0
            puntos1_bloqueo = int(df_jug1[df_jug1['tipo_accion'] == 'bloqueo']['puntos'].iloc[0]) if not df_jug1[df_jug1['tipo_accion'] == 'bloqueo'].empty else 0
            puntos1_total = puntos1_ataque + puntos1_saque + puntos1_bloqueo
            
            puntos2_ataque = int(df_jug2[df_jug2['tipo_accion'] == 'atacar']['puntos'].iloc[0]) if not df_jug2[df_jug2['tipo_accion'] == 'atacar'].empty else 0
            puntos2_saque = int(df_jug2[df_jug2['tipo_accion'] == 'saque']['puntos'].iloc[0]) if not df_jug2[df_jug2['tipo_accion'] == 'saque'].empty else 0
            puntos2_bloqueo = int(df_jug2[df_jug2['tipo_accion'] == 'bloqueo']['puntos'].iloc[0]) if not df_jug2[df_jug2['tipo_accion'] == 'bloqueo'].empty else 0
            puntos2_total = puntos2_ataque + puntos2_saque + puntos2_bloqueo
            
            with col1:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, {COLOR_ROJO} 0%, #8B0000 100%); 
                            padding: 1.5rem; border-radius: 10px; text-align: center; color: white;">
                    <h3 style="margin: 0; color: white;">{jugador1_nombre}</h3>
                    <p style="font-size: 3rem; font-weight: bold; margin: 0.5rem 0;">{puntos1_total}</p>
                    <p style="margin: 0;">🔥 {puntos1_ataque} | 🎯 {puntos1_saque} | 🧱 {puntos1_bloqueo}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, {COLOR_NEGRO} 0%, #333 100%); 
                            padding: 1.5rem; border-radius: 10px; text-align: center; color: white;">
                    <h3 style="margin: 0; color: white;">{jugador2_nombre}</h3>
                    <p style="font-size: 3rem; font-weight: bold; margin: 0.5rem 0;">{puntos2_total}</p>
                    <p style="margin: 0;">🔥 {puntos2_ataque} | 🎯 {puntos2_saque} | 🧱 {puntos2_bloqueo}</p>
                </div>
                """, unsafe_allow_html=True)
            
            # Veredicto final
            st.markdown("---")
            if puntos1_total > puntos2_total:
                ganador = jugador1_nombre
                diff_puntos = puntos1_total - puntos2_total
            elif puntos2_total > puntos1_total:
                ganador = jugador2_nombre
                diff_puntos = puntos2_total - puntos1_total
            else:
                ganador = None
                diff_puntos = 0
            
            if ganador:
                st.success(f"🏆 **{ganador}** lidera amb **{diff_puntos} punts** més!")
            else:
                st.info("🤝 **Empat** en punts directes!")
        
        elif jugador1_id and jugador2_id and jugador1_id == jugador2_id:
            st.warning("Selecciona dos jugadors diferents per comparar")

    # =================================
    # TAB 3: TENDENCIAS DEL EQUIPO
    # =================================
    with tab3:
        st.subheader("📈 Tendències de l'Equip")
        
        df_tendencias = obtener_tendencias_equipo(
            st.session_state.equipo_id,
            st.session_state.temporada_id,
            st.session_state.get('fase_id')
        )
        
        if df_tendencias.empty:
            st.info("No hi ha dades suficients per mostrar tendències")
        else:
            # Resumen general
            st.markdown("##### 📊 Resum de la Temporada")
            
            total_partidos = len(df_tendencias)
            victorias = df_tendencias['victoria'].sum() if 'victoria' in df_tendencias.columns else 0
            derrotas = total_partidos - victorias if victorias else 0
            
            col1, col2, col3, col4 = st.columns(4)
            
            col1.metric("Partits", total_partidos)
            col2.metric("Victòries", int(victorias), f"{int(victorias/total_partidos*100)}%" if total_partidos > 0 else "0%")
            col3.metric("Derrotes", int(derrotas))
            col4.metric("Punts Directes/Partit", f"{df_tendencias['puntos_directos'].mean():.1f}")
            
            st.markdown("---")
            
            # Gráfico de evolución de eficacia
            st.markdown("##### 🔥 Evolució d'Eficàcia")
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df_tendencias['partido_display'],
                y=df_tendencias['eficacia_ataque'],
                mode='lines+markers',
                name='Atac',
                line=dict(color=COLOR_ROJO, width=3),
                marker=dict(size=10)
            ))
            
            fig.add_trace(go.Scatter(
                x=df_tendencias['partido_display'],
                y=df_tendencias['eficacia_recepcion'],
                mode='lines+markers',
                name='Recepció',
                line=dict(color=COLOR_NEGRO, width=3),
                marker=dict(size=10)
            ))
            
            # Líneas de referencia
            fig.add_hline(y=60, line_dash="dash", line_color=COLOR_VERDE, 
                          annotation_text="Bo (60%)")
            fig.add_hline(y=40, line_dash="dash", line_color=COLOR_NARANJA,
                          annotation_text="Regular (40%)")
            
            # Marcar victorias/derrotas con color de fondo
            for idx, row in df_tendencias.iterrows():
                if row['victoria'] == True:
                    fig.add_vrect(
                        x0=idx - 0.4, x1=idx + 0.4,
                        fillcolor="rgba(76, 175, 80, 0.1)",
                        line_width=0
                    )
                elif row['victoria'] == False:
                    fig.add_vrect(
                        x0=idx - 0.4, x1=idx + 0.4,
                        fillcolor="rgba(244, 67, 54, 0.1)",
                        line_width=0
                    )
            
            fig.update_layout(
                title="Eficàcia Atac i Recepció per Partit",
                xaxis_title="Partit",
                yaxis_title="Eficàcia (%)",
                height=400,
                yaxis=dict(range=[0, 100]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                xaxis_tickangle=-45
            )
            
            st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})
            
            st.caption("🟢 Fons verd = Victòria | 🔴 Fons vermell = Derrota")
            
            # Gráfico de puntos directos y errores
            st.markdown("---")
            st.markdown("##### ⚡ Punts Directes vs Errors")
            
            fig2 = go.Figure()
            
            fig2.add_trace(go.Bar(
                x=df_tendencias['partido_display'],
                y=df_tendencias['puntos_directos'],
                name='Punts Directes',
                marker_color=COLOR_VERDE
            ))
            
            fig2.add_trace(go.Bar(
                x=df_tendencias['partido_display'],
                y=df_tendencias['errores'],
                name='Errors',
                marker_color=COLOR_ROJO
            ))
            
            # Línea de balance
            df_tendencias['balance'] = df_tendencias['puntos_directos'] - df_tendencias['errores']
            
            fig2.add_trace(go.Scatter(
                x=df_tendencias['partido_display'],
                y=df_tendencias['balance'],
                mode='lines+markers',
                name='Balanç',
                line=dict(color=COLOR_AMARILLO, width=2, dash='dot'),
                marker=dict(size=8)
            ))
            
            fig2.update_layout(
                title="Punts Directes, Errors i Balanç per Partit",
                xaxis_title="Partit",
                yaxis_title="Quantitat",
                height=400,
                barmode='group',
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                xaxis_tickangle=-45
            )
            
            st.plotly_chart(fig2, use_container_width=True, config={'staticPlot': True})
            
            # Gráfico de Side-out
            st.markdown("---")
            st.markdown("##### 🎯 Evolució del Side-out")
            
            df_sideout = obtener_sideout_por_partido(
                st.session_state.equipo_id,
                st.session_state.temporada_id,
                st.session_state.get('fase_id')
            )
            
            if not df_sideout.empty and df_sideout['eficacia_sideout'].notna().any():
                fig3 = go.Figure()
                
                fig3.add_trace(go.Scatter(
                    x=[f"vs {r}" for r in df_sideout['rival']],
                    y=df_sideout['eficacia_sideout'],
                    mode='lines+markers+text',
                    name='Side-out',
                    line=dict(color=COLOR_ROJO, width=3),
                    marker=dict(size=12),
                    text=df_sideout['eficacia_sideout'].apply(lambda x: f'{x}%' if pd.notna(x) else ''),
                    textposition='top center'
                ))
                
                fig3.add_hline(y=50, line_dash="dash", line_color=COLOR_VERDE, 
                              annotation_text="Objectiu (50%)")
                
                fig3.update_layout(
                    title="% Side-out per Partit",
                    xaxis_title="Partit",
                    yaxis_title="Side-out (%)",
                    height=350,
                    yaxis=dict(range=[0, 80]),
                    xaxis_tickangle=-45
                )
                
                st.plotly_chart(fig3, use_container_width=True, config={'staticPlot': True})
            
            # Insights automáticos
            st.markdown("---")
            st.markdown("##### 💡 Insights")
            
            insights = []
            
            # Tendencia de ataque (últimos 5 partidos vs primeros 5)
            if len(df_tendencias) >= 5:
                primeros_5_ataque = df_tendencias.head(5)['eficacia_ataque'].mean()
                ultimos_5_ataque = df_tendencias.tail(5)['eficacia_ataque'].mean()
                diff_ataque = ultimos_5_ataque - primeros_5_ataque
                
                if diff_ataque > 5:
                    insights.append(f"📈 **Millora en atac:** +{diff_ataque:.1f}% en els últims 5 partits")
                elif diff_ataque < -5:
                    insights.append(f"📉 **Baixada en atac:** {diff_ataque:.1f}% en els últims 5 partits")
                
                primeros_5_rec = df_tendencias.head(5)['eficacia_recepcion'].mean()
                ultimos_5_rec = df_tendencias.tail(5)['eficacia_recepcion'].mean()
                diff_rec = ultimos_5_rec - primeros_5_rec
                
                if diff_rec > 5:
                    insights.append(f"📈 **Millora en recepció:** +{diff_rec:.1f}% en els últims 5 partits")
                elif diff_rec < -5:
                    insights.append(f"📉 **Baixada en recepció:** {diff_rec:.1f}% en els últims 5 partits")
            
            # Mejor y peor partido
            mejor_partido = df_tendencias.loc[df_tendencias['eficacia_ataque'].idxmax()]
            peor_partido = df_tendencias.loc[df_tendencias['eficacia_ataque'].idxmin()]
            
            insights.append(f"🔥 **Millor partit en atac:** vs {mejor_partido['rival']} ({mejor_partido['eficacia_ataque']}%)")
            insights.append(f"⚠️ **Pitjor partit en atac:** vs {peor_partido['rival']} ({peor_partido['eficacia_ataque']}%)")
            
            # Racha de victorias/derrotas
            if 'victoria' in df_tendencias.columns:
                racha_actual = 0
                tipo_racha = None
                
                for v in df_tendencias['victoria'].iloc[::-1]:  # Recorrer de más reciente a más antiguo
                    if tipo_racha is None:
                        tipo_racha = v
                        racha_actual = 1
                    elif v == tipo_racha:
                        racha_actual += 1
                    else:
                        break
                
                if racha_actual >= 2 and tipo_racha == True:
                    insights.append(f"🏆 **Ratxa actual:** {racha_actual} victòries seguides!")
                elif racha_actual >= 2 and tipo_racha == False:
                    insights.append(f"💪 **A trencar la ratxa:** {racha_actual} derrotes seguides")
            
            # Media de puntos directos
            media_puntos = df_tendencias['puntos_directos'].mean()
            insights.append(f"⚡ **Mitjana de punts directes:** {media_puntos:.1f} per partit")
            
            # Media de errores
            media_errores = df_tendencias['errores'].mean()
            insights.append(f"❌ **Mitjana d'errors:** {media_errores:.1f} per partit")
            
            # Mostrar insights
            col1, col2 = st.columns(2)
            for idx, insight in enumerate(insights):
                with col1 if idx % 2 == 0 else col2:
                    st.info(insight)
            
            # Tabla resumen
            st.markdown("---")
            with st.expander("📋 Taula detallada"):
                df_display = df_tendencias[['partido_display', 'resultado', 'eficacia_ataque', 'eficacia_recepcion', 'puntos_directos', 'errores', 'balance']].copy()
                df_display.columns = ['Partit', 'Resultat', 'Efic. Atac (%)', 'Efic. Recep. (%)', 'Punts Directes', 'Errors', 'Balanç']
                st.dataframe(df_display, use_container_width=True, hide_index=True)

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
                <small style="color: {COLOR_GRISOSCURO};"># i +</small>
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

        # === DESTACAT DEL PARTIT ===
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("🏆 Destacat")
        
        # Obtener rankings del equipo para ver si es el mejor en algo
        destacados = []
        
        for accion, nombre, icono in [('atacar', 'Atac', '🔥'), ('saque', 'Saque', '🎯'), ('bloqueo', 'Bloqueig', '🧱'), ('recepción', 'Recepció', '🏐')]:
            df_ranking = obtener_ranking_equipo(partido_ids, accion)
            
            if not df_ranking.empty:
                # Ver si el jugador está en el top 3
                jugador_en_ranking = df_ranking[df_ranking['jugador_id'] == jugador_id]
                
                if not jugador_en_ranking.empty:
                    posicion = int(jugador_en_ranking['ranking'].iloc[0])
                    
                    if posicion == 1:
                        destacados.append(f"{icono} **Millor de l'equip** en {nombre.lower()}!")
                    elif posicion == 2:
                        destacados.append(f"{icono} **2n millor** en {nombre.lower()}")
                    elif posicion == 3:
                        destacados.append(f"{icono} **3r millor** en {nombre.lower()}")
        
        if destacados:
            cols = st.columns(2)
            for idx, dest in enumerate(destacados):
                with cols[idx % 2]:
                    st.success(dest)
        else:
            st.info("Continua treballant per destacar! 💪")
        
        # === COMPARATIVA AMB LA SEVA MITJANA ===
        if partido_seleccionado != "tots" and len(partidos) > 1:
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📊 vs La Teva Mitjana")
            
            # Obtener media del jugador en todos los partidos
            todos_partido_ids = partidos['id'].tolist()
            df_media_jugador = obtener_estadisticas_jugador(todos_partido_ids, jugador_id)
            df_partido_actual = obtener_estadisticas_jugador(partido_ids, jugador_id)
            
            if not df_media_jugador.empty and not df_partido_actual.empty:
                comparativas = []
                
                for accion, nombre in [('atacar', 'Atac'), ('recepción', 'Recepció'), ('saque', 'Saque')]:
                    media_row = df_media_jugador[df_media_jugador['tipo_accion'] == accion]
                    actual_row = df_partido_actual[df_partido_actual['tipo_accion'] == accion]
                    
                    if not media_row.empty and not actual_row.empty:
                        media_efic = float(media_row['eficacia'].iloc[0])
                        actual_efic = float(actual_row['eficacia'].iloc[0])
                        diff = actual_efic - media_efic
                        
                        comparativas.append({
                            'accion': nombre,
                            'actual': actual_efic,
                            'media': media_efic,
                            'diff': diff
                        })
                
                if comparativas:
                    cols = st.columns(len(comparativas))
                    for idx, comp in enumerate(comparativas):
                        with cols[idx]:
                            if comp['diff'] > 5:
                                color = COLOR_VERDE
                                icono = "⬆️"
                            elif comp['diff'] < -5:
                                color = COLOR_ROJO
                                icono = "⬇️"
                            else:
                                color = COLOR_NARANJA
                                icono = "➡️"
                            
                            st.markdown(f"""
                            <div style="background: {COLOR_GRIS}; padding: 1rem; border-radius: 10px; text-align: center;">
                                <strong>{comp['accion']}</strong><br>
                                <span style="font-size: 1.5rem; color: {color};">{icono} {comp['diff']:+.1f}%</span><br>
                                <small>Avui: {comp['actual']}% | Mitjana: {comp['media']}%</small>
                            </div>
                            """, unsafe_allow_html=True)
        
        # === MISSATGE MOTIVACIONAL ===
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Calcular valoración general del partido
        valor = ficha['valor_total'] or 0
        eficacia_ataque = ficha['ataque']['eficacia'] or 0
        puntos = ficha['otras']['puntos_directos'] or 0
        
        if valor >= 10 and eficacia_ataque >= 50:
            mensaje = "🌟 **PARTIT EXCEPCIONAL!** Has estat una estrella!"
            color_msg = COLOR_VERDE
        elif valor >= 5 or eficacia_ataque >= 45:
            mensaje = "💪 **Gran partit!** Continues així!"
            color_msg = COLOR_VERDE
        elif valor >= 0 or eficacia_ataque >= 35:
            mensaje = "👍 **Bon partit!** Segueix treballant!"
            color_msg = COLOR_NARANJA
        elif valor >= -5:
            mensaje = "📈 **Pots donar més!** El proper serà millor!"
            color_msg = COLOR_NARANJA
        else:
            mensaje = "💪 **Cap al davant!** Entrena dur i tornaràs més fort!"
            color_msg = COLOR_ROJO
        
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, {color_msg} 0%, {color_msg}99 100%); 
                    padding: 1.5rem; border-radius: 10px; text-align: center; margin-top: 1rem;">
            <h2 style="color: white; margin: 0;">{mensaje}</h2>
        </div>
        """, unsafe_allow_html=True)


def pagina_importar():
    """Página para importar partidos desde Excel"""
    from importar_partido_streamlit import pagina_importar_partido
    pagina_importar_partido(get_engine)

def pagina_admin():
    """Página de administración"""
    st.markdown("""
    <div class="main-header">
        <h1>⚙️ Administració</h1>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🏆 Fases",
        "🏐 Equips",
        "📅 Temporades", 
        "👥 Jugadors",
        "📊 Partits",
        "👤 Usuaris",
        "📋 Accessos"
    ])
    
    # =================================
    # TAB 1: FASES
    # =================================
    with tab1:
        st.subheader("🏆 Gestió de Fases")
        
        if not st.session_state.get('temporada_id'):
            st.warning("⚠️ Selecciona primer una temporada al menú lateral")
        else:
            # Mostrar fases actuales
            st.markdown("**Fases actuals:**")
            fases_actuales = cargar_fases(st.session_state.temporada_id)
            
            if not fases_actuales.empty:
                st.dataframe(fases_actuales, use_container_width=True, hide_index=True)
            else:
                st.info("No hi ha fases creades per aquesta temporada")
            
            st.markdown("---")
            
            # Formulario para añadir nueva fase
            st.markdown("**➕ Afegir nova fase:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                nuevo_nombre_fase = st.text_input("Nom de la fase:", placeholder="Ex: Segona Fase", key="nueva_fase_nombre")
            
            with col2:
                nuevo_orden_fase = st.number_input("Ordre:", min_value=1, value=len(fases_actuales) + 1, key="nueva_fase_orden")
            
            if st.button("✅ Crear fase", type="primary", key="btn_crear_fase"):
                if not nuevo_nombre_fase:
                    st.error("❌ Has d'escriure un nom per la fase")
                else:
                    try:
                        with get_engine().begin() as conn:
                            conn.execute(text("""
                                INSERT INTO fases (nombre, temporada_id, orden)
                                VALUES (:nombre, :temporada_id, :orden)
                            """), {
                                "nombre": nuevo_nombre_fase,
                                "temporada_id": st.session_state.temporada_id,
                                "orden": nuevo_orden_fase
                            })
                        
                        st.success(f"✅ Fase '{nuevo_nombre_fase}' creada correctament!")
                        st.cache_data.clear()
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error creant la fase: {str(e)}")
            
            # Eliminar fase
            st.markdown("---")
            st.markdown("**🗑️ Eliminar fase:**")
            
            if not fases_actuales.empty:
                fase_eliminar = st.selectbox(
                    "Selecciona fase a eliminar:",
                    options=[None] + fases_actuales['id'].tolist(),
                    format_func=lambda x: "Selecciona..." if x is None else fases_actuales[fases_actuales['id'] == x]['nombre'].iloc[0],
                    key="fase_eliminar"
                )
                
                if fase_eliminar:
                    st.warning("⚠️ Això eliminarà la fase però NO els partits associats (quedaran sense fase)")
                    if st.button("🗑️ Eliminar fase", type="secondary", key="btn_eliminar_fase"):
                        try:
                            with get_engine().begin() as conn:
                                conn.execute(text("UPDATE partidos_new SET fase_id = NULL WHERE fase_id = :fid"), {"fid": fase_eliminar})
                                conn.execute(text("DELETE FROM fases WHERE id = :fid"), {"fid": fase_eliminar})
                            
                            st.success("✅ Fase eliminada!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
    
    # =================================
    # TAB 2: EQUIPOS
    # =================================
    with tab2:
        st.subheader("🏐 Gestió d'Equips")
        
        # Mostrar equipos actuales
        st.markdown("**Equips actuals:**")
        equipos_actuales = cargar_equipos()
        
        if not equipos_actuales.empty:
            st.dataframe(equipos_actuales[['id', 'nombre', 'equipo_letra', 'nombre_completo']], use_container_width=True, hide_index=True)
        else:
            st.info("No hi ha equips creats")
        
        st.markdown("---")
        
        # Formulario para añadir nuevo equipo
        st.markdown("**➕ Afegir nou equip:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nuevo_nombre_equipo = st.text_input("Nom del club:", placeholder="Ex: CV Barcelona", key="nuevo_equipo_nombre")
        
        with col2:
            nueva_letra_equipo = st.text_input("Lletra equip (opcional):", placeholder="Ex: A, B, C...", key="nuevo_equipo_letra")
        
        if st.button("✅ Crear equip", type="primary", key="btn_crear_equipo"):
            if not nuevo_nombre_equipo:
                st.error("❌ Has d'escriure un nom per l'equip")
            else:
                try:
                    with get_engine().begin() as conn:
                        conn.execute(text("""
                            INSERT INTO equipos (nombre, equipo_letra)
                            VALUES (:nombre, :letra)
                        """), {
                            "nombre": nuevo_nombre_equipo,
                            "letra": nueva_letra_equipo if nueva_letra_equipo else None
                        })
                    
                    st.success(f"✅ Equip '{nuevo_nombre_equipo}' creat correctament!")
                    st.cache_data.clear()
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error creant l'equip: {str(e)}")
        
        # Eliminar equipo
        st.markdown("---")
        st.markdown("**🗑️ Eliminar equip:**")
        
        if not equipos_actuales.empty:
            equipo_eliminar = st.selectbox(
                "Selecciona equip a eliminar:",
                options=[None] + equipos_actuales['id'].tolist(),
                format_func=lambda x: "Selecciona..." if x is None else equipos_actuales[equipos_actuales['id'] == x]['nombre_completo'].iloc[0],
                key="equipo_eliminar"
            )
            
            if equipo_eliminar:
                st.error("⚠️ ATENCIÓ: Això eliminarà l'equip, els seus jugadors i tots els partits associats!")
                confirmacio = st.text_input("Escriu 'ELIMINAR' per confirmar:", key="confirm_eliminar_equipo")
                
                if st.button("🗑️ Eliminar equip", type="secondary", key="btn_eliminar_equipo"):
                    if confirmacio == "ELIMINAR":
                        try:
                            with get_engine().begin() as conn:
                                conn.execute(text("""
                                    DELETE FROM acciones_new WHERE partido_id IN 
                                    (SELECT id FROM partidos_new WHERE equipo_id = :eid)
                                """), {"eid": equipo_eliminar})
                                conn.execute(text("DELETE FROM partidos_new WHERE equipo_id = :eid"), {"eid": equipo_eliminar})
                                conn.execute(text("DELETE FROM jugadores WHERE equipo_id = :eid"), {"eid": equipo_eliminar})
                                conn.execute(text("DELETE FROM equipos WHERE id = :eid"), {"eid": equipo_eliminar})
                            
                            st.success("✅ Equip eliminat!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                    else:
                        st.warning("Has d'escriure 'ELIMINAR' per confirmar")
    
    # =================================
    # TAB 3: TEMPORADAS
    # =================================
    with tab3:
        st.subheader("📅 Gestió de Temporades")
        
        # Mostrar temporadas actuales
        st.markdown("**Temporades actuals:**")
        temporadas_actuales = cargar_temporadas()
        
        if not temporadas_actuales.empty:
            st.dataframe(temporadas_actuales, use_container_width=True, hide_index=True)
        else:
            st.info("No hi ha temporades creades")
        
        st.markdown("---")
        
        # Formulario para añadir nueva temporada
        st.markdown("**➕ Afegir nova temporada:**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nuevo_nombre_temp = st.text_input("Nom de la temporada:", placeholder="Ex: 2025-2026", key="nueva_temp_nombre")
        
        with col2:
            nueva_temp_activa = st.checkbox("Temporada activa", value=True, key="nueva_temp_activa")
        
        if st.button("✅ Crear temporada", type="primary", key="btn_crear_temp"):
            if not nuevo_nombre_temp:
                st.error("❌ Has d'escriure un nom per la temporada")
            else:
                try:
                    with get_engine().begin() as conn:
                        if nueva_temp_activa:
                            conn.execute(text("UPDATE temporadas SET activa = false"))
                        
                        conn.execute(text("""
                            INSERT INTO temporadas (nombre, activa)
                            VALUES (:nombre, :activa)
                        """), {
                            "nombre": nuevo_nombre_temp,
                            "activa": nueva_temp_activa
                        })
                    
                    st.success(f"✅ Temporada '{nuevo_nombre_temp}' creada correctament!")
                    st.cache_data.clear()
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error creant la temporada: {str(e)}")
        
        # Eliminar temporada
        st.markdown("---")
        st.markdown("**🗑️ Eliminar temporada:**")
        
        if not temporadas_actuales.empty:
            temp_eliminar = st.selectbox(
                "Selecciona temporada a eliminar:",
                options=[None] + temporadas_actuales['id'].tolist(),
                format_func=lambda x: "Selecciona..." if x is None else temporadas_actuales[temporadas_actuales['id'] == x]['nombre'].iloc[0],
                key="temp_eliminar"
            )
            
            if temp_eliminar:
                st.error("⚠️ ATENCIÓ: Això eliminarà la temporada, les seves fases i tots els partits associats!")
                confirmacio_temp = st.text_input("Escriu 'ELIMINAR' per confirmar:", key="confirm_eliminar_temp")
                
                if st.button("🗑️ Eliminar temporada", type="secondary", key="btn_eliminar_temp"):
                    if confirmacio_temp == "ELIMINAR":
                        try:
                            with get_engine().begin() as conn:
                                conn.execute(text("""
                                    DELETE FROM acciones_new WHERE partido_id IN 
                                    (SELECT id FROM partidos_new WHERE temporada_id = :tid)
                                """), {"tid": temp_eliminar})
                                conn.execute(text("DELETE FROM partidos_new WHERE temporada_id = :tid"), {"tid": temp_eliminar})
                                conn.execute(text("DELETE FROM fases WHERE temporada_id = :tid"), {"tid": temp_eliminar})
                                conn.execute(text("DELETE FROM temporadas WHERE id = :tid"), {"tid": temp_eliminar})
                            
                            st.success("✅ Temporada eliminada!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                    else:
                        st.warning("Has d'escriure 'ELIMINAR' per confirmar")
    
    # =================================
    # TAB 4: JUGADORES
    # =================================
    with tab4:
        st.subheader("👥 Gestió de Jugadors")
        
        if not st.session_state.get('equipo_id'):
            st.warning("⚠️ Selecciona primer un equip al menú lateral")
        else:
            # Mostrar jugadores actuales
            st.markdown(f"**Jugadors de {st.session_state.get('equipo_nombre', '')}:**")
            jugadores_actuales = cargar_jugadores(st.session_state.equipo_id)
            
            if not jugadores_actuales.empty:
                st.dataframe(jugadores_actuales[['id', 'nombre', 'apellido', 'dorsal', 'posicion']], use_container_width=True, hide_index=True)
            else:
                st.info("No hi ha jugadors en aquest equip")
            
            st.markdown("---")
            
            # Formulario para añadir nuevo jugador
            st.markdown("**➕ Afegir nou jugador:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                nuevo_nombre_jug = st.text_input("Nom:", placeholder="Ex: Marc", key="nuevo_jug_nombre")
                nuevo_dorsal = st.number_input("Dorsal:", min_value=0, max_value=99, value=0, key="nuevo_jug_dorsal")
            
            with col2:
                nuevo_apellido_jug = st.text_input("Cognom:", placeholder="Ex: Garcia", key="nuevo_jug_apellido")
                nueva_posicion = st.selectbox(
                    "Posició:",
                    options=[None, "Col·locador", "Oposat", "Central", "Receptor", "Líbero"],
                    key="nuevo_jug_posicion"
                )
            
            if st.button("✅ Crear jugador", type="primary", key="btn_crear_jug"):
                if not nuevo_apellido_jug:
                    st.error("❌ Has d'escriure almenys el cognom del jugador")
                else:
                    try:
                        with get_engine().begin() as conn:
                            conn.execute(text("""
                                INSERT INTO jugadores (nombre, apellido, dorsal, posicion, equipo_id, activo)
                                VALUES (:nombre, :apellido, :dorsal, :posicion, :equipo_id, true)
                            """), {
                                "nombre": nuevo_nombre_jug if nuevo_nombre_jug else None,
                                "apellido": nuevo_apellido_jug,
                                "dorsal": nuevo_dorsal if nuevo_dorsal > 0 else None,
                                "posicion": nueva_posicion,
                                "equipo_id": st.session_state.equipo_id
                            })
                        
                        st.success(f"✅ Jugador '{nuevo_apellido_jug}' creat correctament!")
                        st.cache_data.clear()
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error creant el jugador: {str(e)}")
            
            # Editar jugador
            st.markdown("---")
            st.markdown("**✏️ Editar jugador:**")
            
            if not jugadores_actuales.empty:
                jug_editar = st.selectbox(
                    "Selecciona jugador:",
                    options=[None] + jugadores_actuales['id'].tolist(),
                    format_func=lambda x: "Selecciona..." if x is None else jugadores_actuales[jugadores_actuales['id'] == x]['nombre_completo'].iloc[0],
                    key="jug_editar"
                )
                
                if jug_editar:
                    jug_info = jugadores_actuales[jugadores_actuales['id'] == jug_editar].iloc[0]
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        edit_nombre = st.text_input("Nom:", value=jug_info['nombre'] or "", key=f"edit_jug_nombre_{jug_editar}")
                        edit_dorsal = st.number_input("Dorsal:", min_value=0, max_value=99, value=int(jug_info['dorsal']) if pd.notna(jug_info['dorsal']) else 0, key=f"edit_jug_dorsal_{jug_editar}")
                    
                    with col2:
                        edit_apellido = st.text_input("Cognom:", value=jug_info['apellido'] or "", key=f"edit_jug_apellido_{jug_editar}")
                        posiciones = [None, "Col·locador", "Oposat", "Central", "Receptor", "Líbero"]
                        pos_actual = jug_info['posicion'] if jug_info['posicion'] in posiciones else None
                        edit_posicion = st.selectbox(
                            "Posició:",
                            options=posiciones,
                            index=posiciones.index(pos_actual) if pos_actual else 0,
                            key=f"edit_jug_posicion_{jug_editar}"
                        )
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("💾 Guardar canvis", type="primary", key=f"btn_guardar_jug_{jug_editar}"):
                            try:
                                with get_engine().begin() as conn:
                                    conn.execute(text("""
                                        UPDATE jugadores 
                                        SET nombre = :nombre, apellido = :apellido, dorsal = :dorsal, posicion = :posicion
                                        WHERE id = :id
                                    """), {
                                        "nombre": edit_nombre if edit_nombre else None,
                                        "apellido": edit_apellido,
                                        "dorsal": edit_dorsal if edit_dorsal > 0 else None,
                                        "posicion": edit_posicion,
                                        "id": jug_editar
                                    })
                                
                                st.success("✅ Jugador actualitzat!")
                                st.cache_data.clear()
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                    
                    with col2:
                        if st.button("🚫 Desactivar jugador", type="secondary", key=f"btn_desactivar_jug_{jug_editar}"):
                            try:
                                with get_engine().begin() as conn:
                                    conn.execute(text("UPDATE jugadores SET activo = false WHERE id = :id"), {"id": jug_editar})
                                
                                st.success("✅ Jugador desactivat!")
                                st.cache_data.clear()
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
            
            # Eliminar jugador permanentemente
            st.markdown("---")
            st.markdown("**🗑️ Eliminar jugador permanentment:**")
            
            if not jugadores_actuales.empty:
                jug_eliminar = st.selectbox(
                    "Selecciona jugador a eliminar:",
                    options=[None] + jugadores_actuales['id'].tolist(),
                    format_func=lambda x: "Selecciona..." if x is None else jugadores_actuales[jugadores_actuales['id'] == x]['nombre_completo'].iloc[0],
                    key="jug_eliminar"
                )
                
                if jug_eliminar:
                    st.error("⚠️ ATENCIÓ: Això eliminarà el jugador i totes les seves estadístiques!")
                    confirmacio_jug = st.text_input("Escriu 'ELIMINAR' per confirmar:", key="confirm_eliminar_jug")
                    
                    if st.button("🗑️ Eliminar jugador", type="secondary", key="btn_eliminar_jug"):
                        if confirmacio_jug == "ELIMINAR":
                            try:
                                with get_engine().begin() as conn:
                                    conn.execute(text("DELETE FROM acciones_new WHERE jugador_id = :jid"), {"jid": jug_eliminar})
                                    conn.execute(text("DELETE FROM jugadores WHERE id = :jid"), {"jid": jug_eliminar})
                                
                                st.success("✅ Jugador eliminat!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                        else:
                            st.warning("Has d'escriure 'ELIMINAR' per confirmar")

    # =================================
    # TAB 5: PARTIDOS
    # =================================
    with tab5:
        st.subheader("🏐 Gestió de Partits")
        
        if not st.session_state.get('equipo_id') or not st.session_state.get('temporada_id'):
            st.warning("⚠️ Selecciona primer un equip i temporada al menú lateral")
        else:
            # Mostrar partidos actuales
            st.markdown(f"**Partits de {st.session_state.get('equipo_nombre', '')} - {st.session_state.get('temporada_nombre', '')}:**")
            
            partidos_actuales = cargar_partidos(
                st.session_state.equipo_id,
                st.session_state.temporada_id,
                st.session_state.get('fase_id')
            )
            
            if not partidos_actuales.empty:
                # Mostrar tabla de partidos
                df_display = partidos_actuales.copy()
                df_display['tipus'] = df_display['local'].apply(lambda x: 'Local' if x else 'Visitant')
                df_display = df_display[['id', 'rival', 'tipus', 'fecha', 'resultado', 'fase']]
                df_display.columns = ['ID', 'Rival', 'Tipus', 'Data', 'Resultat', 'Fase']
                st.dataframe(df_display, use_container_width=True, hide_index=True)
            else:
                st.info("No hi ha partits amb els filtres seleccionats")
            
            st.markdown("---")
            
            # Editar partido
            st.markdown("**✏️ Editar partit:**")
            
            if not partidos_actuales.empty:
                partido_editar = st.selectbox(
                    "Selecciona partit a editar:",
                    options=[None] + partidos_actuales['id'].tolist(),
                    format_func=lambda x: "Selecciona..." if x is None 
                        else f"vs {partidos_actuales[partidos_actuales['id'] == x]['rival'].iloc[0]} ({'L' if partidos_actuales[partidos_actuales['id'] == x]['local'].iloc[0] else 'V'})",
                    key="partido_editar"
                )
                
                if partido_editar:
                    partido_info = partidos_actuales[partidos_actuales['id'] == partido_editar].iloc[0]
                    
                    # Cargar fases disponibles
                    fases_disponibles = cargar_fases(st.session_state.temporada_id)
                    
                    # Obtener fase actual del partido
                    fase_actual = None
                    with get_engine().connect() as conn:
                        fase_result = conn.execute(text(
                            "SELECT fase_id FROM partidos_new WHERE id = :pid"
                        ), {"pid": partido_editar}).fetchone()
                        if fase_result:
                            fase_actual = fase_result[0]
                    
                    # Manejar la fecha
                    fecha_actual = partido_info['fecha']
                    if fecha_actual:
                        if isinstance(fecha_actual, str):
                            from datetime import datetime
                            fecha_actual = datetime.strptime(fecha_actual, '%Y-%m-%d').date()
                    else:
                        from datetime import date
                        fecha_actual = date.today()
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        edit_rival = st.text_input("Rival:", value=partido_info['rival'] or "", key=f"edit_rival_{partido_editar}")
                        edit_local = st.selectbox(
                            "Tipus:",
                            options=[True, False],
                            index=0 if partido_info['local'] else 1,
                            format_func=lambda x: "Local" if x else "Visitant",
                            key=f"edit_local_{partido_editar}"
                        )
                        
                        # Selector de fase
                        if not fases_disponibles.empty:
                            fase_opciones = [None] + fases_disponibles['id'].tolist()
                            
                            edit_fase = st.selectbox(
                                "Fase:",
                                options=fase_opciones,
                                index=fase_opciones.index(fase_actual) if fase_actual in fase_opciones else 0,
                                format_func=lambda x: "Sense fase" if x is None 
                                    else fases_disponibles[fases_disponibles['id'] == x]['nombre'].iloc[0],
                                key=f"edit_fase_{partido_editar}"
                            )
                        else:
                            edit_fase = None
                    
                    with col2:
                        edit_fecha = st.date_input("Data:", value=fecha_actual, key=f"edit_fecha_{partido_editar}")
                        edit_resultado = st.text_input("Resultat:", value=partido_info['resultado'] or "", placeholder="Ex: 3-1", key=f"edit_resultado_{partido_editar}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("💾 Guardar canvis", type="primary", key=f"btn_guardar_{partido_editar}"):
                            try:
                                with get_engine().begin() as conn:
                                    conn.execute(text("""
                                        UPDATE partidos_new 
                                        SET rival = :rival, local = :local, fecha = :fecha, 
                                            resultado = :resultado, fase_id = :fase_id
                                        WHERE id = :id
                                    """), {
                                        "rival": edit_rival,
                                        "local": edit_local,
                                        "fecha": edit_fecha,
                                        "resultado": edit_resultado if edit_resultado else None,
                                        "fase_id": edit_fase,
                                        "id": partido_editar
                                    })
                                
                                st.success("✅ Partit actualitzat!")
                                st.cache_data.clear()
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                    
                    with col2:
                        if st.button("🗑️ Eliminar partit", type="secondary", key=f"btn_eliminar_{partido_editar}"):
                            st.session_state.confirmar_eliminar_partido = partido_editar
                    
                    # Confirmación de eliminación
                    if st.session_state.get('confirmar_eliminar_partido') == partido_editar:
                        st.error("⚠️ ATENCIÓ: Això eliminarà el partit i totes les seves accions!")
                        confirmacio_partido = st.text_input("Escriu 'ELIMINAR' per confirmar:", key=f"confirm_eliminar_{partido_editar}")
                        
                        if st.button("🗑️ Confirmar eliminació", type="secondary", key=f"btn_confirmar_{partido_editar}"):
                            if confirmacio_partido == "ELIMINAR":
                                try:
                                    with get_engine().begin() as conn:
                                        conn.execute(text("DELETE FROM acciones_new WHERE partido_id = :pid"), {"pid": partido_editar})
                                        conn.execute(text("DELETE FROM partidos_new WHERE id = :pid"), {"pid": partido_editar})
                                    
                                    st.success("✅ Partit eliminat!")
                                    st.session_state.confirmar_eliminar_partido = None
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error: {str(e)}")
                            else:
                                st.warning("Has d'escriure 'ELIMINAR' per confirmar")

        # Reimportación masiva
        st.markdown("---")
        st.subheader("🔄 Reimportar tots els partits")
        
        st.warning("""
        ⚠️ **Atenció:** Això eliminarà TOTS els partits de l'equip i temporada actual i els reimportarà des dels Excel.
        Utilitza-ho només si necessites actualitzar l'estructura de les dades.
        """)
        
        uploaded_files = st.file_uploader(
            "Puja tots els arxius Excel dels partits:",
            type=['xlsx'],
            accept_multiple_files=True,
            key="reimport_files"
        )
        
        if uploaded_files:
            st.info(f"📁 {len(uploaded_files)} arxius seleccionats")
            
            # Mostrar lista de archivos
            with st.expander("📋 Arxius detectats"):
                for f in uploaded_files:
                    rival = obtener_rival(f.name)
                    tipo = "Local" if es_local(f.name) else "Visitant"
                    st.write(f"• **{rival}** ({tipo}) - `{f.name}`")
            
            confirmacio = st.text_input(
                "Escriu 'REIMPORTAR' per confirmar:",
                key="confirm_reimport"
            )
            
            if st.button("🔄 Reimportar tots els partits", type="primary", key="btn_reimport"):
                if confirmacio != "REIMPORTAR":
                    st.error("Has d'escriure 'REIMPORTAR' per confirmar")
                else:
                    try:
                        with st.spinner("Eliminant partits antics..."):
                            # Eliminar todos los partidos del equipo/temporada
                            with get_engine().begin() as conn:
                                # Obtener IDs de partidos a eliminar
                                partidos_eliminar = conn.execute(text("""
                                    SELECT id FROM partidos_new 
                                    WHERE equipo_id = :equipo_id AND temporada_id = :temporada_id
                                """), {
                                    "equipo_id": st.session_state.equipo_id,
                                    "temporada_id": st.session_state.temporada_id
                                }).fetchall()
                                
                                ids_eliminar = [p[0] for p in partidos_eliminar]
                                
                                if ids_eliminar:
                                    ids_str = ','.join(map(str, ids_eliminar))
                                    conn.execute(text(f"DELETE FROM acciones_new WHERE partido_id IN ({ids_str})"))
                                    conn.execute(text(f"DELETE FROM partidos_new WHERE id IN ({ids_str})"))
                                
                                st.success(f"✅ Eliminats {len(ids_eliminar)} partits antics")
                        
                        # Reimportar cada archivo
                        partidos_importados = 0
                        errores = []
                        
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        for idx, uploaded_file in enumerate(uploaded_files):
                            try:
                                status_text.text(f"Important {uploaded_file.name}...")
                                
                                # Procesar Excel
                                df = pd.read_excel(uploaded_file, header=1)
                                df.columns = [
                                    "id_accion", "tipo_accion", "marca", "jugador_apellido",
                                    "jugador_numero", "zona_jugador", "zona_colocador",
                                    "set_numero", "puntos_local", "puntos_visitante"
                                ]
                                
                                # Filtrar acciones válidas
                                df_filtrado = df[df['jugador_apellido'].notna() & (df['jugador_apellido'].str.strip() != '')]
                                df_filtrado = df_filtrado[df_filtrado['tipo_accion'].isin(['recepción', 'colocación', 'atacar', 'saque', 'defensa', 'bloqueo'])]
                                
                                # Detectar info del partido
                                rival = obtener_rival(uploaded_file.name)
                                local = es_local(uploaded_file.name)
                                
                                # Calcular resultado
                                try:
                                    sets_info = df_filtrado.groupby('set_numero').agg({
                                        'puntos_local': 'max',
                                        'puntos_visitante': 'max'
                                    }).reset_index()
                                    
                                    sets_local = 0
                                    sets_visitante = 0
                                    
                                    for _, row in sets_info.iterrows():
                                        if int(row['puntos_local']) > int(row['puntos_visitante']):
                                            sets_local += 1
                                        else:
                                            sets_visitante += 1
                                    
                                    if local:
                                        resultado = f"{sets_local}-{sets_visitante}"
                                    else:
                                        resultado = f"{sets_visitante}-{sets_local}"
                                except:
                                    resultado = None
                                
                                # Insertar partido
                                with get_engine().begin() as conn:
                                    partido_result = conn.execute(text("""
                                        INSERT INTO partidos_new (
                                            rival, local, fecha, resultado, nombre_archivo,
                                            equipo_id, temporada_id, fase_id
                                        )
                                        VALUES (
                                            :rival, :local, :fecha, :resultado, :nombre_archivo,
                                            :equipo_id, :temporada_id, :fase_id
                                        )
                                        RETURNING id
                                    """), {
                                        "rival": rival,
                                        "local": local,
                                        "fecha": None,
                                        "resultado": resultado,
                                        "nombre_archivo": uploaded_file.name,
                                        "equipo_id": st.session_state.equipo_id,
                                        "temporada_id": st.session_state.temporada_id,
                                        "fase_id": st.session_state.get('fase_id')
                                    })
                                    
                                    partido_id = partido_result.fetchone()[0]
                                    
                                    # Primero, obtener/crear todos los jugadores
                                    apellidos_unicos = df_filtrado['jugador_apellido'].str.strip().unique()
                                    jugadores_map = {}
                                    
                                    for apellido in apellidos_unicos:
                                        jugador_result = conn.execute(text("""
                                            SELECT id FROM jugadores 
                                            WHERE LOWER(apellido) = LOWER(:apellido) AND equipo_id = :equipo_id
                                        """), {"apellido": apellido, "equipo_id": st.session_state.equipo_id}).fetchone()
                                        
                                        if jugador_result:
                                            jugadores_map[apellido.lower()] = jugador_result[0]
                                        else:
                                            nuevo_id = conn.execute(text("""
                                                INSERT INTO jugadores (apellido, equipo_id, activo)
                                                VALUES (:apellido, :equipo_id, true)
                                                RETURNING id
                                            """), {"apellido": apellido, "equipo_id": st.session_state.equipo_id}).fetchone()[0]
                                            jugadores_map[apellido.lower()] = nuevo_id
                                    
                                    # Preparar todas las acciones para insert batch
                                    acciones_batch = []
                                    for _, row in df_filtrado.iterrows():
                                        apellido = row['jugador_apellido'].strip().lower()
                                        acciones_batch.append({
                                            "partido_id": partido_id,
                                            "jugador_id": jugadores_map[apellido],
                                            "set_numero": int(row['set_numero']),
                                            "tipo_accion": row['tipo_accion'],
                                            "marca": row['marca'],
                                            "zona_jugador": row['zona_jugador'] if pd.notna(row['zona_jugador']) else None,
                                            "zona_colocador": row['zona_colocador'] if pd.notna(row['zona_colocador']) else None,
                                            "puntos_local": int(row['puntos_local']) if pd.notna(row['puntos_local']) else None,
                                            "puntos_visitante": int(row['puntos_visitante']) if pd.notna(row['puntos_visitante']) else None
                                        })
                                    
                                    # Insert batch (mucho más rápido)
                                    if acciones_batch:
                                        conn.execute(text("""
                                            INSERT INTO acciones_new (
                                                partido_id, jugador_id, set_numero, tipo_accion, marca,
                                                zona_jugador, zona_colocador, puntos_local, puntos_visitante
                                            )
                                            VALUES (
                                                :partido_id, :jugador_id, :set_numero, :tipo_accion, :marca,
                                                :zona_jugador, :zona_colocador, :puntos_local, :puntos_visitante
                                            )
                                        """), acciones_batch)
                                
                                partidos_importados += 1
                                
                            except Exception as e:
                                errores.append(f"{uploaded_file.name}: {str(e)}")
                            
                            progress_bar.progress((idx + 1) / len(uploaded_files))
                        
                        status_text.empty()
                        progress_bar.empty()
                        
                        # Limpiar caché
                        st.cache_data.clear()
                        
                        # Resultado final
                        st.success(f"✅ **Reimportació completada!** {partidos_importados}/{len(uploaded_files)} partits importats")
                        
                        if errores:
                            st.error("❌ Errors:")
                            for err in errores:
                                st.write(f"  • {err}")
                        
                        st.balloons()
                        
                    except Exception as e:
                        st.error(f"❌ Error general: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
        
    # =================================
    # TAB 6: USUARIOS
    # =================================
    with tab6:
        st.subheader("👤 Gestió d'Usuaris")
        
        # Mostrar usuarios actuales
        st.markdown("**Usuaris actuals:**")
        
        with get_engine().connect() as conn:
            usuarios_actuales = pd.read_sql(text("""
                SELECT u.id, u.username, u.es_admin, u.activo, e.nombre as equipo
                FROM usuarios u
                LEFT JOIN equipos e ON u.equipo_id = e.id
                ORDER BY u.es_admin DESC, u.username
            """), conn)
        
        if not usuarios_actuales.empty:
            df_display = usuarios_actuales.copy()
            df_display['es_admin'] = df_display['es_admin'].apply(lambda x: '✅ Admin' if x else '👤 Usuari')
            df_display['activo'] = df_display['activo'].apply(lambda x: '✅ Actiu' if x else '❌ Inactiu')
            df_display.columns = ['ID', 'Usuari', 'Rol', 'Estat', 'Equip']
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("No hi ha usuaris creats")
        
        st.markdown("---")
        
        # Crear nuevo usuario
        st.markdown("**➕ Crear nou usuari:**")
        
        equipos = cargar_equipos()
        
        col1, col2 = st.columns(2)
        
        with col1:
            nuevo_username = st.text_input("Nom d'usuari:", key="nuevo_username")
            nuevo_password = st.text_input("Contrasenya:", type="password", key="nuevo_password")
        
        with col2:
            equipo_opciones = [None] + equipos['id'].tolist()
            nuevo_equipo = st.selectbox(
                "Equip assignat:",
                options=equipo_opciones,
                format_func=lambda x: "Cap (Admin)" if x is None else equipos[equipos['id'] == x]['nombre_completo'].iloc[0],
                key="nuevo_usuario_equipo"
            )
            nuevo_es_admin = st.checkbox("És administrador?", key="nuevo_es_admin")
        
        if st.button("✅ Crear usuari", type="primary", key="btn_crear_usuario"):
            if not nuevo_username or not nuevo_password:
                st.error("❌ Has d'introduir usuari i contrasenya")
            else:
                try:
                    with get_engine().begin() as conn:
                        conn.execute(text("""
                            INSERT INTO usuarios (username, password, equipo_id, es_admin, activo)
                            VALUES (:username, :password, :equipo_id, :es_admin, TRUE)
                        """), {
                            "username": nuevo_username,
                            "password": encriptar_password(nuevo_password),
                            "equipo_id": nuevo_equipo,
                            "es_admin": nuevo_es_admin
                        })
                    
                    st.success(f"✅ Usuari '{nuevo_username}' creat correctament!")
                    st.rerun()
                    
                except Exception as e:
                    if "unique" in str(e).lower():
                        st.error("❌ Aquest nom d'usuari ja existeix")
                    else:
                        st.error(f"❌ Error: {str(e)}")
        
        # Editar/Eliminar usuario
        st.markdown("---")
        st.markdown("**✏️ Editar usuari:**")
        
        if not usuarios_actuales.empty:
            usuario_editar = st.selectbox(
                "Selecciona usuari:",
                options=[None] + usuarios_actuales['id'].tolist(),
                format_func=lambda x: "Selecciona..." if x is None else usuarios_actuales[usuarios_actuales['id'] == x]['username'].iloc[0],
                key="usuario_editar"
            )
            
            if usuario_editar:
                usuario_info = usuarios_actuales[usuarios_actuales['id'] == usuario_editar].iloc[0]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    edit_password = st.text_input("Nova contrasenya (deixa buit per no canviar):", type="password", key=f"edit_pass_{usuario_editar}")
                    
                    # Buscar equipo_id actual
                    with get_engine().connect() as conn:
                        equipo_actual = conn.execute(text("SELECT equipo_id FROM usuarios WHERE id = :id"), {"id": usuario_editar}).fetchone()
                        equipo_actual_id = equipo_actual[0] if equipo_actual else None
                    
                    edit_equipo = st.selectbox(
                        "Equip:",
                        options=equipo_opciones,
                        index=equipo_opciones.index(equipo_actual_id) if equipo_actual_id in equipo_opciones else 0,
                        format_func=lambda x: "Cap (Admin)" if x is None else equipos[equipos['id'] == x]['nombre_completo'].iloc[0],
                        key=f"edit_equipo_{usuario_editar}"
                    )
                
                with col2:
                    edit_es_admin = st.checkbox("És administrador?", value=usuario_info['es_admin'], key=f"edit_admin_{usuario_editar}")
                    edit_activo = st.checkbox("Usuari actiu?", value=usuario_info['activo'], key=f"edit_activo_{usuario_editar}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("💾 Guardar canvis", type="primary", key=f"btn_guardar_usuario_{usuario_editar}"):
                        try:
                            with get_engine().begin() as conn:
                                if edit_password:
                                    conn.execute(text("""
                                        UPDATE usuarios 
                                        SET password = :password, equipo_id = :equipo_id, es_admin = :es_admin, activo = :activo
                                        WHERE id = :id
                                    """), {
                                        "password": encriptar_password(edit_password),
                                        "equipo_id": edit_equipo,
                                        "es_admin": edit_es_admin,
                                        "activo": edit_activo,
                                        "id": usuario_editar
                                    })
                                else:
                                    conn.execute(text("""
                                        UPDATE usuarios 
                                        SET equipo_id = :equipo_id, es_admin = :es_admin, activo = :activo
                                        WHERE id = :id
                                    """), {
                                        "equipo_id": edit_equipo,
                                        "es_admin": edit_es_admin,
                                        "activo": edit_activo,
                                        "id": usuario_editar
                                    })
                            
                            st.success("✅ Usuari actualitzat!")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                
                with col2:
                    if st.button("🗑️ Eliminar usuari", type="secondary", key=f"btn_eliminar_usuario_{usuario_editar}"):
                        try:
                            with get_engine().begin() as conn:
                                conn.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": usuario_editar})
                            
                            st.success("✅ Usuari eliminat!")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")

    with tab7:
        st.subheader("📋 Registre d'Accessos")
        
        with get_engine().connect() as conn:
            accesos = pd.read_sql(text("""
                SELECT 
                    fecha,
                    username,
                    CASE WHEN exitoso THEN '✅ Èxit' ELSE '❌ Fallat' END as resultat
                FROM registro_accesos
                ORDER BY fecha DESC
                LIMIT 100
            """), conn)
        
        if not accesos.empty:
            accesos['fecha'] = pd.to_datetime(accesos['fecha']).dt.strftime('%d/%m/%Y %H:%M')
            accesos = accesos.rename(columns={
                'fecha': 'Data',
                'username': 'Usuari',
                'resultat': 'Resultat'
            })
            st.dataframe(accesos, use_container_width=True, hide_index=True)
            
            # Resumen
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                total_exitosos = len(accesos[accesos['Resultat'] == '✅ Èxit'])
                st.metric("Accessos exitosos", total_exitosos)
            with col2:
                total_fallidos = len(accesos[accesos['Resultat'] == '❌ Fallat'])
                st.metric("Intents fallits", total_fallidos)
        else:
            st.info("No hi ha registres d'accés")

# =============================================================================
# SIDEBAR Y NAVEGACIÓN
# =============================================================================

def sidebar_contexto():
    """Sidebar con contexto y navegación"""
    
    # Inicializar contador de intentos de login
    if 'intentos_login' not in st.session_state:
        st.session_state.intentos_login = 0
    if 'bloqueado_hasta' not in st.session_state:
        st.session_state.bloqueado_hasta = None
    
    logged_in = st.session_state.get('logged_in', False)
    es_admin = st.session_state.get('es_admin', False)
    
    # Mostrar estado de sesión
    if logged_in:
        usuario = st.session_state.get('usuario', {})
        st.sidebar.markdown(f"👤 **{usuario.get('username', '')}**")
        if st.sidebar.button("🚪 Tancar sessió", use_container_width=True):
            logout()
            st.rerun()
    else:
        st.sidebar.markdown("👤 **Visitant**")
        
        with st.sidebar.expander("🔐 Iniciar sessió"):
            # Verificar si está bloqueado
            import time
            ahora = time.time()
            
            if st.session_state.bloqueado_hasta and ahora < st.session_state.bloqueado_hasta:
                segundos_restantes = int(st.session_state.bloqueado_hasta - ahora)
                st.error(f"⏳ Massa intents. Espera {segundos_restantes} segons.")
            else:
                # Resetear bloqueo si ya pasó el tiempo
                if st.session_state.bloqueado_hasta and ahora >= st.session_state.bloqueado_hasta:
                    st.session_state.intentos_login = 0
                    st.session_state.bloqueado_hasta = None
                
                username = st.text_input("Usuari:", key="sidebar_login_user")
                password = st.text_input("Contrasenya:", type="password", key="sidebar_login_pass")
                
                # Mostrar intentos restantes si hay alguno fallido
                if st.session_state.intentos_login > 0:
                    intentos_restantes = 5 - st.session_state.intentos_login
                    st.warning(f"⚠️ {intentos_restantes} intents restants")
                
                if st.button("Entrar", type="primary", use_container_width=True, key="sidebar_login_btn"):
                    if username and password:
                        usuario = verificar_login(username, password)
                        
                        if usuario:
                            # Login correcto - resetear intentos
                            st.session_state.intentos_login = 0
                            st.session_state.bloqueado_hasta = None
                            
                            st.session_state.logged_in = True
                            st.session_state.usuario = usuario
                            st.session_state.es_admin = usuario['es_admin']

                            # Crear sesión persistente
                            token = crear_sesion(usuario['id'])
                            if token:
                                st.session_state.session_token = token
                                st.query_params['session'] = token
                            
                            if not usuario['es_admin'] and usuario['equipo_id']:
                                st.session_state.equipo_id = usuario['equipo_id']
                                equipos = cargar_equipos()
                                equipo_info = equipos[equipos['id'] == usuario['equipo_id']]
                                if not equipo_info.empty:
                                    st.session_state.equipo_nombre = equipo_info['nombre_completo'].iloc[0]
                            
                            # Registrar acceso exitoso
                            registrar_acceso(usuario['id'], usuario['username'], True)
                            
                            st.success(f"✅ Benvingut, {usuario['username']}!")
                            st.rerun()
                        else:
                            # Login fallido
                            st.session_state.intentos_login += 1
                            
                            # Registrar intento fallido
                            registrar_acceso(None, username, False)
                            
                            if st.session_state.intentos_login >= 5:
                                # Bloquear durante 60 segundos
                                st.session_state.bloqueado_hasta = time.time() + 60
                                st.error("❌ Massa intents. Bloquejat 60 segons.")
                            else:
                                st.error("❌ Usuari o contrasenya incorrectes")
                    else:
                        st.warning("⚠️ Introdueix usuari i contrasenya")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Context de Treball")
    
    # Cargar datos
    equipos = cargar_equipos()
    temporadas = cargar_temporadas()
    
    # Si NO es admin, solo puede ver su equipo
    es_admin = st.session_state.get('es_admin', False)
    
    if es_admin:
        # Admin puede seleccionar cualquier equipo
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
    else:
        # Usuario normal: equipo fijo
        equipo_id = st.session_state.get('equipo_id')
        if equipo_id:
            equipo_nombre = st.session_state.get('equipo_nombre', '')
            st.sidebar.info(f"🏐 **{equipo_nombre}**")
        else:
            st.sidebar.warning("⚠️ No tens equip assignat")
            equipo_id = None
    
    if equipo_id:
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
    
    # Navegación según rol
    if es_admin:
        opciones = ["🏠 Inici", "🏐 Equips", "📊 Partit", "👤 Jugador", "🎴 Fitxes", "📈 Comparativa", "📤 Importar", "⚙️ Admin"]
    elif logged_in:
        opciones = ["🏠 Inici", "🏐 Equips", "📊 Partit", "👤 Jugador", "🎴 Fitxes", "📈 Comparativa"]
    else:
        opciones = ["🏠 Inici", "🏐 Equips"]
    
    pagina = st.sidebar.radio(
        "Navegació",
        opciones,
        label_visibility="collapsed"
    )

    # Botón de donación Ko-fi
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style="text-align: center;">
        <a href="https://ko-fi.com/gerardbalastegui" target="_blank">
            <img src="https://storage.ko-fi.com/cdn/kofi2.png?v=3" alt="Buy Me a Coffee" style="height: 40px;">
        </a>
        <p style="font-size: 0.75rem; color: #888; margin-top: 0.5rem;">Si t'agrada l'app, convida'm a un cafè ☕</p>
    </div>
    """, unsafe_allow_html=True)

    # Footer con marca personal
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style="text-align: center; color: #888; font-size: 0.8rem; padding: 0.5rem;">
        Desenvolupat per <b>Gerard Balastegui Mera</b><br>
        <a href="https://instagram.com/gerardbalastegui" target="_blank" style="color: #E1306C; text-decoration: none;">
            📸 @gerardbalastegui
        </a>
    </div>
    """, unsafe_allow_html=True)
    
    return pagina


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Función principal"""
    
    # Verificar si hay sesión guardada en query params
    if not st.session_state.get('logged_in'):
        token = st.query_params.get('session')
        if token:
            usuario = verificar_sesion(token)
            if usuario:
                st.session_state.logged_in = True
                st.session_state.usuario = usuario
                st.session_state.es_admin = usuario['es_admin']
                st.session_state.session_token = token
                
                if not usuario['es_admin'] and usuario['equipo_id']:
                    st.session_state.equipo_id = usuario['equipo_id']
                    equipos = cargar_equipos()
                    equipo_info = equipos[equipos['id'] == usuario['equipo_id']]
                    if not equipo_info.empty:
                        st.session_state.equipo_nombre = equipo_info['nombre_completo'].iloc[0]
    
    # Sidebar y navegación (ahora siempre visible)
    pagina = sidebar_contexto()
    
    # Determinar nivel de acceso
    logged_in = st.session_state.get('logged_in', False)
    es_admin = st.session_state.get('es_admin', False)
    
    # Páginas públicas (sin login)
    paginas_publicas = ["🏠 Inici", "🏐 Equips"]
    
    # Páginas que requieren login
    paginas_privadas = ["📊 Partit", "👤 Jugador", "🎴 Fitxes", "📈 Comparativa"]
    
    # Páginas solo admin
    paginas_admin = ["📤 Importar", "⚙️ Admin"]
    
    # Routing
    if pagina in paginas_publicas:
        # Acceso libre
        if pagina == "🏠 Inici":
            if not logged_in:
                pagina_inicio_publica()
            else:
                pagina_inicio()
        elif pagina == "🏐 Equips":
            pagina_equipos_publica()
    
    elif pagina in paginas_privadas:
        if not logged_in:
            st.warning("🔐 Has d'iniciar sessió per veure aquesta secció")
            mostrar_login_inline()
        else:
            if pagina == "📊 Partit":
                pagina_partido()
            elif pagina == "👤 Jugador":
                pagina_jugador()
            elif pagina == "🎴 Fitxes":
                pagina_fichas()
            elif pagina == "📈 Comparativa":
                pagina_comparativa()
    
    elif pagina in paginas_admin:
        if not es_admin:
            st.error("⛔ Necessites permisos d'administrador")
        else:
            if pagina == "📤 Importar":
                from importar_partido_streamlit import pagina_importar_partido
                pagina_importar_partido(get_engine)
            elif pagina == "⚙️ Admin":
                pagina_admin()

if __name__ == "__main__":
    main()
