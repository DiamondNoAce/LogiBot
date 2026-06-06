# app.py
# VERSION: modular_project_structure_v2_requested_layout
# ============================================================
# Schlanker Streamlit-Einstiegspunkt.
# Die eigentliche Logik liegt modular in ui/, core/, storage/ und llm/.
# ============================================================

from __future__ import annotations

import streamlit as st

from config import APP_TITLE, APP_ICON, DEFAULT_MODEL
from llm import ollama_client
from ui.common import apply_global_styles
from ui.user_view import render_user_view
from ui.admin_services_view import admin_services_systems
from ui.admin_steps_view import admin_steps_solutions
from ui.admin_rules_view import admin_inference_rules, admin_inference_test
from ui.admin_graph_view import admin_decision_graphs
from ui.admin_import_export_view import admin_json_files


st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")
apply_global_styles()


VIEWS = [
    "Nutzeroberfläche",
    "Admin: Dienste & Systeme",
    "Admin: Schritte & Lösungen",
    "Admin: Inferenzregeln",
    "Admin: Entscheidungsnetz",
    "Admin: JSON-Dateien",
    "Admin: Inferenz-Test",
]


def render_sidebar() -> tuple[str, bool, str, bool]:
    with st.sidebar:
        st.markdown("## Einstellungen")
        view = st.selectbox("Ansicht", VIEWS, key="sidebar_view")
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

    if view == "Nutzeroberfläche":
        render_user_view(use_ollama, model, fallback)
    elif view == "Admin: Dienste & Systeme":
        admin_services_systems()
    elif view == "Admin: Schritte & Lösungen":
        admin_steps_solutions()
    elif view == "Admin: Inferenzregeln":
        admin_inference_rules()
    elif view == "Admin: Entscheidungsnetz":
        admin_decision_graphs()
    elif view == "Admin: JSON-Dateien":
        admin_json_files()
    elif view == "Admin: Inferenz-Test":
        admin_inference_test()


if __name__ == "__main__":
    main()
