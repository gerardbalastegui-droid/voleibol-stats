# -*- coding: utf-8 -*-
"""
analisis_avanzado_v2.py
Módulo de análisis avanzado para informes de voleibol
Contiene funciones para Side-out, Contraataque, Rankings y análisis por rotación
ADAPTADO A LA NUEVA ESTRUCTURA (v2)
"""
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from sqlalchemy import text
from config_v2 import (
    COLOR_ROJO, COLOR_BLANCO, COLOR_NEGRO, COLOR_AMARILLO, COLOR_GRIS,
    COLOR_VERDE, COLOR_NARANJA, A4_H
)

# ============================================================================
# UTILIDADES - INDICADORES SEMÁFORO
# ============================================================================

def obtener_color_semaforo(valor, metrica_tipo="eficacia"):
    """
    Retorna color según valor y tipo de métrica
    
    Args:
        valor: valor numérico del porcentaje
        metrica_tipo: "eficacia" o "eficiencia"
    
    Returns:
        color hexadecimal
    """
    if metrica_tipo == "eficacia":
        # Eficacia: >60% verde, 40-60% amarillo, <40% rojo
        if valor >= 60:
            return COLOR_VERDE
        elif valor >= 40:
            return COLOR_NARANJA
        else:
            return COLOR_ROJO
    else:  # eficiencia
        # Eficiencia: >30% verde, 10-30% amarillo, <10% rojo
        if valor >= 30:
            return COLOR_VERDE
        elif valor >= 10:
            return COLOR_NARANJA
        else:
            return COLOR_ROJO

def aplicar_semaforo_tabla(tabla, df, col_eficacia_idx, col_eficiencia_idx):
    """
    Aplica colores semáforo a las celdas de eficacia y eficiencia
    
    Args:
        tabla: objeto tabla de matplotlib
        df: DataFrame con los datos
        col_eficacia_idx: índice de columna de eficacia
        col_eficiencia_idx: índice de columna de eficiencia
    """
    for row_idx in range(1, len(df) + 1):  # +1 porque fila 0 es header
        # Eficacia
        valor_eficacia = float(df.iloc[row_idx - 1, col_eficacia_idx])
        color_efic = obtener_color_semaforo(valor_eficacia, "eficacia")
        tabla[(row_idx, col_eficacia_idx)].set_facecolor(color_efic)
        tabla[(row_idx, col_eficacia_idx)].set_text_props(color=COLOR_BLANCO, weight="bold")
        
        # Eficiencia
        valor_eficiencia = float(df.iloc[row_idx - 1, col_eficiencia_idx])
        color_efic_efic = obtener_color_semaforo(valor_eficiencia, "eficiencia")
        tabla[(row_idx, col_eficiencia_idx)].set_facecolor(color_efic_efic)
        tabla[(row_idx, col_eficiencia_idx)].set_text_props(color=COLOR_BLANCO, weight="bold")

# ============================================================================
# 1. SIDE-OUT VS CONTRAATAQUE
# ============================================================================

def obtener_datos_sideout_contraataque_v2(conn, partido_ids):
    """
    Obtiene estadísticas separadas de Side-out y Contraataque
    
    Side-out: PRIMER ataque después de cada recepción (máximo 1 por punto)
    Contraataque: Todos los demás ataques
    
    Lógica: 
    - Recorremos acciones ordenadas por ID
    - Tras cada recepción, el siguiente ataque es side-out
    - El resto de ataques son contraataque
    
    Returns:
        DataFrame con columnas: fase, total, eficacia_pct, eficiencia_pct
    """
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    # Estrategia: marcar cada ataque según si es el primero después de una recepción
    query = text(f"""
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
                -- Side-out: ataque inmediatamente después de recepción
                WHEN tipo_accion = 'atacar' AND accion_previa = 'recepción' THEN 'Side-out'
                -- Side-out: ataque después de recepción->colocación
                WHEN tipo_accion = 'atacar' AND accion_previa = 'colocación' AND accion_previa_2 = 'recepción' THEN 'Side-out'
                -- Contraataque: resto de ataques
                WHEN tipo_accion = 'atacar' THEN 'Contraatac'
                ELSE NULL
            END AS fase
        FROM acciones_ordenadas
        WHERE tipo_accion = 'atacar'
    )
    SELECT 
        fase,
        COUNT(*) AS total,
        ROUND((COUNT(*) FILTER (WHERE marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 2) AS eficacia_pct,
        ROUND(((COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))::decimal / NULLIF(COUNT(*),0))*100, 2) AS eficiencia_pct
    FROM ataques_clasificados
    WHERE fase IS NOT NULL
    GROUP BY fase
    ORDER BY fase DESC
    """)
    
    return pd.read_sql(query, conn)

def pagina_sideout_contraataque_v2(pdf, conn, partido_ids, titulo_contexto=""):
    """
    Genera página con análisis de Side-out vs Contraataque
    
    Args:
        pdf: objeto PdfPages
        conn: conexión a BD
        partido_ids: lista de IDs o int
        titulo_contexto: texto adicional para el título (ej: "VS RIVAL")
    """
    df = obtener_datos_sideout_contraataque_v2(conn, partido_ids)
    
    if df.empty:
        return  # No hay datos suficientes
    
    fig = plt.figure(figsize=A4_H)
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.5], hspace=0.35)
    
    # Título
    fig.text(0.02, 0.98, "SIDE-OUT VS CONTRAATAC", fontsize=14, 
            color=COLOR_ROJO, fontweight='bold', verticalalignment='top')
    if titulo_contexto:
        fig.text(0.02, 0.95, titulo_contexto, fontsize=11, 
                color=COLOR_NEGRO, verticalalignment='top')
    fig.text(0.02, 0.93, '─' * 30, fontsize=10, color=COLOR_ROJO, 
            verticalalignment='top')
    
    # TABLA
    ax_tabla = fig.add_subplot(gs[0])
    ax_tabla.axis("off")
    
    # Formatear para display
    df_display = df.copy()
    df_display['eficacia_pct'] = df_display['eficacia_pct'].round(1)
    df_display['eficiencia_pct'] = df_display['eficiencia_pct'].round(1)
    
    df_display.columns = ['Fase', 'Total', 'Eficàcia (%)', 'Eficiència (%)']
    
    tabla = ax_tabla.table(cellText=df_display.values, colLabels=df_display.columns,
                           cellLoc="center", loc="center")
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(11)
    tabla.scale(1, 1.5)
    
    # Header
    for c in range(len(df_display.columns)):
        tabla[(0, c)].set_facecolor(COLOR_ROJO)
        tabla[(0, c)].set_text_props(color=COLOR_BLANCO, weight="bold")
    
    # Aplicar semáforo
    aplicar_semaforo_tabla(tabla, df_display, 2, 3)
    
    # GRÁFICA
    ax_grafica = fig.add_subplot(gs[1])
    
    fases = df_display['Fase'].tolist()
    eficacia = df_display['Eficàcia (%)'].tolist()
    eficiencia = df_display['Eficiència (%)'].tolist()
    
    x = range(len(fases))
    bar_width = 0.35
    
    ax_grafica.bar([i - bar_width/2 for i in x], eficacia, width=bar_width,
                   color=COLOR_ROJO, label="Eficàcia (%)")
    ax_grafica.bar([i + bar_width/2 for i in x], eficiencia, width=bar_width,
                   color=COLOR_NEGRO, label="Eficiència (%)")
    
    ax_grafica.set_xticks(list(x))
    ax_grafica.set_xticklabels(fases, fontsize=12, fontweight='bold')
    ax_grafica.set_ylabel("%", fontsize=11)
    ax_grafica.axhline(0, color=COLOR_AMARILLO, linewidth=1.5)
    ax_grafica.legend(fontsize=10)
    ax_grafica.grid(axis="y", linestyle="--", alpha=0.4)
    
    # Añadir líneas de referencia
    ax_grafica.axhline(60, color=COLOR_VERDE, linewidth=0.5, linestyle='--', alpha=0.3)
    ax_grafica.axhline(40, color=COLOR_NARANJA, linewidth=0.5, linestyle='--', alpha=0.3)
    
    plt.subplots_adjust(left=0.1, right=0.9, top=0.88, bottom=0.1)
    pdf.savefig(fig)
    plt.close(fig)

# ============================================================================
# 2. EFICIENCIA DE ATAQUE POR ROTACIÓN
# ============================================================================

def obtener_datos_ataque_rotacion_v2(conn, partido_ids):
    """
    Obtiene estadísticas de ataque agrupadas por rotación (P1-P6)
    
    Returns:
        DataFrame con: rotacion, total, eficacia_pct, eficiencia_pct
    """
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    query = text(f"""
    SELECT 
        UPPER(zona_colocador) AS rotacion,
        COUNT(*) AS total,
        ROUND((COUNT(*) FILTER (WHERE marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 2) AS eficacia_pct,
        ROUND(((COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))::decimal / NULLIF(COUNT(*),0))*100, 2) AS eficiencia_pct
    FROM acciones_new
    WHERE partido_id IN ({ids_str})
    AND tipo_accion = 'atacar'
    AND zona_colocador IS NOT NULL
    GROUP BY zona_colocador
    ORDER BY zona_colocador
    """)
    
    return pd.read_sql(query, conn)

def pagina_ataque_por_rotacion_v2(pdf, conn, partido_ids, titulo_contexto=""):
    """Genera página con análisis de ataque por rotación"""
    df = obtener_datos_ataque_rotacion_v2(conn, partido_ids)
    
    if df.empty:
        return
    
    # Ordenar por rotación P1-P6
    orden_rotaciones = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6']
    df['rotacion'] = pd.Categorical(df['rotacion'], categories=orden_rotaciones, ordered=True)
    df = df.sort_values('rotacion')
    
    fig = plt.figure(figsize=A4_H)
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.5], hspace=0.35)
    
    # Título
    fig.text(0.02, 0.98, "EFICIÈNCIA D'ATAC PER ROTACIÓ", fontsize=14, 
            color=COLOR_ROJO, fontweight='bold', verticalalignment='top')
    if titulo_contexto:
        fig.text(0.02, 0.95, titulo_contexto, fontsize=11, 
                color=COLOR_NEGRO, verticalalignment='top')
    fig.text(0.02, 0.93, '─' * 30, fontsize=10, color=COLOR_ROJO, 
            verticalalignment='top')
    
    # TABLA
    ax_tabla = fig.add_subplot(gs[0])
    ax_tabla.axis("off")
    
    df_display = df.copy()
    df_display['eficacia_pct'] = df_display['eficacia_pct'].round(1)
    df_display['eficiencia_pct'] = df_display['eficiencia_pct'].round(1)
    df_display.columns = ['Rotació', 'Total', 'Eficàcia (%)', 'Eficiència (%)']
    
    tabla = ax_tabla.table(cellText=df_display.values, colLabels=df_display.columns,
                           cellLoc="center", loc="center")
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(11)
    tabla.scale(1, 1.5)
    
    for c in range(len(df_display.columns)):
        tabla[(0, c)].set_facecolor(COLOR_ROJO)
        tabla[(0, c)].set_text_props(color=COLOR_BLANCO, weight="bold")
    
    aplicar_semaforo_tabla(tabla, df_display, 2, 3)
    
    # GRÁFICA
    ax_grafica = fig.add_subplot(gs[1])
    
    rotaciones = df_display['Rotació'].tolist()
    eficacia = df_display['Eficàcia (%)'].tolist()
    eficiencia = df_display['Eficiència (%)'].tolist()
    
    x = range(len(rotaciones))
    bar_width = 0.35
    
    ax_grafica.bar([i - bar_width/2 for i in x], eficacia, width=bar_width,
                   color=COLOR_ROJO, label="Eficàcia (%)")
    ax_grafica.bar([i + bar_width/2 for i in x], eficiencia, width=bar_width,
                   color=COLOR_NEGRO, label="Eficiència (%)")
    
    ax_grafica.set_xticks(list(x))
    ax_grafica.set_xticklabels(rotaciones, fontsize=12, fontweight='bold')
    ax_grafica.set_ylabel("%", fontsize=11)
    ax_grafica.axhline(0, color=COLOR_AMARILLO, linewidth=1.5)
    ax_grafica.legend(fontsize=10)
    ax_grafica.grid(axis="y", linestyle="--", alpha=0.4)
    
    plt.subplots_adjust(left=0.1, right=0.9, top=0.88, bottom=0.1)
    pdf.savefig(fig)
    plt.close(fig)

# ============================================================================
# 3. CARGA DE JUEGO DEL COLOCADOR
# ============================================================================

def obtener_carga_colocador_v2(conn, partido_ids):
    """
    Analiza distribución de colocaciones por zona/atacante
    
    Returns:
        DataFrame con: zona_atacante, num_colocaciones, pct_total, eficacia_ataque
    """
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    query = text(f"""
    WITH total_coloc AS (
        SELECT COUNT(*) as total
        FROM acciones_new
        WHERE partido_id IN ({ids_str})
        AND tipo_accion = 'atacar'
        AND zona_jugador IS NOT NULL
    )
    SELECT 
        UPPER(zona_jugador) AS zona_atacante,
        COUNT(*) AS num_colocaciones,
        ROUND((COUNT(*)::decimal / (SELECT total FROM total_coloc))*100, 1) AS pct_total,
        ROUND((COUNT(*) FILTER (WHERE marca IN ('#','+'))::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficacia_ataque
    FROM acciones_new
    WHERE partido_id IN ({ids_str})
    AND tipo_accion = 'atacar'
    AND zona_jugador IS NOT NULL
    GROUP BY zona_jugador
    ORDER BY num_colocaciones DESC
    """)
    
    return pd.read_sql(query, conn)

def pagina_carga_colocador_v2(pdf, conn, partido_ids, titulo_contexto=""):
    """Genera página con análisis de carga del colocador"""
    df = obtener_carga_colocador_v2(conn, partido_ids)
    
    if df.empty:
        return
    
    fig = plt.figure(figsize=A4_H)
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.5], hspace=0.35, wspace=0.3)
    
    # Título
    fig.text(0.02, 0.98, "DISTRIBUCIÓ DEL COLOCADOR", fontsize=14, 
            color=COLOR_ROJO, fontweight='bold', verticalalignment='top')
    if titulo_contexto:
        fig.text(0.02, 0.95, titulo_contexto, fontsize=11, 
                color=COLOR_NEGRO, verticalalignment='top')
    fig.text(0.02, 0.93, '─' * 30, fontsize=10, color=COLOR_ROJO, 
            verticalalignment='top')
    
    # TABLA (ocupa ambas columnas)
    ax_tabla = fig.add_subplot(gs[0, :])
    ax_tabla.axis("off")
    
    df_display = df.copy()
    df_display.columns = ['Zona', 'Col·locacions', '% Total', 'Eficàcia Atac (%)']
    
    tabla = ax_tabla.table(cellText=df_display.values, colLabels=df_display.columns,
                           cellLoc="center", loc="center")
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(10)
    tabla.scale(1, 1.4)
    
    for c in range(len(df_display.columns)):
        tabla[(0, c)].set_facecolor(COLOR_ROJO)
        tabla[(0, c)].set_text_props(color=COLOR_BLANCO, weight="bold")
    
    # Colorear por carga (% Total)
    for row_idx in range(1, len(df) + 1):
        pct_carga = float(df.iloc[row_idx - 1]['pct_total'])
        if pct_carga > 25:  # Sobrecarga
            tabla[(row_idx, 2)].set_facecolor(COLOR_ROJO)
            tabla[(row_idx, 2)].set_text_props(color=COLOR_BLANCO, weight="bold")
        elif pct_carga > 15:
            tabla[(row_idx, 2)].set_facecolor(COLOR_NARANJA)
            tabla[(row_idx, 2)].set_text_props(color=COLOR_BLANCO, weight="bold")
        else:
            tabla[(row_idx, 2)].set_facecolor(COLOR_GRIS)
    
    # GRÁFICA DISTRIBUCIÓN (izquierda)
    ax_dist = fig.add_subplot(gs[1, 0])
    
    zonas = df_display['Zona'].tolist()
    pcts = df_display['% Total'].tolist()
    
    ax_dist.barh(zonas, pcts, color=COLOR_ROJO)
    ax_dist.set_xlabel("% del total de col·locacions", fontsize=10)
    ax_dist.set_title("Volum per zona", fontsize=11, fontweight='bold')
    ax_dist.grid(axis="x", linestyle="--", alpha=0.4)
    ax_dist.axvline(16.67, color=COLOR_AMARILLO, linewidth=1, linestyle='--', label='Equilibri (16.67%)')
    ax_dist.legend(fontsize=8)
    
    # GRÁFICA EFICACIA (derecha)
    ax_efic = fig.add_subplot(gs[1, 1])
    
    eficacia = df_display['Eficàcia Atac (%)'].tolist()
    colors = [obtener_color_semaforo(e, "eficacia") for e in eficacia]
    
    ax_efic.barh(zonas, eficacia, color=colors)
    ax_efic.set_xlabel("Eficàcia d'atac (%)", fontsize=10)
    ax_efic.set_title("Rendiment per zona", fontsize=11, fontweight='bold')
    ax_efic.grid(axis="x", linestyle="--", alpha=0.4)
    ax_efic.axvline(60, color=COLOR_VERDE, linewidth=0.5, linestyle='--', alpha=0.3)
    ax_efic.axvline(40, color=COLOR_NARANJA, linewidth=0.5, linestyle='--', alpha=0.3)
    
    plt.subplots_adjust(left=0.1, right=0.95, top=0.88, bottom=0.1)
    pdf.savefig(fig)
    plt.close(fig)

# ============================================================================
# 7. RANKINGS POSITIVOS (MOTIVACIONALES)
# ============================================================================

def obtener_rankings_positivos_v2(conn, partido_ids):
    """
    Obtiene rankings de acciones positivas
    
    Returns:
        dict con DataFrames: 'puntos_directos', 'saques_ruptura', 'bloqueos'
    """
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    # Puntos directos (ataque + saque + bloqueo #) - todos valen igual
    query_puntos = text(f"""
    SELECT 
        j.apellido AS jugador,
        COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar' AND a.marca = '#') AS atac_punt,
        COUNT(*) FILTER (WHERE a.tipo_accion = 'saque' AND a.marca = '#') AS saque_punt,
        COUNT(*) FILTER (WHERE a.tipo_accion = 'bloqueo' AND a.marca = '#') AS bloqueig_punt,
        COUNT(*) FILTER (WHERE a.marca = '#' AND a.tipo_accion IN ('atacar', 'saque', 'bloqueo')) AS total_punts
    FROM acciones_new a
    JOIN jugadores j ON a.jugador_id = j.id
    WHERE a.partido_id IN ({ids_str})
    AND a.tipo_accion IN ('atacar', 'saque', 'bloqueo')
    AND a.marca = '#'
    GROUP BY j.apellido
    HAVING COUNT(*) > 0
    ORDER BY total_punts DESC
    LIMIT 5
    """)
    
    # Saques efectivos (# = 2 puntos, + = 1 punto)
    query_saques = text(f"""
    SELECT 
        j.apellido AS jugador,
        COUNT(*) FILTER (WHERE a.marca = '#') AS ace,
        COUNT(*) FILTER (WHERE a.marca = '+') AS positiu,
        (COUNT(*) FILTER (WHERE a.marca = '#') * 2 + COUNT(*) FILTER (WHERE a.marca = '+')) AS puntuacio
    FROM acciones_new a
    JOIN jugadores j ON a.jugador_id = j.id
    WHERE a.partido_id IN ({ids_str})
    AND a.tipo_accion = 'saque'
    AND a.marca IN ('#', '+')
    GROUP BY j.apellido
    HAVING COUNT(*) > 0
    ORDER BY puntuacio DESC
    LIMIT 5
    """)
    
    # Bloqueos efectivos (# = 2 puntos, + = 1 punto)
    query_bloqueos = text(f"""
    SELECT 
        j.apellido AS jugador,
        COUNT(*) FILTER (WHERE a.marca = '#') AS punt,
        COUNT(*) FILTER (WHERE a.marca = '+') AS positiu,
        (COUNT(*) FILTER (WHERE a.marca = '#') * 2 + COUNT(*) FILTER (WHERE a.marca = '+')) AS puntuacio
    FROM acciones_new a
    JOIN jugadores j ON a.jugador_id = j.id
    WHERE a.partido_id IN ({ids_str})
    AND a.tipo_accion = 'bloqueo'
    AND a.marca IN ('#', '+')
    GROUP BY j.apellido
    HAVING COUNT(*) > 0
    ORDER BY puntuacio DESC
    LIMIT 5
    """)
    
    return {
        'puntos_directos': pd.read_sql(query_puntos, conn),
        'saques_ruptura': pd.read_sql(query_saques, conn),
        'bloqueos': pd.read_sql(query_bloqueos, conn)
    }

def pagina_rankings_positivos_v2(pdf, conn, partido_ids, titulo_contexto=""):
    """Genera página con rankings positivos motivacionales"""
    rankings = obtener_rankings_positivos_v2(conn, partido_ids)
    
    fig = plt.figure(figsize=A4_H)
    gs = fig.add_gridspec(3, 1, hspace=0.4)
    
    # Título
    fig.text(0.02, 0.98, "RANKINGS DESTACATS", fontsize=14, 
            color=COLOR_ROJO, fontweight='bold', verticalalignment='top')
    if titulo_contexto:
        fig.text(0.02, 0.95, titulo_contexto, fontsize=11, 
                color=COLOR_NEGRO, verticalalignment='top')
    fig.text(0.02, 0.93, '─' * 35, fontsize=10, color=COLOR_ROJO, 
            verticalalignment='top')
    
    titulos = [
        "[#] Top Punts Directes (Atac + Saque + Bloqueig)",
        "[+] Top Saques Efectius",
        "[X] Top Bloquejos Efectius"
    ]
    
    dfs = [
        rankings['puntos_directos'][['jugador', 'atac_punt', 'saque_punt', 'bloqueig_punt', 'total_punts']],
        rankings['saques_ruptura'][['jugador', 'ace', 'positiu']],
        rankings['bloqueos'][['jugador', 'punt', 'positiu']]
    ]
    
    nombres_cols = [
        ['Jugador', 'Atac #', 'Saque #', 'Bloq #', 'TOTAL'],
        ['Jugador', 'Ace (#)', 'Positiu (+)'],
        ['Jugador', 'Punt (#)', 'Positiu (+)']
    ]
    
    for idx, (titulo, df, cols) in enumerate(zip(titulos, dfs, nombres_cols)):
        ax = fig.add_subplot(gs[idx])
        ax.axis("off")
        
        # Subtítulo
        ax.text(0.5, 0.95, titulo, transform=ax.transAxes,
               ha='center', fontsize=12, color=COLOR_ROJO, fontweight='bold')
        
        if df.empty:
            ax.text(0.5, 0.5, "No hi ha dades", transform=ax.transAxes,
                   ha='center', fontsize=10, color=COLOR_GRIS)
            continue
        
        df_display = df.copy()
        df_display.columns = cols
        
        tabla = ax.table(cellText=df_display.values, colLabels=df_display.columns,
                        cellLoc="center", loc="center", bbox=[0.1, 0.1, 0.8, 0.7])
        tabla.auto_set_font_size(False)
        tabla.set_fontsize(9)
        
        # Header
        for c in range(len(cols)):
            tabla[(0, c)].set_facecolor(COLOR_ROJO)
            tabla[(0, c)].set_text_props(color=COLOR_BLANCO, weight="bold")
        
        # Colorear top 3
        colores_podio = ["#FFD700", "#C0C0C0", "#CD7F32"]  # Oro, Plata, Bronce
        for row_idx in range(1, min(4, len(df) + 1)):
            for col_idx in range(len(cols)):
                tabla[(row_idx, col_idx)].set_facecolor(colores_podio[row_idx - 1])
                if row_idx == 1:  # Oro con texto en negrita
                    tabla[(row_idx, col_idx)].set_text_props(weight="bold")
    
    plt.subplots_adjust(left=0.05, right=0.95, top=0.9, bottom=0.05)
    pdf.savefig(fig)
    plt.close(fig)
