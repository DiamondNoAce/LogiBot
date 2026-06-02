# llm_ollama.py
# ============================================================
# Optionale lokale LLM-Anbindung über Ollama.
# Keine Kosten, kein API-Key. Ollama muss lokal laufen.
# ============================================================

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

import kb_json

OLLAMA_URL = "http://localhost:11434"


def ollama_available() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def chat(messages: list[dict[str, str]], model: str, *, json_mode: bool = False, temperature: float = 0.0, timeout: int = 120) -> str:
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False, "options": {"temperature": temperature}}
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
        raise RuntimeError("Ollama ist nicht erreichbar. Starte Ollama und lade ein Modell, z. B. ollama pull llama3.2:3b.") from e


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


def kb_context_for_prompt() -> str:
    lines = []
    for service in kb_json.get_services(active_only=True):
        lines.append(f"Dienst: {service.get('key')} = {service.get('name')}")
        for system in service.get("systems", []):
            lines.append(f"  System: {system.get('key')} = {system.get('name')}")
            for step in system.get("steps", []):
                lines.append(f"    Schritt {step.get('number')}: {step.get('phase')} | {step.get('title')} | Keywords: {', '.join(step.get('keywords', []))}")
    return "\n".join(lines[:250])


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
    response = chat([
        {"role": "system", "content": prompt.strip()},
        {"role": "user", "content": user_text.strip()},
    ], model=model, json_mode=True, temperature=0.0)
    data = extract_json(response)
    if not data:
        raise RuntimeError(f"LLM gab kein gültiges JSON zurück: {response}")
    return data


def recognize_facts(user_text: str, model: str) -> dict[str, Any]:
    catalog = kb_json.load_fact_catalog()
    prompt = f"""
Du bist nur für Faktenerkennung zuständig. Du entscheidest keine Lösung.
Extrahiere Fakten für eine IT-Support-Inferenzregel-Engine.
Gib ausschließlich gültiges JSON zurück.
Nutze unbekannte Werte als "unknown".

Faktkatalog:
{json.dumps(catalog, ensure_ascii=False, indent=2)}

Pflichtfelder:
topic, intent, os, account_activated, internet_available, campus_network_available, vpn_client_installed, mfa_configured, eduroam_connected, username_format_correct, email_used_as_username
"""
    response = chat([
        {"role": "system", "content": prompt.strip()},
        {"role": "user", "content": user_text.strip()},
    ], model=model, json_mode=True, temperature=0.0)
    data = extract_json(response)
    if not data:
        raise RuntimeError(f"LLM gab kein gültiges JSON zurück: {response}")
    return data


def formulate_answer(title: str, actions: list[str], model: str) -> str:
    actions_text = "\n".join(f"- {a}" for a in actions)
    prompt = f"""
Du bist ein freundlicher IT-Assistent der Universität Hohenheim.
Formuliere die folgende regelbasierte Empfehlung kurz und verständlich.
Regeln:
- Erfinde keine neuen Schritte.
- Nutze nur die gegebenen Aktionen.
- Schreibe auf Deutsch.
- Maximal 5 Sätze.

Titel: {title}
Aktionen:
{actions_text}
"""
    return chat([{"role": "user", "content": prompt.strip()}], model=model, json_mode=False, temperature=0.2)
