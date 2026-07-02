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
    
    # ---- Home: resum ràpid + historial ----
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
