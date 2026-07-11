# condition_parser.py
# ============================================================
# Gemeinsame Condition-/Operator-Logik für Inferenzregeln und
# Entscheidungsnetze. Unterstützt die technische Sicht aus
# Eduroam_Regeln_technische_Sicht.xlsx:
# - Pre-Conditions
# - Trigger-Conditions
# - Post-Conditions als Metadaten
# - all/any/not-Gruppen
# - Operator-Aliase wie equals, in, ggf., bei Erfolg, unknown
# ============================================================

from __future__ import annotations

import re
from typing import Any

UNKNOWN = "unknown"

# Fact-Aliase erlauben, dass ältere und neue Rule-Engine-Dateien parallel
# funktionieren. Die Excel-Sicht nutzt z. B. `service` und `operating_system`,
# während die bisherige App `topic` und `os` nutzt.
FACT_ALIASES: dict[str, list[str]] = {
    "service": ["topic"],
    "topic": ["service"],
    "operating_system": ["os"],
    "os": ["operating_system"],
    "wifi_enabled": ["wlan_enabled"],
    "wlan_enabled": ["wifi_enabled"],
    "eduroam_profile_configured": ["eduroam_profile_installed", "eduroam_configured"],
    "eduroam_profile_installed": ["eduroam_profile_configured", "eduroam_configured"],
    "internet_access_available": ["internet_available"],
    "connection_successful": ["eduroam_connected"],
    "eduroam_connected": ["connection_successful"],
    "two_fa_ready": ["mfa_configured"],
    "mfa_configured": ["two_fa_ready"],
    "account_exists": ["account_activated"],
    "account_activated": ["account_exists"],
}

OPERATOR_ALIASES: dict[str, str] = {
    "=": "equals",
    "==": "equals",
    "gleich": "equals",
    "equals": "equals",
    "eq": "equals",
    "equal": "equals",
    "is": "equals",
    "ist": "equals",
    "not_equals": "not_equals",
    "not equals": "not_equals",
    "neq": "not_equals",
    "ne": "not_equals",
    "!=": "not_equals",
    "ungleich": "not_equals",
    "in": "in",
    "one_of": "in",
    "one of": "in",
    "not_in": "not_in",
    "not in": "not_in",
    "contains": "contains",
    "enthaelt": "contains",
    "enthält": "contains",
    "contains_any": "contains_any",
    "contains any": "contains_any",
    "contains_all": "contains_all",
    "contains all": "contains_all",
    "starts_with": "starts_with",
    "starts with": "starts_with",
    "ends_with": "ends_with",
    "ends with": "ends_with",
    "regex": "regex",
    "matches": "regex",
    "is_unknown": "is_unknown",
    "unknown": "is_unknown",
    "missing": "is_unknown",
    "is_known": "is_known",
    "known": "is_known",
    "exists": "is_known",
    "truthy": "is_true",
    "is_true": "is_true",
    "true": "is_true",
    "falsy": "is_false",
    "is_false": "is_false",
    "false": "is_false",
    ">": "greater_than",
    "greater_than": "greater_than",
    "greater than": "greater_than",
    "<": "less_than",
    "less_than": "less_than",
    "less than": "less_than",
    ">=": "greater_or_equal",
    "greater_or_equal": "greater_or_equal",
    "<=": "less_or_equal",
    "less_or_equal": "less_or_equal",
    # Excel-Operatoren für Post-Conditions. In WHEN-Bedingungen sind diese
    # nicht direkt entscheidungsfähig, werden aber als Metadaten akzeptiert.
    "ggf.": "metadata",
    "ggf": "metadata",
    "maybe": "metadata",
    "sets": "metadata",
    "set": "metadata",
    "bei erfolg": "metadata",
    "bei fehlschlag": "metadata",
    "wird gesetzt": "metadata",
    "werden abgefragt": "metadata",
}

SUPPORTED_OPERATORS = sorted(set(OPERATOR_ALIASES.values()) | set(OPERATOR_ALIASES.keys()))


def normalize_text(value: Any) -> str:
    return str(value).strip().lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def normalize_operator(operator: Any) -> str:
    raw = normalize_text(operator or "equals")
    return OPERATOR_ALIASES.get(raw, raw)


def parse_value(value: Any) -> Any:
    if isinstance(value, str):
        raw = value.strip()
        norm = normalize_text(raw)
        if norm == "true":
            return True
        if norm == "false":
            return False
        if norm in {"null", "none"}:
            return None
        if norm == "unknown":
            return UNKNOWN
        return raw
    return value


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Excel-Zellen enthalten häufig "false, unknown" oder "true oder not_required".
        text = value.replace(" oder ", ",").replace("/", ",")
        return [parse_value(v.strip()) for v in text.split(",") if v.strip()]
    return [value]


def normalize_scalar(value: Any) -> Any:
    value = parse_value(value)
    if isinstance(value, str):
        return normalize_text(value)
    return value


def is_unknown_value(value: Any) -> bool:
    return value in {UNKNOWN, None, ""}


def get_fact(facts: dict[str, Any], fact_name: str) -> Any:
    fact_name = str(fact_name or "")
    if fact_name in facts and not is_unknown_value(facts.get(fact_name)):
        return facts.get(fact_name)
    # Auch unbekannte explizite Werte sollen zurückgegeben werden, wenn kein Alias etwas Besseres liefert.
    direct_value = facts.get(fact_name, UNKNOWN)
    for alias in FACT_ALIASES.get(fact_name, []):
        if alias in facts and not is_unknown_value(facts.get(alias)):
            return facts.get(alias)
    return direct_value


def _to_number(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def normalize_condition(condition: dict[str, Any]) -> dict[str, Any]:
    condition = dict(condition or {})
    if "field" in condition and "fact" not in condition:
        condition["fact"] = condition.pop("field")
    if "expected" in condition and "value" not in condition:
        condition["value"] = condition.pop("expected")
    condition["operator"] = normalize_operator(condition.get("operator", "equals"))
    return condition


def evaluate_single_condition(condition: dict[str, Any], facts: dict[str, Any]) -> bool:
    condition = normalize_condition(condition)
    fact_name = str(condition.get("fact", ""))
    operator = normalize_operator(condition.get("operator", "equals"))
    expected = condition.get("value")
    actual = get_fact(facts, fact_name)

    if operator == "metadata":
        # Metadata-Operatoren gehören in Post-Conditions. Sie sind nicht als harte WHEN-Bedingung gedacht.
        return True
    if operator == "equals":
        return normalize_scalar(actual) == normalize_scalar(expected)
    if operator == "not_equals":
        return normalize_scalar(actual) != normalize_scalar(expected)
    if operator == "in":
        expected_list = ensure_list(expected)
        return normalize_scalar(actual) in [normalize_scalar(v) for v in expected_list]
    if operator == "not_in":
        expected_list = ensure_list(expected)
        return normalize_scalar(actual) not in [normalize_scalar(v) for v in expected_list]
    if operator == "contains":
        return normalize_text(expected) in normalize_text(actual)
    if operator == "contains_any":
        return any(normalize_text(v) in normalize_text(actual) for v in ensure_list(expected))
    if operator == "contains_all":
        return all(normalize_text(v) in normalize_text(actual) for v in ensure_list(expected))
    if operator == "starts_with":
        return normalize_text(actual).startswith(normalize_text(expected))
    if operator == "ends_with":
        return normalize_text(actual).endswith(normalize_text(expected))
    if operator == "regex":
        try:
            return re.search(str(expected), str(actual), flags=re.IGNORECASE) is not None
        except re.error:
            return False
    if operator == "is_unknown":
        return is_unknown_value(actual)
    if operator == "is_known":
        return not is_unknown_value(actual)
    if operator == "is_true":
        return actual is True or normalize_text(actual) == "true"
    if operator == "is_false":
        return actual is False or normalize_text(actual) == "false"

    left = _to_number(actual)
    right = _to_number(expected)
    if left is None or right is None:
        return False
    if operator == "greater_than":
        return left > right
    if operator == "less_than":
        return left < right
    if operator == "greater_or_equal":
        return left >= right
    if operator == "less_or_equal":
        return left <= right
    return False


def evaluate_condition(condition: dict[str, Any], facts: dict[str, Any]) -> bool:
    """Evaluiert eine einzelne Condition oder eine verschachtelte all/any/not-Gruppe."""
    if not isinstance(condition, dict):
        return False
    if "all" in condition or "any" in condition or "not" in condition:
        matched, _trace = evaluate_when(condition, facts)
        return matched
    return evaluate_single_condition(condition, facts)


def evaluate_when(when: dict[str, Any], facts: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    trace: list[dict[str, Any]] = []
    when = when or {}
    all_conditions = when.get("all", []) or []
    any_conditions = when.get("any", []) or []
    not_conditions = when.get("not", []) or []

    all_ok = True
    for condition in all_conditions:
        ok = evaluate_condition(condition, facts)
        fact_name = str(condition.get("fact", condition.get("field", ""))) if isinstance(condition, dict) else ""
        trace.append({"group": "all", "condition": condition, "actual": get_fact(facts, fact_name), "matched": ok})
        if not ok:
            all_ok = False

    if any_conditions:
        any_ok = False
        for condition in any_conditions:
            ok = evaluate_condition(condition, facts)
            fact_name = str(condition.get("fact", condition.get("field", ""))) if isinstance(condition, dict) else ""
            trace.append({"group": "any", "condition": condition, "actual": get_fact(facts, fact_name), "matched": ok})
            if ok:
                any_ok = True
    else:
        any_ok = True

    not_ok = True
    for condition in not_conditions:
        condition_ok = evaluate_condition(condition, facts)
        fact_name = str(condition.get("fact", condition.get("field", ""))) if isinstance(condition, dict) else ""
        ok = not condition_ok
        trace.append({"group": "not", "condition": condition, "actual": get_fact(facts, fact_name), "matched": ok})
        if not ok:
            not_ok = False

    return all_ok and any_ok and not_ok, trace
