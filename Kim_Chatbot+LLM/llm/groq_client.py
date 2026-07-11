# groq_client.py
# ============================================================
# Schnelle kostenlose/Open-Source-nahe LLM-Anbindung über Groq Cloud.
#
# Rolle des LLM im LogiBot:
# - Freitext in strukturierte Fakten übersetzen
# - Folgeantworten im Kontext der letzten Rückfrage interpretieren
# - regelbasierte Ergebnisse nutzerfreundlich formulieren
#
# Wichtig: Die Rule Engine entscheidet. Groq/LLM entscheidet NICHT fachlich.
# Der API-Key wird über GROQ_API_KEY, Streamlit-Secrets oder die Sidebar gesetzt.
# ============================================================

from __future__ import annotations

import json
import os
import re
from typing import Any

from storage import kb_loader as kb_json

DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"


# ============================================================
# Basisfunktionen
# ============================================================

def _load_dotenv_if_available() -> None:
    """Lädt optional eine lokale .env-Datei, falls python-dotenv installiert ist."""
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        # dotenv ist optional. Die App funktioniert auch ohne dieses Paket.
        pass


def _streamlit_session_api_key() -> str:
    """Liest einen vom Nutzer in der Streamlit-Sitzung eingetragenen Key.

    Wichtig für Streamlit Community Cloud:
    Der Key darf NICHT in os.environ geschrieben werden, weil os.environ pro
    Prozess global ist. Bei mehreren Nutzern könnte sonst versehentlich ein
    fremder Sitzungs-Key verwendet werden. st.session_state ist dagegen
    sitzungsbezogen.
    """
    try:
        import streamlit as st  # type: ignore

        return str(st.session_state.get("session_groq_api_key", "") or "").strip()
    except Exception:
        return ""


def _streamlit_secret_api_key() -> str:
    """Liest optional den App-weiten Key aus Streamlit Secrets.

    Dieser Weg ist für App-Betreiber gedacht. Für öffentliche Demos ist der
    benutzereigene Key in der Sidebar vorzuziehen.
    """
    try:
        import streamlit as st  # type: ignore

        return str(st.secrets.get("GROQ_API_KEY", "") or "").strip()
    except Exception:
        return ""


def configured_api_key_available(api_key: str | None = None) -> bool:
    """True, wenn für die aktuelle Anfrage irgendein Groq-Key verfügbar ist."""
    _load_dotenv_if_available()
    return bool(
        (api_key or "").strip()
        or _streamlit_session_api_key()
        or os.environ.get("GROQ_API_KEY", "").strip()
        or _streamlit_secret_api_key()
    )


def _api_key(api_key: str | None = None) -> str:
    _load_dotenv_if_available()
    # Priorität: explizit übergebener Key -> benutzereigener Streamlit-Session-Key
    # -> lokale/Cloud-Umgebungsvariable -> Streamlit Secret des App-Betreibers.
    key = (
        (api_key or "").strip()
        or _streamlit_session_api_key()
        or os.environ.get("GROQ_API_KEY", "").strip()
        or _streamlit_secret_api_key()
    )
    if not key:
        raise RuntimeError(
            "Groq API-Key fehlt. Trage deinen eigenen Key in der Sidebar ein "
            "oder hinterlege GROQ_API_KEY als Umgebungsvariable bzw. Streamlit Secret."
        )
    return key


def _safe_error_message(error: Exception) -> str:
    msg = str(error)
    # Sicherheitshalber keine langen Token-Fragmente anzeigen.
    msg = re.sub(r"gsk_[A-Za-z0-9_\-]{8,}", "gsk_***", msg)
    return msg


def groq_check(api_key: str | None = None, model: str | None = None) -> tuple[bool, str]:
    """Prüft SDK, API-Key, Modell und Netzwerk mit einer kompakten Diagnose."""
    try:
        chat(
            [{"role": "user", "content": "Antworte nur mit OK."}],
            model=model or DEFAULT_GROQ_MODEL,
            api_key=api_key,
            temperature=0.0,
            timeout=20,
        )
        return True, "Groq ist erreichbar und der API-Key funktioniert."
    except Exception as e:
        return False, _safe_error_message(e)


def groq_available(api_key: str | None = None, model: str | None = None) -> bool:
    """Prüft, ob SDK + API-Key grundsätzlich funktionieren."""
    ok, _message = groq_check(api_key=api_key, model=model)
    return ok


def chat(
    messages: list[dict[str, str]],
    model: str,
    *,
    json_mode: bool = False,
    temperature: float = 0.0,
    timeout: int = 60,
    api_key: str | None = None,
) -> str:
    """Chat-Completions-Aufruf über das offizielle Groq Python SDK."""
    try:
        from groq import Groq  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Das Paket 'groq' ist nicht installiert. Installiere es mit: py -m pip install groq"
        ) from e

    key = _api_key(api_key)
    client = Groq(api_key=key, timeout=timeout)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        # Groq unterstützt für geeignete Modelle OpenAI-kompatibles JSON mode.
        kwargs["response_format"] = {"type": "json_object"}

    try:
        completion = client.chat.completions.create(**kwargs)
        return (completion.choices[0].message.content or "").strip()
    except Exception as e:
        raise RuntimeError(f"Groq-Anfrage fehlgeschlagen: {e}") from e


def extract_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ============================================================
# Kontext für Prompts
# ============================================================

def _limit_text(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [gekürzt]"


def kb_context_for_prompt() -> str:
    """Kompakte Übersicht über Dienste/Systeme/Schritte für die Schritt-Erkennung."""
    lines: list[str] = []
    for service in kb_json.get_services(active_only=True):
        lines.append(f"Dienst: {service.get('key')} = {service.get('name')}")
        for system in service.get("systems", []):
            lines.append(f"  System: {system.get('key')} = {system.get('name')}")
            for step in system.get("steps", []):
                lines.append(
                    f"    Schritt {step.get('number')}: {step.get('phase')} | "
                    f"{step.get('title')} | Keywords: {', '.join(step.get('keywords', []))}"
                )
    return _limit_text("\n".join(lines), 12000)


def fact_context_for_prompt() -> str:
    """Kompakte Übersicht über erlaubte Fakten/Werte aus der Rule Engine."""
    catalog = kb_json.load_fact_catalog()
    global_blocks = kb_json.load_global_blocks(active_only=True)
    knowledge_context = kb_json.knowledge_model_context_for_prompt()
    context = {
        "fact_catalog": catalog,
        "global_blocks": global_blocks,
        "knowledge_model_context": knowledge_context,
    }
    return _limit_text(json.dumps(context, ensure_ascii=False, indent=2), 16000)


def _json_schema_text() -> str:
    return """
Gib ausschließlich gültiges JSON zurück. Kein Markdown, keine Erklärung.
Schema:
{
  "facts": {
    "topic": "eduroam|vpn|mfa|drucker|user_account|support|unknown",
    "service": "eduroam|vpn|mfa|drucker|user_account|support|unknown",
    "intent": "setup|login|troubleshooting|information|unknown",
    "os": "windows|macos|unknown",
    "operating_system": "windows|macos|unknown",
    "account_exists": true|false|"unknown",
    "account_activated": true|false|"unknown",
    "username_known": true|false|"unknown",
    "kuerzel_known": true|false|"unknown",
    "password_known": true|false|"unknown",
    "credentials_valid": true|false|"unknown",
    "internet_available": true|false|"unknown",
    "network_context": "campus_wlan|campus_lan|external_network|unknown",
    "campus_network_available": true|false|"unknown",
    "eduroam_visible": true|false|"unknown",
    "eduroam_profile_configured": true|false|"unknown",
    "eduroam_connected": true|false|"unknown",
    "mfa_configured": true|false|"unknown",
    "mfa_code_status": "valid|invalid|expired|not_available|unknown",
    "two_fa_ready": true|false|"not_required"|"unknown",
    "vpn_client_installed": true|false|"unknown",
    "vpn_profile_configured": true|false|"unknown",
    "vpn_auth_status": "success|failed|not_tested|unknown",
    "vpn_tunnel_status": "connected|failed|not_tested|unknown",
    "internal_resource_accessible": true|false|"unknown",
    "problem_type": "setup|login|connection|mfa|certificate|profile|support|unknown",
    "problem_area": "organisation|login|verbinden|mfa|vpn|support|unknown"
  },
  "confidence": "hoch|mittel|niedrig",
  "reason": "kurze Begründung"
}
Lasse Fakten weg, die du nicht aus der Eingabe ableiten kannst. Nutze keine freien neuen Fact-Keys.
""".strip()




def _compact_fact_schema_text() -> str:
    """Sehr kompaktes Schema für schnelle Faktenerkennung.

    Für Folgeantworten im Dialog braucht das Modell keine komplette JSON-Wissensbasis.
    Es soll nur wenige erlaubte Fakten ausgeben und ansonsten leere Fakten liefern.
    """
    return """
Gib ausschließlich gültiges JSON zurück. Kein Markdown.
Schema:
{
  "facts": {
    "topic": "eduroam|vpn|mfa|user_account|support|unknown",
    "service": "eduroam|vpn|mfa|user_account|support|unknown",
    "intent": "setup|login|troubleshooting|information|password_reset|unknown",
    "os": "windows|macos|ios|android|linux|unknown",
    "operating_system": "windows|macos|ios|android|linux|unknown",
    "account_exists": true|false|"unknown",
    "account_activated": true|false|"unknown",
    "username_known": true|false|"unknown",
    "kuerzel_known": true|false|"unknown",
    "password_known": true|false|"unknown",
    "credentials_valid": true|false|"unknown",
    "internet_available": true|false|"unknown",
    "wifi_available": true|false|"unknown",
    "wifi_enabled": true|false|"unknown",
    "eduroam_visible": true|false|"unknown",
    "eduroam_connected": true|false|"unknown",
    "mfa_configured": true|false|"unknown",
    "two_fa_ready": true|false|"unknown",
    "mfa_code_available": true|false|"unknown",
    "mfa_code_status": "available|valid|invalid|expired|missing|unknown",
    "mfa_challenge_approved": true|false|"unknown",
    "vpn_client_installed": true|false|"unknown",
    "vpn_connected": true|false|"unknown",
    "vpn_auth_status": "success|failed|not_tested|unknown",
    "vpn_tunnel_status": "connected|failed|not_tested|unknown",
    "internal_resource_accessible": true|false|"unknown",
    "help_request": "password_reset|account_data_lost|unknown",
    "explanation_request": "operating_system|mfa|vpn|eduroam|unknown",
    "problem_resolved": true|false|"unknown"
  },
  "confidence": "hoch|mittel|niedrig",
  "reason": "kurze Begründung"
}
Lasse Fakten weg, die nicht direkt aus Eingabe oder letzter Rückfrage ableitbar sind.
""".strip()


def _compact_current_facts(current_facts: dict[str, Any] | None) -> dict[str, Any]:
    """Nur die wichtigsten Fakten in den schnellen Folgeprompt übernehmen."""
    if not current_facts:
        return {}
    keep = {
        "topic", "service", "intent", "os", "operating_system",
        "account_exists", "account_activated", "username_known", "kuerzel_known", "password_known",
        "mfa_configured", "two_fa_ready", "mfa_code_status", "mfa_code_available",
        "vpn_client_installed", "vpn_connected", "vpn_auth_status", "vpn_tunnel_status",
        "wifi_available", "wifi_enabled", "wlan_enabled", "eduroam_visible", "eduroam_connected",
        "problem_resolved", "help_request", "explanation_request",
    }
    return {k: v for k, v in current_facts.items() if k in keep}

def _normalize_llm_fact_response(data: dict[str, Any]) -> dict[str, Any]:
    """Akzeptiert sowohl {facts:{...}} als auch flache JSON-Objekte."""
    if not isinstance(data, dict):
        return {}
    if isinstance(data.get("facts"), dict):
        facts = dict(data.get("facts") or {})
        facts["__confidence"] = data.get("confidence", "mittel")
        facts["__reason"] = data.get("reason", "Groq-Faktenerkennung")
        return facts
    return data


# ============================================================
# 1) LLM in der Nutzeroberfläche: Freitext -> Dienst/System/Schritt
# ============================================================

def recognize_instruction_request(user_text: str, model: str) -> dict[str, Any]:
    prompt = f"""
Du bist nur für Texterkennung zuständig. Du entscheidest keine Lösung.
Erkenne aus der Nutzereingabe den Dienst, das System und den wahrscheinlich betroffenen Schritt aus der JSON-Wissensbasis.
Gib ausschließlich gültiges JSON zurück.

Schema:
{{
  "service_key": "key oder unknown",
  "system_key": "key oder unknown",
  "step_number": Zahl oder null,
  "confidence": "hoch|mittel|niedrig",
  "reason": "kurze Begründung"
}}

Wissensbasis:
{kb_context_for_prompt()}
"""
    response = chat(
        [
            {"role": "system", "content": prompt.strip()},
            {"role": "user", "content": user_text.strip()},
        ],
        model=model,
        json_mode=True,
        temperature=0.0,
    )
    data = extract_json(response)
    if not data:
        raise RuntimeError(f"Groq gab kein gültiges JSON zurück: {response}")
    return data


# ============================================================
# 2) LLM im Gruppen-Inferenztest: Freitext/Folgeantwort -> Fakten
# ============================================================

def recognize_facts(user_text: str, model: str) -> dict[str, Any]:
    """Erstfaktenerkennung ohne Dialogkontext."""
    prompt = f"""
Du bist nur für Faktenerkennung zuständig. Du entscheidest keine Lösung.
Extrahiere Fakten für eine IT-Support-Inferenzregel-Engine.

{_json_schema_text()}

Aktuelle Rule-Engine-Kontexte:
{fact_context_for_prompt()}
"""
    response = chat(
        [
            {"role": "system", "content": prompt.strip()},
            {"role": "user", "content": user_text.strip()},
        ],
        model=model,
        json_mode=True,
        temperature=0.0,
    )
    data = extract_json(response)
    if not data:
        raise RuntimeError(f"Groq gab kein gültiges JSON zurück: {response}")
    return _normalize_llm_fact_response(data)


def recognize_facts_fast(user_text: str, model: str) -> dict[str, Any]:
    """Schnelle Erstfaktenerkennung mit reduziertem Prompt.

    Diese Variante ist für kurze LogiBot-Testdialoge gedacht und vermeidet den
    kompletten Wissensmodell-Kontext. Die Rule Engine validiert danach weiterhin
    deterministisch die Fakten.
    """
    prompt = f"""
Du bist nur für kompakte Faktenerkennung zuständig. Du entscheidest keine Lösung.
Erkenne nur Fakten, die direkt aus der Nutzereingabe hervorgehen.

{_compact_fact_schema_text()}
"""
    response = chat(
        [
            {"role": "system", "content": prompt.strip()},
            {"role": "user", "content": user_text.strip()},
        ],
        model=model,
        json_mode=True,
        temperature=0.0,
        timeout=30,
    )
    data = extract_json(response)
    if not data:
        raise RuntimeError(f"Groq gab kein gültiges JSON zurück: {response}")
    return _normalize_llm_fact_response(data)



def recognize_facts_in_context(
    user_text: str,
    model: str,
    *,
    current_facts: dict[str, Any] | None = None,
    pending_fact: str | None = None,
    pending_question: str | None = None,
    previous_result_summary: str | None = None,
) -> dict[str, Any]:
    """Faktenerkennung für laufende Dialoge."""
    context = {
        "bisherige_fakten": current_facts or {},
        "gerade_abgefragter_fact": pending_fact,
        "letzte_rueckfrage": pending_question,
        "letzte_regelausgabe": previous_result_summary,
    }
    prompt = f"""
Du bist nur für Faktenerkennung in einem laufenden Dialog zuständig.
Du entscheidest keine Lösung und wählst keinen nächsten Schritt.

Nutze die letzte Rückfrage und den gerade abgefragten Fact, um kurze Antworten wie "ja", "nein", "funktioniert" oder "geht nicht" korrekt zu interpretieren.
Wichtig: Bereits bekannte Kernfakten wie topic/service/os sollen nicht geändert werden, außer der Nutzer korrigiert sie ausdrücklich.

{_json_schema_text()}

Dialogkontext:
{json.dumps(context, ensure_ascii=False, indent=2)}

Aktuelle Rule-Engine-Kontexte:
{fact_context_for_prompt()}
"""
    response = chat(
        [
            {"role": "system", "content": prompt.strip()},
            {"role": "user", "content": user_text.strip()},
        ],
        model=model,
        json_mode=True,
        temperature=0.0,
    )
    data = extract_json(response)
    if not data:
        raise RuntimeError(f"Groq gab kein gültiges JSON zurück: {response}")
    return _normalize_llm_fact_response(data)


def recognize_facts_in_context_fast(
    user_text: str,
    model: str,
    *,
    current_facts: dict[str, Any] | None = None,
    pending_fact: str | None = None,
    pending_question: str | None = None,
    previous_result_summary: str | None = None,
) -> dict[str, Any]:
    """Schnelle Faktenerkennung für Folgeantworten im laufenden Dialog.

    Enthält bewusst NICHT den kompletten Rule-Engine-Kontext. Für Antworten wie
    "ja", "nein", "weiß ich nicht", "Windows" oder "MFA ist verfügbar" reichen
    die letzte Frage, der erwartete Fact und wenige Kernfakten aus.
    """
    context = {
        "bisherige_kernfakten": _compact_current_facts(current_facts),
        "gerade_abgefragter_fact": pending_fact,
        "letzte_rueckfrage": pending_question,
    }
    prompt = f"""
Du bist nur für Faktenerkennung in einem laufenden IT-Support-Dialog zuständig.
Du entscheidest keine Lösung und wählst keinen nächsten Schritt.

Regeln:
- Interpretiere die Nutzereingabe im Kontext der letzten Rückfrage.
- Wenn der Nutzer nur "ja" sagt, setze den gerade abgefragten Fact passend auf true bzw. den passenden Status.
- Wenn der Nutzer nur "nein" sagt, setze den gerade abgefragten Fact passend auf false bzw. missing/failed.
- Wenn der Nutzer "weiß ich nicht" oder "vielleicht" sagt, setze keinen falschen Wert; nutze unknown-Hinweise.
- Ändere topic/service/os nur, wenn der Nutzer sie ausdrücklich nennt oder korrigiert.

{_compact_fact_schema_text()}

Dialogkontext:
{json.dumps(context, ensure_ascii=False, indent=2)}
"""
    response = chat(
        [
            {"role": "system", "content": prompt.strip()},
            {"role": "user", "content": user_text.strip()},
        ],
        model=model,
        json_mode=True,
        temperature=0.0,
        timeout=30,
    )
    data = extract_json(response)
    if not data:
        raise RuntimeError(f"Groq gab kein gültiges JSON zurück: {response}")
    return _normalize_llm_fact_response(data)



# ============================================================
# 3) LLM in der Antwortformulierung
# ============================================================

def formulate_answer(title: str, actions: list[str], model: str) -> str:
    actions_text = "\n".join(f"- {a}" for a in actions if str(a).strip())
    prompt = f"""
Du bist ein freundlicher IT-Assistent der Universität Hohenheim.
Formuliere die folgende regelbasierte Empfehlung kurz und verständlich.

Regeln:
- Erfinde keine neuen technischen Schritte.
- Nutze ausschließlich die gegebenen Aktionen/Inhalte.
- Schreibe auf Deutsch.
- Sprich den Nutzer direkt mit "du" an.
- Maximal 5 Sätze.

Titel: {title}
Aktionen/Inhalte:
{actions_text}
"""
    return chat([{"role": "user", "content": prompt.strip()}], model=model, json_mode=False, temperature=0.2)


def formulate_rule_result(
    result_summary: str,
    facts: dict[str, Any],
    model: str,
    *,
    title: str = "Regelbasierte Ausgabe",
) -> str:
    prompt = f"""
Du bist ein freundlicher IT-Assistent der Universität Hohenheim.
Die Rule Engine hat bereits entschieden. Deine Aufgabe ist nur, die Ausgabe verständlich zu formulieren.

Regeln:
- Erfinde keine neuen Fakten, Regeln oder technischen Schritte.
- Nutze nur die regelbasierte Ausgabe und den Faktkontext.
- Wenn die Ausgabe eine Rückfrage ist, formuliere genau diese Rückfrage klar und freundlich.
- Wenn die Ausgabe eine Empfehlung ist, formuliere sie als kurze Handlungsempfehlung.
- Maximal 5 Sätze.

Titel: {title}

Regelbasierte Ausgabe:
{result_summary}

Aktuelle Fakten:
{json.dumps(facts, ensure_ascii=False, indent=2)}
"""
    return chat([{"role": "user", "content": prompt.strip()}], model=model, json_mode=False, temperature=0.2)
