# inference_engine.py
# ============================================================
# JSON-basierte Inferenz-Engine.
# Unterstützt when.all und when.any sowie Actions:
# ask, answer, recommend, redirect_topic, show_steps.
# ============================================================

from __future__ import annotations

import re
from typing import Any

from storage import kb_loader as kb_json

UNKNOWN = "unknown"


def normalize_text(value: Any) -> str:
    return str(value).strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def normalize_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_text(value)
    return value


def get_fact(facts: dict[str, Any], fact_name: str) -> Any:
    return facts.get(fact_name, UNKNOWN)


def evaluate_condition(condition: dict[str, Any], facts: dict[str, Any]) -> bool:
    fact_name = str(condition.get("fact", ""))
    operator = str(condition.get("operator", "equals")).strip().lower()
    expected = condition.get("value")
    actual = get_fact(facts, fact_name)

    if operator == "equals":
        return normalize_scalar(actual) == normalize_scalar(expected)
    if operator in {"not_equals", "not equals", "neq"}:
        return normalize_scalar(actual) != normalize_scalar(expected)
    if operator == "in":
        expected_list = expected if isinstance(expected, list) else [expected]
        return normalize_scalar(actual) in [normalize_scalar(v) for v in expected_list]
    if operator == "contains":
        return normalize_text(expected) in normalize_text(actual)
    if operator in {"is_unknown", "unknown"}:
        return actual in {UNKNOWN, None, ""}
    if operator in {"is_known", "known"}:
        return actual not in {UNKNOWN, None, ""}
    if operator in {"truthy", "is_true"}:
        return actual is True
    if operator in {"falsy", "is_false"}:
        return actual is False
    return False


def evaluate_when(when: dict[str, Any], facts: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    trace: list[dict[str, Any]] = []
    all_conditions = when.get("all", []) or []
    any_conditions = when.get("any", []) or []

    all_ok = True
    for condition in all_conditions:
        ok = evaluate_condition(condition, facts)
        trace.append({"group": "all", "condition": condition, "actual": get_fact(facts, str(condition.get("fact", ""))), "matched": ok})
        if not ok:
            all_ok = False

    if any_conditions:
        any_ok = False
        for condition in any_conditions:
            ok = evaluate_condition(condition, facts)
            trace.append({"group": "any", "condition": condition, "actual": get_fact(facts, str(condition.get("fact", ""))), "matched": ok})
            if ok:
                any_ok = True
    else:
        any_ok = True

    return all_ok and any_ok, trace


def resolve_action(action: dict[str, Any]) -> dict[str, Any]:
    action = dict(action)
    if action.get("type") == "show_steps":
        package_key = action.get("step_package_id") or action.get("package_id")
        package = kb_json.get_step_package(str(package_key)) if package_key else None
        action["step_package"] = package
    return action


def run_inference(facts: dict[str, Any]) -> dict[str, Any]:
    facts = dict(facts)
    rules = kb_json.load_inference_rules(active_only=True)
    matched_rules: list[dict[str, Any]] = []
    evaluated_rules: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    for rule in rules:
        matched, trace = evaluate_when(rule.get("when", {}), facts)
        evaluated_rules.append({
            "rule_id": rule.get("id"),
            "description": rule.get("description", ""),
            "matched": matched,
            "trace": trace,
        })
        if not matched:
            continue

        resolved_actions = [resolve_action(action) for action in rule.get("then", [])]
        matched_rules.append({
            "rule_id": rule.get("id"),
            "module": rule.get("module", "general"),
            "rule_group": rule.get("rule_group", "general"),
            "description": rule.get("description", ""),
            "actions": resolved_actions,
            "stop_after_match": bool(rule.get("stop_after_match")),
        })
        actions.extend(resolved_actions)
        if rule.get("stop_after_match"):
            break

    return {"facts": facts, "matched_rules": matched_rules, "actions": actions, "evaluated_rules": evaluated_rules}


def action_texts(result: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for action in result.get("actions", []):
        typ = action.get("type")
        if typ in {"ask", "answer", "recommend", "redirect_topic"}:
            text = action.get("text", "")
            if text:
                texts.append(text)
        elif typ == "show_steps":
            package = action.get("step_package")
            if package:
                texts.append(f"Schrittpaket: {package.get('title', package.get('id'))}")
            else:
                texts.append(f"Schrittpaket nicht gefunden: {action.get('step_package_id')}")
    return texts


def renderable_summary(result: dict[str, Any]) -> str:
    texts = action_texts(result)
    if not texts:
        return "Es wurde keine passende Regel gefunden. Bitte prüfe, ob die Fakten vollständig sind."
    return "\n".join(f"- {text}" for text in texts)


def facts_from_text(user_text: str) -> dict[str, Any]:
    t = normalize_text(user_text)
    facts: dict[str, Any] = {
        "topic": UNKNOWN,
        "intent": UNKNOWN,
        "os": UNKNOWN,
        "account_activated": UNKNOWN,
        "internet_available": UNKNOWN,
        "campus_network_available": UNKNOWN,
        "vpn_client_installed": UNKNOWN,
        "mfa_configured": UNKNOWN,
        "eduroam_connected": UNKNOWN,
        "username_format_correct": UNKNOWN,
        "email_used_as_username": UNKNOWN,
        "problem_area": UNKNOWN,
    }
    if "eduroam" in t or "wlan" in t:
        facts["topic"] = "eduroam"
    elif "vpn" in t or "cisco" in t or "secure client" in t:
        facts["topic"] = "vpn"
    elif "mfa" in t or "2fa" in t or "multi faktor" in t or "multifaktor" in t or "token" in t or "2fas" in t or "keepass" in t:
        facts["topic"] = "mfa"
    elif "benutzerkonto" in t or "account" in t or "passwort" in t or "benutzername" in t or "idm" in t:
        facts["topic"] = "user_account"
    elif "drucker" in t or "printserver" in t or "drucken" in t:
        facts["topic"] = "drucker"

    if any(x in t for x in ["organisation", "hohenheim", "universitaet", "universität", "uni nicht", "finde die uni", "finde universitaet", "finde universität"]):
        facts["problem_area"] = "organisation"
        facts["intent"] = "organisation"
    if any(x in t for x in ["benutzername", "passwort", "login", "anmelden", "kennwort"]):
        facts["problem_area"] = "login"
    if any(x in t for x in ["verbindet nicht", "keine verbindung", "eduroam geht nicht", "nicht verbunden"]):
        facts["problem_area"] = "verbinden"
        facts["eduroam_connected"] = False

    if any(x in t for x in ["einrichten", "installieren", "installation", "setup", "verbinden", "aktivieren", "erstellen"]):
        facts["intent"] = "setup"
    if any(x in t for x in ["problem", "fehler", "geht nicht", "funktioniert nicht", "klappt nicht", "haengt", "hängt"]):
        facts["intent"] = "troubleshooting"
    if any(x in t for x in ["login", "anmelden", "passwort", "kennwort"]):
        facts["intent"] = "login"
    if any(x in t for x in ["was ist", "info", "information", "wissen"]):
        facts["intent"] = "information"

    if any(x in t for x in ["windows", "win10", "win11", "pc"]):
        facts["os"] = "windows"
    elif any(x in t for x in ["macos", "mac os", "macbook", "apple", "osx", "mac"]):
        facts["os"] = "macos"
    elif "linux" in t:
        facts["os"] = "linux"
    elif "android" in t:
        facts["os"] = "android"
    elif "ipad" in t or "ipados" in t:
        facts["os"] = "ipados"
    elif "iphone" in t or "ios" in t:
        facts["os"] = "ios"
    elif "chromeos" in t or "chromebook" in t:
        facts["os"] = "chromeos"

    if any(x in t for x in ["kein internet", "ohne internet", "offline"]):
        facts["internet_available"] = False
    if any(x in t for x in ["internet vorhanden", "internet funktioniert", "online"]):
        facts["internet_available"] = True
    account_negative = any(x in t for x in ["kein konto", "nicht aktiviert", "konto fehlt", "benutzerkonto fehlt", "account fehlt", "konto noch nicht aktiviert", "noch nicht aktiviert"])
    account_positive = ("konto" in t or "account" in t or "benutzerkonto" in t) and any(x in t for x in ["aktiviert", "freigeschaltet", "vorhanden"])
    if account_negative:
        facts["account_activated"] = False
    elif account_positive:
        facts["account_activated"] = True
    if any(x in t for x in ["mfa fehlt", "kein zweiter faktor", "kein token"]):
        facts["mfa_configured"] = False
    if any(x in t for x in ["mfa eingerichtet", "token eingerichtet", "2fa eingerichtet"]):
        facts["mfa_configured"] = True
    if any(x in t for x in ["email als benutzername", "e-mail als benutzername", "mailadresse"]):
        facts["email_used_as_username"] = True
        facts["username_format_correct"] = False
    return facts
