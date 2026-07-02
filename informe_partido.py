import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from sqlalchemy import text
from config_v2 import (
    engine, A4_H, ZONAS_TABLA, ORDEN_ROTACIONES, RENOMBRAR_COLUMNAS,
    COLOR_ROJO, COLOR_AMARILLO
)
from utils_v2 import separar_mayusculas
from visualizaciones import portada, tabla_y_grafica_combinada, pagina_podio, tabla_estilizada

def pagina_distribucion_ataque_unificada(pdf, dist, rival, local):
    """Genera página de distribución con tabla unificada estilo Excel mejorado"""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from config_v2 import COLOR_ROJO, COLOR_BLANCO, COLOR_NEGRO, A4_H
    
    tipo_partido = "LOCAL" if local else "VISITANT"
    
    fig, ax = plt.subplots(figsize=A4_H)
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 13)
    ax.axis('off')
    
    # Título en esquina superior izquierda
    fig.text(0.02, 0.98, "DISTRIBUCIÓ D'ATAC PER ROTACIÓ", fontsize=14, 
            color=COLOR_ROJO, fontweight='bold', verticalalignment='top')
    fig.text(0.02, 0.96, '─' * 30, fontsize=10, color=COLOR_ROJO, 
            verticalalignment='top')
    
    # Función auxiliar para obtener datos de una zona
    def obtener_dato_zona(rot, zona):
        df_r = dist[dist["rot"] == rot]
        total = df_r["total"].sum()
        if total == 0:
            return "0%"
        
        info_zona = df_r[df_r["zona"] == zona]
        if info_zona.empty:
            return "0%"
        
        pct = (info_zona.iloc[0]['total'] / total * 100)
        pts = info_zona.iloc[0]['puntos']
        if pts > 0:
            return f"{pct:.0f}% ({pts})"
        return f"{pct:.0f}%"
    
    # Configuración
    cell_width = 2.2
    cell_height = 0.85
    spacing = 0.8  # Espacio entre tablas
    start_x = 1.5  # Más a la izquierda para evitar que se corte
    start_y = 7.0
    
    # Calcular ancho total del título: 3 tablas + 2 espacios
    title_width = (cell_width * 2) * 3 + spacing * 2
    
    # TÍTULO PRINCIPAL - mismo ancho que las 3 tablas + espacios
    rect = Rectangle((start_x, start_y + 4.5), title_width, 1.0, 
                     linewidth=1, edgecolor=COLOR_NEGRO, facecolor=COLOR_BLANCO)
    ax.add_patch(rect)
    ax.text(start_x + title_width/2, start_y + 5.0, f"VS {rival.upper()} ({tipo_partido})", 
           ha='center', va='center', fontsize=16, color=COLOR_ROJO, weight='bold')
    
    # ROTACIONES SUPERIORES (P4, P3, P2)
    rotaciones_sup = ["p4", "p3", "p2"]
    nombres_rot_sup = ["P4", "P3", "P2"]
    zonas_filas = [["p5", "p4"], ["p6", "p3"], ["p1", "p2"]]
    
    y_start = start_y + 3.2
    
    # Dibujar cada rotación superior
    for rot_idx, (rot, nombre) in enumerate(zip(rotaciones_sup, nombres_rot_sup)):
        x_offset = start_x + (rot_idx * (cell_width * 2 + spacing))
        y_current = y_start
        
        # 3 filas de datos (cada fila tiene 2 columnas)
        for fila_zonas in zonas_filas:
            # Columna izquierda
            dato_izq = obtener_dato_zona(rot, fila_zonas[0])
            rect = Rectangle((x_offset, y_current), cell_width, cell_height,
                           linewidth=1, edgecolor=COLOR_NEGRO, facecolor=COLOR_BLANCO)
            ax.add_patch(rect)
            ax.text(x_offset + cell_width/2, y_current + cell_height/2, dato_izq,
                   ha='center', va='center', fontsize=9, weight='normal')
            
            # Columna derecha
            dato_der = obtener_dato_zona(rot, fila_zonas[1])
            rect = Rectangle((x_offset + cell_width, y_current), cell_width, cell_height,
                           linewidth=1, edgecolor=COLOR_NEGRO, facecolor=COLOR_BLANCO)
            ax.add_patch(rect)
            ax.text(x_offset + cell_width + cell_width/2, y_current + cell_height/2, dato_der,
                   ha='center', va='center', fontsize=9, weight='normal')
            
            y_current -= cell_height
        
        # Nombre de la rotación debajo - muy pegado a la tabla
        ax.text(x_offset + cell_width, y_current - 0.05, nombre,
               ha='center', va='center', fontsize=13, color=COLOR_ROJO, weight='bold')
    
    # ROTACIONES INFERIORES (P5, P6, P1)
    rotaciones_inf = ["p5", "p6", "p1"]
    nombres_rot_inf = ["P5", "P6", "P1"]
    
    y_start = start_y - 1.0  # Más separado de las superiores
    
    # Dibujar cada rotación inferior
    for rot_idx, (rot, nombre) in enumerate(zip(rotaciones_inf, nombres_rot_inf)):
        x_offset = start_x + (rot_idx * (cell_width * 2 + spacing))
        y_current = y_start
        
        # 3 filas de datos
        for fila_zonas in zonas_filas:
            # Columna izquierda
            dato_izq = obtener_dato_zona(rot, fila_zonas[0])
            rect = Rectangle((x_offset, y_current), cell_width, cell_height,
                           linewidth=1, edgecolor=COLOR_NEGRO, facecolor=COLOR_BLANCO)
            ax.add_patch(rect)
            ax.text(x_offset + cell_width/2, y_current + cell_height/2, dato_izq,
                   ha='center', va='center', fontsize=9, weight='normal')
            
            # Columna derecha
            dato_der = obtener_dato_zona(rot, fila_zonas[1])
            rect = Rectangle((x_offset + cell_width, y_current), cell_width, cell_height,
                           linewidth=1, edgecolor=COLOR_NEGRO, facecolor=COLOR_BLANCO)
            ax.add_patch(rect)
            ax.text(x_offset + cell_width + cell_width/2, y_current + cell_height/2, dato_der,
                   ha='center', va='center', fontsize=9, weight='normal')
            
            y_current -= cell_height
        
        # Nombre de la rotación debajo - muy pegado a la tabla
        ax.text(x_offset + cell_width, y_current - 0.05, nombre,
               ha='center', va='center', fontsize=13, color=COLOR_ROJO, weight='bold')
    
    plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)
    pdf.savefig(fig)
    plt.close(fig)

def estadisticas_equipo(pdf, conn, partido_id):
    """Genera una página con las estadísticas globales del equipo"""
    reglas = {
        "Atac": ("marca IN ('#','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"),
        "Recepció": ("marca IN ('#','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"),
        "Saque": ("marca IN ('#','/','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"),
        "Bloqueig": ("marca IN ('#','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca IN ('/','=')))"),
    }

    datos = []
    nombre_bd = {
        "Atac": "atacar",
        "Recepció": "recepción", 
        "Saque": "saque",
        "Bloqueig": "bloqueo"
    }
    
    for acc, (efic, eficien) in reglas.items():
        resultado = conn.execute(text(f"""
            SELECT 
                COUNT(*) AS total,
                ROUND((COUNT(*) FILTER (WHERE {efic})::decimal / NULLIF(COUNT(*),0))*100,2) AS eficacia_pct,
                ROUND(({eficien}::decimal / NULLIF(COUNT(*),0))*100,2) AS eficiencia_pct
            FROM acciones
            WHERE partido_id = :pid AND tipo_accion = '{nombre_bd[acc]}'
        """), {"pid": partido_id}).fetchone()
        
        datos.append([acc, resultado[0], f"{resultado[1]}%", f"{resultado[2]}%"])
    
    df_equipo = pd.DataFrame(datos, columns=["Acció", "Total", "Eficàcia (%)", "Eficiència (%)"])
    tabla_y_grafica_combinada(pdf, df_equipo, "Estadístiques de l'equip", columna_x="Acció")

def generar_informe_partido(partido_id, nombre_pdf):
    """Genera el informe completo de un partido"""
    with engine.connect() as conn:
        partido = conn.execute(
            text("SELECT rival, local FROM partidos WHERE id = :pid"),
            {"pid": partido_id}
        ).fetchone()

        rival, local = partido
        rival = separar_mayusculas(rival)
        dfs = {}

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

        for acc, (efic, eficien) in reglas.items():
            q = f"""
            SELECT jugador_apellido,
                   COUNT(*) AS total,
                   ROUND((COUNT(*) FILTER (WHERE {efic})::decimal / NULLIF(COUNT(*),0))*100,2) AS eficacia_pct,
                   ROUND(({eficien}::decimal / NULLIF(COUNT(*),0))*100,2) AS eficiencia_pct
            FROM acciones
            WHERE partido_id = %(pid)s AND tipo_accion = '{acc}'
            GROUP BY jugador_apellido
            """
            dfs[nombres_catalan[acc]] = pd.read_sql(q, conn, params={"pid": partido_id}).rename(columns=RENOMBRAR_COLUMNAS)

        dist = pd.read_sql("""
            SELECT
                LOWER(zona_colocador) AS rot,
                LOWER(zona_jugador) AS zona,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE marca = '#') AS puntos
            FROM acciones
            WHERE partido_id = %(pid)s
              AND tipo_accion = 'atacar'
              AND zona_colocador IS NOT NULL
              AND zona_jugador IS NOT NULL
            GROUP BY LOWER(zona_colocador), LOWER(zona_jugador)
        """, conn, params={"pid": partido_id})

        df_top = pd.read_sql("""
            SELECT
                jugador_apellido AS jugador,
                (
                    COUNT(*) FILTER (WHERE tipo_accion = 'atacar'   AND marca = '#')
                  + COUNT(*) FILTER (WHERE tipo_accion = 'saque'    AND marca = '#')
                  + COUNT(*) FILTER (WHERE tipo_accion = 'bloqueo'  AND marca = '#')
                  - COUNT(*) FILTER (WHERE tipo_accion = 'recepción' AND marca = '=')
                  - COUNT(*) FILTER (WHERE tipo_accion = 'atacar'    AND marca = '=')
                  - COUNT(*) FILTER (WHERE tipo_accion = 'saque'     AND marca = '=')
                  - COUNT(*) FILTER (WHERE tipo_accion = 'bloqueo'   AND marca = '/')
                ) AS valor
            FROM acciones
            WHERE partido_id = %(pid)s
            GROUP BY jugador_apellido
            HAVING COUNT(*) FILTER (WHERE marca IN ('#','=','/')) > 0
            ORDER BY valor DESC
            LIMIT 3
        """, conn, params={"pid": partido_id})

        df_todos = pd.read_sql("""
            SELECT
                jugador_apellido AS jugador,
                (
                    COUNT(*) FILTER (WHERE tipo_accion = 'atacar'   AND marca = '#')
                  + COUNT(*) FILTER (WHERE tipo_accion = 'saque'    AND marca = '#')
                  + COUNT(*) FILTER (WHERE tipo_accion = 'bloqueo'  AND marca = '#')
                  - COUNT(*) FILTER (WHERE tipo_accion = 'recepción' AND marca = '=')
                  - COUNT(*) FILTER (WHERE tipo_accion = 'atacar'    AND marca = '=')
                  - COUNT(*) FILTER (WHERE tipo_accion = 'saque'     AND marca = '=')
                  - COUNT(*) FILTER (WHERE tipo_accion = 'bloqueo'   AND marca = '/')
                ) AS valor
            FROM acciones
            WHERE partido_id = %(pid)s
            GROUP BY jugador_apellido
            HAVING COUNT(*) FILTER (WHERE marca IN ('#','=','/')) > 0
            ORDER BY valor DESC
        """, conn, params={"pid": partido_id})

        with PdfPages(nombre_pdf) as pdf:
            portada(pdf, "INFORME DEL PARTIT", f"VS {rival.upper()}")
            
            estadisticas_equipo(pdf, conn, partido_id)

            for acc, df in dfs.items():
                tabla_y_grafica_combinada(pdf, df, acc)

            # Distribución de ataque
            pagina_distribucion_ataque_unificada(pdf, dist, rival, local)

            pagina_podio(pdf, df_top)
            tabla_estilizada(pdf, df_todos, "Valoració dels jugadors")

    print(f"\n✅ Informe de partido generado: {nombre_pdf}")
