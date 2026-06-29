# ollama_client.py
# ============================================================
# Kostenlose/Open-Source LLM-Anbindung über Ollama.
#
# Rolle des LLM im LogiBot:
# - Freitext in strukturierte Fakten übersetzen
# - Folgeantworten im Kontext der letzten Rückfrage interpretieren
# - regelbasierte Ergebnisse nutzerfreundlich formulieren
#
# Wichtig: Die Rule Engine entscheidet. Das LLM entscheidet NICHT fachlich.
# ============================================================

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from storage import kb_loader as kb_json

OLLAMA_URL = "http://localhost:11434"


# ============================================================
# Basisfunktionen
# ============================================================

def ollama_available() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def chat(
    messages: list[dict[str, str]],
    model: str,
    *,
    json_mode: bool = False,
    temperature: float = 0.0,
    timeout: int = 120,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if json_mode:
        payload["format"] = "json"

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = json.loads(res.read().decode("utf-8"))
            return body.get("message", {}).get("content", "").strip()
    except urllib.error.URLError as e:
        raise RuntimeError(
            "Ollama ist nicht erreichbar. Starte Ollama und lade ein Modell, "
            "z. B. mit: ollama pull llama3.2:3b"
        ) from e


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
    return _limit_text("\n".join(lines), 16000)


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
    return _limit_text(json.dumps(context, ensure_ascii=False, indent=2), 22000)


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


def _normalize_llm_fact_response(data: dict[str, Any]) -> dict[str, Any]:
    """Akzeptiert sowohl {facts:{...}} als auch flache JSON-Objekte."""
    if not isinstance(data, dict):
        return {}
    if isinstance(data.get("facts"), dict):
        facts = dict(data.get("facts") or {})
        facts["__confidence"] = data.get("confidence", "mittel")
        facts["__reason"] = data.get("reason", "LLM-Faktenerkennung")
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
        raise RuntimeError(f"LLM gab kein gültiges JSON zurück: {response}")
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
        raise RuntimeError(f"LLM gab kein gültiges JSON zurück: {response}")
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
    """Faktenerkennung für laufende Dialoge.

    Diese Funktion ist für kurze Folgeantworten gedacht, z. B.:
    System: "Ist dein Benutzerkonto aktiviert?"
    Nutzer: "Ja"
    -> account_activated = true
    """
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
        raise RuntimeError(f"LLM gab kein gültiges JSON zurück: {response}")
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
