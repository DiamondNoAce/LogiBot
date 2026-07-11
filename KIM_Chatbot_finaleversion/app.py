# app.py
# VERSION: logibot_admin_excel_layout_wissensmodell_v3
# ============================================================
# Schlanker Streamlit-Einstiegspunkt.
# Die eigentliche Logik liegt modular in ui/, core/, storage/ und llm/.
# ============================================================

from __future__ import annotations

from pathlib import Path
import os
import sys

# Streamlit Community Cloud can start an app from a subfolder.
# This ensures local project modules (ui/, core/, storage/, llm/) are always importable.
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import streamlit as st

from config import APP_TITLE, APP_ICON, DEFAULT_OLLAMA_MODEL, DEFAULT_GROQ_MODEL
from llm import ollama_client, groq_client
from ui.common import apply_global_styles, render_hohenheim_header
from ui.user_view import render_user_view
from ui.admin_services_view import admin_services_systems
from ui.admin_functions_view import admin_functions_answers
from ui.admin_conditions_view import admin_conditions_facts
from ui.admin_rules_view import admin_inference_rules, admin_inference_test
from ui.admin_global_blocks_view import admin_global_blocks
from ui.admin_knowledge_model_view import admin_knowledge_model
from ui.admin_graph_view import admin_decision_graphs
from ui.admin_flows_view import admin_flows
from ui.admin_import_export_view import admin_json_files, admin_rule_validation
from ui.diagnostics_view import admin_tests_diagnostics


st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")
apply_global_styles()


VIEWS = [
    "Nutzeroberfläche",
    "Tests & Diagnose",
    "Admin: Wissensbereiche",
    "Admin: Wissensbausteine",
    "Admin: Funktionen & Antworten",
    "Admin: Regelverwaltung",
    "Admin: Abläufe & Netz",
    "Admin: Entscheidungsnetz",
    "Admin: Wissensmodell",
    "Admin: Globale Bausteine",
    "Admin: Technische JSON-Dateien",
]


def _ensure_active_view() -> None:
    # Interne Navigation aus anderen Views vorm Rendern der Sidebar übernehmen.
    # Wichtig: sidebar_view ist der Key des Sidebar-Selectbox-Widgets und darf
    # nach der Widget-Erzeugung in demselben Streamlit-Lauf nicht mehr gesetzt werden.
    pending_view = st.session_state.pop("pending_view", None)
    if pending_view in VIEWS:
        st.session_state["active_view"] = pending_view
        st.session_state["sidebar_view"] = pending_view

    if "active_view" not in st.session_state or st.session_state["active_view"] not in VIEWS:
        st.session_state["active_view"] = "Nutzeroberfläche"


def _sync_sidebar_view() -> None:
    selected = st.session_state.get("sidebar_view", "Nutzeroberfläche")
    if selected in VIEWS:
        st.session_state["active_view"] = selected


def _groq_config_help_box() -> None:
    st.markdown(
        """
        <div class="card" style="padding:0.85rem 0.95rem; margin-top:0.7rem;">
            <strong>Kein Groq-Key?</strong><br>
            Für die Cloud-Nutzung kannst du deinen eigenen kostenlosen Groq-API-Key verwenden.
            Der Key wird nur in deiner aktuellen Streamlit-Sitzung genutzt und nicht im Projekt gespeichert.
            <br><br>
            <strong>So gehst du vor:</strong><br>
            1. Groq Console öffnen und anmelden oder kostenlos registrieren.<br>
            2. Bereich <em>API Keys</em> öffnen.<br>
            3. <em>Create API Key</em> wählen, Key kopieren und hier einfügen.
            <br><br>
            <a href="https://console.groq.com/keys" target="_blank">Groq API-Key erstellen</a>
            &nbsp;·&nbsp;
            <a href="https://console.groq.com/docs/quickstart" target="_blank">Groq Quickstart öffnen</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> tuple[str, bool, str, str, bool, str, bool]:
    _ensure_active_view()
    active_view = st.session_state["active_view"]

    with st.sidebar:
        st.markdown("## Einstellungen")
        st.selectbox(
            "Ansicht",
            VIEWS,
            index=VIEWS.index(active_view),
            key="sidebar_view",
            on_change=_sync_sidebar_view,
        )
        view = st.session_state.get("active_view", active_view)
        st.markdown("---")
        st.markdown("### LLM-Schicht")
        provider_display = st.selectbox(
            "LLM-Anbieter",
            ["Kein LLM / Fallback", "Ollama lokal", "Groq Cloud"],
            index=0,
            key="sidebar_llm_provider_display",
        )
        provider_map = {
            "Kein LLM / Fallback": "none",
            "Ollama lokal": "ollama",
            "Groq Cloud": "groq",
        }
        llm_provider = provider_map.get(provider_display, "none")
        use_llm = llm_provider != "none"
        st.caption(
            "Das LLM erkennt Freitext und formuliert Antworten. "
            "Die fachliche Entscheidung bleibt immer in der Rule Engine. "
            "Ein LLM-Guard verwirft unbekannte Facts, geratenes Betriebssystem und erfundene technische Schritte."
        )

        llm_mode_display = st.selectbox(
            "LLM-Modus",
            ["Schnell", "Ausgewogen", "Qualität"],
            index=0,
            key="sidebar_llm_mode_display",
            help=(
                "Schnell: lokaler Parser zuerst, Groq nur bei Unsicherheit. "
                "Ausgewogen: kompakte Groq-Prompts bei Bedarf. "
                "Qualität: mehr LLM-Nutzung, dafür langsamer."
            ),
        )
        llm_mode_map = {"Schnell": "fast", "Ausgewogen": "balanced", "Qualität": "quality"}
        llm_mode = llm_mode_map.get(llm_mode_display, "fast")
        llm_formulation = st.toggle(
            "LLM-Antwortformulierung nutzen",
            value=False,
            key="sidebar_llm_formulation",
            help=(
                "Aus = schneller: Die Rule Engine gibt die Antwort direkt aus. "
                "Ein = schöner formuliert, aber meist ein zusätzlicher LLM-Aufruf pro Antwort."
            ),
        )
        if llm_mode == "fast" and llm_provider != "none":
            st.info("Schnellmodus aktiv: einfache Folgeantworten werden lokal erkannt; Groq/Ollama wird nur bei Unsicherheit aufgerufen.")
        if llm_formulation and llm_provider != "none":
            st.warning("Antwortformulierung ist aktiv. Das kann pro Nachricht einen zusätzlichen LLM-Aufruf auslösen.")

        if llm_provider == "groq":
            # App-weiter Key ist optional. Wenn die App öffentlich über Streamlit Cloud
            # geteilt wird, sollten normale Nutzer ihren eigenen Key unten einfügen.
            try:
                app_secret_key = str(st.secrets.get("GROQ_API_KEY", "") or "").strip()
            except Exception:
                app_secret_key = ""
            env_key = os.environ.get("GROQ_API_KEY", "").strip()

            current_session_key = str(st.session_state.get("session_groq_api_key", "") or "").strip()
            groq_key = st.text_input(
                "Dein Groq API-Key für diese Sitzung",
                value=current_session_key,
                type="password",
                key="sidebar_groq_api_key_input",
                placeholder="gsk_...",
                help=(
                    "Füge hier deinen eigenen Groq-Key ein. Der Key wird nur in deiner "
                    "aktuellen Streamlit-Sitzung verwendet und nicht in JSON-Dateien, "
                    "GitHub oder requirements.txt gespeichert."
                ),
            ).strip()
            st.session_state["session_groq_api_key"] = groq_key

            has_any_groq_key = groq_client.configured_api_key_available()
            if groq_key:
                st.success("Benutzereigener Groq-Key ist für diese Sitzung hinterlegt.")
            elif app_secret_key or env_key:
                st.info("Ein App-/Umgebungs-Key ist hinterlegt. Du kannst alternativ trotzdem deinen eigenen Key einfügen.")
            else:
                st.warning("Noch kein Groq API-Key hinterlegt. Ohne Key nutzt die App den regelbasierten Fallback.")
                _groq_config_help_box()
                use_llm = False

            model = st.text_input("Groq-Modell", value=DEFAULT_GROQ_MODEL, key="sidebar_groq_model")
            st.caption("Empfehlung für schnelle Tests: llama-3.1-8b-instant")
            with st.expander("Hinweise zur öffentlichen Streamlit-Cloud-Nutzung"):
                st.markdown(
                    """
                    - Jeder Nutzer kann seinen eigenen Groq-Key in der Sidebar einfügen.
                    - Der Key wird nur in `st.session_state` gehalten und nicht dauerhaft gespeichert.
                    - Der Key wird nicht in die JSON-Wissensbasis geschrieben.
                    - Für eine interne Demo kann der App-Betreiber alternativ `GROQ_API_KEY` als Streamlit Secret hinterlegen.
                    - API-Keys sollten nicht in GitHub, Screenshots oder geteilten ZIP-Dateien stehen.
                    """
                )
        elif llm_provider == "ollama":
            model = st.text_input("Ollama-Modell", value=DEFAULT_OLLAMA_MODEL, key="sidebar_ollama_model")
            st.caption("Empfehlung für lokale Tests: llama3.2:1b. Für bessere Qualität: llama3.2:3b.")
        else:
            model = ""
            st.info("LLM ist deaktiviert. Die App nutzt nur die regelbasierten Fallbacks.")

        fallback = st.toggle("Fallback ohne LLM nutzen", value=True, key="sidebar_fallback")
        if st.button("LLM prüfen", key="sidebar_check_llm"):
            if llm_provider == "ollama":
                if ollama_client.ollama_available():
                    st.success("Ollama ist erreichbar.")
                else:
                    st.error("Ollama ist nicht erreichbar.")
            elif llm_provider == "groq":
                if not groq_client.configured_api_key_available():
                    st.error("Es ist noch kein Groq API-Key hinterlegt. Erstelle einen Key in der Groq Console und füge ihn oben ein.")
                    _groq_config_help_box()
                else:
                    ok, message = groq_client.groq_check(model=model)
                    if ok:
                        st.success(message)
                    else:
                        st.error("Groq ist nicht erreichbar.")
                        with st.expander("Technische Diagnose anzeigen"):
                            st.code(message)
            else:
                st.info("Kein LLM-Anbieter ausgewählt.")
        st.markdown("---")
        st.caption(
            "JSON-Dateien liegen im Ordner `Rule Engine/` mit Unterordnern für Regeln, "
            "Quellen und Schrittpakete. Beim Speichern wird automatisch ein Backup angelegt."
        )
    return view, use_llm, llm_provider, model, fallback, llm_mode, llm_formulation


def main() -> None:
    view, use_llm, llm_provider, model, fallback, llm_mode, llm_formulation = render_sidebar()
    top_nav = {
        "Nutzer": "Nutzeroberfläche",
        "Tests": "Tests & Diagnose",
        "Wissensbereiche": "Admin: Wissensbereiche",
        "Wissensbausteine": "Admin: Wissensbausteine",
        "Funktionen": "Admin: Funktionen & Antworten",
        "Regeln": "Admin: Regelverwaltung",
        "Abläufe & Netz": "Admin: Abläufe & Netz",
        "Wissensmodell": "Admin: Wissensmodell",
    }
    render_hohenheim_header(view, nav_map=top_nav)

    if view == "Nutzeroberfläche":
        render_user_view(use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)
    elif view == "Tests & Diagnose":
        admin_tests_diagnostics(use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)
    elif view == "Admin: Wissensbereiche":
        admin_services_systems()
    elif view == "Admin: Wissensbausteine":
        admin_conditions_facts()
    elif view == "Admin: Funktionen & Antworten":
        admin_functions_answers()
    elif view == "Admin: Regelverwaltung":
        admin_inference_rules()
    elif view == "Admin: Globale Bausteine":
        admin_global_blocks()
    elif view == "Admin: Abläufe & Netz":
        admin_flows()
    elif view == "Admin: Wissensmodell":
        admin_knowledge_model()
    elif view == "Admin: Entscheidungsnetz":
        admin_decision_graphs()
    elif view == "Admin: Technische JSON-Dateien":
        admin_json_files()


if __name__ == "__main__":
    main()
