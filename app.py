# app.py
# VERSION: visual_decision_graph_editor_v9_dialog_state_fix
# ============================================================
# Streamlit-App: Nutzeroberfläche + Adminoberfläche
# Austauschbarer Rule-Engine-Ordner + eigene kleine Rule Engine + optional Ollama
# Keine SQLite-Abhängigkeit.
# ============================================================

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import streamlit as st

import kb_json
import rule_engine
import inference_engine
import llm_ollama
import decision_graph_engine
from rule_engine import RecognitionResult

try:
    from streamlit_flow import streamlit_flow
    from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
    from streamlit_flow.state import StreamlitFlowState
    from streamlit_flow.layouts import TreeLayout
    STREAMLIT_FLOW_AVAILABLE = True
except Exception:
    streamlit_flow = None
    StreamlitFlowNode = None
    StreamlitFlowEdge = None
    StreamlitFlowState = None
    TreeLayout = None
    STREAMLIT_FLOW_AVAILABLE = False

st.set_page_config(page_title="IT-Anleitungsassistent", page_icon="🧠", layout="wide")

DEFAULT_MODEL = "llama3.2:3b"

# ============================================================
# CSS: dunkle Schrift auf hellen Flächen
# ============================================================

st.markdown(
    """
    <style>
        html, body, [data-testid="stAppViewContainer"] { background-color: #ffffff; color: #111827; }
        [data-testid="stSidebar"] { background-color: #f4f5f9; }
        [data-testid="stSidebar"] * { color: #111827 !important; }
        .block-container { max-width: 1200px; padding-top: 2.6rem; padding-bottom: 4rem; }
        label, .stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label { color: #111827 !important; }
        input, textarea, select, input:focus, textarea:focus { color: #111827 !important; background-color: #ffffff !important; caret-color: #111827 !important; }
        .hero-title { font-size: 40px; font-weight: 800; color: #272838; margin-bottom: 0.4rem; }
        .hero-subtitle { color: #5c6270; font-size: 15px; line-height: 1.55; margin-bottom: 1.2rem; }
        .card { border: 1px solid #e3e8f0; border-radius: 12px; background: #ffffff; padding: 1rem 1.1rem; margin-bottom: 1rem; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
        .answer-card { border: 1px solid #d8e5f3; border-left: 5px solid #0d8bd6; border-radius: 10px; background: #ffffff; padding: 1rem 1.1rem; margin-top: 1rem; }
        .answer-title { font-size: 13px; text-transform: uppercase; color: #0b6faa; font-weight: 800; letter-spacing: 0.3px; margin-bottom: 0.55rem; }
        .answer-text { color: #1f2937; font-size: 15px; line-height: 1.58; }
        .step-card { display: flex; gap: 12px; border: 1px solid #e3e8f0; border-left: 4px solid #2f55a4; border-radius: 8px; background-color: #ffffff; padding: 12px 14px; margin-bottom: 10px; }
        .step-number { width: 34px; height: 34px; min-width: 34px; border-radius: 8px; background-color: #2f55a4; color: #ffffff !important; display: flex; align-items: center; justify-content: center; font-weight: 800; }
        .step-title { font-size: 14px; font-weight: 800; color: #244b9b; margin-bottom: 4px; }
        .step-phase { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
        .step-text { font-size: 13px; color: #2f3645; line-height: 1.45; }
        code { color: #111827 !important; background-color: #e8eef8 !important; border-radius: 4px; padding: 2px 4px; }

        .graph-toolbar { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; padding: 0.75rem; border: 1px solid #e5e7eb; border-radius: 12px; background: #f8fafc; margin-bottom: 1rem; }
        .prop-panel { border: 1px solid #e5e7eb; border-radius: 14px; background: #ffffff; padding: 1rem; position: sticky; top: 1rem; }
        .prop-title { font-size: 18px; font-weight: 800; color: #111827; margin-bottom: 0.25rem; }
        .prop-muted { font-size: 13px; color: #6b7280; margin-bottom: 1rem; line-height: 1.45; }
        .selection-pill { display: inline-block; padding: 0.25rem 0.55rem; border-radius: 999px; background: #e8eef8; color: #1f3b78; font-size: 12px; font-weight: 700; margin-bottom: 0.6rem; }
        .canvas-help { color: #6b7280; font-size: 13px; line-height: 1.45; margin: 0.25rem 0 0.75rem 0; }
        .tiny-note { color: #6b7280; font-size: 12px; }
        .view-info {
            border: 1px solid #dbeafe;
            border-left: 5px solid #2563eb;
            background: #eff6ff;
            border-radius: 12px;
            padding: 0.9rem 1rem;
            margin: 0.75rem 0 1.25rem 0;
            color: #1f2937;
            line-height: 1.55;
        }
        .view-info-title {
            font-size: 14px;
            font-weight: 800;
            color: #1e3a8a;
            margin-bottom: 0.25rem;
        }
        .view-info-text {
            font-size: 14px;
            color: #1f2937;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def esc(value: Any) -> str:
    return html.escape(str(value)).replace("\n", "<br>")


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text).splitlines() if line.strip()]


def json_area(label: str, value: Any, key: str, height: int = 220) -> Any:
    raw = st.text_area(label, value=json.dumps(value, ensure_ascii=False, indent=2), height=height, key=key)
    return json.loads(raw)


def select_service(key: str, active_only: bool = False) -> dict[str, Any] | None:
    services = kb_json.get_services(active_only=active_only)
    if not services:
        st.warning("Keine Dienste vorhanden.")
        return None
    return st.selectbox("Dienst auswählen", services, format_func=lambda s: f"{s.get('name')} ({s.get('key')})", key=key)


def select_system(service_key: str, key: str, active_only: bool = False) -> dict[str, Any] | None:
    systems = kb_json.get_systems(service_key, active_only=active_only)
    if not systems:
        st.warning("Keine Systeme für diesen Dienst vorhanden.")
        return None
    return st.selectbox("System auswählen", systems, format_func=lambda s: f"{s.get('name')} ({s.get('key')})", key=key)


def select_step(service_key: str, system_key: str, key: str, active_only: bool = False) -> dict[str, Any] | None:
    steps = kb_json.get_steps(service_key, system_key, active_only=active_only)
    if not steps:
        st.warning("Keine Schritte für dieses System vorhanden.")
        return None
    return st.selectbox("Schritt auswählen", steps, format_func=lambda s: f"{s.get('number')} · {s.get('title')}", key=key)


def render_step_card(step: dict[str, Any]) -> None:
    st.markdown(
        f"""
        <div class="step-card">
            <div class="step-number">{esc(step.get('number'))}</div>
            <div>
                <div class="step-title">{esc(step.get('title'))}</div>
                <div class="step-phase">Phase: {esc(step.get('phase'))}</div>
                <div class="step-text">{esc(step.get('instruction'))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_answer(title: str, text: str) -> None:
    st.markdown(
        f"""
        <div class="answer-card">
            <div class="answer-title">{esc(title)}</div>
            <div class="answer-text">{esc(text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def render_view_info(title: str, text: str) -> None:
    """Zeigt oben in jeder Ansicht eine kurze Erklärung zur Nutzung."""
    st.markdown(
        f"""
        <div class="view-info">
            <div class="view-info-title">{esc(title)}</div>
            <div class="view-info-text">{esc(text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )



# ============================================================
# Interaktiver eduroam-Installationsdurchlauf
# ============================================================


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


def _merge_facts(old_facts: dict[str, Any], new_facts: dict[str, Any]) -> dict[str, Any]:
    """Neue erkannte Fakten in bestehende Fakten übernehmen.

    Unknown/None/leer überschreibt vorhandene Werte nicht. Dadurch kann der Nutzer
    nach einer Rückfrage schrittweise fehlende Informationen ergänzen.
    """
    merged = dict(old_facts or {})
    for key, value in (new_facts or {}).items():
        if value in {None, "", "unknown"}:
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
        if value in {None, "", "unknown"}:
            continue
        if key in sticky and merged.get(key) not in {None, "", "unknown"} and merged.get(key) != value:
            continue
        merged[key] = value
    return merged


def _maybe_start_eduroam_walkthrough_from_facts(user_text: str, facts: dict[str, Any], *, force: bool = False) -> str | None:
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


def admin_services_systems() -> None:
    st.header("Admin · Dienste & Systeme")
    render_view_info(
        "Dienste & Systeme",
        "Hier legst du die Grundstruktur der Wissensbasis an. Ein Dienst ist z. B. eduroam, VPN oder Drucker; darunter liegen die passenden Systeme wie Windows 10/11 oder macOS mit Voraussetzungen und Anleitungslink.",
    )
    tab_service, tab_system = st.tabs(["Dienst bearbeiten", "System bearbeiten"])

    with tab_service:
        services = kb_json.get_services(active_only=False)
        options = [None] + services
        selected = st.selectbox("Bestehenden Dienst auswählen", options, format_func=lambda s: "Neuen Dienst anlegen" if s is None else f"{s.get('name')} ({s.get('key')})", key="admin_service_select")
        selected_service_key = "new" if selected is None else str(selected.get("key", "new"))
        if selected is not None:
            st.caption(f"Aktuell ausgewählt: {selected.get('name')} ({selected.get('key')})")
        with st.form(f"admin_service_form_{selected_service_key}"):
            key = st.text_input("Service-Key", value="" if selected is None else selected.get("key", ""), key=f"admin_service_key_{selected_service_key}")
            name = st.text_input("Name", value="" if selected is None else selected.get("name", ""), key=f"admin_service_name_{selected_service_key}")
            desc = st.text_area("Beschreibung", value="" if selected is None else selected.get("description", ""), key=f"admin_service_desc_{selected_service_key}")
            active = st.checkbox("Aktiv", value=True if selected is None else bool(selected.get("active", True)), key=f"admin_service_active_{selected_service_key}")
            if st.form_submit_button("Dienst speichern"):
                if not key.strip() or not name.strip():
                    st.error("Key und Name sind Pflichtfelder.")
                else:
                    kb_json.upsert_service({"key": key, "name": name, "description": desc, "active": active})
                    st.success("Dienst gespeichert.")
                    st.rerun()

    with tab_system:
        service = select_service("admin_system_service_select", active_only=False)
        if service:
            systems = kb_json.get_systems(service.get("key"), active_only=False)
            options = [None] + systems
            selected = st.selectbox("Bestehendes System auswählen", options, format_func=lambda s: "Neues System anlegen" if s is None else f"{s.get('name')} ({s.get('key')})", key=f"admin_system_select_{service.get('key')}")
            selected_system_key = "new" if selected is None else str(selected.get("key", "new"))
            form_suffix = f"{service.get('key')}_{selected_system_key}"
            if selected is not None:
                st.caption(f"Aktuell ausgewählt: {selected.get('name')} ({selected.get('key')})")
            with st.form(f"admin_system_form_{form_suffix}"):
                key = st.text_input("System-Key", value="" if selected is None else selected.get("key", ""), key=f"admin_system_key_{form_suffix}")
                name = st.text_input("System-Name", value="" if selected is None else selected.get("name", ""), key=f"admin_system_name_{form_suffix}")
                prerequisite = st.text_area("Voraussetzung", value="" if selected is None else selected.get("prerequisite", ""), key=f"admin_system_prereq_{form_suffix}")
                guide_url = st.text_input("Anleitungs-URL", value="" if selected is None else selected.get("guide_url", ""), key=f"admin_system_url_{form_suffix}")
                active = st.checkbox("Aktiv", value=True if selected is None else bool(selected.get("active", True)), key=f"admin_system_active_{form_suffix}")
                if st.form_submit_button("System speichern"):
                    if not key.strip() or not name.strip():
                        st.error("Key und Name sind Pflichtfelder.")
                    else:
                        kb_json.upsert_system(service.get("key"), {"key": key, "name": name, "prerequisite": prerequisite, "guide_url": guide_url, "active": active})
                        st.success("System gespeichert.")
                        st.rerun()


# ============================================================
# Admin: Schritte und Lösungen
# ============================================================


def admin_steps_solutions() -> None:
    st.header("Admin · Schritte & Lösungen")
    render_view_info(
        "Schritte & Lösungen",
        "Hier pflegst du die konkreten Anleitungsschritte und die dazugehörigen Hilfen. Diese Einträge sind die Grundlage dafür, dass Nutzer bei einem erkannten Problem eine passende Empfehlung erhalten.",
    )
    service = select_service("admin_steps_service", active_only=False)
    if not service:
        return
    system = select_system(service.get("key"), "admin_steps_system", active_only=False)
    if not system:
        return

    steps = kb_json.get_steps(service.get("key"), system.get("key"), active_only=False)
    options = [None] + steps
    selected = st.selectbox("Schritt auswählen", options, format_func=lambda s: "Neuen Schritt anlegen" if s is None else f"{s.get('number')} · {s.get('title')}", key=f"admin_step_select_{service.get('key')}_{system.get('key')}")
    selected_step_key = "new" if selected is None else str(selected.get("number", "new"))
    form_suffix = f"{service.get('key')}_{system.get('key')}_{selected_step_key}"
    if selected is not None:
        st.caption(f"Aktuell ausgewählt: Schritt {selected.get('number')} · {selected.get('title')}")

    with st.form(f"admin_step_form_{form_suffix}"):
        number = st.number_input("Schrittnummer", min_value=1, step=1, value=1 if selected is None else int(selected.get("number", 1)), key=f"admin_step_number_{form_suffix}")
        phase = st.text_input("Phase / Intent", value="" if selected is None else selected.get("phase", ""), key=f"admin_step_phase_{form_suffix}")
        title = st.text_input("Titel", value="" if selected is None else selected.get("title", ""), key=f"admin_step_title_{form_suffix}")
        instruction = st.text_area("Anleitungstext", value="" if selected is None else selected.get("instruction", ""), key=f"admin_step_instruction_{form_suffix}")
        keywords = st.text_area("Keywords / Synonyme, ein Begriff pro Zeile", value="" if selected is None else "\n".join(selected.get("keywords", [])), key=f"admin_step_keywords_{form_suffix}")
        st.markdown("**Lösung zum Schritt**")
        sol = {} if selected is None else selected.get("solution", {}) or {}
        problem_title = st.text_input("Problemtyp/Titel", value=sol.get("problem_title", ""), key=f"admin_solution_title_{form_suffix}")
        summary = st.text_area("Kurzbeschreibung", value=sol.get("summary", ""), key=f"admin_solution_summary_{form_suffix}")
        actions = st.text_area("Aktionen, eine Aktion pro Zeile", value="\n".join(sol.get("actions", [])), key=f"admin_solution_actions_{form_suffix}")
        rules_json = st.text_area("Optionale Schritt-Regeln als JSON-Liste", value=json.dumps([] if selected is None else selected.get("rules", []), ensure_ascii=False, indent=2), height=150, key=f"admin_step_rules_{form_suffix}")
        col_save, col_delete = st.columns(2)
        save_clicked = col_save.form_submit_button("Schritt speichern")
        delete_clicked = col_delete.form_submit_button("Schritt löschen")

    if save_clicked:
        try:
            rules = json.loads(rules_json) if rules_json.strip() else []
            step = {
                "number": int(number),
                "phase": phase,
                "title": title,
                "instruction": instruction,
                "keywords": split_lines(keywords),
                "active": active,
                "solution": {"problem_title": problem_title, "summary": summary, "actions": split_lines(actions)},
                "rules": rules,
            }
            kb_json.upsert_step(service.get("key"), system.get("key"), step)
            st.success("Schritt gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(f"Speichern fehlgeschlagen: {e}")

    if delete_clicked and selected is not None:
        kb_json.delete_step(service.get("key"), system.get("key"), int(selected.get("number")))
        st.warning("Schritt gelöscht.")
        st.rerun()

    st.subheader("Aktuelle Schritte")
    for step in kb_json.get_steps(service.get("key"), system.get("key"), active_only=False):
        render_step_card(step)


# ============================================================
# Admin: Inferenzregeln
# ============================================================


def admin_inference_rules() -> None:
    st.header("Admin · Inferenzregeln")
    render_view_info(
        "Inferenzregeln",
        "Hier werden Wenn-Dann-Regeln gepflegt. Die Regeln werten erkannte Fakten aus, setzen neue Fakten oder erzeugen Antworten. Das eignet sich für allgemeine Schlussfolgerungen vor oder neben dem Entscheidungsnetz.",
    )
    rules = kb_json.load_inference_rules(active_only=False)
    options = [None] + rules
    selected = st.selectbox("Regel auswählen", options, format_func=lambda r: "Neue Regel anlegen" if r is None else f"{r.get('id')} · {r.get('description','')}", key="admin_rule_select")
    selected_rule_key = "new" if selected is None else re.sub(r"[^a-zA-Z0-9_-]", "_", str(selected.get("id", "new")))
    if selected is not None:
        st.caption(f"Aktuell ausgewählt: {selected.get('id')} · {selected.get('description','')}")
    with st.form(f"admin_rule_form_{selected_rule_key}"):
        rid = st.text_input("Regel-ID", value="" if selected is None else selected.get("id", ""), key=f"admin_rule_id_{selected_rule_key}")
        module = st.text_input("Modul", value="general" if selected is None else selected.get("module", "general"), key=f"admin_rule_module_{selected_rule_key}")
        group = st.text_input("Regelgruppe", value="general" if selected is None else selected.get("rule_group", "general"), key=f"admin_rule_group_{selected_rule_key}")
        description = st.text_area("Beschreibung", value="" if selected is None else selected.get("description", ""), key=f"admin_rule_desc_{selected_rule_key}")
        priority = st.number_input("Priorität", min_value=0, step=1, value=100 if selected is None else int(selected.get("priority", 100)), key=f"admin_rule_priority_{selected_rule_key}")
        active = st.checkbox("Aktiv", value=True if selected is None else bool(selected.get("active", True)), key=f"admin_rule_active_{selected_rule_key}")
        stop = st.checkbox("Nach Treffer stoppen", value=False if selected is None else bool(selected.get("stop_after_match", False)), key=f"admin_rule_stop_{selected_rule_key}")
        when_raw = st.text_area("WHEN als JSON", value=json.dumps({"all": [], "any": []} if selected is None else selected.get("when", {}), ensure_ascii=False, indent=2), height=220, key=f"admin_rule_when_{selected_rule_key}")
        then_raw = st.text_area("THEN als JSON-Liste", value=json.dumps([] if selected is None else selected.get("then", []), ensure_ascii=False, indent=2), height=220, key=f"admin_rule_then_{selected_rule_key}")
        col_save, col_delete = st.columns(2)
        save_clicked = col_save.form_submit_button("Regel speichern")
        delete_clicked = col_delete.form_submit_button("Regel löschen")

    if save_clicked:
        try:
            rule = {
                "id": rid,
                "module": module,
                "rule_group": group,
                "description": description,
                "priority": int(priority),
                "active": active,
                "stop_after_match": stop,
                "when": json.loads(when_raw),
                "then": json.loads(then_raw),
            }
            kb_json.upsert_inference_rule(rule)
            st.success("Regel gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(f"Regel konnte nicht gespeichert werden: {e}")

    if delete_clicked and selected is not None:
        kb_json.delete_inference_rule(selected.get("id"))
        st.warning("Regel gelöscht.")
        st.rerun()

    with st.expander("Regel-Beispiel"):
        st.code(json.dumps({
            "when": {"all": [{"fact": "topic", "operator": "equals", "value": "eduroam"}], "any": [{"fact": "os", "operator": "equals", "value": "windows"}]},
            "then": [{"type": "answer", "text": "Beispielantwort"}],
        }, ensure_ascii=False, indent=2), language="json")


# ============================================================
# Admin: JSON-Dateien direkt bearbeiten
# ============================================================


def admin_json_files() -> None:
    st.header("Admin · JSON-Dateien")
    render_view_info(
        "JSON-Dateien",
        "Diese Ansicht ist für technische Kontrolle gedacht. Hier kannst du die Dateien aus dem austauschbaren Rule-Engine-Ordner direkt ansehen, herunterladen oder bearbeiten. Aggregierte Einträge wie inference_rules werden aus den Unterordnern rules/, sources/ und step_packages/ zusammengeführt.",
    )
    file_name = st.selectbox("Datei", list(kb_json.FILES.keys()), key="admin_json_file_select")
    data = kb_json.load_json(file_name, [] if file_name in {"inference_rules", "step_packages", "sources"} else {})
    raw = st.text_area("JSON-Inhalt", value=json.dumps(data, ensure_ascii=False, indent=2), height=520, key=f"admin_json_raw_{file_name}")
    col1, col2 = st.columns(2)
    if col1.button("JSON speichern", key=f"admin_json_save_{file_name}"):
        try:
            parsed = json.loads(raw)
            kb_json.save_json(file_name, parsed)
            st.success("JSON gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(f"Ungültiges JSON: {e}")
    col2.download_button("Datei herunterladen", data=json.dumps(data, ensure_ascii=False, indent=2), file_name=f"{file_name}.json", mime="application/json", key=f"admin_json_download_{file_name}")


# ============================================================
# Admin: Inferenz-Test
# ============================================================


def admin_inference_test() -> None:
    st.header("Admin · Inferenz-Test")
    render_view_info(
        "Inferenz-Test",
        "Hier testest du die Inferenzregeln mit manuell eingegebenen Fakten. So kannst du prüfen, welche Regeln matchen, welche Antworten erzeugt werden und ob der Regeltrace plausibel ist.",
    )
    facts_raw = st.text_area("Fakten als JSON", value=json.dumps({"topic": "eduroam", "intent": "setup", "os": "windows", "internet_available": False}, ensure_ascii=False, indent=2), height=250, key="admin_test_facts")
    if st.button("Test ausführen", key="admin_test_run"):
        try:
            facts = json.loads(facts_raw)
            result = inference_engine.run_inference(facts)
            st.subheader("Ausgabe")
            st.write(inference_engine.renderable_summary(result))
            st.subheader("Gematchte Regeln")
            st.json(result.get("matched_rules", []))
            with st.expander("Trace"):
                st.json(result.get("evaluated_rules", []))
        except Exception as e:
            st.error(f"Test fehlgeschlagen: {e}")




# ============================================================
# Admin: Entscheidungsnetz-Editor
# ============================================================

NODE_TYPES = ["start", "question", "condition", "step", "solution", "redirect", "end"]
EDGE_OPERATORS = ["equals", "not_equals", "contains", "in", "exists", "not_exists"]


def _node_format(node: dict[str, Any] | None) -> str:
    if node is None:
        return "Kein Knoten ausgewählt"
    return f"{node.get('id')} · {node.get('type')} · {node.get('label','')}"


def _edge_format(edge: dict[str, Any] | None) -> str:
    if edge is None:
        return "Keine Verbindung ausgewählt"
    return f"{edge.get('id')} · {edge.get('source')} → {edge.get('target')} · {edge.get('label','')}"


def _slugify(value: Any, default: str = "item") -> str:
    text = str(value or "").strip().lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = re.sub(r"[^a-z0-9_\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or default


def _unique_id(existing: set[str], base: str) -> str:
    base = _slugify(base)
    if base not in existing:
        return base
    idx = 2
    while f"{base}_{idx}" in existing:
        idx += 1
    return f"{base}_{idx}"


def _find_node(graph: dict[str, Any], node_id: str | None) -> dict[str, Any] | None:
    if not node_id:
        return None
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


def _find_edge(graph: dict[str, Any], edge_id: str | None) -> dict[str, Any] | None:
    if not edge_id:
        return None
    for edge in graph.get("edges", []):
        if edge.get("id") == edge_id:
            return edge
    return None


def _current_selection(graph_id: str) -> tuple[str | None, str | None]:
    return (
        st.session_state.get(f"graph_selected_type_{graph_id}"),
        st.session_state.get(f"graph_selected_id_{graph_id}"),
    )


def _set_selection(graph_id: str, selected_type: str | None, selected_id: str | None, *, from_canvas: bool = False) -> None:
    """Speichert die aktuelle Auswahl im Session-State.

    from_canvas=True wird gesetzt, wenn die Auswahl direkt aus dem
    streamlit-flow-Canvas kommt. Dadurch kann das manuelle Dropdown im
    Eigenschaften-Panel im nächsten Render-Schritt sauber synchronisiert
    werden. Ohne diese Synchronisierung würde Streamlit wegen des stabilen
    Widget-Keys oft den alten Dropdown-Wert behalten und die Canvas-Auswahl
    direkt wieder überschreiben.
    """
    st.session_state[f"graph_selected_type_{graph_id}"] = selected_type
    st.session_state[f"graph_selected_id_{graph_id}"] = selected_id
    if from_canvas:
        st.session_state[f"graph_canvas_selection_dirty_{graph_id}"] = True


def _get_obj_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _extract_position(node_obj: Any) -> dict[str, int]:
    pos = _get_obj_attr(node_obj, "pos", None)
    if pos is None:
        pos = _get_obj_attr(node_obj, "position", None)
    if isinstance(pos, dict):
        return {"x": int(pos.get("x", 0)), "y": int(pos.get("y", 0))}
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        return {"x": int(pos[0]), "y": int(pos[1])}
    return {"x": 0, "y": 0}


def _graph_node_ids(graph: dict[str, Any]) -> list[str]:
    return [str(n.get("id")) for n in graph.get("nodes", []) if n.get("id")]


def _graph_edge_ids(graph: dict[str, Any]) -> list[str]:
    return [str(e.get("id")) for e in graph.get("edges", []) if e.get("id")]


def graphviz_dot(graph: dict[str, Any]) -> str:
    def q(value: Any) -> str:
        return str(value).replace('"', '\\"')
    lines = ["digraph G {", "rankdir=LR;", "node [shape=box, style=rounded, fontname=Arial];"]
    for node in graph.get("nodes", []):
        node_id = node.get("id")
        node_type = node.get("type", "condition")
        label = f"{node.get('label', node_id)}\\n[{node_type}]"
        shape = "oval" if node_type == "start" else "diamond" if node_type in {"question", "condition"} else "box"
        lines.append(f'"{q(node_id)}" [label="{q(label)}", shape={shape}];')
    for edge in graph.get("edges", []):
        label = edge.get("label", "")
        lines.append(f'"{q(edge.get("source"))}" -> "{q(edge.get("target"))}" [label="{q(label)}"];')
    lines.append("}")
    return "\n".join(lines)


def graph_to_flow_state(graph: dict[str, Any]):
    nodes = []
    edges = []
    graph_id = graph.get("id")
    selected_type, selected_id = _current_selection(graph_id) if graph_id else (None, None)
    for node in graph.get("nodes", []):
        pos = node.get("position") or {}
        x = pos.get("x", 0) if isinstance(pos, dict) else 0
        y = pos.get("y", 0) if isinstance(pos, dict) else 0
        node_type = node.get("type", "condition")
        flow_type = "input" if node_type == "start" else "output" if node_type in {"step", "solution", "redirect", "end"} else "default"
        content = f"**{node.get('label', node.get('id'))}**\n\n`{node_type}`"
        if node_type == "step":
            content += f"\n\n{node.get('service_key','')} / {node.get('system_key','')} / Schritt {node.get('step_number','')}"
        if node_type == "solution" and node.get("solution_text"):
            content += f"\n\n{str(node.get('solution_text'))[:70]}"
        nodes.append(
            StreamlitFlowNode(
                str(node.get("id")),
                (x, y),
                {"content": content},
                flow_type,
                "right",
                "left",
                selected=(selected_type == "node" and selected_id == str(node.get("id"))),
                selectable=True,
                connectable=True,
                deletable=True,
            )
        )
    for edge in graph.get("edges", []):
        edges.append(
            StreamlitFlowEdge(
                str(edge.get("id")),
                str(edge.get("source")),
                str(edge.get("target")),
                label=str(edge.get("label", "")),
                animated=True,
                selected=(selected_type == "edge" and selected_id == str(edge.get("id"))),
                deletable=True,
                focusable=True,
                marker_end={"type": "arrowclosed"},
            )
        )
    return StreamlitFlowState(nodes, edges)


def _read_canvas_selection(flow_state: Any) -> tuple[str | None, str | None]:
    """Versucht, einen Klick/Selection aus streamlit-flow zu erkennen.

    In aktuellen streamlit-flow-Versionen wird die angeklickte Node/Edge vor
    allem als ``selected_id`` im zurückgegebenen StreamlitFlowState gespeichert.
    Ältere Versionen bzw. Beispiele verwenden teils andere Feldnamen. Deshalb
    prüfen wir mehrere Varianten und klassifizieren die ID anhand der vorhandenen
    Node- und Edge-Listen.
    """

    def _clean_id(value: Any) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, dict):
            value = (
                value.get("id")
                or value.get("node")
                or value.get("node_id")
                or value.get("edge")
                or value.get("edge_id")
                or value.get("selected_id")
                or value.get("selectedId")
            )
        if value is None or value == "":
            return None
        return str(value)

    node_ids = {str(_get_obj_attr(node_obj, "id", "")) for node_obj in (_get_obj_attr(flow_state, "nodes", []) or [])}
    edge_ids = {str(_get_obj_attr(edge_obj, "id", "")) for edge_obj in (_get_obj_attr(flow_state, "edges", []) or [])}

    # Wichtigster Fall bei streamlit-flow >= 1.x: selected_id.
    for attr in ["selected_id", "selectedId"]:
        selected = _clean_id(_get_obj_attr(flow_state, attr, None))
        if selected:
            if selected in node_ids:
                return "node", selected
            if selected in edge_ids:
                return "edge", selected

    # Fallback-Feldnamen aus älteren Versionen / Beispielen.
    for attr in ["selected_node", "selected_node_id", "clicked_node", "clicked_node_id", "node_on_click"]:
        value = _clean_id(_get_obj_attr(flow_state, attr, None))
        if value:
            return "node", value
    for attr in ["selected_edge", "selected_edge_id", "clicked_edge", "clicked_edge_id", "edge_on_click"]:
        value = _clean_id(_get_obj_attr(flow_state, attr, None))
        if value:
            return "edge", value

    # Weitere Fallbacks, falls ausgewählte Elemente als Flag markiert sind.
    for node_obj in _get_obj_attr(flow_state, "nodes", []) or []:
        if bool(_get_obj_attr(node_obj, "selected", False)):
            return "node", str(_get_obj_attr(node_obj, "id", ""))
    for edge_obj in _get_obj_attr(flow_state, "edges", []) or []:
        if bool(_get_obj_attr(edge_obj, "selected", False)):
            return "edge", str(_get_obj_attr(edge_obj, "id", ""))
    return None, None


def apply_flow_state_to_graph(graph: dict[str, Any], flow_state: Any) -> dict[str, Any]:
    graph = dict(graph)
    nodes = [dict(n) for n in graph.get("nodes", [])]
    edges = [dict(e) for e in graph.get("edges", [])]
    node_by = {n.get("id"): n for n in nodes}
    edge_ids = {e.get("id") for e in edges}

    for node_obj in _get_obj_attr(flow_state, "nodes", []) or []:
        node_id = str(_get_obj_attr(node_obj, "id", ""))
        if not node_id:
            continue
        if node_id in node_by:
            node_by[node_id]["position"] = _extract_position(node_obj)
        else:
            nodes.append({"id": node_id, "type": "condition", "label": node_id, "position": _extract_position(node_obj)})

    for edge_obj in _get_obj_attr(flow_state, "edges", []) or []:
        edge_id = str(_get_obj_attr(edge_obj, "id", ""))
        source = str(_get_obj_attr(edge_obj, "source", ""))
        target = str(_get_obj_attr(edge_obj, "target", ""))
        if not source or not target:
            continue
        if not edge_id:
            edge_id = f"{source}__to__{target}"
        if edge_id not in edge_ids:
            edges.append({"id": edge_id, "source": source, "target": target, "label": "neu", "priority": 100, "condition": {}})
            edge_ids.add(edge_id)

    graph["nodes"] = nodes
    graph["edges"] = edges
    return graph


def _auto_layout_graph(graph: dict[str, Any]) -> dict[str, Any]:
    graph = dict(graph)
    nodes = [dict(n) for n in graph.get("nodes", [])]
    edges = graph.get("edges", [])
    start = graph.get("start_node_id") or "start"
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        outgoing.setdefault(str(edge.get("source")), []).append(str(edge.get("target")))
    levels: dict[str, int] = {}
    queue = [(start, 0)]
    while queue:
        node_id, level = queue.pop(0)
        if node_id in levels and levels[node_id] <= level:
            continue
        levels[node_id] = level
        for target in outgoing.get(node_id, []):
            queue.append((target, level + 1))
    for node in nodes:
        levels.setdefault(str(node.get("id")), 0)
    by_level: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        by_level.setdefault(levels.get(str(node.get("id")), 0), []).append(node)
    for level, level_nodes in by_level.items():
        for idx, node in enumerate(sorted(level_nodes, key=lambda n: str(n.get("id")))):
            node["position"] = {"x": int(level * 260), "y": int(idx * 135)}
    graph["nodes"] = nodes
    return graph


def _condition_to_simple(condition: Any) -> tuple[str, str, str, str]:
    if not isinstance(condition, dict) or not condition:
        return "none", "", "equals", ""
    if "all" in condition or "any" in condition:
        return "json", "", "equals", json.dumps(condition, ensure_ascii=False, indent=2)
    fact = condition.get("fact", condition.get("field", ""))
    operator = condition.get("operator", "equals")
    value = condition.get("value", "")
    return "simple", str(fact), str(operator), str(value)


def _build_condition(mode: str, fact: str, operator: str, value: str, raw_json: str) -> dict[str, Any]:
    if mode == "none":
        return {}
    if mode == "json":
        return json.loads(raw_json) if raw_json.strip() else {}
    cond: dict[str, Any] = {"fact": fact.strip(), "operator": operator}
    if operator not in {"exists", "not_exists"}:
        # Komma-getrennte Liste für operator=in komfortabel unterstützen.
        if operator == "in":
            cond["value"] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            cond["value"] = value.strip()
    return cond


def _graph_quick_add_node(graph: dict[str, Any], node_type: str = "question", source_id: str | None = None) -> dict[str, Any]:
    graph = dict(graph)
    nodes = [dict(n) for n in graph.get("nodes", [])]
    existing = {str(n.get("id")) for n in nodes}
    node_id = _unique_id(existing, f"{node_type}_node")
    base_x, base_y = 120, 120
    source = _find_node(graph, source_id)
    if source and isinstance(source.get("position"), dict):
        base_x = int(source["position"].get("x", 0)) + 280
        base_y = int(source["position"].get("y", 0))
    else:
        base_y = len(nodes) * 95
    nodes.append({"id": node_id, "type": node_type, "label": f"Neuer {node_type}-Knoten", "question": "", "position": {"x": base_x, "y": base_y}})
    graph["nodes"] = nodes
    return graph


def _graph_quick_add_path(graph: dict[str, Any], source_id: str | None, target_type: str = "question") -> tuple[dict[str, Any], str, str]:
    graph = dict(graph)
    if not source_id:
        source_id = graph.get("start_node_id") or (graph.get("nodes", [{}])[0].get("id") if graph.get("nodes") else "start")
    graph = _graph_quick_add_node(graph, target_type, source_id=source_id)
    target_id = str(graph["nodes"][-1]["id"])
    edge_existing = {str(e.get("id")) for e in graph.get("edges", [])}
    edge_id = _unique_id(edge_existing, f"{source_id}_to_{target_id}")
    graph.setdefault("edges", []).append({"id": edge_id, "source": source_id, "target": target_id, "label": "neuer Pfad", "priority": 100, "condition": {}})
    return graph, target_id, edge_id


def _rename_node_in_graph(graph: dict[str, Any], old_id: str, new_id: str) -> dict[str, Any]:
    if old_id == new_id:
        return graph
    graph = dict(graph)
    for node in graph.get("nodes", []):
        if node.get("id") == old_id:
            node["id"] = new_id
    for edge in graph.get("edges", []):
        if edge.get("source") == old_id:
            edge["source"] = new_id
        if edge.get("target") == old_id:
            edge["target"] = new_id
    if graph.get("start_node_id") == old_id:
        graph["start_node_id"] = new_id
    return graph


def render_graph_canvas_interactive(graph: dict[str, Any]) -> Any:
    st.markdown('<div class="canvas-help">Klicke einen Knoten oder eine Verbindung an, bearbeite die Auswahl rechts und speichere. Neue Knoten/Pfade kannst du über die Plus-Buttons anlegen.</div>', unsafe_allow_html=True)
    if STREAMLIT_FLOW_AVAILABLE:
        state_key = f"flow_state_{graph.get('id')}"
        graph_signature = json.dumps({"id": graph.get("id"), "nodes": graph.get("nodes", []), "edges": graph.get("edges", [])}, sort_keys=True, ensure_ascii=False)
        sig_key = f"flow_sig_{graph.get('id')}"
        if state_key not in st.session_state or st.session_state.get(sig_key) != graph_signature:
            st.session_state[state_key] = graph_to_flow_state(graph)
            st.session_state[sig_key] = graph_signature
        try:
            st.session_state[state_key] = streamlit_flow(
                f"decision_flow_visual_editor_{graph.get('id')}",
                st.session_state[state_key],
                layout=TreeLayout(direction="right") if TreeLayout else None,
                fit_view=True,
                height=650,
                enable_node_menu=True,
                enable_edge_menu=True,
                enable_pane_menu=True,
                get_edge_on_click=True,
                get_node_on_click=True,
                show_minimap=True,
                hide_watermark=True,
                allow_new_edges=True,
                min_zoom=0.1,
            )
        except TypeError:
            # Fallback für ältere streamlit-flow-Versionen mit weniger Parametern.
            st.session_state[state_key] = streamlit_flow(
                f"decision_flow_visual_editor_{graph.get('id')}",
                st.session_state[state_key],
                height=650,
                fit_view=True,
            )
        sel_type, sel_id = _read_canvas_selection(st.session_state[state_key])
        if sel_type and sel_id:
            _set_selection(graph.get("id"), sel_type, sel_id, from_canvas=True)
        return st.session_state[state_key]
    st.info("Für den interaktiven Canvas installiere: py -m pip install streamlit-flow-component. Bis dahin wird eine Graphviz-Vorschau angezeigt.")
    st.graphviz_chart(graphviz_dot(graph), use_container_width=True)
    return None


def _node_properties_panel(graph: dict[str, Any], node: dict[str, Any]) -> None:
    graph_id = graph.get("id")
    st.markdown('<div class="selection-pill">Knoten ausgewählt</div>', unsafe_allow_html=True)
    st.markdown(f"**{node.get('label', node.get('id'))}**")
    st.caption(f"ID: {node.get('id')} · Typ: {node.get('type')}")

    with st.form(f"node_prop_form_{graph_id}_{node.get('id')}"):
        old_id = str(node.get("id"))
        node_id = st.text_input("Knoten-ID", value=old_id, key=f"node_prop_id_{graph_id}_{old_id}")
        node_type = st.selectbox("Knotentyp", NODE_TYPES, index=NODE_TYPES.index(node.get("type", "condition")) if node.get("type") in NODE_TYPES else 2, key=f"node_prop_type_{graph_id}_{old_id}")
        label = st.text_input("Label", value=node.get("label", ""), key=f"node_prop_label_{graph_id}_{old_id}")
        question = st.text_area("Frage / Beschreibung / Lösungstext", value=node.get("question", node.get("solution_text", "")), height=120, key=f"node_prop_question_{graph_id}_{old_id}")

        service_options = [""] + [s.get("key") for s in kb_json.get_services(active_only=False)]
        current_service = node.get("service_key", "")
        service_index = service_options.index(current_service) if current_service in service_options else 0
        service_key = st.selectbox("Service-Key", service_options, index=service_index, key=f"node_prop_service_{graph_id}_{old_id}")

        system_options = [""]
        if service_key:
            system_options += [s.get("key") for s in kb_json.get_systems(service_key, active_only=False)]
        current_system = node.get("system_key", "")
        system_index = system_options.index(current_system) if current_system in system_options else 0
        system_key = st.selectbox("System-Key", system_options, index=system_index, key=f"node_prop_system_{graph_id}_{old_id}")

        step_options = [0]
        if service_key and system_key:
            step_options += [int(s.get("number")) for s in kb_json.get_steps(service_key, system_key, active_only=False)]
        current_step = int(node.get("step_number", 0) or 0)
        step_index = step_options.index(current_step) if current_step in step_options else 0
        step_number = st.selectbox("Schritt", step_options, index=step_index, format_func=lambda x: "Kein Schritt" if x == 0 else f"Schritt {x}", key=f"node_prop_step_{graph_id}_{old_id}")

        target_service_key = st.text_input("Redirect: Ziel-Service-Key", value=node.get("target_service_key", ""), key=f"node_prop_target_service_{graph_id}_{old_id}")
        target_graph_id = st.text_input("Redirect: Ziel-Graph-ID", value=node.get("target_graph_id", ""), key=f"node_prop_target_graph_{graph_id}_{old_id}")

        col1, col2 = st.columns(2)
        save = col1.form_submit_button("Knoten speichern")
        delete = col2.form_submit_button("Knoten löschen")

    if save:
        try:
            node_id_clean = _slugify(node_id, "node")
            existing_ids = {n.get("id") for n in graph.get("nodes", []) if n.get("id") != old_id}
            if node_id_clean in existing_ids:
                st.error("Diese Knoten-ID existiert bereits.")
                return
            updated_graph = _rename_node_in_graph(graph, old_id, node_id_clean)
            updated_node = _find_node(updated_graph, node_id_clean) or {}
            updated_node.update({"id": node_id_clean, "type": node_type, "label": label or node_id_clean})
            updated_node.pop("question", None)
            updated_node.pop("solution_text", None)
            if question:
                if node_type == "solution":
                    updated_node["solution_text"] = question
                else:
                    updated_node["question"] = question
            for key in ["service_key", "system_key", "step_number", "target_service_key", "target_graph_id"]:
                updated_node.pop(key, None)
            if service_key:
                updated_node["service_key"] = service_key
            if system_key:
                updated_node["system_key"] = system_key
            if step_number:
                updated_node["step_number"] = int(step_number)
            if target_service_key:
                updated_node["target_service_key"] = target_service_key.strip()
            if target_graph_id:
                updated_node["target_graph_id"] = target_graph_id.strip()
            # Replace node in graph.
            updated_nodes = []
            for n in updated_graph.get("nodes", []):
                updated_nodes.append(updated_node if n.get("id") == node_id_clean else n)
            updated_graph["nodes"] = updated_nodes
            kb_json.upsert_decision_graph(updated_graph)
            _set_selection(graph_id, "node", node_id_clean)
            st.success("Knoten gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(f"Knoten konnte nicht gespeichert werden: {e}")

    if delete:
        if node.get("id") == graph.get("start_node_id"):
            st.error("Der Start-Knoten kann nicht gelöscht werden. Ändere zuerst den Start-Knoten in den Graph-Stammdaten.")
        else:
            kb_json.delete_graph_node(graph_id, node.get("id"))
            _set_selection(graph_id, None, None)
            st.warning("Knoten gelöscht.")
            st.rerun()

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("+ Pfad von hier", key=f"quick_path_from_{graph_id}_{node.get('id')}"):
        updated, target_id, edge_id = _graph_quick_add_path(graph, node.get("id"), "question")
        kb_json.upsert_decision_graph(updated)
        _set_selection(graph_id, "edge", edge_id)
        st.rerun()
    if c2.button("+ Ziel-Lösung", key=f"quick_solution_from_{graph_id}_{node.get('id')}"):
        updated, target_id, edge_id = _graph_quick_add_path(graph, node.get("id"), "solution")
        # Make label clearer for the new solution node.
        for n in updated.get("nodes", []):
            if n.get("id") == target_id:
                n["label"] = "Neue Lösung"
                n["solution_text"] = "Hier Lösungstext eintragen."
        kb_json.upsert_decision_graph(updated)
        _set_selection(graph_id, "node", target_id)
        st.rerun()


def _edge_properties_panel(graph: dict[str, Any], edge: dict[str, Any]) -> None:
    graph_id = graph.get("id")
    st.markdown('<div class="selection-pill">Verbindung ausgewählt</div>', unsafe_allow_html=True)
    st.markdown(f"**{edge.get('source')} → {edge.get('target')}**")
    st.caption(f"ID: {edge.get('id')}")
    node_ids = _graph_node_ids(graph)
    mode, fact, operator, value_or_raw = _condition_to_simple(edge.get("condition", {}))

    with st.form(f"edge_prop_form_{graph_id}_{edge.get('id')}"):
        old_id = str(edge.get("id"))
        edge_id = st.text_input("Edge-ID", value=old_id, key=f"edge_prop_id_{graph_id}_{old_id}")
        source = st.selectbox("Quelle", node_ids, index=node_ids.index(edge.get("source")) if edge.get("source") in node_ids else 0, key=f"edge_prop_source_{graph_id}_{old_id}")
        target = st.selectbox("Ziel", node_ids, index=node_ids.index(edge.get("target")) if edge.get("target") in node_ids else 0, key=f"edge_prop_target_{graph_id}_{old_id}")
        label = st.text_input("Pfad-Label", value=edge.get("label", ""), key=f"edge_prop_label_{graph_id}_{old_id}")
        priority = st.number_input("Priorität", min_value=0, step=1, value=int(edge.get("priority", 100)), key=f"edge_prop_priority_{graph_id}_{old_id}")
        condition_mode = st.radio("Bedingung", ["none", "simple", "json"], index=["none", "simple", "json"].index(mode), format_func=lambda x: {"none":"Keine Bedingung", "simple":"Einfache Bedingung", "json":"Erweiterte JSON-Bedingung"}[x], key=f"edge_prop_cond_mode_{graph_id}_{old_id}")
        cond_fact = fact
        cond_operator = operator if operator in EDGE_OPERATORS else "equals"
        cond_value = value_or_raw if mode == "simple" else ""
        raw_json = value_or_raw if mode == "json" else json.dumps(edge.get("condition", {}), ensure_ascii=False, indent=2)
        if condition_mode == "simple":
            cond_fact = st.text_input("Fakt/Feld", value=cond_fact, placeholder="z. B. topic, service, os, intent", key=f"edge_prop_fact_{graph_id}_{old_id}")
            cond_operator = st.selectbox("Operator", EDGE_OPERATORS, index=EDGE_OPERATORS.index(cond_operator), key=f"edge_prop_operator_{graph_id}_{old_id}")
            if cond_operator not in {"exists", "not_exists"}:
                cond_value = st.text_input("Wert", value=cond_value, placeholder="z. B. eduroam oder windows", key=f"edge_prop_value_{graph_id}_{old_id}")
        elif condition_mode == "json":
            raw_json = st.text_area("Condition JSON", value=raw_json, height=160, key=f"edge_prop_raw_{graph_id}_{old_id}")
        col1, col2 = st.columns(2)
        save = col1.form_submit_button("Verbindung speichern")
        delete = col2.form_submit_button("Verbindung löschen")

    if save:
        try:
            new_edge_id = _slugify(edge_id or f"{source}_to_{target}", "edge")
            condition = _build_condition(condition_mode, cond_fact, cond_operator, cond_value, raw_json)
            updated_edges = []
            replaced = False
            for e in graph.get("edges", []):
                if e.get("id") == old_id:
                    updated_edges.append({"id": new_edge_id, "source": source, "target": target, "label": label, "priority": int(priority), "condition": condition})
                    replaced = True
                else:
                    updated_edges.append(e)
            if not replaced:
                updated_edges.append({"id": new_edge_id, "source": source, "target": target, "label": label, "priority": int(priority), "condition": condition})
            updated_graph = dict(graph)
            updated_graph["edges"] = updated_edges
            kb_json.upsert_decision_graph(updated_graph)
            _set_selection(graph_id, "edge", new_edge_id)
            st.success("Verbindung gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(f"Verbindung konnte nicht gespeichert werden: {e}")

    if delete:
        kb_json.delete_graph_edge(graph_id, edge.get("id"))
        _set_selection(graph_id, None, None)
        st.warning("Verbindung gelöscht.")
        st.rerun()


def _empty_properties_panel(graph: dict[str, Any]) -> None:
    graph_id = graph.get("id")
    st.markdown('<div class="prop-title">Eigenschaften</div>', unsafe_allow_html=True)
    st.markdown('<div class="prop-muted">Wähle im Canvas einen Knoten oder Pfad aus. Alternativ kannst du über die Schnellaktionen neue Elemente erzeugen.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("+ Knoten", key=f"empty_add_node_{graph_id}"):
        updated = _graph_quick_add_node(graph, "question")
        kb_json.upsert_decision_graph(updated)
        _set_selection(graph_id, "node", updated["nodes"][-1]["id"])
        st.rerun()
    start_id = graph.get("start_node_id") or (graph.get("nodes", [{}])[0].get("id") if graph.get("nodes") else None)
    if c2.button("+ Pfad", key=f"empty_add_path_{graph_id}"):
        updated, target_id, edge_id = _graph_quick_add_path(graph, start_id, "question")
        kb_json.upsert_decision_graph(updated)
        _set_selection(graph_id, "edge", edge_id)
        st.rerun()


def render_graph_properties_panel(graph: dict[str, Any]) -> None:
    graph_id = graph.get("id")
    selected_type, selected_id = _current_selection(graph_id)

    # Manuelle Auswahl bleibt als Fallback vorhanden, aber kompakt im Eigenschaftenbereich.
    selection_options = ["Keine Auswahl"] + [f"node::{n}" for n in _graph_node_ids(graph)] + [f"edge::{e}" for e in _graph_edge_ids(graph)]
    current_value = "Keine Auswahl"
    if selected_type and selected_id:
        candidate = f"{selected_type}::{selected_id}"
        if candidate in selection_options:
            current_value = candidate
    manual_key = f"graph_manual_selection_{graph_id}"

    # Wenn die Auswahl gerade aus dem Canvas kam, muss der Selectbox-Wert
    # vor dem Erzeugen des Widgets synchronisiert werden. Sonst behält
    # Streamlit den alten Wert der Selectbox und überschreibt die Canvas-Auswahl.
    if st.session_state.pop(f"graph_canvas_selection_dirty_{graph_id}", False):
        st.session_state[manual_key] = current_value

    selected_raw = st.selectbox(
        "Auswahl",
        selection_options,
        index=selection_options.index(current_value),
        format_func=lambda x: "Keine Auswahl" if x == "Keine Auswahl" else ("Knoten: " + x.split("::",1)[1] if x.startswith("node::") else "Pfad: " + x.split("::",1)[1]),
        key=manual_key,
    )
    if selected_raw == "Keine Auswahl":
        selected_type, selected_id = None, None
        _set_selection(graph_id, None, None)
    else:
        selected_type, selected_id = selected_raw.split("::", 1)
        _set_selection(graph_id, selected_type, selected_id)

    if selected_type == "node":
        node = _find_node(graph, selected_id)
        if node:
            _node_properties_panel(graph, node)
        else:
            _empty_properties_panel(graph)
    elif selected_type == "edge":
        edge = _find_edge(graph, selected_id)
        if edge:
            _edge_properties_panel(graph, edge)
        else:
            _empty_properties_panel(graph)
    else:
        _empty_properties_panel(graph)


def _graph_toolbar(graph: dict[str, Any], flow_state: Any = None) -> None:
    graph_id = graph.get("id")
    selected_type, selected_id = _current_selection(graph_id)
    st.markdown('<div class="graph-toolbar">', unsafe_allow_html=True)
    cols = st.columns([1, 1, 1, 1, 1, 1.2])
    if cols[0].button("+ Knoten", key=f"toolbar_add_node_{graph_id}"):
        updated = _graph_quick_add_node(graph, "question", source_id=selected_id if selected_type == "node" else None)
        kb_json.upsert_decision_graph(updated)
        _set_selection(graph_id, "node", updated["nodes"][-1]["id"])
        st.rerun()
    if cols[1].button("+ Pfad", key=f"toolbar_add_path_{graph_id}"):
        source_id = selected_id if selected_type == "node" else graph.get("start_node_id")
        updated, target_id, edge_id = _graph_quick_add_path(graph, source_id, "question")
        kb_json.upsert_decision_graph(updated)
        _set_selection(graph_id, "edge", edge_id)
        st.rerun()
    if cols[2].button("Duplizieren", key=f"toolbar_duplicate_{graph_id}"):
        if selected_type == "node" and selected_id:
            source = _find_node(graph, selected_id)
            if source:
                updated = dict(graph)
                nodes = [dict(n) for n in graph.get("nodes", [])]
                new_node = dict(source)
                new_node["id"] = _unique_id({n.get("id") for n in nodes}, f"{source.get('id')}_copy")
                new_node["label"] = f"{source.get('label', source.get('id'))} Kopie"
                pos = dict(new_node.get("position", {})) if isinstance(new_node.get("position"), dict) else {"x": 0, "y": 0}
                new_node["position"] = {"x": int(pos.get("x", 0)) + 80, "y": int(pos.get("y", 0)) + 80}
                nodes.append(new_node)
                updated["nodes"] = nodes
                kb_json.upsert_decision_graph(updated)
                _set_selection(graph_id, "node", new_node["id"])
                st.rerun()
        elif selected_type == "edge" and selected_id:
            source_edge = _find_edge(graph, selected_id)
            if source_edge:
                updated = dict(graph)
                edges = [dict(e) for e in graph.get("edges", [])]
                new_edge = dict(source_edge)
                new_edge["id"] = _unique_id({e.get("id") for e in edges}, f"{source_edge.get('id')}_copy")
                new_edge["label"] = f"{source_edge.get('label', '')} Kopie".strip()
                edges.append(new_edge)
                updated["edges"] = edges
                kb_json.upsert_decision_graph(updated)
                _set_selection(graph_id, "edge", new_edge["id"])
                st.rerun()
        else:
            st.warning("Wähle zuerst einen Knoten oder Pfad aus.")
    if cols[3].button("Löschen", key=f"toolbar_delete_{graph_id}"):
        if selected_type == "node" and selected_id:
            if selected_id == graph.get("start_node_id"):
                st.error("Start-Knoten kann nicht gelöscht werden.")
            else:
                kb_json.delete_graph_node(graph_id, selected_id)
                _set_selection(graph_id, None, None)
                st.rerun()
        elif selected_type == "edge" and selected_id:
            kb_json.delete_graph_edge(graph_id, selected_id)
            _set_selection(graph_id, None, None)
            st.rerun()
    if cols[4].button("Auto-Layout", key=f"toolbar_auto_layout_{graph_id}"):
        kb_json.upsert_decision_graph(_auto_layout_graph(graph))
        st.rerun()
    if cols[5].button("Canvas speichern", key=f"toolbar_apply_canvas_{graph_id}"):
        if flow_state is None:
            st.info("Kein Canvas-State verfügbar.")
        else:
            try:
                updated = apply_flow_state_to_graph(graph, flow_state)
                kb_json.upsert_decision_graph(updated)
                st.success("Canvas-Änderungen gespeichert.")
                st.rerun()
            except Exception as e:
                st.error(f"Canvas konnte nicht gespeichert werden: {e}")
    st.markdown('</div>', unsafe_allow_html=True)


def _graph_meta_editor(selected_graph: dict[str, Any] | None) -> None:
    with st.expander("Graph-Stammdaten", expanded=selected_graph is None):
        with st.form("admin_graph_meta_form"):
            graph_id = st.text_input("Graph-ID", value="" if selected_graph is None else selected_graph.get("id", ""), key="admin_graph_id")
            name = st.text_input("Name", value="" if selected_graph is None else selected_graph.get("name", ""), key="admin_graph_name")
            description = st.text_area("Beschreibung", value="" if selected_graph is None else selected_graph.get("description", ""), key="admin_graph_description")
            start_node_id = st.text_input("Start-Knoten-ID", value="start" if selected_graph is None else selected_graph.get("start_node_id", "start"), key="admin_graph_start")
            active = st.checkbox("Aktiv", value=True if selected_graph is None else bool(selected_graph.get("active", True)), key="admin_graph_active")
            col_save, col_delete = st.columns(2)
            save_meta = col_save.form_submit_button("Graph speichern")
            delete_meta = col_delete.form_submit_button("Graph löschen")
        if save_meta:
            try:
                graph = selected_graph or {"nodes": [], "edges": []}
                graph = dict(graph)
                graph.update({"id": _slugify(graph_id, "graph"), "name": name, "description": description, "start_node_id": start_node_id.strip() or "start", "active": active})
                if not graph.get("nodes"):
                    graph["nodes"] = [{"id": "start", "type": "start", "label": "Start", "position": {"x": 0, "y": 0}}]
                kb_json.upsert_decision_graph(graph)
                st.success("Graph gespeichert.")
                st.rerun()
            except Exception as e:
                st.error(f"Speichern fehlgeschlagen: {e}")
        if delete_meta and selected_graph is not None:
            kb_json.delete_decision_graph(selected_graph.get("id"))
            st.warning("Graph gelöscht.")
            st.rerun()


def _graph_test_panel(graph: dict[str, Any]) -> None:
    with st.expander("Graph testen", expanded=False):
        sample = {"topic": "eduroam", "os": "windows", "intent": "login", "internet_available": True}
        facts_raw = st.text_area("Fakten als JSON", value=json.dumps(sample, ensure_ascii=False, indent=2), height=190, key=f"graph_test_facts_{graph.get('id')}")
        if st.button("Graph ausführen", key=f"graph_test_run_{graph.get('id')}"):
            try:
                facts = json.loads(facts_raw)
                result = decision_graph_engine.run_decision_graph(graph, facts)
                render_answer("Graph-Ausgabe", decision_graph_engine.render_summary(result))
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Pfad")
                    st.json(result.get("path", []))
                with col2:
                    st.subheader("Terminal / Status")
                    st.json({k: v for k, v in result.items() if k not in {"graph", "facts", "evaluated_edges", "path"}})
                with st.expander("Kanten-Trace"):
                    st.json(result.get("evaluated_edges", []))
            except Exception as e:
                st.error(f"Graph-Test fehlgeschlagen: {e}")


def _graph_json_panel(graph: dict[str, Any]) -> None:
    with st.expander("Graph-JSON anzeigen / bearbeiten", expanded=False):
        raw = st.text_area("Graph-JSON", value=json.dumps(graph, ensure_ascii=False, indent=2), height=520, key=f"admin_graph_json_raw_{graph.get('id')}")
        if st.button("Graph-JSON speichern", key=f"admin_graph_json_save_{graph.get('id')}"):
            try:
                parsed = json.loads(raw)
                kb_json.upsert_decision_graph(parsed)
                st.success("Graph-JSON gespeichert.")
                st.rerun()
            except Exception as e:
                st.error(f"Ungültiges Graph-JSON: {e}")


def admin_decision_graphs() -> None:
    st.header("Admin · Grafischer Entscheidungsnetz-Editor")
    render_view_info(
        "Grafischer Entscheidungsnetz-Editor",
        "Hier baust du Entscheidungswege als Knoten und Verbindungen. Klicke einen Knoten oder Pfad im Canvas an, bearbeite die Eigenschaften rechts und speichere anschließend. Die Struktur wird als JSON gespeichert und von der Rule Engine interpretiert.",
    )
    st.markdown("Wähle einen Graphen aus, klicke Knoten oder Pfade im Canvas an und bearbeite sie rechts im Eigenschaften-Panel. Gespeichert wird in `Rule Engine/decision_graphs.json`.")

    graphs = kb_json.load_decision_graphs(active_only=False)
    graph_options = [None] + graphs
    selected_graph = st.selectbox(
        "Entscheidungsnetz auswählen",
        graph_options,
        format_func=lambda g: "Neues Entscheidungsnetz anlegen" if g is None else f"{g.get('name')} ({g.get('id')})",
        key="admin_graph_select",
    )

    _graph_meta_editor(selected_graph)

    if selected_graph is None:
        st.info("Lege zuerst ein Entscheidungsnetz an oder wähle ein vorhandenes aus.")
        return

    graph = kb_json.get_decision_graph(selected_graph.get("id")) or selected_graph
    graph_id = graph.get("id")
    if f"graph_selected_type_{graph_id}" not in st.session_state:
        _set_selection(graph_id, "node", graph.get("start_node_id") or (graph.get("nodes", [{}])[0].get("id") if graph.get("nodes") else None))

    # Canvas links, Eigenschaften rechts.
    left, right = st.columns([2.15, 1], gap="large")

    with left:
        flow_state = render_graph_canvas_interactive(graph)
        _graph_toolbar(graph, flow_state)

    with right:
        st.markdown('<div class="prop-panel">', unsafe_allow_html=True)
        render_graph_properties_panel(graph)
        st.markdown('</div>', unsafe_allow_html=True)

    _graph_test_panel(kb_json.get_decision_graph(graph_id) or graph)
    _graph_json_panel(kb_json.get_decision_graph(graph_id) or graph)


# ============================================================
# App Routing
# ============================================================

with st.sidebar:
    st.markdown("## Einstellungen")
    view = st.selectbox("Ansicht", ["Nutzeroberfläche", "Admin: Dienste & Systeme", "Admin: Schritte & Lösungen", "Admin: Inferenzregeln", "Admin: Entscheidungsnetz", "Admin: JSON-Dateien", "Admin: Inferenz-Test"], key="sidebar_view")
    st.markdown("---")
    use_ollama = st.toggle("Ollama nutzen", value=False, key="sidebar_use_ollama")
    model = st.text_input("Ollama-Modell", value=DEFAULT_MODEL, key="sidebar_model")
    fallback = st.toggle("Fallback ohne Ollama nutzen", value=True, key="sidebar_fallback")
    if st.button("Ollama prüfen", key="sidebar_check_ollama"):
        if llm_ollama.ollama_available():
            st.success("Ollama ist erreichbar.")
        else:
            st.error("Ollama ist nicht erreichbar.")
    st.markdown("---")
    st.caption("JSON-Dateien liegen im Ordner `Rule Engine/` mit Unterordnern für Regeln, Quellen und Schrittpakete. Beim Speichern wird automatisch ein Backup angelegt.")

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
