# -*- coding: utf-8 -*-
"""
informe_partido_v2.py
Informe de partido adaptado a la NUEVA ESTRUCTURA
(usa partidos_new, acciones_new, jugadores con ID)
"""
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from sqlalchemy import text
from config_v2 import (
    engine, A4_H, ZONAS_TABLA, ORDEN_ROTACIONES, RENOMBRAR_COLUMNAS,
    COLOR_ROJO, COLOR_AMARILLO, COLOR_BLANCO, COLOR_NEGRO, COLOR_GRIS,
    TABLA_PARTIDOS, TABLA_ACCIONES
)
from utils_v2 import separar_mayusculas, obtener_info_partido
from visualizaciones import portada, tabla_y_grafica_combinada, pagina_podio, tabla_estilizada

# Importar módulos de análisis avanzado (VERSIÓN V2)
from analisis_avanzado_v2 import (
    pagina_sideout_contraataque_v2,
    pagina_ataque_por_rotacion_v2,
    pagina_carga_colocador_v2,
    pagina_rankings_positivos_v2
)
from analisis_errores_v2 import pagina_analisis_errores_v2

# Importar funciones originales (sin modificar, compatibles)
from informe_partido import (
    pagina_distribucion_ataque_unificada
)

def estadisticas_equipo_v2(pdf, conn, partido_id):
    """Genera página con estadísticas globales del equipo en formato tabla + gráfica (VERSIÓN V2)"""
    
    reglas = {
        "atacar": ("marca IN ('#','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"),
        "recepción": ("marca IN ('#','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"),
        "saque": ("marca IN ('#','/','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"),
        "bloqueo": ("marca IN ('#','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca IN ('/','=')))"),
    }
    
    nombres_cat = {
        "atacar": "Atac",
        "recepción": "Recepció", 
        "saque": "Saque",
        "bloqueo": "Bloqueig"
    }
    
    # Recopilar datos
    datos = []
    for accion_bd, (efic_cond, eficien_expr) in reglas.items():
        q = text(f"""
        SELECT 
            COUNT(*) as total,
            ROUND((COUNT(*) FILTER (WHERE {efic_cond})::decimal / NULLIF(COUNT(*),0))*100, 2) as eficacia_pct,
            ROUND(({eficien_expr}::decimal / NULLIF(COUNT(*),0))*100, 2) as eficiencia_pct
        FROM {TABLA_ACCIONES}
        WHERE partido_id = :pid AND tipo_accion = :tipo
        """)
        
        df = pd.read_sql(q, conn, params={"pid": partido_id, "tipo": accion_bd})
        
        if not df.empty and df.iloc[0]['total'] > 0:
            datos.append([
                nombres_cat[accion_bd],
                int(df.iloc[0]['total']),
                f"{df.iloc[0]['eficacia_pct']:.1f}%",
                f"{df.iloc[0]['eficiencia_pct']:.1f}%"
            ])
    
    # Crear DataFrame para la tabla
    df_tabla = pd.DataFrame(datos, columns=['Acció', 'Total', 'Eficàcia', 'Eficiència'])
    
    # Crear figura con tabla y gráfica
    fig = plt.figure(figsize=A4_H)
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1], hspace=0.4)
    
    # Título
    fig.text(0.5, 0.95, "ESTADÍSTIQUES GLOBALS DE L'EQUIP", 
            ha='center', fontsize=14, color=COLOR_ROJO, weight='bold')
    
    # TABLA
    ax_tabla = fig.add_subplot(gs[0])
    ax_tabla.axis('off')
    
    tabla = ax_tabla.table(cellText=df_tabla.values, 
                          colLabels=df_tabla.columns,
                          cellLoc='center', loc='center')
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(10)
    tabla.scale(1, 2)
    
    # Estilizar encabezados
    for col in range(len(df_tabla.columns)):
        tabla[(0, col)].set_facecolor(COLOR_ROJO)
        tabla[(0, col)].set_text_props(color=COLOR_BLANCO, weight='bold')
    
    # Estilizar filas
    for row in range(1, len(df_tabla) + 1):
        for col in range(len(df_tabla.columns)):
            tabla[(row, col)].set_facecolor(COLOR_GRIS if row % 2 == 0 else COLOR_BLANCO)
    
    # GRÁFICA DE BARRAS
    ax_grafica = fig.add_subplot(gs[1])
    
    # Extraer valores numéricos de eficacia y eficiencia
    acciones = df_tabla['Acció'].tolist()
    eficacia = [float(x.strip('%')) for x in df_tabla['Eficàcia']]
    eficiencia = [float(x.strip('%')) for x in df_tabla['Eficiència']]
    
    x = range(len(acciones))
    bar_width = 0.35
    
    ax_grafica.bar([i - bar_width/2 for i in x], eficacia, width=bar_width, 
                   color=COLOR_ROJO, label='Eficàcia (%)')
    ax_grafica.bar([i + bar_width/2 for i in x], eficiencia, width=bar_width, 
                   color=COLOR_NEGRO, label='Eficiència (%)')
    
    ax_grafica.set_xticks(x)
    ax_grafica.set_xticklabels(acciones, fontsize=10)
    ax_grafica.set_ylabel('%', fontsize=10)
    ax_grafica.legend(fontsize=9)
    ax_grafica.grid(axis='y', alpha=0.3)
    ax_grafica.axhline(0, color=COLOR_AMARILLO, linewidth=1)
    
    plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
    pdf.savefig(fig)
    plt.close(fig)

def generar_informe_partido_v2(partido_id, nombre_pdf, incluir_analisis_avanzado=True):
    """
    Genera el informe completo de un partido (NUEVA ESTRUCTURA)
    
    Args:
        partido_id: ID del partido en partidos_new
        nombre_pdf: ruta del PDF a generar
        incluir_analisis_avanzado: si True, añade las nuevas secciones
    """
    with engine.connect() as conn:
        # Obtener información del partido (nueva estructura)
        info_partido = obtener_info_partido(partido_id)
        
        if not info_partido:
            print(f"\n❌ No s'ha trobat el partit amb ID {partido_id}")
            return
        
        rival = separar_mayusculas(info_partido['rival'])
        tipo_partido = "LOCAL" if info_partido['local'] else "VISITANT"
        titulo_contexto = f"VS {rival.upper()} ({tipo_partido})"
        
        # Información adicional del contexto
        equipo_completo = info_partido['equipo_completo']
        temporada = info_partido['temporada']
        fase = info_partido['fase'] if info_partido['fase'] else "N/A"
        
        dfs = {}

        # IMPORTANTE: Las queries ahora usan acciones_new y JOIN con jugadores
        reglas = {
            "atacar": ("marca IN ('#','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"),
            "recepción": ("marca IN ('#','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"),
            "saque": ("marca IN ('#','/','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"),
            "bloqueo": ("marca IN ('#','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca IN ('/','=')))"),
        }

        nombres_catalan = {
            "atacar": "Atac",
            "recepción": "Recepció",
            "saque": "Saque",
            "bloqueo": "Bloqueig"
        }

        # Consultas adaptadas: JOIN con tabla jugadores
        for acc, (efic, eficien) in reglas.items():
            q = text(f"""
            SELECT j.apellido as jugador_apellido,
                   COUNT(*) AS total,
                   ROUND((COUNT(*) FILTER (WHERE {efic})::decimal / NULLIF(COUNT(*),0))*100,2) AS eficacia_pct,
                   ROUND(({eficien}::decimal / NULLIF(COUNT(*),0))*100,2) AS eficiencia_pct
            FROM {TABLA_ACCIONES} a
            JOIN jugadores j ON a.jugador_id = j.id
            WHERE a.partido_id = :pid AND a.tipo_accion = :tipo_acc
            GROUP BY j.apellido
            """)
            dfs[nombres_catalan[acc]] = pd.read_sql(q, conn, params={"pid": partido_id, "tipo_acc": acc}).rename(columns=RENOMBRAR_COLUMNAS)

        # Distribución de ataque (adaptada)
        dist = pd.read_sql(text(f"""
            SELECT
                LOWER(zona_colocador) AS rot,
                LOWER(zona_jugador) AS zona,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE marca = '#') AS puntos
            FROM {TABLA_ACCIONES}
            WHERE partido_id = :pid
              AND tipo_accion = 'atacar'
              AND zona_colocador IS NOT NULL
              AND zona_jugador IS NOT NULL
            GROUP BY LOWER(zona_colocador), LOWER(zona_jugador)
        """), conn, params={"pid": partido_id})

        # Top 3 (adaptado con JOIN)
        df_top = pd.read_sql(text(f"""
            SELECT
                j.apellido AS jugador,
                (
                    COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar'   AND a.marca = '#')
                  + COUNT(*) FILTER (WHERE a.tipo_accion = 'saque'    AND a.marca = '#')
                  + COUNT(*) FILTER (WHERE a.tipo_accion = 'bloqueo'  AND a.marca = '#')
                  - COUNT(*) FILTER (WHERE a.tipo_accion = 'recepción' AND a.marca = '=')
                  - COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar'    AND a.marca = '=')
                  - COUNT(*) FILTER (WHERE a.tipo_accion = 'saque'     AND a.marca = '=')
                  - COUNT(*) FILTER (WHERE a.tipo_accion = 'bloqueo'   AND a.marca = '/')
                ) AS valor
            FROM {TABLA_ACCIONES} a
            JOIN jugadores j ON a.jugador_id = j.id
            WHERE a.partido_id = :pid
            GROUP BY j.apellido
            HAVING COUNT(*) FILTER (WHERE a.marca IN ('#','=','/')) > 0
            ORDER BY valor DESC
            LIMIT 3
        """), conn, params={"pid": partido_id})

        # Todos los jugadores (adaptado)
        df_todos = pd.read_sql(text(f"""
            SELECT
                j.apellido AS jugador,
                (
                    COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar'   AND a.marca = '#')
                  + COUNT(*) FILTER (WHERE a.tipo_accion = 'saque'    AND a.marca = '#')
                  + COUNT(*) FILTER (WHERE a.tipo_accion = 'bloqueo'  AND a.marca = '#')
                  - COUNT(*) FILTER (WHERE a.tipo_accion = 'recepción' AND a.marca = '=')
                  - COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar'    AND a.marca = '=')
                  - COUNT(*) FILTER (WHERE a.tipo_accion = 'saque'     AND a.marca = '=')
                  - COUNT(*) FILTER (WHERE a.tipo_accion = 'bloqueo'   AND a.marca = '/')
                ) AS valor
            FROM {TABLA_ACCIONES} a
            JOIN jugadores j ON a.jugador_id = j.id
            WHERE a.partido_id = :pid
            GROUP BY j.apellido
            HAVING COUNT(*) FILTER (WHERE a.marca IN ('#','=','/')) > 0
            ORDER BY valor DESC
        """), conn, params={"pid": partido_id})

        # ============================================================
        # GENERAR PDF
        # ============================================================
        with PdfPages(nombre_pdf) as pdf:
            # PORTADA (mejorada con contexto)
            titulo_portada = f"INFORME DEL PARTIT\n{equipo_completo}"
            subtitulo_portada = f"VS {rival.upper()} ({tipo_partido})\n{temporada} - {fase}"
            portada(pdf, titulo_portada, subtitulo_portada)
            
            # ESTADÍSTICAS DEL EQUIPO
            estadisticas_equipo_v2(pdf, conn, partido_id)

            # ============================================================
            # ANÁLISIS AVANZADO (VERSIÓN V2)
            # ============================================================
            if incluir_analisis_avanzado:
                # 1. Side-out vs Contraataque
                pagina_sideout_contraataque_v2(pdf, conn, partido_id, titulo_contexto)
                
                # 2. Eficiencia de ataque por rotación
                pagina_ataque_por_rotacion_v2(pdf, conn, partido_id, titulo_contexto)
                
                # 3. Carga de juego del colocador
                pagina_carga_colocador_v2(pdf, conn, partido_id, titulo_contexto)
                
                # 4. Análisis de errores
                pagina_analisis_errores_v2(pdf, conn, partido_id, titulo_contexto)
            
            # ============================================================
            # SECCIONES ORIGINALES
            # ============================================================
            # Estadísticas por acción
            for acc, df in dfs.items():
                tabla_y_grafica_combinada(pdf, df, acc)

            # Distribución de ataque
            pagina_distribucion_ataque_unificada(pdf, dist, rival, info_partido['local'])

            # ============================================================
            # RANKINGS POSITIVOS (VERSIÓN V2)
            # ============================================================
            if incluir_analisis_avanzado:
                pagina_rankings_positivos_v2(pdf, conn, partido_id, titulo_contexto)

            # Podio y valores
            pagina_podio(pdf, df_top)
            tabla_estilizada(pdf, df_todos, "Valoració dels jugadors")

    print(f"\n✅ Informe de partit v2 generat: {nombre_pdf}")
    print(f"   📋 Equip: {equipo_completo}")
    print(f"   📅 Temporada: {temporada} - Fase: {fase}")
    if incluir_analisis_avanzado:
        print("   📊 Amb anàlisi avançat")
