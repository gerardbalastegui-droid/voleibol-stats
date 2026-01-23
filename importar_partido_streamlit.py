# -*- coding: utf-8 -*-
"""
importar_partido_streamlit.py
Módulo para importar partidos desde la web Streamlit
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
import re
from datetime import date

# =============================================================================
# FUNCIONES AUXILIARES (adaptadas de importar_partido_v2.py)
# =============================================================================

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
    return True  # Por defecto local

def calcular_resultado(df, local):
    """Calcula el resultado del partido"""
    try:
        sets_info = df.groupby('set_numero').agg({
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
            return f"{sets_local}-{sets_visitante}"
        else:
            return f"{sets_visitante}-{sets_local}"
    except:
        return None

def partido_ya_existe(engine, nombre_archivo):
    """Verifica si un partido ya fue importado"""
    with engine.connect() as conn:
        resultado = conn.execute(
            text("SELECT COUNT(*) FROM partidos_new WHERE nombre_archivo = :nombre"),
            {"nombre": nombre_archivo}
        ).scalar()
        return resultado > 0

def obtener_o_crear_jugador(conn, apellido, equipo_id):
    """Obtiene o crea un jugador por apellido"""
    # Buscar existente
    resultado = conn.execute(text("""
        SELECT id FROM jugadores 
        WHERE LOWER(apellido) = LOWER(:apellido) AND equipo_id = :equipo_id
    """), {"apellido": apellido, "equipo_id": equipo_id}).fetchone()
    
    if resultado:
        return resultado[0]
    
    # Crear nuevo
    resultado = conn.execute(text("""
        INSERT INTO jugadores (apellido, equipo_id, activo)
        VALUES (:apellido, :equipo_id, true)
        RETURNING id
    """), {"apellido": apellido, "equipo_id": equipo_id})
    
    return resultado.fetchone()[0]

def procesar_excel(uploaded_file):
    """
    Procesa el archivo Excel y devuelve el DataFrame formateado
    """
    try:
        # Leer Excel con header en fila 1 (la fila 0 tiene info del equipo)
        df = pd.read_excel(uploaded_file, header=1)
        
        # Renombrar columnas
        df.columns = [
            "id_accion", "tipo_accion", "marca", "jugador_apellido",
            "jugador_numero", "zona_jugador", "zona_colocador",
            "set_numero", "puntos_local", "puntos_visitante"
        ]
        
        return df, None
    except Exception as e:
        return None, str(e)

def validar_datos(df):
    """Valida los datos del DataFrame"""
    errores = []
    
    # Verificar columnas necesarias
    columnas_requeridas = ['tipo_accion', 'marca', 'jugador_apellido', 'set_numero']
    for col in columnas_requeridas:
        if col not in df.columns:
            errores.append(f"Falta la columna: {col}")
    
    if errores:
        return False, errores
    
    # Verificar tipos de acción válidos
    acciones_validas = ['recepción', 'colocación', 'atacar', 'saque', 'defensa', 'bloqueo']
    acciones_en_df = df['tipo_accion'].dropna().unique()
    acciones_invalidas = [a for a in acciones_en_df if a not in acciones_validas]
    if acciones_invalidas:
        errores.append(f"Accions no vàlides: {acciones_invalidas}")
    
    # Verificar marcas válidas
    marcas_validas = ['#', '+', '!', '-', '/', '=']
    marcas_en_df = df['marca'].dropna().unique()
    marcas_invalidas = [m for m in marcas_en_df if m not in marcas_validas]
    if marcas_invalidas:
        errores.append(f"Marques no vàlides: {marcas_invalidas}")
    
    if errores:
        return False, errores
    
    return True, []

# =============================================================================
# PÁGINA PRINCIPAL DE IMPORTACIÓN
# =============================================================================

def pagina_importar_partido(get_engine_func):
    """
    Página de Streamlit para importar partidos
    
    Args:
        get_engine_func: Función que devuelve el engine de SQLAlchemy
    """
    engine = get_engine_func()
    
    st.markdown("""
    <div class="main-header">
        <h1>📤 Importar Partit</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Verificar contexto
    if not st.session_state.get('equipo_id') or not st.session_state.get('temporada_id'):
        st.warning("⚠️ Selecciona primer un equip i temporada al menú lateral")
        return
    
    # Mostrar contexto actual
    st.info(f"""
    **Context actual:**
    - 📋 Equip: {st.session_state.get('equipo_nombre', '-')}
    - 📅 Temporada: {st.session_state.get('temporada_nombre', '-')}
    - 🏆 Fase: {st.session_state.get('fase_nombre', 'Totes les fases')}
    """)
    
    # Si no hay fase seleccionada, pedir que seleccione una
    if not st.session_state.get('fase_id'):
        st.warning("⚠️ Per importar un partit, has de seleccionar una fase específica al menú lateral")
        return
    
    st.markdown("---")
    
    # =================================
    # PASO 1: Subir archivo
    # =================================
    st.subheader("1️⃣ Puja l'arxiu Excel")
    
    st.markdown("""
    💡 **Format del nom del fitxer:** `partido01_vs_NomRival_home.xlsx` o `partido01_vs_NomRival_guest.xlsx`
    - `home` = Partit local
    - `guest` = Partit visitant
    """)
    
    uploaded_file = st.file_uploader(
        "Selecciona l'arxiu Excel del partit",
        type=['xlsx'],
        help="Arxiu generat per l'aplicació d'estadístiques"
    )
    
    if uploaded_file is None:
        st.info("👆 Puja un arxiu Excel per continuar")
        return
    
    # =================================
    # PASO 2: Detectar información
    # =================================
    st.markdown("---")
    st.subheader("2️⃣ Informació detectada")
    
    nombre_archivo = uploaded_file.name
    
    # Verificar si ya existe
    if partido_ya_existe(engine, nombre_archivo):
        st.error(f"❌ Aquest partit ja ha estat importat: `{nombre_archivo}`")
        return
    
    # Detectar rival y tipo
    rival_detectado = obtener_rival(nombre_archivo)
    es_local_detectado = es_local(nombre_archivo)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        rival = st.text_input("Rival", value=rival_detectado)
    
    with col2:
        tipo_partido = st.selectbox(
            "Tipus de partit",
            options=["Local", "Visitant"],
            index=0 if es_local_detectado else 1
        )
        local = tipo_partido == "Local"
    
    with col3:
        fecha = st.date_input("Data del partit", value=date.today())
    
    # =================================
    # PASO 3: Procesar y previsualizar
    # =================================
    st.markdown("---")
    st.subheader("3️⃣ Previsualització de les dades")
    
    # Procesar Excel
    df, error = procesar_excel(uploaded_file)
    
    if error:
        st.error(f"❌ Error llegint l'arxiu: {error}")
        return
    
    # Calcular resultado
    resultado = calcular_resultado(df, local)
    
    # Filtrar acciones válidas
    df_filtrado = df[df['jugador_apellido'].notna() & (df['jugador_apellido'].str.strip() != '')]
    df_filtrado = df_filtrado[df_filtrado['tipo_accion'].isin(['recepción', 'colocación', 'atacar', 'saque', 'defensa', 'bloqueo'])]
    
    # Validar
    valido, errores = validar_datos(df_filtrado)
    
    if not valido:
        st.error("❌ Errors de validació:")
        for err in errores:
            st.write(f"  • {err}")
        return
    
    # Mostrar resumen
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Accions totals", len(df_filtrado))
    
    with col2:
        st.metric("Jugadors", df_filtrado['jugador_apellido'].nunique())
    
    with col3:
        st.metric("Sets", df_filtrado['set_numero'].nunique())
    
    with col4:
        st.metric("Resultat", resultado or "?")
    
    # Mostrar jugadores detectados
    with st.expander("👥 Jugadors detectats"):
        jugadores_detectados = df_filtrado['jugador_apellido'].unique()
        
        # Verificar cuáles ya existen
        with engine.connect() as conn:
            jugadores_existentes = conn.execute(text("""
                SELECT apellido FROM jugadores 
                WHERE equipo_id = :equipo_id AND LOWER(apellido) IN :apellidos
            """), {
                "equipo_id": st.session_state.equipo_id,
                "apellidos": tuple([j.lower() for j in jugadores_detectados])
            }).fetchall()
            existentes = [j[0].lower() for j in jugadores_existentes]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**✅ Ja existents:**")
            for j in jugadores_detectados:
                if j.lower() in existentes:
                    st.write(f"  • {j}")
        
        with col2:
            st.markdown("**🆕 Nous (es crearan):**")
            nuevos = [j for j in jugadores_detectados if j.lower() not in existentes]
            if nuevos:
                for j in nuevos:
                    st.write(f"  • {j}")
            else:
                st.write("  Cap")
    
    # Mostrar acciones por tipo
    with st.expander("📊 Resum d'accions"):
        resumen = df_filtrado.groupby('tipo_accion').agg({
            'id_accion': 'count',
            'marca': lambda x: (x == '#').sum()
        }).reset_index()
        resumen.columns = ['Acció', 'Total', 'Punts (#)']
        st.dataframe(resumen, use_container_width=True, hide_index=True)
    
    # =================================
    # PASO 4: Importar
    # =================================
    st.markdown("---")
    st.subheader("4️⃣ Confirmar importació")
    
    st.markdown(f"""
    **Resum final:**
    - 🏐 **Rival:** {rival}
    - 📍 **Tipus:** {tipo_partido}
    - 📅 **Data:** {fecha}
    - 📊 **Resultat:** {resultado or 'No calculat'}
    - 👥 **Jugadors:** {df_filtrado['jugador_apellido'].nunique()}
    - 📝 **Accions:** {len(df_filtrado)}
    """)
    
    if st.button("✅ Importar partit", type="primary", use_container_width=True):
        try:
            with st.spinner("Important..."):
                # Crear partido
                with engine.begin() as conn:
                    # Insertar partido
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
                        "fecha": fecha,
                        "resultado": resultado,
                        "nombre_archivo": nombre_archivo,
                        "equipo_id": st.session_state.equipo_id,
                        "temporada_id": st.session_state.temporada_id,
                        "fase_id": st.session_state.fase_id
                    })
                    
                    partido_id = partido_result.fetchone()[0]
                    
                    # Insertar acciones
                    jugadores_creados = []
                    
                    for _, row in df_filtrado.iterrows():
                        apellido = row['jugador_apellido'].strip()
                        
                        # Obtener o crear jugador
                        jugador_id = obtener_o_crear_jugador(conn, apellido, st.session_state.equipo_id)
                        
                        # Insertar acción
                        conn.execute(text("""
                            INSERT INTO acciones_new (
                                partido_id, jugador_id, set_numero, tipo_accion, marca,
                                zona_jugador, zona_colocador
                            )
                            VALUES (
                                :partido_id, :jugador_id, :set_numero, :tipo_accion, :marca,
                                :zona_jugador, :zona_colocador
                            )
                        """), {
                            "partido_id": partido_id,
                            "jugador_id": jugador_id,
                            "set_numero": int(row['set_numero']),
                            "tipo_accion": row['tipo_accion'],
                            "marca": row['marca'],
                            "zona_jugador": row['zona_jugador'] if pd.notna(row['zona_jugador']) else None,
                            "zona_colocador": row['zona_colocador'] if pd.notna(row['zona_colocador']) else None
                        })
                
                # Limpiar caché para que se actualicen los datos
                st.cache_data.clear()
                
                st.success(f"""
                ✅ **Partit importat correctament!**
                
                - 🆔 ID del partit: **{partido_id}**
                - 🏐 {rival} ({tipo_partido})
                - 📊 Resultat: {resultado or '-'}
                - 📝 {len(df_filtrado)} accions importades
                """)
                
                st.balloons()
                
                # Botón para ir al informe
                st.markdown("---")
                st.info("👉 Ara pots anar a **📊 Partit** per veure les estadístiques")
                
        except Exception as e:
            st.error(f"❌ Error important: {str(e)}")
            import traceback
            st.code(traceback.format_exc())


# =============================================================================
# FUNCIÓN PARA INTEGRAR EN app.py
# =============================================================================

def agregar_pagina_importar(app_module):
    """
    Ejemplo de cómo integrar esta página en tu app.py existente
    
    En tu app.py, añade al sidebar:
    
    ```python
    pagina = st.sidebar.radio(
        "Selecciona secció:",
        options=["🏠 Inici", "📊 Partit", "👤 Jugador", "🎴 Fitxes", "📈 Comparativa", "📤 Importar"],
        key='navegacion'
    )
    
    # Y en el routing:
    elif pagina == "📤 Importar":
        from importar_partido_streamlit import pagina_importar_partido
        pagina_importar_partido(get_engine)
    ```
    """
    pass
