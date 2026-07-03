# -*- coding: utf-8 -*-
"""
translations.py - Sistema de traduccions CA/DE per a Voleibol Stats.

Ús:
    from translations import t, IDIOMES, IDIOMA_PER_DEFECTE
    st.write(t("usuari"))                       # text simple
    st.success(t("benvingut").format("Marc"))   # text amb variable

Migració incremental: si una clau encara no existeix, t() retorna la
pròpia clau (no peta res), així es pot anar traduint per parts.
"""
import streamlit as st

# Idiomes disponibles (clau interna -> nom visible al selector)
IDIOMES = {"ca": "Català", "de": "Deutsch"}
IDIOMA_PER_DEFECTE = "ca"

TRANSLATIONS = {
    # ---------------------------------------------------------------
    # Selector d'idioma
    # ---------------------------------------------------------------
    "idioma": {"ca": "Idioma", "de": "Sprache"},

    # ---------------------------------------------------------------
    # Login / sessió
    # ---------------------------------------------------------------
    "iniciar_sessio": {"ca": "🔐 Iniciar sessió", "de": "🔐 Anmelden"},
    "login_titol": {"ca": "Inicia sessió per continuar", "de": "Zum Fortfahren anmelden"},
    "usuari": {"ca": "Usuari:", "de": "Benutzer:"},
    "contrasenya": {"ca": "Contrasenya:", "de": "Passwort:"},
    "entrar": {"ca": "Entrar", "de": "Anmelden"},
    "visitant": {"ca": "Visitant", "de": "Gast"},
    "tancar_sessio": {"ca": "🚪 Tancar sessió", "de": "🚪 Abmelden"},
    "benvingut": {"ca": "✅ Benvingut, {}!", "de": "✅ Willkommen, {}!"},
    "error_credencials": {
        "ca": "❌ Usuari o contrasenya incorrectes",
        "de": "❌ Benutzer oder Passwort falsch",
    },
    "avis_credencials": {
        "ca": "⚠️ Introdueix usuari i contrasenya",
        "de": "⚠️ Benutzer und Passwort eingeben",
    },
    "intents_restants": {"ca": "⚠️ {} intents restants", "de": "⚠️ {} Versuche übrig"},
    "massa_intents_espera": {
        "ca": "⏳ Massa intents. Espera {} segons.",
        "de": "⏳ Zu viele Versuche. Warte {} Sekunden.",
    },
    "massa_intents_bloqueig": {
        "ca": "❌ Massa intents. Bloquejat 60 segons.",
        "de": "❌ Zu viele Versuche. 60 Sekunden gesperrt.",
    },

    # ---------------------------------------------------------------
    # Context de treball (sidebar)
    # ---------------------------------------------------------------
    "context_treball": {"ca": "Context de Treball", "de": "Arbeitskontext"},
    "equip": {"ca": "Equip:", "de": "Team:"},
    "selecciona_equip": {"ca": "Selecciona l'equip...", "de": "Team auswählen..."},
    "temporada": {"ca": "Temporada:", "de": "Saison:"},
    "selecciona_temporada": {"ca": "Selecciona la temporada...", "de": "Saison auswählen..."},
    "fase_opcional": {"ca": "Fase (opcional):", "de": "Phase (optional):"},
    "totes_fases": {"ca": "Totes les fases", "de": "Alle Phasen"},
    "sense_equip": {"ca": "⚠️ No tens equip assignat", "de": "⚠️ Kein Team zugewiesen"},

    # ---------------------------------------------------------------
    # Navegació
    # ---------------------------------------------------------------
    "nav_inici": {"ca": "Inici", "de": "Start"},
    "nav_equips": {"ca": "Equips", "de": "Teams"},
    "nav_partit": {"ca": "Partit", "de": "Spiel"},
    "nav_jugador": {"ca": "Jugador", "de": "Spieler"},
    "nav_fitxes": {"ca": "Fitxes", "de": "Spielerkarten"},
    "nav_comparativa": {"ca": "Comparativa", "de": "Vergleich"},
    "nav_informes": {"ca": "Informes", "de": "Berichte"},
    "nav_importar": {"ca": "Importar", "de": "Importieren"},
    "nav_admin": {"ca": "Admin", "de": "Admin"},

    # ---------------------------------------------------------------
    # Portes d'accés (routing)
    # ---------------------------------------------------------------
    "avis_login": {
        "ca": "🔐 Has d'iniciar sessió per veure aquesta secció",
        "de": "🔐 Bitte melde dich an, um diesen Bereich zu sehen",
    },
    "avis_admin": {
        "ca": "⛔ Necessites permisos d'administrador",
        "de": "⛔ Du brauchst Administratorrechte",
    },

    # ---------------------------------------------------------------
    # Ko-fi
    # ---------------------------------------------------------------
    "kofi_text": {
        "ca": "Si t'agrada l'app, convida'm a un cafè ☕",
        "de": "Wenn dir die App gefällt, spendier mir einen Kaffee ☕",
    },

    # ---------------------------------------------------------------
    # Home: resum ràpid + historial
    # ---------------------------------------------------------------
    "resum_rapid": {"ca": "📊 Resum ràpid", "de": "📊 Schnellübersicht"},
    "partits": {"ca": "Partits", "de": "Spiele"},
    "temporada_metric": {"ca": "Temporada", "de": "Saison"},
    "benvinguda_titol": {"ca": "Benvingut al sistema d'anàlisi estadístic!", "de": "Willkommen im Statistik-Analysesystem!"},
    "benvinguda_intro": {"ca": "Utilitza el menú lateral per seleccionar el context de treball i navegar entre les seccions.", "de": "Nutze das Seitenmenü, um den Arbeitskontext auszuwählen und zwischen den Bereichen zu navigieren."},
    "historial_titol": {"ca": "📋 Historial de Partits", "de": "📋 Spielverlauf"},
    "victories": {"ca": "Victòries", "de": "Siege"},
    "derrotes": {"ca": "Derrotes", "de": "Niederlagen"},
    "sets_favor_contra": {"ca": "Sets (favor-contra)", "de": "Sätze (für-gegen)"},
    "sense_partits": {"ca": "Encara no hi ha partits registrats", "de": "Noch keine Spiele erfasst"},
    "local_curt": {"ca": "🏠", "de": "🏠"},
    "visitant_curt": {"ca": "✈️", "de": "✈️"},

    # ---------------------------------------------------------------
    # Informes (PDF)
    # ---------------------------------------------------------------
    "informe_titol": {"ca": "📄 Generador d'Informes", "de": "📄 Berichtsgenerator"},
    "avis_context": {"ca": "⚠️ Selecciona primer un equip i temporada al menú lateral", "de": "⚠️ Wähle zuerst Team und Saison im Seitenmenü"},
    "informe_selecciona_partit": {"ca": "Selecciona un partit:", "de": "Spiel auswählen:"},
    "informe_blocs": {"ca": "Blocs a incloure:", "de": "Abschnitte einschließen:"},
    "informe_generar": {"ca": "📄 Generar informe", "de": "📄 Bericht erstellen"},
    "informe_generant": {"ca": "Generant l'informe...", "de": "Bericht wird erstellt..."},
    "informe_descarregar": {"ca": "⬇️ Descarregar PDF", "de": "⬇️ PDF herunterladen"},
    "informe_cap_bloc": {"ca": "⚠️ Selecciona almenys un bloc", "de": "⚠️ Mindestens einen Abschnitt auswählen"},
    "informe_error": {"ca": "❌ No s'ha pogut generar l'informe", "de": "❌ Bericht konnte nicht erstellt werden"},
    "bloc_eficacia_equip": {"ca": "Eficàcia de l'equip", "de": "Team-Effizienz"},
    "bloc_detall_jugador": {"ca": "Detall per jugador", "de": "Details pro Spieler"},
    "bloc_sideout": {"ca": "Side-out i contraatac", "de": "Side-out und Konter"},
    "bloc_rotacions": {"ca": "Rotacions", "de": "Rotationen"},
    "bloc_distribucio": {"ca": "Distribució del col·locador", "de": "Zuspieler-Verteilung"},
    "bloc_distribucio_recepcio": {"ca": "Distribució segons recepció", "de": "Verteilung nach Annahme"},
    "bloc_errors": {"ca": "Anàlisi d'errors", "de": "Fehleranalyse"},
    "bloc_rankings": {"ca": "Rànquings positius", "de": "Positiv-Rankings"},
    "bloc_valor_jugadors": {"ca": "Valor dels jugadors", "de": "Spielerwert"},

    # ---- Informes: jugador ----
    "informe_ambit": {"ca": "Àmbit de l'informe:", "de": "Berichtstyp:"},
    "ambit_partit": {"ca": "Partit", "de": "Spiel"},
    "ambit_jugador": {"ca": "Jugador", "de": "Spieler"},
    "informe_selecciona_jugador": {"ca": "Selecciona un jugador:", "de": "Spieler auswählen:"},
    "informe_abast": {"ca": "Sobre quins partits:", "de": "Über welche Spiele:"},
    "abast_partit": {"ca": "Un partit concret", "de": "Ein einzelnes Spiel"},
    "abast_temporada": {"ca": "Tota la temporada", "de": "Gesamte Saison"},
    "informe_temporada_ctx": {"ca": "Tota la temporada ({} partits)", "de": "Gesamte Saison ({} Spiele)"},
    "sense_jugadors": {"ca": "No hi ha jugadors en aquest equip", "de": "Keine Spieler in diesem Team"},
    "bloc_metriques": {"ca": "Mètriques principals", "de": "Hauptkennzahlen"},
}


def get_lang():
    """Retorna l'idioma actiu (per defecte 'ca')."""
    return st.session_state.get("lang", IDIOMA_PER_DEFECTE)


def t(key):
    """Tradueix una clau a l'idioma actiu. Si falta, retorna la clau."""
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key
    lang = get_lang()
    return entry.get(lang, entry.get(IDIOMA_PER_DEFECTE, key))
