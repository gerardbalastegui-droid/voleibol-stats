# -*- coding: utf-8 -*-
"""
app.py - Aplicación Streamlit para estadísticas de Voleibol
Sistema de informes interactivo para el club
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
    # En producción, usar variables de entorno
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
        return pd.read_sql(text("""
            SELECT id, apellido, nombre, dorsal, posicion
            FROM jugadores
            WHERE equipo_id = :eid AND activo = true
            ORDER BY apellido
        """), conn, params={"eid": equipo_id})

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
                j.apellido AS jugador,
                COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar' AND a.marca = '#') AS ataque,
                COUNT(*) FILTER (WHERE a.tipo_accion = 'saque' AND a.marca = '#') AS saque,
                COUNT(*) FILTER (WHERE a.tipo_accion = 'bloqueo' AND a.marca = '#') AS bloqueo,
                COUNT(*) FILTER (WHERE a.marca = '#' AND a.tipo_accion IN ('atacar', 'saque', 'bloqueo')) AS total
            FROM acciones_new a
            JOIN jugadores j ON a.jugador_id = j.id
            WHERE a.partido_id IN ({ids_str})
            AND a.tipo_accion IN ('atacar', 'saque', 'bloqueo')
            AND a.marca = '#'
            GROUP BY j.apellido
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
            SELECT 
                COALESCE(a.zona, 'Sin zona') as zona,
                COUNT(*) as colocaciones,
                ROUND((COUNT(*)::decimal / SUM(COUNT(*)) OVER()) * 100, 1) as porcentaje
            FROM acciones_new a
            WHERE a.partido_id IN ({ids_str})
            AND a.tipo_accion = 'colocación'
            GROUP BY a.zona
            ORDER BY colocaciones DESC
        """), conn)
        
        return df

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
        title='Distribución de Acciones',
        xaxis_title='Tipo de Acción',
        yaxis_title='Cantidad',
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
        name='Eficacia',
        x=tipos,
        y=df_resumen['eficacia'],
        marker_color=colores,
        text=df_resumen['eficacia'].apply(lambda x: f'{x}%'),
        textposition='outside'
    ))
    
    # Líneas de referencia
    fig.add_hline(y=60, line_dash="dash", line_color=COLOR_VERDE, 
                  annotation_text="Bueno (60%)")
    fig.add_hline(y=40, line_dash="dash", line_color=COLOR_NARANJA,
                  annotation_text="Regular (40%)")
    
    fig.update_layout(
        title='Eficacia por Tipo de Acción',
        xaxis_title='Tipo de Acción',
        yaxis_title='Eficacia (%)',
        height=400,
        yaxis=dict(range=[0, 100])
    )
    
    return fig

def crear_grafico_sideout(df_sideout):
    """Crea gráfico de side-out vs contraataque"""
    fig = make_subplots(rows=1, cols=2, subplot_titles=['Eficacia', 'Eficiencia'])
    
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
        title='Side-out vs Contraataque',
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
        'atacar': 'Ataque',
        'saque': 'Saque',
        'recepción': 'Recepción',
        'bloqueo': 'Bloqueo',
        'defensa': 'Defensa',
        'colocación': 'Colocación'
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
        name='Eficacia'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )
        ),
        title='Perfil del Jugador (Eficacia %)',
        height=400
    )
    
    return fig

def crear_podio(df_top, titulo="🏆 Top Anotadores"):
    """Crea visualización de podio"""
    if df_top.empty:
        st.info("No hay datos para mostrar el podio")
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
    if 'equipo_id' not in st.session_state or not st.session_state.equipo_id:
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
    
    # Selector de partido
    partidos['display'] = partidos.apply(
        lambda x: f"vs {x['rival']} ({'Local' if x['local'] else 'Visitant'}) - {x.get('fase', '')}", 
        axis=1
    )
    
    partido_seleccionado = st.selectbox(
        "Selecciona un partit:",
        options=partidos['id'].tolist(),
        format_func=lambda x: partidos[partidos['id'] == x]['display'].iloc[0]
    )
    
    if partido_seleccionado:
        # Info del partido
        info_partido = partidos[partidos['id'] == partido_seleccionado].iloc[0]
        
        st.markdown(f"""
        ### 🏐 vs {info_partido['rival']}
        **Tipus:** {'Local' if info_partido['local'] else 'Visitant'} | 
        **Fase:** {info_partido.get('fase', '-')} |
        **Resultat:** {info_partido.get('resultado', '-')}
        """)
        
        st.markdown("---")
        
        # Cargar datos
        df_resumen = obtener_resumen_acciones(partido_seleccionado)
        df_sideout = obtener_sideout_contraataque(partido_seleccionado)
        df_top = obtener_top_jugadores(partido_seleccionado)
        
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
        
        # === GRÁFICOS ===
        st.markdown("---")
        
        tab1, tab2, tab3 = st.tabs(["📊 Accions", "⚔️ Side-out", "🏆 Rankings"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(crear_grafico_acciones(df_resumen), use_container_width=True)
            with col2:
                st.plotly_chart(crear_grafico_eficacia(df_resumen), use_container_width=True)
            
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
        
        with tab2:
            if not df_sideout.empty:
                st.plotly_chart(crear_grafico_sideout(df_sideout), use_container_width=True)
                
                # Tabla side-out
                col1, col2 = st.columns(2)
                for idx, row in df_sideout.iterrows():
                    target_col = col1 if row['fase'] == 'Side-out' else col2
                    with target_col:
                        st.markdown(f"""
                        <div style="background: {COLOR_GRIS}; padding: 1rem; border-radius: 10px; text-align: center;">
                            <h3>{row['fase']}</h3>
                            <p><strong>Total:</strong> {row['total']} ataques</p>
                            <p><strong>Eficàcia:</strong> {row['eficacia']}%</p>
                            <p><strong>Eficiència:</strong> {row['eficiencia']}%</p>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("No hi ha dades de side-out/contraatac")
        
        with tab3:
            crear_podio(df_top, "🏆 Top Anotadors del Partit")
            
            if not df_top.empty:
                st.markdown("---")
                st.subheader("📋 Detall complet")
                st.dataframe(df_top.rename(columns={
                    'jugador': 'Jugador',
                    'ataque': 'Atac',
                    'saque': 'Saque',
                    'bloqueo': 'Bloqueig',
                    'total': 'Total'
                }), use_container_width=True, hide_index=True)

def pagina_jugador():
    """Página de análisis de jugador"""
    st.markdown("""
    <div class="main-header">
        <h1>👤 Informe de Jugador</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Verificar contexto
    if 'equipo_id' not in st.session_state or not st.session_state.equipo_id:
        st.warning("⚠️ Selecciona primer un equip i temporada al menú lateral")
        return
    
    # Cargar jugadores
    jugadores = cargar_jugadores(st.session_state.equipo_id)
    
    if jugadores.empty:
        st.info("No hi ha jugadors en aquest equip")
        return
    
    # Selector de jugador
    jugadores['display'] = jugadores.apply(
        lambda x: f"{x['apellido']} {x['nombre'] or ''} (#{x['dorsal'] or '-'})", 
        axis=1
    )
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        jugador_id = st.selectbox(
            "Selecciona un jugador:",
            options=jugadores['id'].tolist(),
            format_func=lambda x: jugadores[jugadores['id'] == x]['display'].iloc[0]
        )
    
    with col2:
        # Opción: todos los partidos o uno específico
        partidos = cargar_partidos(
            st.session_state.equipo_id,
            st.session_state.temporada_id,
            st.session_state.get('fase_id')
        )
        
        partidos['display'] = partidos.apply(
            lambda x: f"vs {x['rival']}", axis=1
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
        ### {jugador_info['apellido']} {jugador_info['nombre'] or ''}
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
                col.metric(f"{icono} {nombre}", "-", "Sin datos")
        
        # === GRÁFICOS ===
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico radar
            fig_radar = crear_grafico_radar_jugador(df_jugador)
            if fig_radar:
                st.plotly_chart(fig_radar, use_container_width=True)
        
        with col2:
            # Gráfico de barras
            fig = go.Figure()
            
            for _, row in df_jugador.iterrows():
                fig.add_trace(go.Bar(
                    name=row['tipo_accion'].capitalize(),
                    x=['#', '+', '!', '-', '='],
                    y=[row['puntos'], row['positivos'], row['neutros'], 
                       row['negativos'], row['errores']],
                ))
            
            fig.update_layout(
                title='Distribució per Marca',
                barmode='group',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        
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

def pagina_comparativa():
    """Página de comparación de partidos"""
    st.markdown("""
    <div class="main-header">
        <h1>📈 Comparativa de Partits</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Verificar contexto
    if 'equipo_id' not in st.session_state or not st.session_state.equipo_id:
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
        partido1 = st.selectbox(
            "Partit 1:",
            options=partidos['id'].tolist(),
            format_func=lambda x: partidos[partidos['id'] == x]['display'].iloc[0],
            key='partido1'
        )
    
    with col2:
        partido2 = st.selectbox(
            "Partit 2:",
            options=partidos['id'].tolist(),
            format_func=lambda x: partidos[partidos['id'] == x]['display'].iloc[0],
            key='partido2',
            index=1 if len(partidos) > 1 else 0
        )
    
    if partido1 and partido2 and partido1 != partido2:
        info1 = partidos[partidos['id'] == partido1].iloc[0]
        info2 = partidos[partidos['id'] == partido2].iloc[0]
        
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
            name=f"vs {info1['rival']}",
            x=nombres,
            y=eficacias1,
            marker_color=COLOR_ROJO,
            text=[f'{e}%' for e in eficacias1],
            textposition='outside'
        ))
        
        fig.add_trace(go.Bar(
            name=f"vs {info2['rival']}",
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
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabla comparativa
        st.subheader("📋 Taula Comparativa")
        
        comparativa = []
        for accion, nombre in zip(acciones, nombres):
            fila1 = df1[df1['tipo_accion'] == accion]
            fila2 = df2[df2['tipo_accion'] == accion]
            
            e1 = float(fila1['eficacia'].iloc[0]) if not fila1.empty else 0
            e2 = float(fila2['eficacia'].iloc[0]) if not fila2.empty else 0
            diff = e2 - e1
            
            comparativa.append({
                'Acció': nombre,
                f'vs {info1["rival"]}': f'{e1}%',
                f'vs {info2["rival"]}': f'{e2}%',
                'Diferència': f'{diff:+.1f}%'
            })
        
        st.dataframe(pd.DataFrame(comparativa), use_container_width=True, hide_index=True)
    
    elif partido1 == partido2:
        st.warning("Selecciona dos partits diferents per comparar")

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
    
    # Selector de equipo
    equipo_id = st.sidebar.selectbox(
        "Equip:",
        options=equipos['id'].tolist(),
        format_func=lambda x: equipos[equipos['id'] == x]['nombre_completo'].iloc[0],
        key='select_equipo'
    )
    
    if equipo_id:
        st.session_state.equipo_id = equipo_id
        st.session_state.equipo_nombre = equipos[equipos['id'] == equipo_id]['nombre_completo'].iloc[0]
    
    # Selector de temporada
    temporada_id = st.sidebar.selectbox(
        "Temporada:",
        options=temporadas['id'].tolist(),
        format_func=lambda x: temporadas[temporadas['id'] == x]['nombre'].iloc[0],
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
    
    st.sidebar.markdown("---")
    
    # Navegación
    st.sidebar.subheader("📍 Navegació")
    
    pagina = st.sidebar.radio(
        "Selecciona secció:",
        options=["🏠 Inici", "📊 Partit", "👤 Jugador", "📈 Comparativa"],
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
    elif pagina == "📈 Comparativa":
        pagina_comparativa()

if __name__ == "__main__":
    main()
