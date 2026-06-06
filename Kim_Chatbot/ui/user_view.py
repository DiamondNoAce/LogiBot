from __future__ import annotations

from typing import Any

import streamlit as st

from storage import kb_loader as kb_json
from core import rule_engine
from core import inference_engine
from llm import ollama_client as llm_ollama
from core import decision_graph_engine
from core.rule_engine import RecognitionResult

from ui.common import render_answer, render_step_card, render_view_info
from core.dialog_manager import (
    _eduroam_followup_question,
    _handle_walkthrough_free_answer,
    _next_step_number,
    _previous_step_number,
    start_eduroam_walkthrough,
    stop_eduroam_walkthrough,
    start_group_inference_session,
    update_group_inference_session,
    reset_group_inference_session,
    start_graph_test_session,
    update_graph_test_session,
    reset_graph_test_session,
)

def _render_session_history(history: list[dict[str, Any]]) -> None:
    for item in history or []:
        role = item.get("role")
        text = item.get("text", "")
        if role == "user":
            st.markdown(f"**Du:** {text}")
        else:
            st.markdown(f"**System:** {text}")


def render_group_inference_session(use_ollama: bool, model: str, fallback: bool) -> None:
    session = st.session_state.get("group_inference_session")
    if not session:
        return
    result = session.get("result", {})
    facts = session.get("facts", {})

    render_answer("Regelbasierte Ausgabe", inference_engine.renderable_summary(result))
    st.caption(session.get("status", ""))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Aktuelle Fakten")
        st.json(facts)
    with col2:
        st.subheader("Gematchte Regeln")
        st.json(result.get("matched_rules", []))

    with st.expander("Vollständiger Regeltrace"):
        st.json(result.get("evaluated_rules", []))
    with st.expander("Bisheriger Dialog"):
        _render_session_history(session.get("history", []))

    # Die Folgeeingabe befindet sich oben im Hauptformular des Gruppen-Inferenztests.
    # Dadurch bleibt der Dialog an einer Stelle und ein Klick auf den Button startet
    # keine neue Session mehr versehentlich von vorne.
    return


def render_graph_test_session(use_ollama: bool, model: str, fallback: bool) -> None:
    session = st.session_state.get("graph_test_session")
    if not session:
        return
    result = session.get("result", {})
    facts = session.get("facts", {})

    render_answer("Entscheidungsnetz-Ausgabe", decision_graph_engine.render_summary(result))
    st.caption(f"Graph: {session.get('graph_name')} · {session.get('status', '')}")

    status = result.get("status")
    if status == "question":
        st.info(f"Rückfrage aus dem Entscheidungsnetz: {result.get('message') or 'Ich brauche noch weitere Informationen.'}")
    elif status == "terminal":
        terminal = result.get("terminal", {})
        node = terminal.get("node", {})
        st.success(f"Zielknoten erreicht: {node.get('label', 'Unbenannt')} ({terminal.get('node_type')})")
    elif status == "error":
        st.error(result.get("message", "Der Graph konnte nicht ausgeführt werden."))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Aktuelle Fakten")
        st.json(facts)
    with col2:
        st.subheader("Genommener Pfad")
        st.json(result.get("path", []))

    with st.expander("Trace / Kantenprüfung"):
        st.json(result.get("evaluated_edges", []))
    with st.expander("Bisheriger Dialog"):
        _render_session_history(session.get("history", []))

    # Die Folgeeingabe befindet sich oben im Hauptformular des Entscheidungsnetz-Tests.
    return


def _advance_walkthrough(answer: str) -> None:
    state = st.session_state.get("eduroam_walkthrough") or {}
    if not state:
        return
    service_key = state.get("service_key", "eduroam")
    system_key = state.get("system_key", "windows")
    current = int(state.get("current_step", 1))
    state.setdefault("history", []).append({"step": current, "answer": answer})

    next_number = _next_step_number(service_key, system_key, current)
    if next_number is None:
        state["done"] = True
        state["show_solution"] = False
    else:
        state["current_step"] = next_number
        state["show_solution"] = False
    st.session_state.eduroam_walkthrough = state


def render_eduroam_walkthrough() -> None:
    state = st.session_state.get("eduroam_walkthrough")
    if not state or not state.get("active"):
        return

    service_key = state.get("service_key", "eduroam")
    system_key = state.get("system_key", "windows")
    steps = kb_json.get_steps(service_key, system_key, active_only=True)
    if not steps:
        st.warning("Für diesen eduroam-Durchlauf wurden keine Schritte gefunden.")
        return

    st.markdown("---")
    st.subheader("eduroam-Installation interaktiv durchspielen")
    st.caption("Der Durchlauf fragt nach jedem Schritt weitere Informationen ab. Wenn du bei einem Schritt mit „Nein“ antwortest, wird die passende regelbasierte Lösung angezeigt.")

    if state.get("done"):
        render_answer(
            "eduroam-Durchlauf abgeschlossen",
            "Du hast alle Schritte der eduroam-Installationsanleitung durchgespielt. Teste jetzt kurz, ob dein Gerät automatisch mit eduroam verbunden wird.",
        )
        with st.expander("Durchlauf-Historie"):
            st.json(state.get("history", []))
        if st.button("Durchlauf neu starten", key="walkthrough_restart_done"):
            start_eduroam_walkthrough(system_key, int(state.get("started_from", 1)), state.get("reason", ""))
            st.rerun()
        if st.button("Durchlauf beenden", key="walkthrough_stop_done"):
            stop_eduroam_walkthrough()
            st.rerun()
        return

    current = int(state.get("current_step", steps[0].get("number", 1)))
    step = kb_json.get_step(service_key, system_key, current)
    if not step:
        st.warning("Der aktuelle Schritt wurde nicht gefunden.")
        return

    total = len(steps)
    numbers = [int(s.get("number")) for s in steps]
    current_index = numbers.index(current) + 1 if current in numbers else 1
    st.progress(current_index / max(total, 1))
    st.caption(f"{kb_json.get_system(service_key, system_key).get('name', system_key)} · Schritt {current_index}/{total} · Einstieg: Schritt {state.get('started_from')} · {state.get('reason','')}")
    render_step_card(step)

    question = _eduroam_followup_question(system_key, step)
    st.markdown(f"**Folgefrage:** {question}")

    if state.get("last_free_answer_hint"):
        st.info(state.get("last_free_answer_hint"))
        state["last_free_answer_hint"] = ""
        st.session_state.eduroam_walkthrough = state

    if not state.get("show_solution"):
        with st.form(f"walkthrough_free_answer_form_{system_key}_{current}", clear_on_submit=True):
            free_answer = st.text_input(
                "Oder frei antworten",
                placeholder="Beispiel: Ja, hat funktioniert. / Nein, ich hänge hier.",
                key=f"walkthrough_free_answer_{system_key}_{current}",
            )
            free_submitted = st.form_submit_button("Antwort auswerten")
        if free_submitted:
            _handle_walkthrough_free_answer(free_answer)
            st.rerun()

        col_yes, col_no, col_back, col_stop = st.columns([1.2, 1.4, 1, 1])
        if col_yes.button("Ja, weiter", key=f"walkthrough_yes_{system_key}_{current}"):
            _advance_walkthrough("ja")
            st.rerun()
        if col_no.button("Nein, ich hänge hier", key=f"walkthrough_no_{system_key}_{current}"):
            state["show_solution"] = True
            state.setdefault("history", []).append({"step": current, "answer": "nein", "action": "solution_shown"})
            st.session_state.eduroam_walkthrough = state
            st.rerun()
        previous = _previous_step_number(service_key, system_key, current)
        if col_back.button("Zurück", disabled=previous is None, key=f"walkthrough_back_{system_key}_{current}"):
            if previous is not None:
                state["current_step"] = previous
                state["show_solution"] = False
                st.session_state.eduroam_walkthrough = state
                st.rerun()
        if col_stop.button("Beenden", key=f"walkthrough_stop_{system_key}_{current}"):
            stop_eduroam_walkthrough()
            st.rerun()
    else:
        solution = kb_json.get_solution(service_key, system_key, current) or {}
        actions = solution.get("actions", [])
        title = solution.get("problem_title", f"Hilfe zu Schritt {current}")
        render_answer(title, "\n".join(f"- {a}" for a in actions) if actions else "Für diesen Schritt ist keine konkrete Lösung hinterlegt.")
        col_retry, col_next, col_stop = st.columns([1.4, 1.4, 1])
        if col_retry.button("Nach Lösung erneut prüfen", key=f"walkthrough_retry_{system_key}_{current}"):
            state["show_solution"] = False
            st.session_state.eduroam_walkthrough = state
            st.rerun()
        if col_next.button("Hat jetzt funktioniert → weiter", key=f"walkthrough_fixed_next_{system_key}_{current}"):
            _advance_walkthrough("nach_loesung_weiter")
            st.rerun()
        if col_stop.button("Durchlauf beenden", key=f"walkthrough_stop_solution_{system_key}_{current}"):
            stop_eduroam_walkthrough()
            st.rerun()

    with st.expander("Bisherige Antworten im Durchlauf"):
        st.json(state.get("history", []))

# ============================================================
# Nutzeroberfläche
# ============================================================


def render_user_view(use_ollama: bool, model: str, fallback: bool) -> None:
    st.markdown('<div class="hero-title">IT-Anleitungsassistent</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">JSON-Wissensbasis + eigene Rule Engine. Optional erkennt ein lokales LLM über Ollama deine Freitexteingabe.</div>', unsafe_allow_html=True)
    render_view_info(
        "Nutzeroberfläche",
        "Diese Ansicht ist für normale Nutzer gedacht. Hier kann ein Problem frei beschrieben werden; die App erkennt Dienst, System und Schritt und zeigt die passende Anleitung oder Lösung aus der Wissensbasis an.",
    )

    mode = st.radio("Auswertungsmodus", ["Anleitung suchen", "Gruppen-Inferenztest", "Entscheidungsnetz-Test"], horizontal=True, key="user_mode")

    if mode == "Anleitung suchen":
        st.caption("Sucht anhand deiner Freitexteingabe direkt eine passende Anleitung, einen Schritt und eine hinterlegte Lösung.")
        user_text = st.text_area("Beschreibe dein Problem", placeholder="Beispiel: Ich nutze Windows 11 und finde Universität Hohenheim bei eduroam nicht.", height=110, key="user_instruction_text")
        if st.button("Prüfen", key="user_instruction_submit"):
            rec: RecognitionResult
            if use_ollama:
                try:
                    data = llm_ollama.recognize_instruction_request(user_text, model)
                    rec = RecognitionResult(
                        service_key=str(data.get("service_key", "unknown")),
                        system_key=str(data.get("system_key", "unknown")),
                        step_number=data.get("step_number"),
                        confidence=str(data.get("confidence", "niedrig")),
                        reason=str(data.get("reason", "LLM-Erkennung")),
                    )
                except Exception as e:
                    if not fallback:
                        st.error(f"LLM-Erkennung fehlgeschlagen: {e}")
                        return
                    rec = rule_engine.recognize(user_text)
                    st.info(f"Ollama nicht verfügbar, Fallback genutzt: {e}")
            else:
                rec = rule_engine.recognize(user_text)

            result = rule_engine.get_solution_for_recognition(rec)
            with st.expander("Erkennung anzeigen", expanded=True):
                st.json(rec.__dict__)

            if not result:
                st.warning("Ich konnte noch keine eindeutige passende Anleitung finden. Ergänze bitte Dienst, System oder Schritt.")
                return

            service = result["service"] or {}
            system = result["system"] or {}
            step = result["step"]
            solution = result["solution"]
            actions = solution.get("actions", [])
            title = f"{service.get('name')} · {system.get('name')} · Schritt {step.get('number')}: {step.get('title')}"
            text = "\n".join(f"- {a}" for a in actions)
            if use_ollama:
                try:
                    text = llm_ollama.formulate_answer(solution.get("problem_title", title), actions, model)
                except Exception:
                    pass
            render_answer(title, text)
            st.caption(f"Installationsschritt: {step.get('instruction')}")
            if system.get("guide_url"):
                st.info(f"Offizielle Anleitung: {system.get('guide_url')}")

    elif mode == "Gruppen-Inferenztest":
        st.caption("Testet die Gruppen-Inferenzregeln als fortlaufenden Dialog. Nach der ersten Eingabe kannst du Rückfragen beantworten und die Inferenz mit weiteren Antworten fortführen.")
        st.markdown("""
        In diesem Modus wird zuerst aus deinem Freitext eine Faktensammlung erzeugt. Danach laufen die Gruppen-Inferenzregeln.
        Wenn noch Informationen fehlen, kannst du unten weitere Antworten eingeben. Bei eduroam startet zusätzlich ein interaktiver
        Schritt-für-Schritt-Durchlauf der Installationsanleitung.
        """)

        session_active = bool(st.session_state.get("group_inference_session"))
        render_group_inference_session(use_ollama, model, fallback)

        user_text = st.text_area(
            "Weitere Antwort" if session_active else "Erste Eingabe für Faktenerkennung",
            placeholder=(
                "Beispiel: Ja, mein Benutzerkonto ist aktiviert."
                if session_active
                else "Beispiel: Ich möchte eduroam unter Windows installieren und bin bei der Organisationsauswahl hängen geblieben."
            ),
            height=110,
            key="user_inference_text",
        )
        col_run, col_reset = st.columns([1, 1])
        button_label = "Antwort auswerten und Dialog fortführen" if session_active else "Inferenz starten"
        if col_run.button(button_label, key="user_inference_submit"):
            try:
                if session_active:
                    update_group_inference_session(user_text, use_ollama, model, fallback)
                else:
                    start_group_inference_session(user_text, use_ollama, model, fallback)
                st.rerun()
            except Exception as e:
                st.error(f"Inferenz konnte nicht ausgeführt werden: {e}")

        if col_reset.button("Dialog zurücksetzen", key="user_inference_reset_session"):
            reset_group_inference_session()
            st.rerun()

        render_eduroam_walkthrough()

    else:
        st.caption("Führt ein gespeichertes Entscheidungsnetz als fortlaufenden Testdialog aus. Wenn ein Knoten eine Rückfrage erzeugt, kannst du direkt antworten und das Netz mit den neuen Fakten erneut durchlaufen.")
        graphs = kb_json.load_decision_graphs(active_only=True)
        if not graphs:
            st.info("Es sind noch keine Entscheidungsnetze vorhanden.")
        else:
            graph = st.selectbox(
                "Entscheidungsnetz auswählen",
                graphs,
                format_func=lambda g: f"{g.get('name')} ({g.get('id')})",
                key="user_graph_select",
            )
            session_active = bool(st.session_state.get("graph_test_session"))
            render_graph_test_session(use_ollama, model, fallback)

            user_text = st.text_area(
                "Weitere Antwort" if session_active else "Erste Eingabe für Fakten / Graph-Test",
                placeholder=(
                    "Beispiel: Ja, mein Benutzerkonto ist aktiviert."
                    if session_active
                    else "Beispiel: Ich habe ein eduroam Login-Problem unter Windows."
                ),
                height=110,
                key="user_graph_text",
            )
            col_run, col_reset = st.columns([1, 1])
            button_label = "Antwort auswerten und Graph fortführen" if session_active else "Entscheidungsnetz starten"
            if col_run.button(button_label, key="user_graph_submit"):
                try:
                    if session_active:
                        update_graph_test_session(user_text, use_ollama, model, fallback)
                    else:
                        start_graph_test_session(graph, user_text, use_ollama, model, fallback)
                    st.rerun()
                except Exception as e:
                    st.error(f"Entscheidungsnetz konnte nicht ausgeführt werden: {e}")

            if col_reset.button("Graph-Dialog zurücksetzen", key="user_graph_reset_session"):
                reset_graph_test_session()
                st.rerun()

            render_eduroam_walkthrough()

    with st.expander("Alle Dienste und Schritte anzeigen"):
        for service in kb_json.get_services(active_only=True):
            st.subheader(f"{service.get('name')} ({service.get('key')})")
            for system in service.get("systems", []):
                st.markdown(f"**{system.get('name')} ({system.get('key')})**")
                if system.get("prerequisite"):
                    st.caption(f"Voraussetzung: {system.get('prerequisite')}")
                for step in sorted(system.get("steps", []), key=lambda s: int(s.get("number", 0))):
                    render_step_card(step)


# ============================================================
# Admin: Dienste und Systeme
# ============================================================
