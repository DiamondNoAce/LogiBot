from __future__ import annotations

from typing import Any

import streamlit as st

from storage import kb_loader as kb_json
from core import rule_engine
from core import inference_engine
from llm import ollama_client as llm_ollama
from core import decision_graph_engine

def _wizard_system_from_facts(facts: dict[str, Any]) -> str:
    os_value = str(facts.get("os", "unknown")).strip().lower()
    if os_value in {"windows", "win", "win10", "win11"}:
        return "windows"
    if os_value in {"mac", "macos", "mac os", "osx", "os x"}:
        return "macos"
    return "unknown"


def _step_by_phase(service_key: str, system_key: str, phase_contains: str) -> int | None:
    for step in kb_json.get_steps(service_key, system_key, active_only=True):
        phase = str(step.get("phase", "")).lower()
        title = str(step.get("title", "")).lower()
        if phase_contains.lower() in phase or phase_contains.lower() in title:
            return int(step.get("number"))
    return None


def _guess_eduroam_step_from_facts(user_text: str, facts: dict[str, Any]) -> tuple[str, int | None, str]:
    """Bestimmt den Einstiegsschritt für den Durchlauf.

    Die Inferenzregeln erkennen eher abstrakte Fakten wie topic/os/intent.
    Für den Durchlauf wird daraus ein konkreter eduroam-Schritt abgeleitet.
    """
    system_key = _wizard_system_from_facts(facts)

    # Fallback über die normale Schritt-Erkennung nutzen, falls der Freitext konkret genug ist.
    rec = rule_engine.recognize(user_text)
    if rec.service_key == "eduroam" and rec.system_key in {"windows", "mac", "macos"}:
        system_key = rec.system_key
        if rec.step_number is not None:
            return system_key, int(rec.step_number), f"Schritt über normale Rule Engine erkannt: {rec.reason}"

    if system_key == "unknown":
        return system_key, None, "Betriebssystem noch unbekannt."

    # Ableitung aus Fakten der Gruppen-Inferenz.
    problem_area = str(facts.get("problem_area", "unknown")).lower()
    intent = str(facts.get("intent", "unknown")).lower()

    if facts.get("internet_available") is False:
        return system_key, _step_by_phase("eduroam", system_key, "vorbereitung") or 1, "Kein Internet erkannt."
    if problem_area == "organisation" or intent == "organisation":
        return system_key, _step_by_phase("eduroam", system_key, "organisation"), "Organisationsauswahl erkannt."
    if problem_area == "login" or intent == "login":
        return system_key, _step_by_phase("eduroam", system_key, "benutzerdaten"), "Login-/Benutzerdatenproblem erkannt."
    if problem_area == "verbinden" or facts.get("eduroam_connected") is False:
        return system_key, _step_by_phase("eduroam", system_key, "verbinden"), "Verbindungsproblem erkannt."

    # Wenn nur eduroam + OS + Setup erkannt wurde, wird die Anleitung von vorne durchgespielt.
    if intent in {"setup", "unknown", "troubleshooting"}:
        first = kb_json.get_steps("eduroam", system_key, active_only=True)
        if first:
            return system_key, int(first[0].get("number")), "Allgemeiner eduroam-Setup-Durchlauf."

    return system_key, None, "Kein konkreter Schritt ableitbar."


def _eduroam_followup_question(system_key: str, step: dict[str, Any]) -> str:
    phase = str(step.get("phase", "")).lower()
    title = str(step.get("title", "")).lower()

    if "vorbereitung" in phase or "internet" in title:
        return "Hast du aktuell eine aktive Internetverbindung?"
    if "cat" in phase:
        return "Konntest du cat.eduroam.org im Browser öffnen?"
    if "organisation" in phase:
        return "Konntest du als Organisation „Universität Hohenheim“ auswählen?"
    if "installer_download" in phase or "download" in phase:
        return "Konntest du den passenden eduroam-Installer herunterladen?"
    if "datei_starten" in phase:
        return "Konntest du die heruntergeladene Datei starten und im Installer auf „Weiter“ klicken?"
    if "datei_oeffnen" in phase:
        return "Konntest du die heruntergeladene mobileconfig-Datei öffnen?"
    if "hinweis" in phase:
        return "Konntest du das Hinweisfenster mit „OK“ bestätigen?"
    if "geraeteverwaltung" in phase:
        return "Konntest du die Geräteverwaltung bzw. Profile in den macOS-Einstellungen öffnen?"
    if "profil" in phase:
        return "Konntest du das eduroam-Profil auswählen und installieren?"
    if "benutzerdaten" in phase or "login" in title:
        return "Konntest du den Benutzernamen im Format benutzername@uni-hohenheim.de und dein Hohenheimer Passwort eingeben?"
    if "systempasswort" in phase:
        return "Konntest du die Installation mit dem Betriebssystem-Passwort deines Macs bestätigen?"
    if "zertifikat" in phase or "sicherheitswarnung" in title:
        return "Konntest du die Sicherheitswarnung bzw. Zertifikatsabfrage mit „Ja“ bestätigen?"
    if "fertigstellen" in phase:
        return "Konntest du auf „Fertigstellen“ klicken?"
    if "verbinden" in phase:
        return "Bist du jetzt mit eduroam verbunden?"
    return "Hat dieser Schritt funktioniert?"


def _next_step_number(service_key: str, system_key: str, current_number: int) -> int | None:
    numbers = [int(s.get("number")) for s in kb_json.get_steps(service_key, system_key, active_only=True)]
    for number in numbers:
        if number > int(current_number):
            return number
    return None


def _previous_step_number(service_key: str, system_key: str, current_number: int) -> int | None:
    numbers = [int(s.get("number")) for s in kb_json.get_steps(service_key, system_key, active_only=True)]
    previous = None
    for number in numbers:
        if number >= int(current_number):
            return previous
        previous = number
    return previous


def start_eduroam_walkthrough(system_key: str, step_number: int, reason: str = "") -> None:
    st.session_state.eduroam_walkthrough = {
        "active": True,
        "done": False,
        "service_key": "eduroam",
        "system_key": system_key,
        "current_step": int(step_number),
        "started_from": int(step_number),
        "reason": reason,
        "show_solution": False,
        "history": [],
    }



def stop_eduroam_walkthrough() -> None:
    st.session_state.eduroam_walkthrough = None


def _normalize_response_text(text: str) -> str:
    return str(text).strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def _text_answer_is_positive(text: str) -> bool:
    t = _normalize_response_text(text)
    negative_markers = ["nicht", "nein", "kein", "keine", "fehler", "problem", "haenge", "haengt", "geht nicht", "klappt nicht"]
    positive_markers = ["ja", "weiter", "funktioniert", "klappt", "erledigt", "fertig", "ok", "passt", "geschafft"]
    return any(x in t for x in positive_markers) and not any(x in t for x in negative_markers)


def _text_answer_is_negative(text: str) -> bool:
    t = _normalize_response_text(text)
    negative_markers = ["nein", "nicht", "kein", "keine", "fehler", "problem", "haenge", "haengt", "geht nicht", "klappt nicht", "funktioniert nicht"]
    return any(x in t for x in negative_markers)


def _handle_walkthrough_free_answer(answer_text: str) -> None:
    state = st.session_state.get("eduroam_walkthrough") or {}
    if not state or not answer_text.strip():
        return

    current = int(state.get("current_step", 1))
    state.setdefault("history", []).append({"step": current, "answer": answer_text, "input_type": "freitext"})

    if _text_answer_is_positive(answer_text):
        st.session_state.eduroam_walkthrough = state
        _advance_walkthrough("freitext_ja")
        return

    if _text_answer_is_negative(answer_text):
        state["show_solution"] = True
        state["last_free_answer_hint"] = "Ich habe erkannt, dass du bei diesem Schritt hängen geblieben bist. Daher zeige ich die passende Lösung an."
        st.session_state.eduroam_walkthrough = state
        return

    # Falls die Antwort nicht eindeutig Ja/Nein ist, als Zusatzinfo speichern und noch einmal nachfragen.
    state["last_free_answer_hint"] = (
        "Ich konnte aus deiner Antwort noch nicht eindeutig erkennen, ob der Schritt funktioniert hat. "
        "Antworte z. B. mit 'Ja, weiter' oder 'Nein, ich hänge hier'."
    )
    st.session_state.eduroam_walkthrough = state


# ============================================================
# Interaktive Test-Sessions für Nutzeroberfläche
# ============================================================


def _is_unknown_value(value: Any) -> bool:
    return value is None or value == "" or (isinstance(value, str) and value.lower() == "unknown")


def _merge_facts(old_facts: dict[str, Any], new_facts: dict[str, Any]) -> dict[str, Any]:
    """Neue erkannte Fakten in bestehende Fakten übernehmen.

    Unknown/None/leer überschreibt vorhandene Werte nicht. Dadurch kann der Nutzer
    nach einer Rückfrage schrittweise fehlende Informationen ergänzen.
    """
    merged = dict(old_facts or {})
    for key, value in (new_facts or {}).items():
        if _is_unknown_value(value):
            continue
        merged[key] = value
    return merged


def _recognize_facts_for_session(user_text: str, use_ollama: bool, model: str, fallback: bool) -> tuple[dict[str, Any], str]:
    if use_ollama:
        try:
            return llm_ollama.recognize_facts(user_text, model), "Ollama-Faktenerkennung genutzt"
        except Exception as e:
            if not fallback:
                raise
            return inference_engine.facts_from_text(user_text), f"Ollama nicht verfügbar, Fallback genutzt: {e}"
    return inference_engine.facts_from_text(user_text), "Regelbasierte Faktenerkennung ohne LLM"


def _pending_ask_fact(result: dict[str, Any]) -> str | None:
    """Liest aus dem letzten Inferenzergebnis, welche Information gerade abgefragt wurde.

    Dadurch kann eine kurze Folgeantwort wie "Ja" oder "Nein" korrekt als Fakt
    gespeichert werden, statt den Dialog wieder von vorne zu beginnen.
    """
    for action in result.get("actions", []) or []:
        if action.get("type") == "ask" and action.get("fact"):
            return str(action.get("fact"))
    return None


def _answer_is_yes(text: str) -> bool:
    t = _normalize_response_text(text)
    yes_words = ["ja", "jep", "yes", "genau", "stimmt", "korrekt", "aktiviert", "vorhanden", "eingerichtet", "funktioniert", "klappt", "online"]
    no_words = ["nein", "nicht", "kein", "keine", "fehlt", "ohne", "problem", "fehler", "klappt nicht", "funktioniert nicht"]
    return any(word in t for word in yes_words) and not any(word in t for word in no_words)


def _answer_is_no(text: str) -> bool:
    t = _normalize_response_text(text)
    no_words = ["nein", "nicht", "kein", "keine", "fehlt", "ohne", "problem", "fehler", "klappt nicht", "funktioniert nicht"]
    return any(word in t for word in no_words)


def _contextual_facts_from_answer(answer_text: str, pending_fact: str | None) -> dict[str, Any]:
    """Ergänzt Fakten aus kurzen Folgeantworten.

    Beispiel: Wenn die Engine vorher `account_activated` gefragt hat, wird "Ja"
    zu `{"account_activated": True}`. Zusätzlich werden häufige freie Formulierungen
    wie "mein Benutzerkonto ist aktiviert" erkannt.
    """
    t = _normalize_response_text(answer_text)
    facts: dict[str, Any] = {}

    if pending_fact:
        if _answer_is_yes(answer_text):
            facts[pending_fact] = True
        elif _answer_is_no(answer_text):
            facts[pending_fact] = False

    if ("konto" in t or "account" in t or "benutzerkonto" in t) and any(x in t for x in ["aktiviert", "freigeschaltet", "vorhanden"]):
        facts["account_activated"] = True
    if ("konto" in t or "account" in t or "benutzerkonto" in t) and any(x in t for x in ["nicht aktiviert", "kein", "keine", "fehlt", "noch nicht"]):
        facts["account_activated"] = False

    if any(x in t for x in ["internet funktioniert", "internet vorhanden", "online", "wlan funktioniert"]):
        facts["internet_available"] = True
    if any(x in t for x in ["kein internet", "ohne internet", "offline", "internet geht nicht"]):
        facts["internet_available"] = False

    if any(x in t for x in ["windows", "win10", "win11", "pc"]):
        facts["os"] = "windows"
    if any(x in t for x in ["macos", "mac os", "macbook", "apple", "osx", "mac"]):
        facts["os"] = "macos"

    if "eduroam" in t:
        facts["topic"] = "eduroam"
    elif "vpn" in t:
        facts["topic"] = "vpn"
    elif "mfa" in t or "2fa" in t:
        facts["topic"] = "mfa"

    if any(x in t for x in ["einrichten", "installieren", "setup", "verbinden"]):
        facts["intent"] = "setup"
    elif any(x in t for x in ["problem", "fehler", "geht nicht", "funktioniert nicht", "haenge", "haengt"]):
        facts["intent"] = "troubleshooting"
    elif any(x in t for x in ["login", "anmelden", "passwort", "kennwort"]):
        facts["intent"] = "login"

    return facts


def _merge_facts_contextual(old_facts: dict[str, Any], new_facts: dict[str, Any]) -> dict[str, Any]:
    """Merge für laufende Dialoge.

    Bereits erkannte Kernfakten wie topic und os bleiben stabil. Dadurch springt der
    Dialog nicht zurück, wenn eine Folgeantwort z. B. nur "Benutzerkonto aktiviert"
    enthält und die einfache Texterkennung daraus topic=user_account ableiten würde.
    """
    merged = dict(old_facts or {})
    sticky = {"topic", "os"}
    for key, value in (new_facts or {}).items():
        if _is_unknown_value(value):
            continue
        if key in sticky and not _is_unknown_value(merged.get(key)) and merged.get(key) != value:
            continue
        merged[key] = value
    return merged


def _maybe_start_eduroam_walkthrough_from_facts(user_text: str, facts: dict[str, Any], *, force: bool = False) -> str | None:
    """Startet den eduroam-Durchlauf nur, wenn noch keiner aktiv ist.

    Auf Streamlit Community Cloud führt jede Eingabe zu einem kompletten Rerun.
    Ohne diese Schutzabfrage kann ein bereits laufender Schritt-für-Schritt-
    Durchlauf bei Folgeantworten wie "Ja" oder "Benutzerkonto ist aktiviert"
    erneut gestartet und dadurch auf einen früheren Schritt zurückgesetzt werden.
    """
    existing_walkthrough = st.session_state.get("eduroam_walkthrough") or {}
    if existing_walkthrough.get("active") and not force:
        return None

    topic = str(facts.get("topic", "unknown")).lower()
    if topic != "eduroam" and not force:
        return None
    system_key, step_number, reason = _guess_eduroam_step_from_facts(user_text, facts)
    if system_key in {"windows", "mac", "macos"} and step_number is not None:
        start_eduroam_walkthrough(system_key, int(step_number), reason)
        return f"eduroam-Durchlauf gestartet: {system_key}, Schritt {step_number} ({reason})"
    return "eduroam erkannt, aber Betriebssystem oder konkreter Schritt ist noch unklar."


def start_group_inference_session(user_text: str, use_ollama: bool, model: str, fallback: bool) -> None:
    facts, status = _recognize_facts_for_session(user_text, use_ollama, model, fallback)
    result = inference_engine.run_inference(facts)
    st.session_state.group_inference_session = {
        "active": True,
        "initial_text": user_text,
        "facts": facts,
        "result": result,
        "status": status,
        "pending_fact": _pending_ask_fact(result),
        "history": [{"role": "user", "text": user_text}, {"role": "engine", "text": inference_engine.renderable_summary(result)}],
    }
    _maybe_start_eduroam_walkthrough_from_facts(user_text, facts)


def update_group_inference_session(answer_text: str, use_ollama: bool, model: str, fallback: bool) -> None:
    session = st.session_state.get("group_inference_session") or {}
    if not session or not answer_text.strip():
        return
    pending_fact = _pending_ask_fact(session.get("result", {}))
    new_facts, status = _recognize_facts_for_session(answer_text, use_ollama, model, fallback)
    contextual_facts = _contextual_facts_from_answer(answer_text, pending_fact)
    combined_new_facts = _merge_facts_contextual(new_facts, contextual_facts)
    facts = _merge_facts_contextual(session.get("facts", {}), combined_new_facts)
    result = inference_engine.run_inference(facts)
    session["facts"] = facts
    session["result"] = result
    session["status"] = status
    session["pending_fact"] = _pending_ask_fact(result)
    session.setdefault("history", []).append({"role": "user", "text": answer_text, "new_facts": combined_new_facts, "answered_fact": pending_fact})
    session["history"].append({"role": "engine", "text": inference_engine.renderable_summary(result)})
    st.session_state.group_inference_session = session
    _maybe_start_eduroam_walkthrough_from_facts(answer_text, facts)


def reset_group_inference_session() -> None:
    st.session_state.group_inference_session = None
    stop_eduroam_walkthrough()


def _graph_by_id(graph_id: str) -> dict[str, Any] | None:
    for graph in kb_json.load_decision_graphs(active_only=True):
        if graph.get("id") == graph_id:
            return graph
    return None


def _maybe_start_eduroam_walkthrough_from_graph_result(result: dict[str, Any]) -> str | None:
    existing_walkthrough = st.session_state.get("eduroam_walkthrough") or {}
    if existing_walkthrough.get("active"):
        return None

    if result.get("status") != "terminal":
        return None
    terminal = result.get("terminal", {}) or {}
    node = terminal.get("node", {}) or {}
    if terminal.get("node_type") == "step" and node.get("service_key") == "eduroam":
        system_key = str(node.get("system_key", "windows"))
        step_number = int(node.get("step_number", 1))
        start_eduroam_walkthrough(system_key, step_number, "Einstieg aus dem Entscheidungsnetz-Test")
        return f"eduroam-Durchlauf aus Entscheidungsnetz gestartet: Schritt {step_number}."
    return None


def start_graph_test_session(graph: dict[str, Any], user_text: str, use_ollama: bool, model: str, fallback: bool) -> None:
    facts, status = _recognize_facts_for_session(user_text, use_ollama, model, fallback)
    result = decision_graph_engine.run_decision_graph(graph, facts)
    st.session_state.graph_test_session = {
        "active": True,
        "graph_id": graph.get("id"),
        "graph_name": graph.get("name"),
        "initial_text": user_text,
        "facts": facts,
        "result": result,
        "status": status,
        "history": [{"role": "user", "text": user_text}, {"role": "graph", "text": decision_graph_engine.render_summary(result)}],
    }
    _maybe_start_eduroam_walkthrough_from_graph_result(result)


def update_graph_test_session(answer_text: str, use_ollama: bool, model: str, fallback: bool) -> None:
    session = st.session_state.get("graph_test_session") or {}
    if not session or not answer_text.strip():
        return
    graph = _graph_by_id(session.get("graph_id"))
    if not graph:
        return
    result_before = session.get("result", {})
    pending_fact = result_before.get("fact") or result_before.get("expected_fact")
    new_facts, status = _recognize_facts_for_session(answer_text, use_ollama, model, fallback)
    contextual_facts = _contextual_facts_from_answer(answer_text, pending_fact)
    combined_new_facts = _merge_facts_contextual(new_facts, contextual_facts)
    facts = _merge_facts_contextual(session.get("facts", {}), combined_new_facts)
    result = decision_graph_engine.run_decision_graph(graph, facts)
    session["facts"] = facts
    session["result"] = result
    session["status"] = status
    session.setdefault("history", []).append({"role": "user", "text": answer_text, "new_facts": combined_new_facts, "answered_fact": pending_fact})
    session["history"].append({"role": "graph", "text": decision_graph_engine.render_summary(result)})
    st.session_state.graph_test_session = session
    _maybe_start_eduroam_walkthrough_from_graph_result(result)


def reset_graph_test_session() -> None:
    st.session_state.graph_test_session = None
    stop_eduroam_walkthrough()



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


