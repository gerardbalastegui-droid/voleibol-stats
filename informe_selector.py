# -*- coding: utf-8 -*-
"""
informe_selector.py
Generador selectiu d'informes de partit en PDF, a memòria (per descarregar).

Reutilitza els blocs ja existents del generador de PDF. Només afegeix la
capa de "tria de blocs" i la sortida a io.BytesIO per a st.download_button.

IMPORTANT: config_v2 fixa el backend de matplotlib a "Agg", per això
s'importa abans que res que faci servir pyplot.
"""
import io
import pandas as pd
from sqlalchemy import text

# config_v2 primer: fixa engine (DATABASE_URL) i backend Agg
from config_v2 import engine, RENOMBRAR_COLUMNAS, TABLA_ACCIONES
from utils_v2 import separar_mayusculas, obtener_info_partido

from visualizaciones import portada, tabla_y_grafica_combinada, tabla_estilizada
from informe_partido_v2 import estadisticas_equipo_v2
from analisis_avanzado_v2 import (
    pagina_sideout_contraataque_v2,
    pagina_ataque_por_rotacion_v2,
    pagina_carga_colocador_v2,
    pagina_rankings_positivos_v2,
)
from analisis_errores_v2 import pagina_analisis_errores_v2
from informe_partido import pagina_distribucion_ataque_unificada

from matplotlib.backends.backend_pdf import PdfPages


# Claus dels blocs disponibles (ordre = ordre al PDF).
# La portada sempre s'inclou; no és un bloc triable.
BLOCS_PARTIT = [
    "eficacia_equip",        # estadisticas_equipo_v2
    "detall_jugador",        # tabla_y_grafica_combinada (una pàgina per acció)
    "sideout",               # pagina_sideout_contraataque_v2
    "rotacions",             # pagina_ataque_por_rotacion_v2
    "distribucio",           # pagina_carga_colocador_v2
    "distribucio_recepcio",  # pagina_distribucion_ataque_unificada
    "errors",                # pagina_analisis_errores_v2
    "rankings",              # pagina_rankings_positivos_v2
    "valor_jugadors",        # tabla_estilizada (df_todos)
]

# Regles d'eficàcia/eficiència per acció (mateixes que a l'informe original)
_REGLAS = {
    "atacar":    ("marca IN ('#','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"),
    "recepción": ("marca IN ('#','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"),
    "saque":     ("marca IN ('#','/','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca = '='))"),
    "bloqueo":   ("marca IN ('#','+')", "(COUNT(*) FILTER (WHERE marca = '#') - COUNT(*) FILTER (WHERE marca IN ('/','=')))"),
}
_NOMBRES_CAT = {"atacar": "Atac", "recepción": "Recepció", "saque": "Saque", "bloqueo": "Bloqueig"}


def generar_pdf_partido(partido_id, bloques):
    """
    Genera el PDF d'un partit amb només els blocs seleccionats.

    Args:
        partido_id: ID a partidos_new.
        bloques: llista/set de claus de BLOCS_PARTIT.

    Returns:
        io.BytesIO amb el PDF (posicionat a l'inici), o None si no hi ha partit.
    """
    info = obtener_info_partido(partido_id)
    if not info:
        return None

    bloques = set(bloques)

    rival = separar_mayusculas(info['rival'])
    tipo = "LOCAL" if info['local'] else "VISITANT"
    titulo_contexto = f"VS {rival.upper()} ({tipo})"
    equipo_completo = info['equipo_completo']
    temporada = info['temporada']
    fase = info['fase'] if info['fase'] else "N/A"

    buffer = io.BytesIO()

    with engine.connect() as conn:
        # --- Dades precomputades només per als blocs que ho necessiten ---
        dfs = {}
        if "detall_jugador" in bloques:
            for acc, (efic, eficien) in _REGLAS.items():
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
                dfs[_NOMBRES_CAT[acc]] = pd.read_sql(
                    q, conn, params={"pid": partido_id, "tipo_acc": acc}
                ).rename(columns=RENOMBRAR_COLUMNAS)

        dist = None
        if "distribucio_recepcio" in bloques:
            dist = pd.read_sql(text(f"""
                SELECT LOWER(zona_colocador) AS rot, LOWER(zona_jugador) AS zona,
                       COUNT(*) AS total, COUNT(*) FILTER (WHERE marca = '#') AS puntos
                FROM {TABLA_ACCIONES}
                WHERE partido_id = :pid AND tipo_accion = 'atacar'
                  AND zona_colocador IS NOT NULL AND zona_jugador IS NOT NULL
                GROUP BY LOWER(zona_colocador), LOWER(zona_jugador)
            """), conn, params={"pid": partido_id})

        df_todos = None
        if "valor_jugadors" in bloques:
            df_todos = pd.read_sql(text(f"""
                SELECT j.apellido AS jugador,
                    (
                        COUNT(*) FILTER (WHERE a.tipo_accion = 'atacar'    AND a.marca = '#')
                      + COUNT(*) FILTER (WHERE a.tipo_accion = 'saque'     AND a.marca = '#')
                      + COUNT(*) FILTER (WHERE a.tipo_accion = 'bloqueo'   AND a.marca = '#')
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

        # --- Muntatge del PDF ---
        with PdfPages(buffer) as pdf:
            # Portada (sempre)
            titulo_portada = f"INFORME DEL PARTIT\n{equipo_completo}"
            subtitulo_portada = f"VS {rival.upper()} ({tipo})\n{temporada} - {fase}"
            portada(pdf, titulo_portada, subtitulo_portada)

            if "eficacia_equip" in bloques:
                estadisticas_equipo_v2(pdf, conn, partido_id)

            if "detall_jugador" in bloques:
                for acc, df in dfs.items():
                    tabla_y_grafica_combinada(pdf, df, acc)

            if "sideout" in bloques:
                pagina_sideout_contraataque_v2(pdf, conn, partido_id, titulo_contexto)

            if "rotacions" in bloques:
                pagina_ataque_por_rotacion_v2(pdf, conn, partido_id, titulo_contexto)

            if "distribucio" in bloques:
                pagina_carga_colocador_v2(pdf, conn, partido_id, titulo_contexto)

            if "distribucio_recepcio" in bloques and dist is not None:
                pagina_distribucion_ataque_unificada(pdf, dist, rival, info['local'])

            if "errors" in bloques:
                pagina_analisis_errores_v2(pdf, conn, partido_id, titulo_contexto)

            if "rankings" in bloques:
                pagina_rankings_positivos_v2(pdf, conn, partido_id, titulo_contexto)

            if "valor_jugadors" in bloques and df_todos is not None:
                tabla_estilizada(pdf, df_todos, "Valoració dels jugadors")

    buffer.seek(0)
    return buffer
