from __future__ import annotations

import streamlit as st

from storage import kb_loader as kb_json
from llm import fact_extraction, groq_client, ollama_client
from core.dialog_manager import (
    start_group_inference_session,
    update_group_inference_session,
    reset_group_inference_session,
    start_graph_test_session,
    update_graph_test_session,
    reset_graph_test_session,
)
from ui.common import render_view_title
from ui.user_view import (
    render_group_inference_session,
    render_graph_test_session,
    render_eduroam_walkthrough,
)
from ui.admin_import_export_view import admin_rule_validation


def _render_group_inference_test(
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str,
    llm_formulation: bool,
) -> None:
    st.subheader("Gruppen-Inferenztest")
    st.caption(
        "Diagnosemodus für Admins: zeigt Fakten, gematchte Regeln und den vollständigen Regeltrace. "
        "Die normale Nutzeroberfläche verwendet dieselbe Logik, blendet diese technischen Details aber aus."
    )
    st.markdown(
        """
        In diesem Modus wird zuerst aus Freitext eine Faktensammlung erzeugt. Danach laufen die Gruppen-Inferenzregeln.
        Im Schnellmodus wird zuerst der lokale Fallback-Parser genutzt; Groq/Ollama wird nur bei unsicherem Freitext aufgerufen.
        Sobald eine Regel ein Schrittpaket erreicht, startet automatisch der interaktive Schritt-für-Schritt-Durchlauf.
        """
    )

    session_active = bool(st.session_state.get("group_inference_session"))
    render_group_inference_session(use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)

    col_reset, _ = st.columns([1, 3])
    if col_reset.button("Dialog zurücksetzen", key="diag_inference_reset_session"):
        reset_group_inference_session()
        st.rerun()

    st.info("Eingabe unten schreiben und mit Enter absenden.")
    input_placeholder = (
        "Antwort eingeben und mit Enter absenden" if session_active else "Problem beschreiben und mit Enter absenden"
    )
    user_text = st.chat_input(input_placeholder, key="diag_inference_chat_input")

    if user_text is not None:
        try:
            cleaned_text = user_text.strip()
            if not cleaned_text:
                st.warning("Bitte gib zuerst eine Antwort ein.")
            elif session_active:
                update_group_inference_session(cleaned_text, use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)
                st.rerun()
            else:
                start_group_inference_session(cleaned_text, use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)
                st.rerun()
        except Exception as e:
            st.error(f"Inferenz konnte nicht ausgeführt werden: {e}")

    render_eduroam_walkthrough()


def _render_decision_graph_test(
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str,
    llm_formulation: bool,
) -> None:
    st.subheader("Entscheidungsnetz-Test")
    st.caption(
        "Diagnosemodus für Admins: führt ein gespeichertes Entscheidungsnetz als Testdialog aus und zeigt Fakten, Pfad und Kantenprüfung."
    )
    graphs = kb_json.load_decision_graphs(active_only=True)
    if not graphs:
        st.info("Es sind noch keine Entscheidungsnetze vorhanden.")
        return

    graph = st.selectbox(
        "Entscheidungsnetz auswählen",
        graphs,
        format_func=lambda g: f"{g.get('name')} ({g.get('id')})",
        key="diag_graph_select",
    )
    session_active = bool(st.session_state.get("graph_test_session"))
    render_graph_test_session(use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)

    col_reset, _ = st.columns([1, 3])
    if col_reset.button("Graph-Dialog zurücksetzen", key="diag_graph_reset_session"):
        reset_graph_test_session()
        st.rerun()

    st.info("Eingabe unten schreiben und mit Enter absenden.")
    graph_placeholder = (
        "Antwort eingeben und mit Enter absenden" if session_active else "Problem für den Graph-Test beschreiben und mit Enter absenden"
    )
    user_text = st.chat_input(graph_placeholder, key="diag_graph_chat_input")

    if user_text is not None:
        try:
            cleaned_text = user_text.strip()
            if not cleaned_text:
                st.warning("Bitte gib zuerst eine Antwort ein.")
            elif session_active:
                update_graph_test_session(cleaned_text, use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)
                st.rerun()
            else:
                start_graph_test_session(graph, cleaned_text, use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)
                st.rerun()
        except Exception as e:
            st.error(f"Entscheidungsnetz konnte nicht ausgeführt werden: {e}")

    render_eduroam_walkthrough()


def _render_llm_test(use_llm: bool, llm_provider: str, model: str, fallback: bool, llm_mode: str) -> None:
    st.subheader("LLM-Test")
    st.caption("Prüft Provider, API-Key/Verfügbarkeit und die Faktenerkennung mit einem kurzen Testtext.")

    if not use_llm or llm_provider == "none":
        st.info("Aktuell ist kein LLM-Anbieter ausgewählt. Wähle links in der Sidebar Groq Cloud oder Ollama lokal aus.")
        return

    if llm_provider == "groq":
        if not groq_client.configured_api_key_available():
            st.warning("Für Groq ist noch kein API-Key hinterlegt. Trage in der Sidebar einen Key ein.")
        else:
            ok, message = groq_client.groq_check(model=model)
            st.success(message) if ok else st.error(message)
    elif llm_provider == "ollama":
        if ollama_client.ollama_available():
            st.success("Ollama ist erreichbar.")
        else:
            st.error("Ollama ist nicht erreichbar. Starte Ollama lokal und prüfe das Modell.")

    with st.form("diag_llm_fact_test_form"):
        sample = st.text_area(
            "Testeingabe",
            value="Ich möchte eduroam auf Windows einrichten, aber ich kenne mein Passwort nicht.",
            height=100,
        )
        submitted = st.form_submit_button("Fakten erkennen")
    if submitted:
        try:
            if llm_mode == "quality":
                data = fact_extraction.recognize_facts(sample, model, provider=llm_provider)
            else:
                data = fact_extraction.recognize_facts_fast(sample, model, provider=llm_provider)
            st.json(data)
        except Exception as e:
            if fallback:
                st.warning(f"LLM-Erkennung fehlgeschlagen. Fallback wäre in der App aktiv. Technische Meldung: {e}")
            else:
                st.error(f"LLM-Erkennung fehlgeschlagen: {e}")


def admin_tests_diagnostics(
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str = "fast",
    llm_formulation: bool = False,
) -> None:
    render_view_title(
        "Tests & Diagnose",
        "Tests & Diagnose",
        "Hier liegen Gruppen-Inferenztest, Entscheidungsnetz-Test, Regelprüfung und LLM-Test. Dadurch bleibt die Nutzeroberfläche einfach, während Admins weiterhin alle internen Entscheidungen prüfen können.",
        subtitle="Technische Prüfwerkzeuge für Admins, Projektteam und Entwicklung. Normale Nutzer sehen diese Debug-Informationen nicht.",
        hero=True,
    )

    mode = st.radio(
        "Diagnosewerkzeug auswählen",
        ["Gruppen-Inferenztest", "Entscheidungsnetz-Test", "Regelprüfung", "LLM-Test"],
        horizontal=True,
        key="diag_mode",
    )

    if mode == "Gruppen-Inferenztest":
        _render_group_inference_test(use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)
    elif mode == "Entscheidungsnetz-Test":
        _render_decision_graph_test(use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)
    elif mode == "Regelprüfung":
        admin_rule_validation()
    else:
        _render_llm_test(use_llm, llm_provider, model, fallback, llm_mode)
