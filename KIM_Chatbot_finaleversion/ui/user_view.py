from __future__ import annotations

from typing import Any

import streamlit as st

from storage import kb_loader as kb_json
from core import rule_engine
from core import inference_engine
from core import fallback_fact_extraction
from llm import fact_extraction, response_generation
from core import decision_graph_engine
from core.rule_engine import RecognitionResult

from ui.common import render_answer, render_step_card, render_view_title
from core.dialog_manager import (
    _walkthrough_followup_question,
    _handle_walkthrough_free_answer,
    _next_step_number,
    _previous_step_number,
    get_walkthrough_steps,
    get_walkthrough_step,
    get_walkthrough_title,
    start_step_walkthrough,
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


def _bump_counter(key: str) -> None:
    st.session_state[key] = int(st.session_state.get(key, 0)) + 1


def _render_admin_decision_diagnosis(diagnosis: dict[str, Any] | None) -> None:
    """Zeigt in Tests & Diagnose, warum eine Antwort gewählt wurde."""
    if not diagnosis:
        return
    with st.expander("Warum wurde diese Antwort gewählt?", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Sicherheitsstatus", str(diagnosis.get("status", "unbekannt")))
        c2.metric("Score", str(diagnosis.get("score", "-")))
        c3.metric("Nächste Aktion", str(diagnosis.get("next_action", "-")))

        reasons = diagnosis.get("reasons", []) or []
        risks = diagnosis.get("risks", []) or []
        missing = diagnosis.get("missing_information", []) or []
        if reasons:
            st.markdown("**Erkannte Hinweise:**")
            for reason in reasons:
                st.markdown(f"- {reason}")
        if missing:
            st.markdown("**Noch fehlende Informationen:**")
            for item in missing:
                st.markdown(f"- {item}")
        if risks:
            st.markdown("**Sicherheits-/Unsicherheitsgründe:**")
            for risk in risks:
                st.markdown(f"- {risk}")
        with st.expander("Diagnose als JSON anzeigen", expanded=False):
            st.json(diagnosis)


def _render_dialog_context(context: dict[str, Any] | None) -> None:
    if not context:
        return
    with st.expander("Gesprächskontext", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("Dienst", str(context.get("dienst", "unbekannt")))
        c2.metric("Absicht", str(context.get("absicht", "unbekannt")))
        c3.metric("Betriebssystem", str(context.get("betriebssystem", "unbekannt")))
        if context.get("problemkontext"):
            st.caption(f"Problemkontext: {context.get('problemkontext')}")
        hints = context.get("bekannte_hinweise") or []
        if hints:
            st.markdown("**Merker aus dem bisherigen Dialog:**")
            for hint in hints:
                st.markdown(f"- {hint}")
        if context.get("offene_information") or context.get("letzte_rueckfrage"):
            st.markdown("**Aktuell offen:**")
            if context.get("offene_information"):
                st.markdown(f"- Fakt: `{context.get('offene_information')}`")
            if context.get("letzte_rueckfrage"):
                st.markdown(f"- Rückfrage: {context.get('letzte_rueckfrage')}")
        guard_notes = context.get("llm_guard_notes") or []
        if guard_notes:
            st.markdown("**LLM-Guard:**")
            for note in guard_notes:
                st.markdown(f"- {note}")
        with st.expander("Support-Zusammenfassung anzeigen", expanded=False):
            st.markdown(str(context.get("support_zusammenfassung") or ""))



def _instruction_text_mentions_system(text: str) -> bool:
    return fallback_fact_extraction.text_mentions_operating_system(text)


def _service_has_multiple_systems(service_key: str) -> bool:
    return len(kb_json.get_systems(service_key, active_only=True)) > 1


def _support_fallback_hint() -> str:
    return (
        "Ich konnte keine eindeutig passende Anleitung auswählen. Ergänze bitte Dienst, Betriebssystem/Gerät und was genau passieren soll. "
        "Wenn die passende Anleitung nicht in der Wissensbasis enthalten ist oder du nicht weiterkommst, wende dich bitte an den KIM-IT-Service-Desk."
    )


def render_group_inference_session(
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str = "fast",
    llm_formulation: bool = False,
) -> None:
    session = st.session_state.get("group_inference_session")
    if not session:
        return
    result = session.get("result", {})
    facts = session.get("facts", {})

    render_answer("Regelbasierte Ausgabe", session.get("reply_text") or inference_engine.renderable_summary(result))
    st.caption(" · ".join(x for x in [session.get("status", ""), session.get("reply_status", "")] if x))
    if use_llm:
        st.caption(f"LLM-Modus: {session.get('llm_mode', llm_mode)} · Antwortformulierung: {'aktiv' if session.get('llm_formulation') else 'aus'}")

    _render_admin_decision_diagnosis(session.get("decision_diagnosis"))
    _render_dialog_context(session.get("dialog_context"))

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


def render_graph_test_session(
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str = "fast",
    llm_formulation: bool = False,
) -> None:
    session = st.session_state.get("graph_test_session")
    if not session:
        return
    result = session.get("result", {})
    facts = session.get("facts", {})

    render_answer("Entscheidungsnetz-Ausgabe", session.get("reply_text") or decision_graph_engine.render_summary(result))
    st.caption(f"Graph: {session.get('graph_name')} · {session.get('status', '')} · {session.get('reply_status', '')}")
    if use_llm:
        st.caption(f"LLM-Modus: {session.get('llm_mode', llm_mode)} · Antwortformulierung: {'aktiv' if session.get('llm_formulation') else 'aus'}")

    _render_admin_decision_diagnosis(session.get("decision_diagnosis"))
    _render_dialog_context(session.get("dialog_context"))

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

    next_number = _next_step_number(service_key, system_key, current, state.get("package_id"))
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
    package_id = state.get("package_id")
    steps = get_walkthrough_steps(state)
    if not steps:
        st.warning("Für diesen Schrittpaket-Durchlauf wurden keine Schritte gefunden.")
        return

    walkthrough_title = get_walkthrough_title(state)
    st.markdown("---")
    st.subheader(f"{walkthrough_title} interaktiv durchspielen")
    st.caption("Der Durchlauf fragt nach jedem Schritt weitere Informationen ab. Wenn du bei einem Schritt mit „Nein“ antwortest, wird die passende regelbasierte Lösung angezeigt. Du kannst oben im Chat oder direkt in der Schrittkarte antworten.")

    if state.get("done"):
        render_answer(
            "Schrittpaket-Durchlauf abgeschlossen",
            f"Du hast alle Schritte aus '{walkthrough_title}' durchgespielt. Prüfe jetzt kurz, ob dein ursprüngliches Anliegen gelöst ist.",
        )
        with st.expander("Durchlauf-Historie"):
            st.json(state.get("history", []))
        if st.button("Durchlauf neu starten", key="walkthrough_restart_done"):
            start_step_walkthrough(service_key, system_key, int(state.get("started_from", 1)), state.get("reason", ""), package_id=package_id, package_title=state.get("package_title"))
            st.rerun()
        if st.button("Durchlauf beenden", key="walkthrough_stop_done"):
            stop_eduroam_walkthrough()
            st.rerun()
        return

    current = int(state.get("current_step", steps[0].get("number", 1)))
    step = get_walkthrough_step(state, current)
    if not step:
        st.warning("Der aktuelle Schritt wurde nicht gefunden.")
        return

    total = len(steps)
    numbers = [int(s.get("number")) for s in steps]
    current_index = numbers.index(current) + 1 if current in numbers else 1
    key_prefix = f"{service_key}_{system_key}_{package_id or 'all'}_{current}".replace(".", "_").replace("-", "_")
    st.progress(current_index / max(total, 1))
    system = kb_json.get_system(service_key, system_key) or {}
    service = kb_json.get_service(service_key) or {}
    system_label = system.get('name', system_key)
    service_label = service.get('name', service_key)
    st.caption(f"{service_label} · {system_label} · Schritt {current_index}/{total} · Einstieg: Schritt {state.get('started_from')} · {state.get('reason','')}")
    render_step_card(step)

    question = _walkthrough_followup_question(service_key, system_key, step)
    st.markdown(f"**Folgefrage:** {question}")

    if state.get("last_free_answer_hint"):
        st.info(state.get("last_free_answer_hint"))
        state["last_free_answer_hint"] = ""
        st.session_state.eduroam_walkthrough = state

    if not state.get("show_solution"):
        with st.form(f"walkthrough_free_answer_form_{key_prefix}", clear_on_submit=True):
            free_answer = st.text_input(
                "Oder frei antworten",
                placeholder="Beispiel: Ja, hat funktioniert. / Nein, ich hänge hier.",
                key=f"walkthrough_free_answer_{key_prefix}",
            )
            free_submitted = st.form_submit_button("Antwort auswerten")
        if free_submitted:
            _handle_walkthrough_free_answer(free_answer)
            st.rerun()

        col_yes, col_no, col_back, col_stop = st.columns([1.2, 1.4, 1, 1])
        if col_yes.button("Ja, weiter", key=f"walkthrough_yes_{key_prefix}"):
            _advance_walkthrough("ja")
            st.rerun()
        if col_no.button("Nein, ich hänge hier", key=f"walkthrough_no_{key_prefix}"):
            state["show_solution"] = True
            state.setdefault("history", []).append({"step": current, "answer": "nein", "action": "solution_shown"})
            st.session_state.eduroam_walkthrough = state
            st.rerun()
        previous = _previous_step_number(service_key, system_key, current, package_id)
        if col_back.button("Zurück", disabled=previous is None, key=f"walkthrough_back_{key_prefix}"):
            if previous is not None:
                state["current_step"] = previous
                state["show_solution"] = False
                st.session_state.eduroam_walkthrough = state
                st.rerun()
        if col_stop.button("Beenden", key=f"walkthrough_stop_{key_prefix}"):
            stop_eduroam_walkthrough()
            st.rerun()
    else:
        solution = step.get("solution") or kb_json.get_solution(service_key, system_key, current) or {}
        actions = solution.get("actions", [])
        title = solution.get("problem_title", f"Hilfe zu Schritt {current}")
        render_answer(title, "\n".join(f"- {a}" for a in actions) if actions else "Für diesen Schritt ist keine konkrete Lösung hinterlegt.")
        col_retry, col_next, col_stop = st.columns([1.4, 1.4, 1])
        if col_retry.button("Nach Lösung erneut prüfen", key=f"walkthrough_retry_{key_prefix}"):
            state["show_solution"] = False
            st.session_state.eduroam_walkthrough = state
            st.rerun()
        if col_next.button("Hat jetzt funktioniert → weiter", key=f"walkthrough_fixed_next_{key_prefix}"):
            _advance_walkthrough("nach_loesung_weiter")
            st.rerun()
        if col_stop.button("Durchlauf beenden", key=f"walkthrough_stop_solution_{key_prefix}"):
            stop_eduroam_walkthrough()
            st.rerun()

    with st.expander("Bisherige Antworten im Durchlauf"):
        st.json(state.get("history", []))

def _run_instruction_search(
    user_text: str,
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str,
    llm_formulation: bool,
) -> dict[str, Any]:
    """Führt die direkte Anleitungssuche aus.

    Die Funktion ist bewusst in `session_state` speicherbar, damit die Suche
    wie ein Chatfeld mit Enter funktioniert und das Ergebnis nach dem Rerun
    sichtbar bleibt.
    """
    rec: RecognitionResult
    local_rec = rule_engine.recognize(user_text)
    local_is_clear = local_rec.service_key != "unknown" and local_rec.confidence in {"hoch", "mittel"}
    status = "Regelbasierte lokale Anleitungserkennung genutzt."

    if use_llm and not (llm_mode == "fast" and local_is_clear):
        try:
            data = fact_extraction.recognize_instruction_request(user_text, model, provider=llm_provider)
            rec = RecognitionResult(
                service_key=str(data.get("service_key", "unknown")),
                system_key=str(data.get("system_key", "unknown")),
                step_number=data.get("step_number"),
                confidence=str(data.get("confidence", "niedrig")),
                reason=str(data.get("reason", "LLM-Erkennung")),
            )
            status = f"{fact_extraction.provider_label(llm_provider)}-Erkennung genutzt."
        except Exception as e:
            if not fallback:
                raise
            rec = local_rec
            status = f"LLM nicht verfügbar, Fallback genutzt: {e}"
    else:
        rec = local_rec
        if use_llm and llm_mode == "fast" and local_is_clear:
            status = "Schnellmodus: lokale Anleitungserkennung war eindeutig, LLM-Aufruf übersprungen."

    needs_system_clarification = (
        rec.service_key != "unknown"
        and _service_has_multiple_systems(rec.service_key)
        and not _instruction_text_mentions_system(user_text)
    )
    result = None if needs_system_clarification else rule_engine.get_solution_for_recognition(rec)
    output_text = ""
    title = ""
    guide_url = ""
    instruction = ""
    clarification_text = ""

    if needs_system_clarification:
        service = kb_json.get_service(rec.service_key) or {}
        service_label = service.get("name") or rec.service_key
        clarification_text = (
            f"Ich habe {service_label} erkannt, aber kein eindeutiges Betriebssystem/Gerät. "
            "Bitte ergänze z. B. Windows, macOS, Android, iOS/iPadOS, Linux oder ChromeOS, damit keine falsche Anleitung ausgegeben wird."
        )
        status = "Sichere Rückfrage: Betriebssystem/Gerät fehlt, daher keine Anleitung geraten."

    if result:
        service = result["service"] or {}
        system = result["system"] or {}
        step = result["step"]
        solution = result["solution"]
        actions = solution.get("actions", [])
        title = f"{service.get('name')} · {system.get('name')} · Schritt {step.get('number')}: {step.get('title')}"
        output_text = "\n".join(f"- {a}" for a in actions)
        if use_llm and llm_formulation:
            try:
                output_text = response_generation.formulate_answer(solution.get("problem_title", title), actions, model, provider=llm_provider)
            except Exception:
                pass
        instruction = str(step.get("instruction", ""))
        guide_url = str(system.get("guide_url", "") or "")

    return {
        "query": user_text,
        "recognition": rec.__dict__,
        "result_found": bool(result),
        "title": title,
        "text": output_text,
        "instruction": instruction,
        "guide_url": guide_url,
        "status": status,
        "clarification_text": clarification_text,
    }


def _render_instruction_search_result(payload: dict[str, Any] | None) -> None:
    if not payload:
        return
    st.markdown(f"**Du:** {payload.get('query', '')}")
    status = str(payload.get("status", ""))
    if status:
        st.caption(status)
    with st.expander("Technische Erkennung anzeigen", expanded=False):
        st.json(payload.get("recognition", {}))
    if not payload.get("result_found"):
        clarification = str(payload.get("clarification_text", "") or "")
        st.warning(clarification or _support_fallback_hint())
        return
    render_answer(str(payload.get("title", "Passende Anleitung")), str(payload.get("text", "")))
    if payload.get("instruction"):
        st.caption(f"Installationsschritt: {payload.get('instruction')}")
    if payload.get("guide_url"):
        st.info(f"Offizielle Anleitung: {payload.get('guide_url')}")

def _render_public_dialog_history(history: list[dict[str, Any]]) -> None:
    """Nutzerfreundliche Dialoganzeige ohne technische Regel-/Fact-Details."""
    for item in history or []:
        role = item.get("role")
        text = str(item.get("text", "") or "").strip()
        if not text:
            continue
        if role == "user":
            with st.chat_message("user"):
                st.markdown(text)
        else:
            with st.chat_message("assistant"):
                st.markdown(text)


def render_public_problem_session() -> None:
    """Zeigt den produktiven Nutzerdialog ohne Debug-Ausgaben."""
    session = st.session_state.get("group_inference_session")
    if not session:
        st.markdown(
            """
            <div class="card">
                <strong>Beschreibe dein Anliegen in einem Satz.</strong><br>
                Beispiele: „Ich möchte eduroam auf Windows einrichten“, „Mein VPN funktioniert nicht“,
                „Ich habe mein Passwort vergessen“ oder „Ich brauche Zugriff auf Bibliotheksdatenbanken“.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    _render_public_dialog_history(session.get("history", []))


def _start_topic_dialog(
    prompt: str,
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str,
    llm_formulation: bool,
) -> None:
    reset_group_inference_session()
    start_group_inference_session(prompt, use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)


def _render_common_topics(
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str,
    llm_formulation: bool,
) -> None:
    st.caption("Wähle ein häufiges Anliegen aus. Danach führt dich der Assistent schrittweise weiter.")
    topics = [
        ("eduroam einrichten", "Ich möchte eduroam einrichten."),
        ("VPN verbinden", "Ich möchte mich mit dem VPN verbinden."),
        ("MFA / 2FA", "Ich habe ein Problem mit MFA und dem Code aus der Authenticator-App."),
        ("Passwort vergessen", "Ich habe mein Hohenheimer Passwort vergessen und brauche Hilfe beim Zurücksetzen."),
        ("Bibliotheksdatenbanken", "Ich möchte auf die Datenbanken der Bibliothek zugreifen."),
        ("Support kontaktieren", "Ich weiß nicht weiter und möchte den KIM-Support kontaktieren."),
    ]
    cols = st.columns(3)
    for i, (label, prompt) in enumerate(topics):
        with cols[i % 3]:
            st.markdown(
                f"""
                <div class="card" style="min-height: 88px;">
                    <strong>{label}</strong><br>
                    <span style="color: var(--hoh-muted); font-size: 13px;">Startet einen geführten Dialog.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"{label} starten", key=f"topic_start_{i}", use_container_width=True):
                _start_topic_dialog(prompt, use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)
                st.rerun()

    st.markdown("---")
    render_public_problem_session()
    if st.session_state.get("group_inference_session"):
        col_reset, _ = st.columns([1, 3])
        if col_reset.button("Dialog zurücksetzen", key="topic_dialog_reset"):
            reset_group_inference_session()
            st.rerun()
        user_text = st.chat_input("Antwort eingeben und mit Enter absenden", key="topic_dialog_chat_input")
        if user_text is not None:
            cleaned_text = user_text.strip()
            if cleaned_text:
                update_group_inference_session(cleaned_text, use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)
                st.rerun()
    render_eduroam_walkthrough()


# ============================================================
# Nutzeroberfläche
# ============================================================


def render_user_view(
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str = "fast",
    llm_formulation: bool = False,
) -> None:
    render_view_title(
        "IT-Anleitungsassistent",
        "Nutzeroberfläche",
        "Diese Ansicht ist bewusst einfach gehalten: Nutzer sehen keine technischen Debugdaten. Der Assistent führt dich über Rückfragen und passende Anleitungen zur Lösung.",
        subtitle="Beschreibe dein IT-Problem, suche eine Anleitung oder wähle ein häufiges Thema aus. Technische Tests sind in die Ansicht „Tests & Diagnose“ verschoben.",
        hero=True,
    )

    mode = st.radio(
        "Was möchtest du tun?",
        ["Problem schildern", "Anleitung suchen", "Häufige Themen"],
        horizontal=True,
        key="user_mode",
    )

    if mode == "Problem schildern":
        st.caption("Der Assistent führt dich über Rückfragen zur passenden Lösung oder Anleitung.")
        render_public_problem_session()

        col_reset, _ = st.columns([1, 3])
        if col_reset.button("Dialog zurücksetzen", key="user_problem_reset_session"):
            reset_group_inference_session()
            st.rerun()

        session_active = bool(st.session_state.get("group_inference_session"))
        placeholder = "Antwort eingeben und mit Enter absenden" if session_active else "Problem beschreiben und mit Enter absenden"
        user_text = st.chat_input(placeholder, key="user_problem_chat_input")

        if user_text is not None:
            try:
                cleaned_text = user_text.strip()
                if not cleaned_text:
                    st.warning("Bitte gib zuerst eine Beschreibung ein.")
                elif session_active:
                    update_group_inference_session(cleaned_text, use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)
                    st.rerun()
                else:
                    start_group_inference_session(cleaned_text, use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)
                    st.rerun()
            except Exception as e:
                st.error(f"Der Dialog konnte nicht fortgeführt werden: {e}")

        render_eduroam_walkthrough()

    elif mode == "Anleitung suchen":
        st.caption("Sucht direkt eine passende Anleitung, einen Schritt und eine hinterlegte Lösung aus der Wissensbasis.")
        st.info("Eingabe unten schreiben und mit Enter absenden. Ein normales Enter startet die Suche; STRG+Enter ist nicht nötig.")

        col_reset, _ = st.columns([1, 3])
        if col_reset.button("Suche zurücksetzen", key="user_instruction_reset"):
            st.session_state.user_instruction_search_result = None
            st.rerun()

        _render_instruction_search_result(st.session_state.get("user_instruction_search_result"))

        user_text = st.chat_input(
            "Problem oder Anleitung eingeben und mit Enter absenden",
            key="user_instruction_chat_input",
        )
        if user_text is not None:
            cleaned_text = user_text.strip()
            if not cleaned_text:
                st.warning("Bitte gib zuerst eine Beschreibung ein.")
            else:
                try:
                    st.session_state.user_instruction_search_result = _run_instruction_search(
                        cleaned_text,
                        use_llm,
                        llm_provider,
                        model,
                        fallback,
                        llm_mode,
                        llm_formulation,
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Anleitungssuche konnte nicht ausgeführt werden: {e}")

    else:
        _render_common_topics(use_llm, llm_provider, model, fallback, llm_mode, llm_formulation)

    with st.expander("Anleitungskatalog anzeigen"):
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
