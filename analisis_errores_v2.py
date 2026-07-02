# -*- coding: utf-8 -*-
"""
analisis_errores_v2.py
Módulo de análisis de errores y tendencias comparativas
ADAPTADO A LA NUEVA ESTRUCTURA (v2)
"""
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from sqlalchemy import text
from config_v2 import (
    COLOR_ROJO, COLOR_BLANCO, COLOR_NEGRO, COLOR_AMARILLO, COLOR_GRIS,
    COLOR_VERDE, COLOR_NARANJA, A4_H
)

# ============================================================================
# 4. ERROR FORZADO VS ERROR NO FORZADO
# ============================================================================

def obtener_analisis_errores_v2(conn, partido_ids):
    """
    Clasifica errores en forzados (provocados por rival) y no forzados (propios)
    
    Criterios:
    - Error forzado: cuando el rival tiene acción positiva previa (#, +)
    - Error no forzado: error sin presión clara del rival
    
    Returns:
        DataFrame con: tipo_accion, errores_forzados, errores_no_forzados, total_errores
    """
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    
    ids_str = ','.join(map(str, partido_ids))
    
    # Contar errores por tipo de acción - solo acciones con errores
    
    query = text(f"""
    WITH errores_por_tipo AS (
        SELECT 
            tipo_accion,
            SUM(CASE WHEN tipo_accion = 'defensa' AND marca = '=' THEN 1 ELSE 0 END) AS errores_forzados,
            SUM(CASE WHEN tipo_accion IN ('atacar', 'saque', 'recepción') AND marca = '=' THEN 1
                     WHEN tipo_accion = 'bloqueo' AND marca = '/' THEN 1
                     ELSE 0 END) AS errores_no_forzados,
            COUNT(*) AS total_errores
        FROM acciones_new a
        WHERE a.partido_id IN ({ids_str})
        AND (
            (tipo_accion IN ('atacar', 'saque', 'recepción') AND marca = '=')
            OR (tipo_accion = 'bloqueo' AND marca IN ('=', '/'))
            OR (tipo_accion = 'defensa' AND marca = '=')
        )
        GROUP BY tipo_accion
    )
    SELECT 
        tipo_accion,
        errores_forzados,
        errores_no_forzados,
        total_errores
    FROM errores_por_tipo
    WHERE total_errores > 0
    ORDER BY total_errores DESC
    """)
    
    df = pd.read_sql(query, conn)
    
    # Calcular porcentajes
    df['pct_forzados'] = (df['errores_forzados'] / df['total_errores'] * 100).round(1)
    df['pct_no_forzados'] = (df['errores_no_forzados'] / df['total_errores'] * 100).round(1)
    
    return df

def pagina_analisis_errores_v2(pdf, conn, partido_ids, titulo_contexto=""):
    """Genera página con análisis de errores forzados vs no forzados"""
    df = obtener_analisis_errores_v2(conn, partido_ids)
    
    if df.empty:
        return
    
    # Renombrar acciones a catalán
    nombres_cat = {
        'atacar': 'Atac',
        'recepción': 'Recepció',
        'saque': 'Saque',
        'bloqueo': 'Bloqueig',
        'defensa': 'Defensa'
    }
    df['tipo_accion'] = df['tipo_accion'].map(nombres_cat).fillna(df['tipo_accion'])
    
    fig = plt.figure(figsize=A4_H)
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.5], hspace=0.4, wspace=0.3)
    
    # Título
    fig.text(0.02, 0.98, "ANÀLISI D'ERRORS", fontsize=14, 
            color=COLOR_ROJO, fontweight='bold', verticalalignment='top')
    if titulo_contexto:
        fig.text(0.02, 0.95, titulo_contexto, fontsize=11, 
                color=COLOR_NEGRO, verticalalignment='top')
    fig.text(0.02, 0.93, '─' * 30, fontsize=10, color=COLOR_ROJO, 
            verticalalignment='top')
    
    # TABLA (ocupa ambas columnas superiores)
    ax_tabla = fig.add_subplot(gs[0, :])
    ax_tabla.axis("off")
    
    df_display = df[['tipo_accion', 'errores_forzados', 'errores_no_forzados', 'total_errores']].copy()
    df_display.columns = ['Acció', 'Errors Forçats', 'Errors No Forçats', 'Total Errors']
    
    tabla = ax_tabla.table(cellText=df_display.values, colLabels=df_display.columns,
                           cellLoc="center", loc="center")
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(11)
    tabla.scale(1, 1.5)
    
    for c in range(len(df_display.columns)):
        tabla[(0, c)].set_facecolor(COLOR_ROJO)
        tabla[(0, c)].set_text_props(color=COLOR_BLANCO, weight="bold")
    
    # Colorear errores no forzados (más preocupantes)
    for row_idx in range(1, len(df) + 1):
        # Errores forzados (columna 1) - más tolerables
        tabla[(row_idx, 1)].set_facecolor(COLOR_NARANJA)
        tabla[(row_idx, 1)].set_text_props(weight="normal")
        
        # Errores no forzados (columna 2) - más preocupantes
        tabla[(row_idx, 2)].set_facecolor(COLOR_ROJO)
        tabla[(row_idx, 2)].set_text_props(color=COLOR_BLANCO, weight="bold")
    
    # GRÁFICA DE BARRAS APILADAS (izquierda)
    ax_barras = fig.add_subplot(gs[1, 0])
    
    acciones = df_display['Acció'].tolist()
    forzados = df['errores_forzados'].tolist()
    no_forzados = df['errores_no_forzados'].tolist()
    
    x = range(len(acciones))
    
    ax_barras.bar(x, forzados, label='Errors Forçats', color=COLOR_NARANJA)
    ax_barras.bar(x, no_forzados, bottom=forzados, label='Errors No Forçats', color=COLOR_ROJO)
    
    ax_barras.set_xticks(x)
    ax_barras.set_xticklabels(acciones, fontsize=11)
    ax_barras.set_ylabel("Nombre d'errors", fontsize=10)
    ax_barras.set_title("Composició dels errors", fontsize=11, fontweight='bold')
    ax_barras.legend(fontsize=9)
    ax_barras.grid(axis="y", linestyle="--", alpha=0.4)
    
    # GRÁFICA DE PORCENTAJES (derecha)
    ax_pct = fig.add_subplot(gs[1, 1])
    
    # Filtrar filas válidas y asegurar tipos correctos
    df_valido = df[df['total_errores'] > 0].copy()
    
    if not df_valido.empty and 'pct_forzados' in df_valido.columns:
        acciones_validas = [str(x) for x in df_display.loc[df_valido.index, 'Acció'].tolist()]
        pct_forzados = df_valido['pct_forzados'].fillna(0).astype(float).tolist()
        pct_no_forzados = df_valido['pct_no_forzados'].fillna(0).astype(float).tolist()
        
        ax_pct.barh(acciones_validas, pct_forzados, label='% Forçats', color=COLOR_NARANJA)
        ax_pct.barh(acciones_validas, pct_no_forzados, left=pct_forzados, label='% No Forçats', color=COLOR_ROJO)
        
        ax_pct.set_xlabel("Percentatge (%)", fontsize=10)
        ax_pct.set_title("Proporció d'errors", fontsize=11, fontweight='bold')
        ax_pct.legend(fontsize=9)
        ax_pct.grid(axis="x", linestyle="--", alpha=0.4)
        ax_pct.set_xlim(0, 100)
        
        # Añadir valores en las barras
        for i, (pf, pnf) in enumerate(zip(pct_forzados, pct_no_forzados)):
            if pf > 0:
                ax_pct.text(pf/2, i, f'{pf:.0f}%', ha='center', va='center', 
                           fontsize=9, color=COLOR_BLANCO, weight='bold')
            if pnf > 0:
                ax_pct.text(pf + pnf/2, i, f'{pnf:.0f}%', ha='center', va='center',
                           fontsize=9, color=COLOR_BLANCO, weight='bold')
    else:
        ax_pct.text(0.5, 0.5, "No hi ha dades suficients", transform=ax_pct.transAxes,
                   ha='center', va='center', fontsize=10, color=COLOR_GRIS)
    
    plt.subplots_adjust(left=0.1, right=0.95, top=0.88, bottom=0.1)
    pdf.savefig(fig)
    plt.close(fig)

# ============================================================================
# 9. COMPARATIVA CON TENDENCIAS (IDA/VUELTA o PARTIDO A vs B)
# ============================================================================

def obtener_tendencias_comparativa_v2(conn, partido1_id, partido2_id):
    """
    Compara estadísticas clave entre dos partidos y calcula tendencias
    
    Returns:
        DataFrame con: metrica, valor_p1, valor_p2, variacion, tendencia
    """
    
    acciones_analizar = {
        "Atac": "atacar",
        "Recepció": "recepción",
        "Saque": "saque",
        "Bloqueig": "bloqueo"
    }
    
    resultados = []
    
    for nombre_cat, nombre_bd in acciones_analizar.items():
        # Definir reglas de eficacia y eficiencia
        if nombre_bd == "saque":
            efic_regla = "marca IN ('#','/','+')"
            eficien_regla = "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"
        elif nombre_bd == "bloqueo":
            efic_regla = "marca IN ('#','+')"
            eficien_regla = "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca IN ('/','=')))"
        else:
            efic_regla = "marca IN ('#','+')"
            eficien_regla = "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"
        
        for partido_id, sufijo in [(partido1_id, 'p1'), (partido2_id, 'p2')]:
            query = text(f"""
            SELECT 
                ROUND((COUNT(*) FILTER (WHERE {efic_regla})::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficacia,
                ROUND(({eficien_regla}::decimal / NULLIF(COUNT(*),0))*100, 1) AS eficiencia
            FROM acciones_new
            WHERE partido_id = :pid AND tipo_accion = '{nombre_bd}'
            """)
            
            resultado = conn.execute(query, {"pid": partido_id}).fetchone()
            
            if sufijo == 'p1':
                efic_p1, eficien_p1 = resultado[0] or 0, resultado[1] or 0
            else:
                efic_p2, eficien_p2 = resultado[0] or 0, resultado[1] or 0
        
        # Calcular variaciones y tendencias
        var_efic = efic_p2 - efic_p1
        var_eficien = eficien_p2 - eficien_p1
        
        # Determinar tendencia (mejora, igual, empeora)
        def calc_tendencia(var):
            if var > 5:
                return "[+] Millora"
            elif var < -5:
                return "[-] Empitjora"
            else:
                return "[=] Similar"
        
        resultados.append({
            'metrica': f"{nombre_cat} - Eficàcia",
            'partit_1': efic_p1,
            'partit_2': efic_p2,
            'variacio': var_efic,
            'tendencia': calc_tendencia(var_efic)
        })
        
        resultados.append({
            'metrica': f"{nombre_cat} - Eficiència",
            'partit_1': eficien_p1,
            'partit_2': eficien_p2,
            'variacio': var_eficien,
            'tendencia': calc_tendencia(var_eficien)
        })
    
    return pd.DataFrame(resultados)

def pagina_tendencias_comparativa_v2(pdf, conn, partido1_id, partido2_id, rival1, rival2):
    """
    Genera página final de comparativa con tendencias visuales
    
    Args:
        pdf: objeto PdfPages
        conn: conexión BD
        partido1_id, partido2_id: IDs de partidos
        rival1, rival2: nombres de rivales
    """
    df = obtener_tendencias_comparativa_v2(conn, partido1_id, partido2_id)
    
    fig = plt.figure(figsize=A4_H)
    ax = fig.add_subplot(111)
    ax.axis("off")
    
    # Título
    fig.text(0.02, 0.98, "ANALISI DE TENDENCIES", fontsize=14, 
            color=COLOR_ROJO, fontweight='bold', verticalalignment='top')
    fig.text(0.02, 0.95, f"Evolucio del rendiment entre partits", fontsize=11, 
            color=COLOR_NEGRO, verticalalignment='top')
    fig.text(0.02, 0.93, '─' * 40, fontsize=10, color=COLOR_ROJO, 
            verticalalignment='top')
    
    # Subtítulos de partidos
    fig.text(0.25, 0.88, f"PARTIT 1: {rival1.upper()}", fontsize=11, 
            ha='center', color=COLOR_NEGRO, fontweight='bold')
    fig.text(0.75, 0.88, f"PARTIT 2: {rival2.upper()}", fontsize=11, 
            ha='center', color=COLOR_NEGRO, fontweight='bold')
    
    # Tabla con tendencias
    df_display = df.copy()
    df_display['partit_1'] = df_display['partit_1'].apply(lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else str(x))
    df_display['partit_2'] = df_display['partit_2'].apply(lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else str(x))
    df_display['variacio'] = df_display['variacio'].apply(lambda x: f"+{x:.1f}%" if x > 0 else f"{x:.1f}%")
    
    df_display.columns = ['Mètrica', 'Partit 1', 'Partit 2', 'Variació', 'Tendència']
    
    tabla = ax.table(cellText=df_display.values, colLabels=df_display.columns,
                     cellLoc="center", loc="center", bbox=[0.05, 0.1, 0.9, 0.7])
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(10)
    
    # Header
    for c in range(len(df_display.columns)):
        tabla[(0, c)].set_facecolor(COLOR_ROJO)
        tabla[(0, c)].set_text_props(color=COLOR_BLANCO, weight="bold")
    
    # Colorear filas según tendencia
    for row_idx in range(1, len(df) + 1):
        tendencia = df.iloc[row_idx - 1]['tendencia']
        variacion = df.iloc[row_idx - 1]['variacio']
        
        # Color de fondo según tendencia
        if "[+]" in tendencia:
            color_fondo = "#E8F5E9"  # Verde claro
            tabla[(row_idx, 4)].set_facecolor(COLOR_VERDE)
            tabla[(row_idx, 4)].set_text_props(color=COLOR_BLANCO, weight="bold")
        elif "[-]" in tendencia:
            color_fondo = "#FFEBEE"  # Rojo claro
            tabla[(row_idx, 4)].set_facecolor(COLOR_ROJO)
            tabla[(row_idx, 4)].set_text_props(color=COLOR_BLANCO, weight="bold")
        else:
            color_fondo = COLOR_GRIS
            tabla[(row_idx, 4)].set_facecolor(COLOR_AMARILLO)
            tabla[(row_idx, 4)].set_text_props(weight="bold")
        
        # Aplicar color de fondo a toda la fila
        for col in range(4):  # Excluir columna de tendencia
            tabla[(row_idx, col)].set_facecolor(color_fondo)
        
        # Colorear columna de variación
        if variacion > 0:
            tabla[(row_idx, 3)].set_text_props(color=COLOR_VERDE, weight="bold")
        elif variacion < 0:
            tabla[(row_idx, 3)].set_text_props(color=COLOR_ROJO, weight="bold")
    
    # Leyenda
    fig.text(0.5, 0.05, 
            "[+] Millora significativa (+5%)  |  [=] Rendiment similar (+-5%)  |  [-] Empitjorament (-5%)",
            ha='center', fontsize=9, color=COLOR_GRIS, style='italic')
    
    plt.subplots_adjust(left=0.05, right=0.95, top=0.9, bottom=0.1)
    pdf.savefig(fig)
    plt.close(fig)
