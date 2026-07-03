# -*- coding: utf-8 -*-
"""
informe_jugador.py
Generador selectiu d'informes de JUGADOR en PDF, a memòria (per descarregar).

Mateixa filosofia que informe_selector.py:
- Reescriu les queries aquí, amb l'engine de config_v2 (Railway).
- Reutilitza les funcions de dibuix de visualizaciones.py.
- config_v2 s'importa primer perquè fixa el backend Agg de matplotlib.

Àmbit: pot ser un sol partit o tota la temporada (la pàgina passa la
llista de partido_ids ja filtrada per fase).
"""
import io
import pandas as pd
from sqlalchemy import text

# config_v2 primer: engine (DATABASE_URL) + backend Agg
from config_v2 import engine, TABLA_ACCIONES

from visualizaciones import portada, tabla_y_grafica_combinada

from matplotlib.backends.backend_pdf import PdfPages


# Claus dels blocs disponibles (ordre = ordre al PDF).
# La portada sempre s'inclou; no és un bloc triable.
# (De moment només "metriques"; anirem afegint la resta un a un.)
BLOCS_JUGADOR = [
    "metriques",
    "radar",
]

_NOMBRES_CAT = {"atacar": "Atac", "recepción": "Recepció", "saque": "Saque", "bloqueo": "Bloqueig"}
_ORDEN = ["atacar", "recepción", "saque", "bloqueo"]


def _info_jugador(conn, jugador_id):
    """Retorna dict amb dades bàsiques del jugador, o None."""
    r = conn.execute(text("""
        SELECT apellido, nombre, dorsal, posicion
        FROM jugadores WHERE id = :jid
    """), {"jid": jugador_id}).fetchone()
    if not r:
        return None
    apellido, nombre, dorsal, posicion = r
    nombre_completo = f"{nombre} {apellido}" if nombre else apellido
    return {
        "nombre_completo": nombre_completo,
        "dorsal": dorsal,
        "posicion": posicion,
    }


def _bloc_metriques(pdf, conn, partido_ids_str, jugador_id):
    """Taula + gràfic d'eficàcia/eficiència per acció (atac, recepció, saque, bloqueig)."""
    df = pd.read_sql(text(f"""
        SELECT tipo_accion,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE marca = '#') AS puntos,
               COUNT(*) FILTER (WHERE marca = '+') AS positivos,
               COUNT(*) FILTER (WHERE marca = '=') AS errores
        FROM {TABLA_ACCIONES}
        WHERE partido_id IN ({partido_ids_str})
          AND jugador_id = :jid
          AND tipo_accion IN ('atacar', 'recepción', 'saque', 'bloqueo')
        GROUP BY tipo_accion
    """), conn, params={"jid": jugador_id})

    if df.empty:
        return  # sense dades per aquest jugador

    df['eficacia'] = ((df['puntos'] + df['positivos']) / df['total'] * 100).round(1)
    df['eficiencia'] = ((df['puntos'] - df['errores']) / df['total'] * 100).round(1)

    filas = []
    for acc in _ORDEN:
        r = df[df['tipo_accion'] == acc]
        if r.empty:
            continue
        row = r.iloc[0]
        filas.append([
            _NOMBRES_CAT[acc],
            int(row['total']),
            f"{row['eficacia']}%",
            f"{row['eficiencia']}%",
        ])

    if not filas:
        return

    df_disp = pd.DataFrame(filas, columns=["Acció", "Total", "Eficàcia (%)", "Eficiència (%)"])
    tabla_y_grafica_combinada(pdf, df_disp, "Estadístiques principals", columna_x="Acció")

def _bloc_radar(pdf, conn, partido_ids_str, jugador_id):
    """Radar de perfil: eficàcia per acció (atac, recepció, saque, bloqueig)."""
    import matplotlib.pyplot as plt
    import numpy as np
    from config_v2 import COLOR_ROJO, COLOR_NEGRO, A4_H

    df = pd.read_sql(text(f"""
        SELECT tipo_accion,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE marca = '#') AS puntos,
               COUNT(*) FILTER (WHERE marca = '+') AS positivos
        FROM {TABLA_ACCIONES}
        WHERE partido_id IN ({partido_ids_str})
          AND jugador_id = :jid
          AND tipo_accion IN ('atacar', 'recepción', 'saque', 'bloqueo')
        GROUP BY tipo_accion
    """), conn, params={"jid": jugador_id})

    if df.empty:
        return

    df['eficacia'] = ((df['puntos'] + df['positivos']) / df['total'] * 100).round(1)

    # Ordenar i muntar categories/valors
    categorias, valores = [], []
    for acc in _ORDEN:
        r = df[df['tipo_accion'] == acc]
        if not r.empty:
            categorias.append(_NOMBRES_CAT[acc])
            valores.append(float(r.iloc[0]['eficacia']))

    if len(categorias) < 3:
        return  # un radar amb menys de 3 eixos no té sentit

    # Tancar el polígon
    angulos = np.linspace(0, 2 * np.pi, len(categorias), endpoint=False).tolist()
    valores_c = valores + valores[:1]
    angulos_c = angulos + angulos[:1]

    fig = plt.figure(figsize=A4_H)
    # Títol
    fig.text(0.02, 0.98, "PERFIL DEL JUGADOR", fontsize=14,
             color=COLOR_ROJO, fontweight='bold', verticalalignment='top')
    fig.text(0.02, 0.955, "Eficàcia per acció (%)", fontsize=11,
             color=COLOR_NEGRO, verticalalignment='top')
    fig.text(0.02, 0.935, '─' * 30, fontsize=10, color=COLOR_ROJO,
             verticalalignment='top')

    ax = fig.add_subplot(111, polar=True)
    ax.set_position([0.15, 0.08, 0.7, 0.78])  # deixar espai per al títol

    ax.plot(angulos_c, valores_c, color=COLOR_ROJO, linewidth=2)
    ax.fill(angulos_c, valores_c, color=COLOR_ROJO, alpha=0.25)

    ax.set_xticks(angulos)
    ax.set_xticklabels(categorias, fontsize=12, fontweight='bold')
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8, color="#888")
    ax.grid(color="#CCCCCC", linestyle="--", linewidth=0.6)

    # Valors a cada vèrtex
    for ang, val in zip(angulos, valores):
        ax.text(ang, val + 6, f"{val:.0f}%", ha='center', va='center',
                fontsize=10, color=COLOR_NEGRO, fontweight='bold')

    pdf.savefig(fig)
    plt.close(fig)


def generar_pdf_jugador(jugador_id, partido_ids, contexto_txt, bloques):
    """
    Genera el PDF d'un jugador amb només els blocs seleccionats.

    Args:
        jugador_id: ID a jugadores.
        partido_ids: llista d'IDs de partits (ja filtrats per fase per la pàgina).
        contexto_txt: text de context per a la portada (ex: "vs Farners (V)"
                      o "Tota la temporada (19 partits)").
        bloques: llista/set de claus de BLOCS_JUGADOR.

    Returns:
        io.BytesIO amb el PDF (posicionat a l'inici), o None si no hi ha dades.
    """
    if isinstance(partido_ids, int):
        partido_ids = [partido_ids]
    if not partido_ids:
        return None

    bloques = set(bloques)
    ids_str = ','.join(map(str, partido_ids))
    buffer = io.BytesIO()

    with engine.connect() as conn:
        info = _info_jugador(conn, jugador_id)
        if not info:
            return None

        dorsal = info['dorsal'] if info['dorsal'] is not None else "-"
        posicion = info['posicion'] if info['posicion'] else "-"

        with PdfPages(buffer) as pdf:
            # Portada (sempre)
            titulo = f"INFORME DE JUGADOR\n{info['nombre_completo']}"
            subtitulo = f"#{dorsal} · {posicion}\n{contexto_txt}"
            portada(pdf, titulo, subtitulo)

            if "metriques" in bloques:
                _bloc_metriques(pdf, conn, ids_str, jugador_id)
            if "radar" in bloques:
                _bloc_radar(pdf, conn, ids_str, jugador_id)

    buffer.seek(0)
    return buffer
