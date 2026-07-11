# inference_engine.py
# ============================================================
# JSON-basierte Inferenz-Engine.
# Unterstützt when.all und when.any sowie Actions:
# ask, answer, recommend, redirect_topic, show_steps.
# ============================================================

from __future__ import annotations

from typing import Any

from storage import kb_loader as kb_json
from core.condition_parser import UNKNOWN, evaluate_condition, evaluate_when, get_fact, normalize_text


def resolve_action(action: dict[str, Any]) -> dict[str, Any]:
    action = dict(action)
    if action.get("type") == "show_steps":
        package_key = action.get("step_package_id") or action.get("package_id")
        package = kb_json.get_step_package(str(package_key)) if package_key else None
        action["step_package"] = package
    return action


def _apply_set_fact_actions(actions: list[dict[str, Any]], facts: dict[str, Any]) -> None:
    """Setzt Fakten aus set_fact-Actions direkt im aktuellen Inferenzlauf.

    Dadurch können globale Bausteine und Dienstregeln Fakten ergänzen, ohne dass
    diese Logik in der UI dupliziert werden muss.
    """
    for action in actions:
        if action.get("type") == "set_fact" and action.get("fact"):
            facts[str(action.get("fact"))] = action.get("value")



def _compact_user_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reduziert Ausgaben auf eine klare nächste Nutzerfrage.

    Einige Regeldateien können mehrere passende Ask-Actions liefern. Für den Dialog
    ist das verwirrend. Sichtbar bleibt daher nur die erste Rückfrage plus die
    direkt dazugehörigen Hinweise; technische set_fact-Actions bleiben erhalten.
    """
    if not actions:
        return actions
    compact: list[dict[str, Any]] = []
    seen_texts: set[str] = set()
    first_ask_seen = False
    stop_after_next_ask = False
    for action in actions:
        typ = action.get("type")
        text = str(action.get("text", ""))
        if typ == "set_fact":
            compact.append(action)
            continue
        if typ == "ask":
            if first_ask_seen:
                stop_after_next_ask = True
                continue
            first_ask_seen = True
        if first_ask_seen and stop_after_next_ask:
            continue
        key = f"{typ}:{text}"
        if text and key in seen_texts:
            continue
        if text:
            seen_texts.add(key)
        compact.append(action)
    return compact

def _evaluate_rule_list(
    rules: list[dict[str, Any]],
    facts: dict[str, Any],
    matched_rules: list[dict[str, Any]],
    evaluated_rules: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    *,
    source: str,
) -> bool:
    """Evaluiert eine Regelliste und gibt True zurück, wenn gestoppt werden soll."""
    for rule in rules:
        matched, trace = evaluate_when(rule.get("when", {}), facts)
        evaluated_rules.append({
            "rule_id": rule.get("id"),
            "description": rule.get("description", ""),
            "source": source,
            "scope": rule.get("scope", "service"),
            "global_block_id": rule.get("global_block_id"),
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
            "source": source,
            "scope": rule.get("scope", "service"),
            "global_block_id": rule.get("global_block_id"),
            "actions": resolved_actions,
            "stop_after_match": bool(rule.get("stop_after_match")),
        })
        actions.extend(resolved_actions)
        _apply_set_fact_actions(resolved_actions, facts)
        if rule.get("stop_after_match"):
            return True
    return False


def run_inference(facts: dict[str, Any]) -> dict[str, Any]:
    facts = dict(facts)
    matched_rules: list[dict[str, Any]] = []
    evaluated_rules: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    # 1. Dienstübergreifende Baustein-Regeln laufen zuerst.
    global_rules = kb_json.load_global_inference_rules(active_only=True)
    stopped = _evaluate_rule_list(global_rules, facts, matched_rules, evaluated_rules, actions, source="global_blocks")
    if stopped:
        return {"facts": facts, "matched_rules": matched_rules, "actions": _compact_user_actions(actions), "evaluated_rules": evaluated_rules}

    # 2. Danach laufen die dienst-/modulspezifischen Regeln aus Rule Engine/rules/.
    #    Die aus der Excel-Sicht abgeleiteten technischen Eduroam-Regeln liegen vor
    #    den allgemeinen eduroam-Regeln und können selbst fehlende Facts abfragen.
    service_rules = kb_json.load_inference_rules(active_only=True)
    service_stopped = _evaluate_rule_list(service_rules, facts, matched_rules, evaluated_rules, actions, source="service_rules")
    if service_stopped or actions:
        return {"facts": facts, "matched_rules": matched_rules, "actions": _compact_user_actions(actions), "evaluated_rules": evaluated_rules}

    # 3. Falls keine spezifische Regel greifen konnte, fragt die Engine fehlende
    #    Pflichtinformationen aus den globalen Bausteinen ab. Dadurch blockieren
    #    globale Bausteine keine spezifischen Troubleshooting-Regeln mehr.
    missing_global_action = kb_json.first_missing_required_global_fact(facts)
    if missing_global_action:
        actions.append(missing_global_action)
        matched_rules.append({
            "rule_id": f"global.missing_fact.{missing_global_action.get('fact')}",
            "module": "global",
            "rule_group": missing_global_action.get("global_block_id"),
            "description": f"Fehlender globaler Fakt: {missing_global_action.get('fact')}",
            "source": "global_blocks",
            "scope": "global",
            "global_block_id": missing_global_action.get("global_block_id"),
            "actions": [missing_global_action],
            "stop_after_match": True,
        })
        evaluated_rules.append({
            "rule_id": f"global.missing_fact.{missing_global_action.get('fact')}",
            "description": "Pflichtinformation aus globalem Baustein fehlt.",
            "source": "global_blocks",
            "scope": "global",
            "matched": True,
            "trace": [{"condition": {"fact": missing_global_action.get("fact"), "operator": "is_unknown"}, "actual": facts.get(str(missing_global_action.get("fact")), UNKNOWN), "matched": True}],
        })

    return {"facts": facts, "matched_rules": matched_rules, "actions": _compact_user_actions(actions), "evaluated_rules": evaluated_rules}


def action_texts(result: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for action in result.get("actions", []):
        typ = action.get("type")
        if typ in {"ask", "answer", "recommend", "redirect_topic"}:
            text = action.get("text", "")
            if text:
                texts.append(text)
        elif typ == "function":
            function_id = action.get("function_id") or action.get("id")
            func = kb_json.get_function_item(str(function_id)) if function_id else None
            if func:
                label = func.get("display_name") or function_id
                response = func.get("response_text") or func.get("purpose") or ""
                texts.append(f"{label}: {response}" if response else f"Funktion: {label}")
            else:
                texts.append(f"Funktion ausführen: {function_id}")
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


def _set_credential_fact_aliases(facts: dict[str, Any]) -> None:
    """Synchronisiert inhaltlich gleiche Zugangsdaten-Fakten.

    Im Wissensmodell werden teilweise `username_known` und `kuerzel_known`
    getrennt verwendet. Für Hohenheim-Kontexte meint eine Nutzerantwort wie
    "Ich kenne mein Kürzel" aber gleichzeitig, dass der relevante Benutzername
    grundsätzlich bekannt ist. Diese Synchronisierung verhindert, dass die
    Inferenz dieselbe Rückfrage immer wieder stellt.
    """
    if facts.get("kuerzel_known") is True:
        facts["username_known"] = True
    if facts.get("username_known") is True:
        facts["kuerzel_known"] = True
    if facts.get("kuerzel_known") is False and facts.get("username_known") == UNKNOWN:
        facts["username_known"] = False
    if facts.get("username_known") is False and facts.get("kuerzel_known") == UNKNOWN:
        facts["kuerzel_known"] = False



def facts_from_text(user_text: str) -> dict[str, Any]:
    t = normalize_text(user_text)
    facts: dict[str, Any] = {
        "topic": UNKNOWN,
        "service": UNKNOWN,
        "intent": UNKNOWN,
        "os": UNKNOWN,
        "operating_system": UNKNOWN,
        "device_type": UNKNOWN,
        "account_exists": UNKNOWN,
        "account_activated": UNKNOWN,
        "username_known": UNKNOWN,
        "kuerzel_known": UNKNOWN,
        "password_known": UNKNOWN,
        "password_recently_changed": UNKNOWN,
        "saved_old_credentials": UNKNOWN,
        "internet_available": UNKNOWN,
        "internet_access_available": UNKNOWN,
        "campus_network_available": UNKNOWN,
        "vpn_client_installed": UNKNOWN,
        "mfa_configured": UNKNOWN,
        "two_fa_required": "not_required",
        "two_fa_ready": "not_required",
        "wifi_available": UNKNOWN,
        "wifi_enabled": UNKNOWN,
        "wlan_enabled": UNKNOWN,
        "eduroam_visible": UNKNOWN,
        "eduroam_profile_configured": UNKNOWN,
        "eduroam_profile_installed": UNKNOWN,
        "connection_attempt_status": UNKNOWN,
        "connection_test_required": UNKNOWN,
        "internet_access_available": UNKNOWN,
        "eduroam_connected": UNKNOWN,
        "connection_successful": UNKNOWN,
        "username_format_correct": UNKNOWN,
        "identifier_entered_type": UNKNOWN,
        "email_used_as_username": UNKNOWN,
        "certificate_warning_shown": UNKNOWN,
        "certificate_checked": UNKNOWN,
        "problem_type": UNKNOWN,
        "problem_area": UNKNOWN,
        "user_problem_resolved": UNKNOWN,
        "user_request_answered": UNKNOWN,
        "needs_human_support": UNKNOWN,
        "human_support_needed": UNKNOWN,
        "escalation_reason": UNKNOWN,
        "source_type": UNKNOWN,
        "journey_type": UNKNOWN,
        "account_status": UNKNOWN,
        "account_locked": UNKNOWN,
        "credentials_valid": UNKNOWN,
        "network_context": UNKNOWN,
        "auth_status": UNKNOWN,
        "firewall_proxy_relevant": UNKNOWN,
        "internal_service_access_required": UNKNOWN,
        "mfa_problem_type": UNKNOWN,
        "mfa_app_available": UNKNOWN,
        "mfa_push_available": UNKNOWN,
        "mfa_code_available": UNKNOWN,
        "mfa_recovery_available": UNKNOWN,
        "mfa_challenge_approved": UNKNOWN,
        "vpn_client_version_healthy": UNKNOWN,
        "vpn_endpoint_reachable": UNKNOWN,
        "vpn_endpoint_url": UNKNOWN,
        "login_form_requested": UNKNOWN,
        "vpn_auth_status": UNKNOWN,
        "vpn_tunnel_status": UNKNOWN,
        "vpn_connected": UNKNOWN,
        "internal_resource_accessible": UNKNOWN,
        "eduroam_installation_source": UNKNOWN,
        "eduroam_ca_certificate_present": UNKNOWN,
        "eduroam_scope": UNKNOWN,
        "setup_source_checked": UNKNOWN,
        "external_network": UNKNOWN,
        "service_certificate_status": UNKNOWN,
        "status_goal": UNKNOWN,
        "problem_resolved": UNKNOWN,
        "support_needed": UNKNOWN,
        "support_reason": UNKNOWN,
        "mfa_device_lost": UNKNOWN,
        "mfa_app_installed": UNKNOWN,
        "mfa_totp_available": UNKNOWN,
        "mfa_code_status": UNKNOWN,
        "mfa_recovery_required": UNKNOWN,
        "mfa_enrollment_method": UNKNOWN,
        "mfa_enrollment_required": UNKNOWN,
        "mfa_request_setup": UNKNOWN,
        "mfa_requires_credentials": UNKNOWN,
        "mfa_required_for_vpn_login": UNKNOWN,
        "vpn_installation_status": UNKNOWN,
        "campus_network_required": UNKNOWN,
        "eduroam_for_vpn_setup_required": UNKNOWN,
        "vpn_gateway_profile_valid": UNKNOWN,
        "vpn_gateway_selected": UNKNOWN,
        "vpn_login_form_valid": UNKNOWN,
        "vpn_client_problem_type": UNKNOWN,
        "vpn_problem_type": UNKNOWN,
        "vpn_tunnel_active": UNKNOWN,
        "vpn_permission_required": UNKNOWN,
        "eduroam_campus_location_required": UNKNOWN,
        "eduroam_campus_location_available": UNKNOWN,
        "eduroam_certificate_warning_scope": UNKNOWN,
        "eduroam_certificate_valid": UNKNOWN,
        "eduroam_profile_status": UNKNOWN,
        "eduroam_problem_type": UNKNOWN,
        "eduroam_profile_missing": UNKNOWN,
        "eduroam_cat_profile_installed": UNKNOWN,
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

    facts["service"] = facts["topic"]

    # Wissensmodell: Journey/Quelle und übergreifende Problemtypen
    if any(x in t for x in ["anleitung", "setup", "einrichtung", "installieren", "installationsanleitung"]):
        facts["source_type"] = "setup"
        facts["journey_type"] = "setup"
    if any(x in t for x in ["problem", "fehler", "troubleshooting", "geht nicht", "funktioniert nicht"]):
        facts["source_type"] = "troubleshooting"
        facts["journey_type"] = "troubleshooting"
    if any(x in t for x in ["login", "anmeldung", "anmelden"]):
        facts["journey_type"] = "login"

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
    facts["operating_system"] = facts["os"]

    # Wissensmodell: Netzwerk-Kontext
    if any(x in t for x in ["am campus", "auf dem campus", "in der uni", "an der uni", "uni-netz", "campusnetz"]):
        facts["network_context"] = "campus"
        facts["campus_network_available"] = True
    if any(x in t for x in ["zuhause", "home office", "daheim", "von zuhause", "homeoffice"]):
        facts["network_context"] = "home"
        facts["campus_network_available"] = False
    if any(x in t for x in ["firma", "firmennetz", "fremdes netz", "andere uni", "fremde hochschule", "proxy", "firewall"]):
        facts["network_context"] = "external_network"
        facts["firewall_proxy_relevant"] = True
    if any(x in t for x in ["vpn verbunden", "per vpn", "über vpn", "ueber vpn"]):
        facts["network_context"] = "vpn"
        facts["vpn_connected"] = True
        facts["vpn_tunnel_status"] = "connected"

    no_internet_after_connection = any(x in t for x in ["verbunden aber kein internet", "kein internet nach verbindung", "internet geht nicht trotz verbindung"])
    if any(x in t for x in ["kein internet", "ohne internet", "offline"]) and not no_internet_after_connection:
        facts["internet_available"] = False
    if any(x in t for x in ["internet vorhanden", "internet funktioniert", "online"]):
        facts["internet_available"] = True
    account_negative = any(x in t for x in ["kein konto", "nicht aktiviert", "konto fehlt", "benutzerkonto fehlt", "account fehlt", "konto noch nicht aktiviert", "noch nicht aktiviert"])
    account_positive = ("konto" in t or "account" in t or "benutzerkonto" in t) and any(x in t for x in ["aktiviert", "aktiv", "freigeschaltet", "vorhanden"])
    if account_negative:
        facts["account_activated"] = False
        facts["account_status"] = "not_activated"
    elif account_positive:
        facts["account_activated"] = True
        facts["account_status"] = "active"
    if any(x in t for x in ["account gesperrt", "account ist gesperrt", "konto gesperrt", "konto ist gesperrt", "account blockiert", "konto blockiert", "login gesperrt"]) or (("gesperrt" in t or "blockiert" in t) and any(y in t for y in ["account", "konto", "benutzerkonto", "login"])):
        facts["account_locked"] = True
        facts["account_status"] = "locked"
        facts["needs_human_support"] = True
        facts["human_support_needed"] = True
        facts["escalation_reason"] = "account_locked"
    if any(x in t for x in ["mfa fehlt", "kein zweiter faktor", "kein token"]):
        facts["mfa_configured"] = False
    if any(x in t for x in ["mfa eingerichtet", "token eingerichtet", "2fa eingerichtet"]):
        facts["mfa_configured"] = True
    if any(x in t for x in ["email als benutzername", "e-mail als benutzername", "mailadresse", "vorname.nachname", "e-mail adresse", "email adresse"]):
        facts["email_used_as_username"] = True
        facts["identifier_entered_type"] = "email_personal"
        facts["username_format_correct"] = False
    if any(x in t for x in ["nur kuerzel", "nur kürzel", "reines kuerzel", "reines kürzel"]):
        facts["identifier_entered_type"] = "kuerzel"
        facts["username_format_correct"] = False
    if any(x in t for x in ["kuerzel@uni-hohenheim.de", "kürzel@uni-hohenheim.de", "@uni-hohenheim.de"]):
        facts["identifier_entered_type"] = "email_kuerzel_domain"
        facts["username_format_correct"] = True
        facts["username_known"] = True
    # Zugangsdaten / Benutzerkennung robuster erkennen.
    # Wichtig: negative Muster zuerst prüfen, damit "nicht" nicht versehentlich als bekannt gilt.
    username_negative = any(x in t for x in [
        "benutzername unbekannt", "benutzername fehlt", "kenne mein benutzername nicht",
        "kenne meinen benutzernamen nicht", "kenne mein kuerzel nicht", "kenne mein kürzel nicht",
        "kuerzel unbekannt", "kürzel unbekannt", "kuerzel fehlt", "kürzel fehlt",
    ])
    username_positive = any(x in t for x in [
        "benutzername bekannt", "benutzernamen bekannt", "kuerzel bekannt", "kürzel bekannt",
        "ich kenne mein kuerzel", "ich kenne mein kürzel", "ich kenne meinen benutzernamen",
        "ich kenne mein benutzername", "kenne mein kuerzel", "kenne mein kürzel",
        "kenne meinen benutzernamen", "mein kuerzel", "mein kürzel", "mein benutzername",
        "meinen benutzernamen", "benutzername habe ich", "benutzernamen habe ich",
        "benutzername hab ich", "benutzernamen hab ich", "kuerzel habe ich", "kürzel habe ich",
        "kuerzel hab ich", "kürzel hab ich",
    ]) or (
        any(x in t for x in ["benutzername", "benutzernamen", "kuerzel", "kürzel", "kennung", "benutzerkennung"])
        and any(x in t for x in ["kenne", "bekannt", "habe", "hab", "vorhanden", "weiss", "weiß"])
        and not any(x in t for x in ["nicht", "kein", "keine", "unbekannt", "fehlt", "vergessen"])
    )
    if username_negative:
        facts["username_known"] = False
        facts["kuerzel_known"] = False
    elif username_positive:
        facts["username_known"] = True
        facts["kuerzel_known"] = True

    password_negative = any(x in t for x in [
        "passwort vergessen", "kennwort vergessen", "passwort unbekannt", "kennwort unbekannt",
        "kenne mein passwort nicht", "kenne mein kennwort nicht", "passwort fehlt",
        "kennwort fehlt", "kein passwort", "kein kennwort",
    ])
    password_positive = any(x in t for x in [
        "passwort bekannt", "kennwort bekannt", "ich kenne mein passwort", "ich kenne mein kennwort",
        "kenne mein passwort", "kenne mein kennwort", "passwort habe ich", "kennwort habe ich",
        "passwort hab ich", "kennwort hab ich", "mein passwort", "mein kennwort",
        "benutzername und passwort", "benutzernamen und passwort", "kuerzel und passwort", "kürzel und passwort",
        "zugangsdaten bekannt", "zugangsdaten habe ich", "zugangsdaten hab ich",
        "zugangsdaten vorhanden",
    ]) or (
        any(x in t for x in ["passwort", "kennwort", "zugangsdaten"])
        and any(x in t for x in ["kenne", "bekannt", "habe", "hab", "vorhanden", "weiss", "weiß"])
        and not any(x in t for x in ["nicht", "kein", "keine", "unbekannt", "fehlt", "vergessen", "falsch"])
    )
    if password_negative:
        facts["password_known"] = False
    elif password_positive:
        facts["password_known"] = True

    if any(x in t for x in ["zugangsdaten bekannt", "zugangsdaten habe ich", "zugangsdaten hab ich", "zugangsdaten vorhanden"]):
        facts["username_known"] = True
        facts["kuerzel_known"] = True
        facts["password_known"] = True

    _set_credential_fact_aliases(facts)
    if any(x in t for x in ["zugangsdaten funktionieren", "login funktioniert", "passwort funktioniert", "benutzername und passwort funktionieren"]):
        facts["credentials_valid"] = True
        facts["auth_status"] = "accepted"
    if any(x in t for x in ["zugangsdaten falsch", "login abgelehnt", "passwort falsch", "authentifizierung fehlgeschlagen", "login fehlgeschlagen"]):
        facts["credentials_valid"] = False
        facts["auth_status"] = "rejected"
    if any(x in t for x in ["passwort geaendert", "passwort geändert", "kennwort geaendert", "kennwort geändert", "neues passwort"]):
        facts["password_recently_changed"] = True
    if any(x in t for x in ["kein wlan", "wlan fehlt", "kein wifi"]):
        facts["wifi_available"] = False
    if any(x in t for x in ["wlan vorhanden", "wifi vorhanden"]):
        facts["wifi_available"] = True
    if any(x in t for x in ["wlan deaktiviert", "wifi deaktiviert", "wlan aus"]):
        facts["wifi_enabled"] = False
        facts["wlan_enabled"] = False
    if any(x in t for x in ["wlan aktiviert", "wlan ist aktiviert", "wifi aktiviert", "wifi ist aktiviert", "wlan an"]):
        facts["wifi_enabled"] = True
        facts["wlan_enabled"] = True
        facts["wifi_available"] = True
    if any(x in t for x in ["eduroam nicht sichtbar", "eduroam wird nicht angezeigt", "eduroam fehlt", "eduroam nicht in der liste"]):
        facts["eduroam_visible"] = False
        facts["problem_type"] = "eduroam_not_visible"
    if any(x in t for x in ["eduroam sichtbar", "eduroam ist sichtbar", "eduroam wird angezeigt"]):
        facts["eduroam_visible"] = True
    if any(x in t for x in ["profil installiert", "profil eingerichtet", "eduroam eingerichtet"]):
        facts["eduroam_profile_configured"] = True
        facts["eduroam_profile_installed"] = True
    if any(x in t for x in ["profil fehlt", "profil nicht installiert", "noch nicht eingerichtet"]):
        facts["eduroam_profile_configured"] = False
        facts["eduroam_profile_installed"] = False
    if any(x in t for x in ["zertifikat", "sicherheitswarnung", "certificate warning"]):
        facts["certificate_warning_shown"] = True
        facts["problem_type"] = "certificate_warning"
    if any(x in t for x in ["keine verbindung", "verbindet nicht", "authentifizierung fehlgeschlagen", "authentication failed"]):
        facts["connection_attempt_status"] = "failed"
        facts["problem_type"] = "authentication_failed" if "auth" in t else "cannot_connect"
    if any(x in t for x in ["verbunden aber kein internet", "kein internet nach verbindung", "internet geht nicht"]):
        facts["connection_attempt_status"] = "success"
        facts["internet_access_available"] = False
        facts["problem_type"] = "no_internet"
    if any(x in t for x in ["verbindung bricht ab", "abbrueche", "abbrüche", "disconnect", "connection drops"]):
        facts["problem_type"] = "connection_drops"
    if any(x in t for x in ["eduroam verbunden", "verbindung erfolgreich"]):
        facts["eduroam_connected"] = True
        facts["connection_successful"] = True
        facts["connection_attempt_status"] = "success"
    if facts.get("account_activated") is True:
        facts["account_exists"] = True
    elif facts.get("account_activated") is False:
        facts["account_exists"] = False
    # Wissensmodell: MFA-spezifische Zustände
    if any(x in t for x in ["handy verloren", "smartphone verloren", "neues handy", "kein zugriff auf authenticator", "2fa app weg", "mfa app weg"]):
        facts["mfa_problem_type"] = "lost_device"
        facts["mfa_app_available"] = False
    if any(x in t for x in ["recovery code", "recovery-code", "wiederherstellungscode", "backup code"]):
        facts["mfa_problem_type"] = "recovery"
        facts["mfa_recovery_available"] = True
    if any(x in t for x in ["push kommt nicht", "keine push", "mfa push", "push anfrage"]):
        facts["mfa_problem_type"] = "no_code"
        facts["mfa_code_available"] = False
        facts["mfa_totp_available"] = False
        facts["mfa_code_status"] = "missing"
    if any(x in t for x in ["code kommt nicht", "kein code", "keinen code", "kein mfa code", "keinen mfa code", "tan fehlt", "2fa code fehlt"]):
        facts["mfa_problem_type"] = "no_code"
        facts["mfa_code_available"] = False
    if any(x in t for x in ["mfa bestätigt", "mfa bestaetigt", "2fa bestätigt", "2fa bestaetigt", "code eingegeben"]):
        facts["mfa_challenge_approved"] = True
        facts["mfa_challenge_status"] = "approved"
    if any(x in t for x in ["mfa abgelehnt", "2fa abgelehnt", "challenge abgelehnt", "timeout"]):
        facts["mfa_challenge_approved"] = False
        facts["mfa_challenge_status"] = "rejected" if "abgelehnt" in t else "timeout"

    # Wissensmodell: VPN-spezifische Zustände
    if any(x in t for x in ["cisco secure client installiert", "vpn client installiert", "secure client installiert"]):
        facts["vpn_client_installed"] = True
    if any(x in t for x in ["vpn client fehlt", "cisco fehlt", "secure client fehlt", "vpn nicht installiert"]):
        facts["vpn_client_installed"] = False
    if any(x in t for x in ["vpn.uni-hohenheim.de", "vpn endpunkt", "vpn server"]):
        facts["vpn_endpoint_reachable"] = True
        facts["vpn_endpoint_url"] = "vpn.uni-hohenheim.de"
    if any(x in t for x in ["vpn login formular", "login formular", "vpn fragt login", "vpn fragt nach login"]):
        facts["login_form_requested"] = True
    if any(x in t for x in ["vpn tunnel verbunden", "tunnel verbunden", "vpn ist verbunden"]):
        facts["vpn_tunnel_status"] = "connected"
        facts["vpn_connected"] = True
    if any(x in t for x in ["vpn tunnel fehlgeschlagen", "tunnel fehlgeschlagen", "vpn verbindet nicht"]):
        facts["vpn_tunnel_status"] = "failed"
        facts["vpn_connected"] = False
    if any(x in t for x in ["interne ressourcen erreichbar", "internen dienst erreicht", "intranet erreichbar"]):
        facts["internal_resource_accessible"] = True
    if any(x in t for x in ["interne ressourcen nicht erreichbar", "interne ressource nicht erreichbar", "ressource nicht erreichbar", "interner dienst nicht erreichbar", "intranet nicht erreichbar"]):
        facts["internal_resource_accessible"] = False
        facts["internal_service_access_required"] = True

    if facts.get("mfa_configured") is True:
        facts["two_fa_ready"] = True
    elif facts.get("mfa_configured") is False:
        facts["two_fa_ready"] = False


    # Wissensmodell v2: Quelle/Journey, Statusziel und Support
    if any(x in t for x in ["fertig", "abgeschlossen", "hat funktioniert", "funktioniert jetzt", "problem geloest", "problem gelöst"]):
        facts["problem_resolved"] = True
        facts["user_problem_resolved"] = True
        facts["status_goal"] = "problem_resolved"
    if any(x in t for x in ["immer noch nicht", "weiterhin nicht", "ungeloest", "ungelöst", "klappt weiterhin nicht"]):
        facts["problem_resolved"] = False
        facts["user_problem_resolved"] = False
        facts["problem_unresolved"] = True
        facts["status_goal"] = "support_needed"
    if any(x in t for x in ["support", "servicedesk", "service desk", "kim-it", "eskalieren"]):
        facts["needs_human_support"] = True
        facts["support_needed"] = True
        facts["status_goal"] = "support_needed"

    # Wissensmodell v2: MFA als zeitbasierter Code, keine Push-Annahme
    if any(x in t for x in ["totp", "zeitbasierter code", "30 sekunden", "30-sekunden", "authenticator code", "authenticator-code", "2fa-code", "mfa-code"]):
        facts["mfa_totp_available"] = True
        facts["mfa_code_available"] = True
        facts["mfa_code_status"] = "available"
        facts["second_factor_source"] = "authenticator_app"
    if any(x in t for x in ["code abgelaufen", "code ist abgelaufen", "code expired", "totp abgelaufen"]):
        facts["mfa_code_status"] = "expired"
        facts["mfa_challenge_status"] = "timeout"
        facts["mfa_challenge_approved"] = False
    if any(x in t for x in ["code ungültig", "code ungueltig", "ungültiger code", "ungueltiger code", "falscher code"]):
        facts["mfa_code_status"] = "invalid"
        facts["mfa_challenge_approved"] = False
    if any(x in t for x in ["kein code", "code fehlt", "sehe keinen code", "authenticator app nicht verfügbar", "authenticator app nicht verfuegbar"]):
        facts["mfa_code_status"] = "missing"
        facts["mfa_totp_available"] = False
        facts["mfa_code_available"] = False
    if any(x in t for x in ["handy verloren", "smartphone verloren", "gerät verloren", "geraet verloren", "authenticator verloren", "authenticator ist verloren", "neues handy", "app gelöscht", "app geloescht"]):
        facts["mfa_device_lost"] = True
        facts["mfa_problem_type"] = "lost_device"
        facts["mfa_app_available"] = False
        facts["mfa_recovery_required"] = True
    if any(x in t for x in ["mfa einrichten", "mfa registrieren", "2fa einrichten", "2fa registrieren"]):
        facts["mfa_enrollment_required"] = True
        facts["mfa_request_setup"] = True

    # Wissensmodell v2: VPN-Client, Gateway, Tunnel und Ressourcen
    if any(x in t for x in ["vpn profil", "vpn-profil", "gateway", "vpn gateway", "serverprofil"]):
        facts["vpn_profile_configured"] = True if any(y in t for y in ["korrekt", "gültig", "gueltig", "eingestellt", "konfiguriert"]) else facts.get("vpn_profile_configured", UNKNOWN)
        facts["vpn_gateway_selected"] = True
    if any(x in t for x in ["gateway falsch", "profil falsch", "vpn profil falsch", "falscher server"]):
        facts["vpn_gateway_profile_valid"] = False
        facts["vpn_problem_type"] = "client_problem"
    if any(x in t for x in ["client problem", "vpn client problem", "secure client problem", "client startet nicht", "client veraltet"]):
        facts["vpn_client_version_healthy"] = False
        facts["vpn_client_problem_type"] = "client_failed"
        facts["vpn_problem_type"] = "client_problem"
    if any(x in t for x in ["firewall blockiert vpn", "proxy blockiert vpn", "vpn im firmennetz", "vpn im fremdnetz"]):
        facts["firewall_proxy_relevant"] = True
        facts["external_network"] = True
        facts["vpn_problem_type"] = "firewall_proxy"
    if any(x in t for x in ["keine berechtigung", "permission", "zugriff verweigert", "ressource nicht berechtigt"]):
        facts["vpn_permission_required"] = True
        facts["vpn_problem_type"] = "permission_missing"

    # Wissensmodell v2: eduroam Campus/SSID/Profile/Zertifikat/Verbindung
    if any(x in t for x in ["nicht am campus", "nicht auf dem campus", "nicht vor ort"]):
        facts["eduroam_campus_location_available"] = False
        facts["campus_network_available"] = False
    if any(x in t for x in ["am campus", "auf dem campus", "vor ort"]):
        facts["eduroam_campus_location_available"] = True
    if facts.get("eduroam_visible") is False:
        facts["eduroam_problem_type"] = "not_visible"
    if any(x in t for x in ["cat profil", "cat-profil", "eduroam profil", "profil fehlt", "profil ungültig", "profil ungueltig"]):
        facts["eduroam_profile_status"] = "missing" if any(y in t for y in ["fehlt", "nicht installiert"]) else facts.get("eduroam_profile_status", UNKNOWN)
        if facts.get("eduroam_profile_status") == "missing":
            facts["eduroam_profile_missing"] = True
            facts["eduroam_profile_configured"] = False
            facts["eduroam_problem_type"] = "profile_missing"
    if any(x in t for x in ["cat profil installiert", "cat-profil installiert", "profil installiert", "profil konfiguriert"]):
        facts["eduroam_cat_profile_installed"] = True
        facts["eduroam_profile_status"] = "installed"
    if any(x in t for x in ["zertifikat gültig", "zertifikat gueltig", "zertifikat geprüft", "zertifikat geprueft"]):
        facts["eduroam_certificate_valid"] = True
        facts["certificate_checked"] = True
    if facts.get("certificate_warning_shown") is True:
        facts["eduroam_problem_type"] = "certificate_warning"
        facts["eduroam_certificate_warning_scope"] = "eduroam_only"
    if facts.get("internet_access_available") is False and facts.get("eduroam_connected") is True:
        facts["eduroam_problem_type"] = "no_internet"

    # Aliase angleichen, damit globale und technische Regeln dieselben Fakten sehen.
    if facts.get("needs_human_support") is not UNKNOWN:
        facts["human_support_needed"] = facts.get("needs_human_support")
    if facts.get("eduroam_connected") is True:
        facts["auth_status"] = "accepted" if facts.get("auth_status") == UNKNOWN else facts.get("auth_status")
    _set_credential_fact_aliases(facts)
    return facts
