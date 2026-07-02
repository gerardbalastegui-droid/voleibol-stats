import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.image as mpimg
from config_v2 import COLOR_ROJO, COLOR_BLANCO, COLOR_NEGRO, COLOR_AMARILLO, COLOR_GRIS, A4_H

# -----------------------------
# FUNCIONES DE UTILIDAD
# -----------------------------
def limpiar_porcentaje(serie):
    """
    Convierte una serie de porcentajes a float, manejando None, 'None', strings y NaN
    
    Args:
        serie: Serie de pandas con valores que pueden ser: números, strings con %, None, 'None', NaN
    
    Returns:
        Lista de floats
    """
    def convertir(val):
        # Verificar None/vacío PRIMERO
        if val is None or pd.isna(val) or val == '':
            return 0.0
        
        # Convertir todo a string
        val_str = str(val)
        
        # Verificar si el string es 'None' o 'nan'
        if val_str == 'None' or val_str == 'nan':
            return 0.0
        
        # Intentar convertir con try-except (nunca falla)
        try:
            # Quitar '%' si existe
            val_limpio = val_str.rstrip('%').strip()
            return float(val_limpio)
        except (ValueError, AttributeError):
            return 0.0
    
    return [convertir(x) for x in serie]

# -----------------------------
# PORTADA
# -----------------------------
def portada(pdf, titulo, subtitulo=""):
    fig, ax = plt.subplots(figsize=A4_H)
    ax.axis("off")

    # Título en esquina superior izquierda
    ax.text(0.02, 0.98, titulo, fontsize=16, color=COLOR_ROJO, 
            fontweight='bold', transform=ax.transAxes, verticalalignment='top')
    ax.text(0.02, 0.96, '─' * 35, fontsize=10, color=COLOR_ROJO, 
            transform=ax.transAxes, verticalalignment='top')

    if subtitulo:
        ax.text(0.05, 0.72, subtitulo,
                fontsize=18, color=COLOR_NEGRO)

    try:
        logo_path = os.path.join(os.path.dirname(__file__), "recursos", "voleigironalogo.png")
        logo = mpimg.imread(logo_path)
        imagebox = OffsetImage(logo, zoom=0.18)
        ab = AnnotationBbox(imagebox, (0.92, 0.08), frameon=False)
        ax.add_artist(ab)
    except Exception:
        pass  # sense logo si no es troba el fitxer

    pdf.savefig(fig)
    plt.close(fig)

# -----------------------------
# TABLAS
# -----------------------------
def tabla_estilizada(pdf, df, titulo):
    fig, ax = plt.subplots(figsize=A4_H)
    ax.axis("off")
    # Título en esquina superior izquierda
    ax.text(0.02, 0.98, titulo.upper(), fontsize=14, color=COLOR_ROJO, 
            fontweight='bold', style='italic', transform=ax.transAxes, 
            verticalalignment='top')
    ax.text(0.02, 0.95, '─' * 30, transform=ax.transAxes,
           fontsize=10, color=COLOR_ROJO, verticalalignment='top')

    tabla = ax.table(cellText=df.values, colLabels=df.columns,
                     cellLoc="center", loc="center")

    tabla.auto_set_font_size(False)
    tabla.set_fontsize(11)
    tabla.scale(1, 1.5)
    
    # Ajustar ancho de columnas para Eficàcia y Eficiència
    for i, col in enumerate(df.columns):
        if 'Eficàcia' in col or 'Eficiència' in col or 'Eficacia' in col or 'Eficiencia' in col:
            for row in range(len(df) + 1):
                tabla[(row, i)].set_width(0.15)  # Más ancho para estas columnas

    for (r, c), cell in tabla.get_celld().items():
        if r == 0:
            cell.set_facecolor(COLOR_ROJO)
            cell.set_text_props(color=COLOR_BLANCO, weight="bold")
        else:
            cell.set_facecolor(COLOR_GRIS)

    plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
    pdf.savefig(fig)
    plt.close(fig)

def tabla_y_grafica_combinada(pdf, df, titulo, columna_x="Jugador"):
    """Crea una página con tabla arriba y gráfica abajo"""
    fig = plt.figure(figsize=A4_H)
    
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.2], hspace=0.35)
    
    # Título en esquina superior izquierda
    fig.text(0.02, 0.98, titulo.upper(), fontsize=14, color=COLOR_ROJO, 
            fontweight='bold', style='italic', verticalalignment='top')
    fig.text(0.02, 0.96, '─' * 30, fontsize=10, color=COLOR_ROJO, 
            verticalalignment='top')
    
    # PARTE SUPERIOR: TABLA
    ax_tabla = fig.add_subplot(gs[0])
    ax_tabla.axis("off")
    
    tabla = ax_tabla.table(cellText=df.values, colLabels=df.columns,
                           cellLoc="center", loc="center")
    
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(10)
    tabla.scale(1, 1.3)
    
    # Ajustar ancho de columnas para Eficàcia y Eficiència
    for i, col in enumerate(df.columns):
        if 'Eficàcia' in col or 'Eficiència' in col or 'Eficacia' in col or 'Eficiencia' in col:
            for row in range(len(df) + 1):
                tabla[(row, i)].set_width(0.15)  # Más ancho para estas columnas
    
    for (r, c), cell in tabla.get_celld().items():
        if r == 0:
            cell.set_facecolor(COLOR_ROJO)
            cell.set_text_props(color=COLOR_BLANCO, weight="bold")
        else:
            cell.set_facecolor(COLOR_GRIS)
    
    # PARTE INFERIOR: GRÁFICA
    ax_grafica = fig.add_subplot(gs[1])
    
    etiquetas = df[columna_x].tolist()
    
    # Usar función de limpieza robusta
    if "Eficàcia (%)" in df.columns:
        eficacia = limpiar_porcentaje(df["Eficàcia (%)"])
    elif "Eficacia (%)" in df.columns:
        eficacia = limpiar_porcentaje(df["Eficacia (%)"])
    else:
        eficacia = [0] * len(etiquetas)
    
    if "Eficiència (%)" in df.columns:
        eficiencia = limpiar_porcentaje(df["Eficiència (%)"])
    elif "Eficiencia (%)" in df.columns:
        eficiencia = limpiar_porcentaje(df["Eficiencia (%)"])
    else:
        eficiencia = [0] * len(etiquetas)
    
    n = len(etiquetas)
    x = range(n)
    bar_width = min(0.6, 1.2 / max(n, 1))
    
    ax_grafica.bar(
        [i - bar_width/2 for i in x],
        eficacia,
        width=bar_width,
        color=COLOR_ROJO,
        label="Eficàcia (%)"
    )
    
    ax_grafica.bar(
        [i + bar_width/2 for i in x],
        eficiencia,
        width=bar_width,
        color=COLOR_NEGRO,
        label="Eficiència (%)"
    )
    
    ax_grafica.set_xticks(list(x))
    ax_grafica.set_xticklabels(etiquetas, rotation=45, ha="right")
    ax_grafica.set_ylabel("%")
    ax_grafica.axhline(0, color=COLOR_AMARILLO, linewidth=1)
    ax_grafica.legend()
    ax_grafica.grid(axis="y", linestyle="--", alpha=0.4)
    
    plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
    pdf.savefig(fig)
    plt.close(fig)

# -----------------------------
# GRÁFICAS
# -----------------------------
def pagina_podio(pdf, df_top):
    fig, ax = plt.subplots(figsize=A4_H)
    ax.axis("off")

    # Título en esquina superior izquierda
    fig.text(0.02, 0.98, "TOP 3 JUGADORS", fontsize=14, color=COLOR_ROJO, 
            fontweight='bold', style='italic', verticalalignment='top')
    fig.text(0.02, 0.96, '─' * 30, fontsize=10, color=COLOR_ROJO, 
            verticalalignment='top')

    posiciones = [0, -1.5, 1.5]
    alturas = [3, 2, 1]
    colores = ["#D4AF37", "#C0C0C0", "#CD7F32"]

    for i, (_, row) in enumerate(df_top.iterrows()):
        x = posiciones[i]
        h = alturas[i]

        ax.bar(x, h, width=0.9, color=colores[i])

        ax.text(
            x, h + 0.15,
            row["jugador"].upper(),
            ha="center", va="bottom",
            fontsize=14, fontweight="bold"
        )

        ax.text(
            x, h / 2,
            f"{row['valor']}",
            ha="center", va="center",
            fontsize=18, color=COLOR_NEGRO, fontweight="bold"
        )

    ax.set_xlim(-3, 3)
    ax.set_ylim(0, 3.8)

    plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
    pdf.savefig(fig)
    plt.close(fig)
