# app.py
# VERSION: hohenheim_style_clickable_header_nav_v2
# ============================================================
# Schlanker Streamlit-Einstiegspunkt.
# Die eigentliche Logik liegt modular in ui/, core/, storage/ und llm/.
# ============================================================

from __future__ import annotations

import streamlit as st

from config import APP_TITLE, APP_ICON, DEFAULT_MODEL
from llm import ollama_client
from ui.common import apply_global_styles, render_hohenheim_header
from ui.user_view import render_user_view
from ui.admin_services_view import admin_services_systems
from ui.admin_steps_view import admin_steps_solutions
from ui.admin_rules_view import admin_inference_rules, admin_inference_test
from ui.admin_global_blocks_view import admin_global_blocks
from ui.admin_knowledge_model_view import admin_knowledge_model
from ui.admin_graph_view import admin_decision_graphs
from ui.admin_import_export_view import admin_json_files, admin_rule_validation


st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")
apply_global_styles()


VIEWS = [
    "Nutzeroberfläche",
    "Admin: Dienste & Systeme",
    "Admin: Schritte & Lösungen",
    "Admin: Inferenzregeln",
    "Admin: Globale Bausteine",
    "Admin: Wissensmodell",
    "Admin: Entscheidungsnetz",
    "Admin: JSON-Dateien",
    "Admin: Regelprüfung",
    "Admin: Inferenz-Test",
]


def _ensure_active_view() -> None:
    if "active_view" not in st.session_state or st.session_state["active_view"] not in VIEWS:
        st.session_state["active_view"] = "Nutzeroberfläche"


def _sync_sidebar_view() -> None:
    selected = st.session_state.get("sidebar_view", "Nutzeroberfläche")
    if selected in VIEWS:
        st.session_state["active_view"] = selected


def render_sidebar() -> tuple[str, bool, str, bool]:
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
        use_ollama = st.toggle("Ollama nutzen", value=False, key="sidebar_use_ollama")
        model = st.text_input("Ollama-Modell", value=DEFAULT_MODEL, key="sidebar_model")
        fallback = st.toggle("Fallback ohne Ollama nutzen", value=True, key="sidebar_fallback")
        if st.button("Ollama prüfen", key="sidebar_check_ollama"):
            if ollama_client.ollama_available():
                st.success("Ollama ist erreichbar.")
            else:
                st.error("Ollama ist nicht erreichbar.")
        st.markdown("---")
        st.caption(
            "JSON-Dateien liegen im Ordner `Rule Engine/` mit Unterordnern für Regeln, "
            "Quellen und Schrittpakete. Beim Speichern wird automatisch ein Backup angelegt."
        )
    return view, use_ollama, model, fallback


def main() -> None:
    view, use_ollama, model, fallback = render_sidebar()
    top_nav = {
        "Nutzer": "Nutzeroberfläche",
        "Dienste": "Admin: Dienste & Systeme",
        "Schritte": "Admin: Schritte & Lösungen",
        "Regeln": "Admin: Inferenzregeln",
        "Globale Bausteine": "Admin: Globale Bausteine",
        "Entscheidungsnetz": "Admin: Entscheidungsnetz",
        "Wissensmodell": "Admin: Wissensmodell",
    }
    render_hohenheim_header(view, nav_map=top_nav)

    if view == "Nutzeroberfläche":
        render_user_view(use_ollama, model, fallback)
    elif view == "Admin: Dienste & Systeme":
        admin_services_systems()
    elif view == "Admin: Schritte & Lösungen":
        admin_steps_solutions()
    elif view == "Admin: Inferenzregeln":
        admin_inference_rules()
    elif view == "Admin: Globale Bausteine":
        admin_global_blocks()
    elif view == "Admin: Wissensmodell":
        admin_knowledge_model()
    elif view == "Admin: Entscheidungsnetz":
        admin_decision_graphs()
    elif view == "Admin: JSON-Dateien":
        admin_json_files()
    elif view == "Admin: Regelprüfung":
        admin_rule_validation()
    elif view == "Admin: Inferenz-Test":
        admin_inference_test()


if __name__ == "__main__":
    main()
