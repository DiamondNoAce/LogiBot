"""Sicherheitsgrenzen für die optionale LLM-Schicht.

Das LLM darf im LogiBot nur assistieren:
- Freitext in bekannte Fakten übersetzen
- Rückfragen sprachlich formulieren
- bereits regelbasierte Ausgaben verständlicher machen

Die fachliche Auswahl von Regeln, Schritten und Support-Fallbacks bleibt immer
bei Rule Engine, Entscheidungsnetz und Dialog-Guard. Dieses Modul filtert daher
LLM-Ausgaben, bevor sie in den Dialogzustand übernommen werden.
"""
from __future__ import annotations

import re
from typing import Any

from storage import kb_loader
from core.condition_parser import normalize_text

ALLOWED_SERVICES = {
    "eduroam", "vpn", "mfa", "drucker", "user_account", "support", "other_service",
    "unknown", "mixed", "none", ""
}
ALLOWED_SYSTEMS = {
    "windows", "mac", "macos", "linux", "android", "ios", "ipados", "chromeos",
    "general", "unknown", "none", ""
}
ALLOWED_INTENTS = {
    "setup", "login", "troubleshooting", "information", "support", "unknown",
    "invalid_or_unclear", "none", ""
}
ALLOWED_CONFIDENCE = {"hoch", "mittel", "niedrig", "unknown", ""}

# Interne Guard-Fakten, die nicht im fact_catalog stehen müssen, aber bewusst
# von der lokalen Erkennung oder vom Dialog-Manager genutzt werden.
INTERNAL_ALLOWED_FACTS = {
    "topic", "service", "intent", "os", "operating_system", "device_type",
    "__confidence", "__reason", "__llm_guard_notes",
    "multi_topic_query", "mentioned_services", "invalid_request", "user_question",
    "question_target_fact", "explanation_request", "help_request", "user_request",
    "source_type", "journey_type", "pending_setup_service", "awaiting_setup_os",
    "unknown_request_flow", "unknown_request_attempts",
    "service_previously_used", "service_previously_worked", "previous_use_context",
    "skip_initial_prerequisites", "credentials_assumed_from_previous_use",
    "eduroam_previously_worked", "vpn_previously_worked", "mfa_previously_worked",
    "profile_recreation_required", "connection_test_required", "problem_resolved",
    "problem_unresolved", "support_needed", "needs_human_support", "human_support_needed",
    "account_status", "network_context", "problem_type", "problem_area",
    "eduroam_problem_type", "vpn_problem_type", "mfa_problem_type",
    "eduroam_profile_status", "eduroam_cat_profile_installed",
    "connection_attempt_status", "eduroam_internet_access", "other_wifi_visible",
    "vpn_installation_status", "vpn_gateway_selected", "mfa_required_for_vpn_login",
    "mfa_totp_available", "second_factor_source", "internet_access_available",
}

FORBIDDEN_LLM_FACT_KEYS = {
    "answer", "response", "message", "text", "steps", "instructions", "solution",
    "technical_steps", "recommendation", "rule_id", "selected_rule", "action",
    "actions", "then", "when", "python", "code", "sql", "password", "api_key",
}

STICKY_FACTS = {"topic", "service", "os", "operating_system"}


def _catalog_fact_keys() -> set[str]:
    keys: set[str] = set()
    try:
        catalog = kb_loader.load_fact_catalog()
        for section in catalog.values():
            if isinstance(section, dict):
                keys.update(str(k) for k in section.keys())
    except Exception:
        pass
    try:
        keys.update(str(item.get("key")) for item in kb_loader.load_condition_catalog(active_only=False) if item.get("key"))
    except Exception:
        pass
    return {k for k in keys if k}


def allowed_fact_keys() -> set[str]:
    return _catalog_fact_keys() | INTERNAL_ALLOWED_FACTS


def _is_known(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip().lower() in {"", "unknown", "none", "null"}:
        return False
    return True


def _contains_term(text: str, term: str) -> bool:
    normalized_text = normalize_text(text or "")
    normalized_term = normalize_text(term or "").strip()
    if not normalized_text or not normalized_term:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(normalized_term) + r"(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def _text_mentions_value(user_text: str, key: str, value: Any) -> bool:
    t = normalize_text(user_text or "")
    v = normalize_text(str(value or ""))
    if not v or v in {"unknown", "none"}:
        return False
    aliases = {
        "eduroam": ["eduroam", "wlan", "wifi"],
        "vpn": ["vpn", "cisco", "secure client"],
        "mfa": ["mfa", "2fa", "authenticator", "code", "token", "einmalcode"],
        "user_account": ["passwort", "konto", "account", "benutzername", "kennung", "kuerzel", "kürzel"],
        "windows": ["windows", "win10", "win11", "pc"],
        "macos": ["macos", "mac os", "macbook", "osx", "apple", "mac"],
        "mac": ["macos", "mac os", "macbook", "osx", "apple", "mac"],
        "linux": ["linux"],
        "android": ["android"],
        "ios": ["ios", "iphone"],
        "ipados": ["ipados", "ipad"],
        "chromeos": ["chromeos", "chrome os", "chromebook"],
    }
    candidates = aliases.get(v, [v])
    return any(_contains_term(t, c) for c in candidates)


def _local_confirms(local_facts: dict[str, Any] | None, key: str, value: Any) -> bool:
    if not local_facts:
        return False
    if key in {"topic", "service"}:
        return local_facts.get("topic") == value or local_facts.get("service") == value
    if key in {"os", "operating_system"}:
        return local_facts.get("os") == value or local_facts.get("operating_system") == value
    return local_facts.get(key) == value


def _normalize_os(value: Any) -> str:
    raw = str(value or "unknown").strip().lower()
    aliases = {
        "win": "windows", "win10": "windows", "win11": "windows", "pc": "windows",
        "mac": "macos", "mac os": "macos", "osx": "macos", "os x": "macos", "macbook": "macos",
        "iphone": "ios", "ipad": "ipados", "chrome os": "chromeos", "chromebook": "chromeos",
    }
    return aliases.get(raw, raw)


def filter_llm_facts(
    llm_facts: dict[str, Any],
    *,
    user_text: str = "",
    current_facts: dict[str, Any] | None = None,
    pending_fact: str | None = None,
    local_facts: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Entfernt unerlaubte oder spekulative LLM-Fakten.

    Besonders wichtig: Ein LLM darf im laufenden Dialog keinen Dienst oder kein
    Betriebssystem wechseln/erfinden, wenn der Nutzer das nicht explizit genannt
    hat oder die lokale Erkennung den Wert bestätigt.
    """
    current_facts = current_facts or {}
    local_facts = local_facts or {}
    allowed = allowed_fact_keys()
    filtered: dict[str, Any] = {}
    notes: list[str] = []

    for raw_key, value in (llm_facts or {}).items():
        key = str(raw_key).strip()
        if not key:
            continue
        lower_key = key.lower()
        if lower_key in FORBIDDEN_LLM_FACT_KEYS:
            notes.append(f"LLM-Key verworfen, weil er eine Antwort/Aktion statt eines Facts enthält: {key}")
            continue
        if key not in allowed:
            notes.append(f"Unbekannter LLM-Fact verworfen: {key}")
            continue

        if key in {"topic", "service"}:
            value = str(value or "unknown").strip().lower()
            if value not in ALLOWED_SERVICES:
                notes.append(f"Unerlaubter Service-Wert verworfen: {value}")
                continue
        elif key in {"os", "operating_system"}:
            value = _normalize_os(value)
            if value not in ALLOWED_SYSTEMS:
                notes.append(f"Unerlaubter Betriebssystem-Wert verworfen: {value}")
                continue
        elif key == "intent":
            value = str(value or "unknown").strip().lower()
            if value not in ALLOWED_INTENTS:
                notes.append(f"Unerlaubter Intent-Wert verworfen: {value}")
                continue
        elif key == "__confidence":
            value = str(value or "mittel").strip().lower()
            if value not in ALLOWED_CONFIDENCE:
                value = "mittel"

        if key in STICKY_FACTS and _is_known(current_facts.get(key)) and current_facts.get(key) != value:
            explicitly_corrected = any(word in normalize_text(user_text) for word in ["doch", "eigentlich", "korrektur", "nicht", "sondern", "statt"])
            if not explicitly_corrected and not _text_mentions_value(user_text, key, value) and not _local_confirms(local_facts, key, value):
                notes.append(f"Spekulative Änderung von {key} verworfen: {current_facts.get(key)} -> {value}")
                continue

        # Wenn nach OS gefragt wurde, darf das LLM nur ein OS setzen, wenn der Text
        # tatsächlich ein OS nennt. So wird „Wie erkenne ich das?“ nicht zu Windows.
        if key in {"os", "operating_system"} and pending_fact in {"os", "operating_system"}:
            if not _text_mentions_value(user_text, key, value) and not _local_confirms(local_facts, key, value):
                notes.append(f"OS-Wert ohne ausdrückliche Nennung verworfen: {value}")
                continue

        filtered[key] = value

    if notes:
        filtered["__llm_guard_notes"] = notes
    return filtered, notes


def filter_instruction_recognition(data: dict[str, Any], *, user_text: str = "") -> tuple[dict[str, Any], list[str]]:
    """Filtert die direkte Anleitungserkennung des LLM."""
    cleaned = dict(data or {})
    notes: list[str] = []
    service = str(cleaned.get("service_key", "unknown") or "unknown").lower()
    system = _normalize_os(cleaned.get("system_key", "unknown"))
    confidence = str(cleaned.get("confidence", "niedrig") or "niedrig").lower()

    if service not in ALLOWED_SERVICES:
        cleaned["service_key"] = "unknown"
        notes.append(f"Unerlaubter Service-Key aus Anleitungserkennung verworfen: {service}")
    else:
        cleaned["service_key"] = service

    if system not in ALLOWED_SYSTEMS:
        cleaned["system_key"] = "unknown"
        notes.append(f"Unerlaubter System-Key aus Anleitungserkennung verworfen: {system}")
    elif system != "unknown" and not _text_mentions_value(user_text, "system_key", system):
        # Direkte Anleitungssuche darf kein Betriebssystem raten.
        cleaned["system_key"] = "unknown"
        cleaned["confidence"] = "niedrig"
        notes.append(f"System-Key ohne explizite Nennung verworfen: {system}")
    else:
        cleaned["system_key"] = system

    if confidence not in ALLOWED_CONFIDENCE:
        cleaned["confidence"] = "niedrig"
    if notes:
        cleaned["guard_notes"] = notes
    return cleaned, notes


_FORBIDDEN_RESPONSE_PATTERNS = [
    r"passwort\s+(hier|im\s+chat|in\s+den\s+chat)\s+(eingeben|schreiben|posten|senden)",
    r"api[-_ ]?key\s+(hier|im\s+chat|eingeben|schreiben|posten)",
    r"benutzerkennung\s+(hier|im\s+chat)\s+(eingeben|schreiben|posten|senden)",
]


def guard_formulated_response(candidate: str, source_text: str, *, fallback_text: str | None = None) -> tuple[str, list[str]]:
    """Akzeptiert LLM-Formulierungen nur, wenn sie im sicheren Rahmen bleiben."""
    fallback = fallback_text if fallback_text is not None else source_text
    text = str(candidate or "").strip()
    notes: list[str] = []
    if not text:
        return fallback, ["Leere LLM-Formulierung verworfen."]

    normalized = normalize_text(text)
    for pattern in _FORBIDDEN_RESPONSE_PATTERNS:
        if re.search(pattern, normalized):
            return fallback, ["LLM-Formulierung verworfen: fordert sensible Eingabe im Chat an."]

    # Neue URLs oder Shell-Kommandos dürfen nicht erfunden werden.
    candidate_urls = set(re.findall(r"https?://\S+", text))
    source_urls = set(re.findall(r"https?://\S+", source_text or ""))
    invented_urls = candidate_urls - source_urls
    if invented_urls:
        return fallback, [f"LLM-Formulierung verworfen: neue URL(s) erfunden: {', '.join(sorted(invented_urls))}"]

    command_markers = ["sudo ", "rm -", "powershell", "cmd.exe", "regedit", "terminal", "curl "]
    if any(marker in normalized for marker in command_markers) and not any(marker in normalize_text(source_text or "") for marker in command_markers):
        return fallback, ["LLM-Formulierung verworfen: möglicher neuer technischer Befehl."]

    # Antwort darf gerne schöner sein, aber nicht ausufern.
    if len(text) > max(1200, len(str(source_text or "")) * 3 + 300):
        return fallback, ["LLM-Formulierung verworfen: deutlich länger als die Regelbasis-Ausgabe."]

    return text, notes
