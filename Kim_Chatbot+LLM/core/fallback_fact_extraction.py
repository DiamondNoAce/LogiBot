"""Regelbasierte Freitext- und Kontext-Faktenerkennung ohne LLM.

Dieses Modul ist bewusst deterministisch: Es soll die wichtigsten kurzen
Folgeantworten in laufenden Dialogen verstehen, wenn Ollama/Groq deaktiviert ist.
Die Rule Engine entscheidet danach weiterhin selbst über den nächsten Schritt.
"""
from __future__ import annotations

from typing import Any

from core.condition_parser import UNKNOWN, normalize_text


def is_unknown_value(value: Any) -> bool:
    return value is None or value == "" or (isinstance(value, str) and value.lower() == "unknown")


def _has_any(text: str, phrases: list[str]) -> bool:
    return any(p in text for p in phrases)


def _detect_previous_service_use(t: str) -> bool:
    """Erkennt, ob der Nutzer einen Dienst schon genutzt hat und nun ein neues Problem meldet.

    In diesem Fall sollen nicht wieder die Basisvoraussetzungen wie Account,
    Benutzername oder Passwort abgefragt werden. Diese Fakten werden als
    grundsätzlich vorhanden angenommen und der Dialog springt in den
    Troubleshooting-Pfad.
    """
    explicit_previous = [
        "bereits genutzt", "bereits verwendet", "bereits benutzt", "schon genutzt",
        "schon verwendet", "schon benutzt", "vorher genutzt", "vorher verwendet",
        "vorher benutzt", "bisher genutzt", "bisher verwendet", "normal genutzt",
        "normal verwendet", "normal benutzt", "hat vorher funktioniert",
        "funktionierte vorher", "ging vorher", "ging bisher", "hat bisher funktioniert",
        "bis vor", "vor einer woche", "letzte woche", "letzter woche",
        "seit gestern", "seit heute", "seit einer woche", "seit letzte woche",
        "seit letzter woche", "seit kurzem", "auf einmal", "plötzlich", "ploetzlich",
    ]
    stopped_working = [
        "geht nicht mehr", "funktioniert nicht mehr", "klappt nicht mehr",
        "verbindet nicht mehr", "kann mich nicht mehr verbinden",
        "komme nicht mehr rein", "nicht mehr rein",
    ]
    return _has_any(t, explicit_previous) or _has_any(t, stopped_working)


def _apply_existing_service_assumptions(facts: dict[str, Any], service_key: str) -> None:
    """Setzt sichere Grundannahmen für Dienste, die früher schon funktioniert haben."""
    if not service_key:
        return
    facts["service_previously_used"] = True
    facts["service_previously_worked"] = True
    facts["previous_use_context"] = "existing_service_stopped_working"
    facts["intent"] = "troubleshooting"
    facts["journey_type"] = "troubleshooting"
    facts["source_type"] = "troubleshooting"
    facts["skip_initial_prerequisites"] = True

    # Gemeinsame Login-Grundlagen: Wenn der Dienst bereits genutzt wurde,
    # sind Account und Kennung grundsätzlich vorhanden. Das Passwort kann
    # sich geändert haben, aber die Frage soll gezielt danach gestellt werden.
    facts["account_exists"] = True
    facts["account_activated"] = True
    facts["account_status"] = "active"
    facts["username_known"] = True
    facts["kuerzel_known"] = True
    facts["password_known"] = True
    facts["credentials_assumed_from_previous_use"] = True

    if service_key == "eduroam":
        facts["eduroam_previously_worked"] = True
        # Bei einem Dienst, der letzte Woche noch funktioniert hat, sind diese
        # Basisvoraussetzungen fachlich plausibel vorhanden. Sie sollen im
        # Troubleshooting nicht erneut abgefragt werden.
        facts["wifi_available"] = True
        facts["wifi_enabled"] = True
        facts["wlan_enabled"] = True
        facts["eduroam_profile_configured"] = True
        facts["eduroam_profile_installed"] = True
        facts["eduroam_profile_status"] = "installed"
        facts["eduroam_cat_profile_installed"] = True
        # "geht nicht mehr" ist zunächst mehrdeutig: eventuell kann sich der
        # Nutzer gar nicht verbinden, eventuell ist er verbunden, aber hat kein
        # Internet. Deshalb nicht direkt auf failed setzen, sondern gezielt nach
        # Sichtbarkeit und Verbindungsstatus fragen.
        facts["connection_attempt_status"] = "not_tested"
        facts["connection_test_required"] = True
        facts["problem_type"] = facts.get("problem_type") or "existing_connection_issue"
        facts["eduroam_problem_type"] = facts.get("eduroam_problem_type") or "existing_connection_issue"
        # two_fa_ready ist für eduroam nicht relevant, verhindert aber
        # technische Regeln, die andernfalls auf einen unbekannten zweiten Faktor warten.
        facts["two_fa_ready"] = "not_required"
    elif service_key == "vpn":
        facts["vpn_previously_worked"] = True
        facts["vpn_client_installed"] = True
        facts["vpn_installation_status"] = "installed"
        facts["vpn_profile_configured"] = True
        facts["vpn_gateway_selected"] = True
        facts["mfa_configured"] = True
        facts["two_fa_ready"] = True
        facts["mfa_required_for_vpn_login"] = True
        facts["vpn_connected"] = False
        facts["vpn_tunnel_status"] = "failed"
        facts["vpn_problem_type"] = facts.get("vpn_problem_type") or "existing_connection_failed"
    elif service_key == "mfa":
        facts["mfa_previously_worked"] = True
        facts["mfa_configured"] = True
        facts["two_fa_ready"] = True
        facts["mfa_app_available"] = True
        facts["mfa_problem_type"] = facts.get("mfa_problem_type") or "existing_mfa_problem"


def _sync_aliases(facts: dict[str, Any]) -> dict[str, Any]:
    synced = dict(facts or {})
    if synced.get("kuerzel_known") is True:
        synced["username_known"] = True
    if synced.get("username_known") is True:
        synced["kuerzel_known"] = True
    if synced.get("kuerzel_known") is False and is_unknown_value(synced.get("username_known")):
        synced["username_known"] = False
    if synced.get("username_known") is False and is_unknown_value(synced.get("kuerzel_known")):
        synced["kuerzel_known"] = False
    if synced.get("account_activated") is True:
        synced["account_exists"] = True
        synced["account_status"] = "active"
    elif synced.get("account_activated") is False:
        synced["account_exists"] = False
        synced["account_status"] = "not_activated"
    if synced.get("mfa_configured") is True:
        synced["two_fa_ready"] = True
    elif synced.get("mfa_configured") is False:
        synced["two_fa_ready"] = False
    if synced.get("wifi_enabled") is True:
        synced["wlan_enabled"] = True
        synced["wifi_available"] = True
    if synced.get("wlan_enabled") is True:
        synced["wifi_enabled"] = True
        synced["wifi_available"] = True
    if synced.get("mfa_code_status") == "available":
        synced["mfa_code_available"] = True
        synced["mfa_totp_available"] = True
        synced["second_factor_source"] = "authenticator_app"
    return synced


YES_MARKERS = [
    "ja", "jaa", "jap", "jep", "jo", "yes", "genau", "stimmt", "korrekt", "richtig",
    "klar", "natuerlich", "natürlich", "habe ich", "hab ich", "kenne ich", "kenn ich",
    "funktioniert", "klappt", "geht", "erledigt", "fertig", "passt", "vorhanden",
    "aktiv", "aktiviert", "eingerichtet", "verfuegbar", "verfügbar", "angezeigt",
]
NO_MARKERS = [
    "nein", "nee", "noe", "nö", "no", "nicht", "kein", "keine", "ohne", "fehlt",
    "unbekannt", "vergessen", "verloren", "weg", "klappt nicht", "funktioniert nicht",
    "geht nicht", "geht leider nicht", "falsch", "abgelehnt", "ungueltig", "ungültig",
]
UNKNOWN_MARKERS = [
    "weiss nicht", "weiß nicht", "keine ahnung", "unklar", "vielleicht", "bin mir nicht sicher",
    "nicht sicher", "ka", "kp", "weiss ich nicht", "weiß ich nicht",
]

QUESTION_STARTERS = [
    "wie", "was", "woran", "wo", "welche", "welcher", "welches", "warum", "weshalb",
    "kannst", "koennen", "können", "kann ich", "soll ich", "muss ich", "wofuer", "wofür",
]
QUESTION_MARKERS = [
    "?", "wie erkenne", "wie sehe", "wo sehe", "woran erkenne", "was bedeutet", "was ist",
    "wie kann ich", "kannst du", "erklaer", "erklär", "erklaere", "erkläre",
]


def is_user_question(text: str) -> bool:
    """Erkennt, ob die Eingabe eher eine Rückfrage/Verständnisfrage ist.

    Wichtig: Solche Eingaben sollen nicht blind als Antwort auf die letzte
    Ja/Nein- oder OS-Frage interpretiert werden. Wenn ein LLM aktiv ist, darf
    es hier bevorzugt zur Kontextklärung genutzt werden; ohne LLM greifen
    feste Erklärpfade.
    """
    t = normalize_text(text).strip()
    if not t:
        return False
    first = t.split()[0] if t.split() else ""
    return first in QUESTION_STARTERS or _has_any(t, QUESTION_MARKERS)


def _mentions_operating_system_help(t: str) -> bool:
    if not _has_any(t, ["betriebssystem", "betriebsystem", "os", "system"]):
        return False
    help_words = ["was", "wie", "woran", "wo", "welches", "welcher", "welche", "erkenne", "sehen", "finde", "heraus", "raus", "bedeutet", "erklaer", "erklär"]
    return is_user_question(t) or _has_any(t, help_words)


def answer_is_yes(text: str) -> bool:
    t = normalize_text(text)
    if _has_any(t, ["geht nicht", "funktioniert nicht", "klappt nicht", "nicht vorhanden", "nicht angezeigt"]):
        return False
    return _has_any(t, YES_MARKERS) and not _has_any(t, ["nein", "kein", "keine", "ohne", "vergessen", "verloren", "ungueltig", "ungültig"])


def answer_is_no(text: str) -> bool:
    t = normalize_text(text)
    return _has_any(t, NO_MARKERS)


def answer_is_unknown(text: str) -> bool:
    return _has_any(normalize_text(text), UNKNOWN_MARKERS)


BOOLEAN_FACTS = {
    "account_exists", "account_activated", "username_known", "kuerzel_known", "password_known", "password_recently_changed",
    "internet_available", "internet_access_available", "campus_network_available", "vpn_client_installed",
    "mfa_configured", "two_fa_ready", "wifi_available", "wifi_enabled", "wlan_enabled", "eduroam_visible",
    "eduroam_profile_configured", "eduroam_profile_installed", "eduroam_connected", "connection_successful",
    "username_format_correct", "certificate_warning_shown", "certificate_checked", "needs_human_support",
    "human_support_needed", "account_locked", "credentials_valid", "mfa_app_available", "mfa_code_available",
    "mfa_recovery_available", "mfa_challenge_approved", "mfa_totp_available", "mfa_required_for_vpn_login",
    "vpn_client_version_healthy", "vpn_endpoint_reachable", "login_form_requested", "vpn_connected",
    "internal_resource_accessible", "setup_source_checked", "external_network", "problem_resolved",
    "eduroam_internet_access",
    "user_problem_resolved", "support_needed", "problem_unresolved",
    "service_previously_used", "service_previously_worked", "skip_initial_prerequisites",
    "eduroam_previously_worked", "vpn_previously_worked", "mfa_previously_worked",
    "credentials_assumed_from_previous_use",
}

FACT_KEYWORDS = {
    "username_known": ["benutzername", "benutzernamen", "kuerzel", "kürzel", "kennung", "benutzerkennung", "zugangsdaten", "daten"],
    "kuerzel_known": ["benutzername", "benutzernamen", "kuerzel", "kürzel", "kennung", "benutzerkennung", "zugangsdaten", "daten"],
    "password_known": ["passwort", "kennwort", "zugangsdaten", "daten"],
    "password_recently_changed": ["passwort", "kennwort", "geaendert", "geändert", "neues passwort", "seitdem", "letzter erfolgreicher"],
    "account_exists": ["konto", "account", "benutzerkonto", "aktiv", "aktiviert", "freigeschaltet"],
    "account_activated": ["konto", "account", "benutzerkonto", "aktiv", "aktiviert", "freigeschaltet"],
    "mfa_configured": ["mfa", "2fa", "authenticator", "zweiter faktor", "eingerichtet"],
    "two_fa_ready": ["mfa", "2fa", "authenticator", "code", "token"],
    "mfa_code_available": ["mfa", "2fa", "code", "authenticator", "token"],
    "mfa_totp_available": ["mfa", "2fa", "code", "authenticator", "token", "30 sekunden"],
    "mfa_challenge_approved": ["mfa", "2fa", "code", "authenticator", "token", "login", "anmeldung", "eingegeben"],
    "mfa_required_for_vpn_login": ["mfa", "2fa", "code", "vpn", "login", "abgefragt"],
    "vpn_client_installed": ["vpn", "cisco", "secure client", "client", "installiert"],
    "vpn_connected": ["vpn", "tunnel", "verbunden"],
    "internet_available": ["internet", "online", "offline"],
    "internet_access_available": ["internet", "online", "offline"],
    "wifi_available": ["wlan", "wifi", "funknetz", "adapter"],
    "wifi_enabled": ["wlan", "wifi", "aktiviert", "an", "aus"],
    "wlan_enabled": ["wlan", "wifi", "aktiviert", "an", "aus"],
    "eduroam_visible": ["eduroam", "sichtbar", "angezeigt", "liste"],
    "eduroam_connected": ["eduroam", "verbunden", "verbindung", "verbinden"],
    "connection_attempt_status": ["eduroam", "verbinden", "verbindung", "verbunden", "login", "anmeldung"],
    "internet_access_available": ["internet", "online", "offline", "zugriff"],
    "eduroam_internet_access": ["internet", "online", "offline", "zugriff"],
    "eduroam_profile_configured": ["eduroam", "profil", "installiert", "eingerichtet"],
    "eduroam_profile_installed": ["eduroam", "profil", "installiert", "eingerichtet"],
    "problem_resolved": ["problem", "funktioniert", "klappt", "geht wieder", "gelöst", "geloest"],
    "user_problem_resolved": ["problem", "funktioniert", "klappt", "geht wieder", "gelöst", "geloest"],
}


def _looks_like_simple_reply(text: str) -> bool:
    t = normalize_text(text)
    words = [w for w in t.replace(",", " ").replace(".", " ").replace("!", " ").split() if w]
    if len(words) > 5:
        return False
    # Kurze Antworten mit eigenem Sachkontext dürfen nicht blind auf die letzte Frage gemappt werden.
    # Beispiel: Frage nach Passwort, Antwort "Jaa ich kenne mein Kürzel" darf nicht password_known=True setzen.
    content_markers = [
        "konto", "account", "benutzerkonto", "benutzername", "benutzernamen", "kuerzel", "kennung",
        "passwort", "kennwort", "zugangsdaten", "mfa", "2fa", "code", "authenticator", "vpn",
        "eduroam", "wlan", "wifi", "internet", "profil", "zertifikat", "client",
    ]
    if _has_any(t, content_markers):
        return False
    return answer_is_yes(t) or answer_is_no(t) or answer_is_unknown(t)


def _answer_addresses_pending_fact(text: str, pending_fact: str | None) -> bool:
    if not pending_fact:
        return False
    if _looks_like_simple_reply(text):
        return True
    t = normalize_text(text)
    return _has_any(t, FACT_KEYWORDS.get(str(pending_fact), []))


def _base_facts_from_text(text: str) -> dict[str, Any]:
    t = normalize_text(text)
    facts: dict[str, Any] = {}

    if is_user_question(text):
        facts["user_question"] = True

    if "eduroam" in t or ("wlan" in t and "vpn" not in t):
        facts["topic"] = "eduroam"
        facts["service"] = "eduroam"
    elif "vpn" in t or "cisco" in t or "secure client" in t:
        facts["topic"] = "vpn"
        facts["service"] = "vpn"
    elif "mfa" in t or "2fa" in t or "authenticator" in t or "zweiter faktor" in t or "totp" in t:
        facts["topic"] = "mfa"
        facts["service"] = "mfa"
    elif _has_any(t, ["benutzerkonto", "account", "passwort", "benutzername", "idm", "kennwort"]):
        facts["topic"] = "user_account"
        facts["service"] = "user_account"

    if _has_any(t, ["bibliothek", "datenbank", "datenbanken", "e-journal", "ejournal", "e-book", "ebook"]):
        facts["user_request"] = "library_database_access"
        facts["internal_service_access_required"] = True
        facts["vpn_needed"] = True
        # Für externe Bibliotheksdatenbanken ist VPN der relevante Dienstpfad.
        if "vpn" not in t and "eduroam" not in t:
            facts["topic"] = "vpn"
            facts["service"] = "vpn"
            facts["intent"] = "information"

    # Wenn der Nutzer sagt, dass ein Dienst bereits funktioniert hat und nun
    # nicht mehr geht, wird direkt in den Troubleshooting-Kontext gewechselt.
    # Dadurch werden Basisvoraussetzungen wie Account-Aktivierung nicht erneut
    # abgefragt.
    current_service = str(facts.get("service") or facts.get("topic") or "").lower()
    if current_service in {"eduroam", "vpn", "mfa"} and _detect_previous_service_use(t):
        _apply_existing_service_assumptions(facts, current_service)

    if _has_any(t, ["einrichten", "installieren", "installation", "setup", "verbinden", "aktivieren", "erstellen"]):
        if not facts.get("service_previously_used"):
            facts["intent"] = "setup"
    if _has_any(t, ["problem", "fehler", "geht nicht", "funktioniert nicht", "klappt nicht", "haengt", "hängt", "geht nicht mehr", "funktioniert nicht mehr"]):
        facts["intent"] = "troubleshooting"
    if _has_any(t, ["login", "anmelden", "anmeldung"]):
        facts["intent"] = "login"
    if _has_any(t, ["info", "information", "nur eine allgemeine information", "allgemeine information"]):
        facts["intent"] = "information"
    if _has_any(t, ["reset", "zuruecksetzen", "zurücksetzen", "passwort vergessen", "kennwort vergessen"]):
        facts["intent"] = "password_reset"
        facts["help_request"] = "password_reset"
        facts["password_known"] = False

    if _has_any(t, ["windows", "win10", "win11", "pc"]):
        facts["os"] = "windows"
    elif _has_any(t, ["macos", "mac os", "macbook", "apple", "osx", "mac"]):
        facts["os"] = "macos"
    elif "linux" in t:
        facts["os"] = "linux"
    elif "android" in t:
        facts["os"] = "android"
    elif "ipad" in t or "ipados" in t:
        facts["os"] = "ipados"
    elif "iphone" in t or "ios" in t:
        facts["os"] = "ios"
    if "os" in facts:
        facts["operating_system"] = facts["os"]

    if _mentions_operating_system_help(t) or _has_any(t, ["was ist ein betriebssystem", "was ist betriebssystem", "was ist ein betriebsystem", "was ist betriebsystem", "was bedeutet betriebssystem", "betriebssystem?", "was ist ein os"]):
        facts["explanation_request"] = "operating_system"
        facts["question_target_fact"] = "os"
        # Eine Rückfrage wie „Wie erkenne ich mein Betriebssystem?“ darf nicht
        # versehentlich als konkrete OS-Antwort interpretiert werden.
        if not _has_any(t, ["windows", "win10", "win11", "macos", "macbook", "linux", "android", "iphone", "ipad", "ios", "ipados"]):
            facts.pop("os", None)
            facts.pop("operating_system", None)
    elif _has_any(t, ["was ist mfa", "was bedeutet mfa", "was ist 2fa", "was ist authenticator"]):
        facts["explanation_request"] = "mfa"
        facts["question_target_fact"] = "mfa"
    elif _has_any(t, ["was ist vpn", "was bedeutet vpn"]):
        facts["explanation_request"] = "vpn"
        facts["question_target_fact"] = "vpn"
    elif _has_any(t, ["was ist eduroam", "was bedeutet eduroam"]):
        facts["explanation_request"] = "eduroam"
        facts["question_target_fact"] = "eduroam"

    # Account/Zugangsdaten
    if _has_any(t, ["kein konto", "nicht aktiviert", "konto fehlt", "account fehlt", "konto noch nicht aktiviert", "noch nicht aktiviert"]):
        facts["account_activated"] = False
    elif _has_any(t, ["konto ist aktiv", "konto aktiv", "konto aktiviert", "account aktiv", "account aktiviert", "benutzerkonto aktiviert", "besitze ein benutzerkonto", "habe ein benutzerkonto"]):
        facts["account_activated"] = True

    if _has_any(t, ["daten vergessen", "daten verloren", "zugangsdaten vergessen", "zugangsdaten verloren"]):
        facts["account_data_lost"] = True
        facts["username_known"] = False
        facts["kuerzel_known"] = False
        facts["password_known"] = False
        facts["help_request"] = "account_data_lost"

    username_negative = _has_any(t, [
        "benutzername unbekannt", "benutzername fehlt", "kenne meinen benutzernamen nicht", "kenne mein benutzername nicht",
        "kenne mein kuerzel nicht", "kenne mein kürzel nicht", "kuerzel unbekannt", "kürzel unbekannt", "kuerzel fehlt", "kürzel fehlt",
    ])
    username_positive = _has_any(t, [
        "benutzername bekannt", "benutzernamen bekannt", "kuerzel bekannt", "kürzel bekannt", "ich kenne mein kuerzel", "ich kenne mein kürzel",
        "kenne mein kuerzel", "kenne mein kürzel", "ich kenne meinen benutzernamen", "kenne meinen benutzernamen", "mein benutzername",
        "meinen benutzernamen", "mein kuerzel", "mein kürzel", "benutzername habe ich", "benutzernamen habe ich", "kuerzel habe ich", "kürzel habe ich",
    ]) or (_has_any(t, ["@uni-hohenheim.de"]) and "eduroam" not in t)
    if username_negative:
        facts["username_known"] = False
        facts["kuerzel_known"] = False
    elif username_positive and not _has_any(t, ["nicht", "kein", "keine", "vergessen", "verloren"]):
        facts["username_known"] = True
        facts["kuerzel_known"] = True

    if _has_any(t, ["kuerzel@uni-hohenheim.de", "kürzel@uni-hohenheim.de", "@uni-hohenheim.de"]):
        facts["identifier_entered_type"] = "email_kuerzel_domain"
        facts["username_format_correct"] = True
        facts["username_known"] = True
        facts["kuerzel_known"] = True

    password_negative = _has_any(t, [
        "passwort vergessen", "kennwort vergessen", "passwort unbekannt", "kennwort unbekannt", "kenne mein passwort nicht",
        "kenne mein kennwort nicht", "passwort fehlt", "kennwort fehlt", "kein passwort", "kein kennwort",
    ])
    password_positive = _has_any(t, [
        "passwort bekannt", "kennwort bekannt", "ich kenne mein passwort", "ich kenne mein kennwort", "kenne mein passwort", "kenne mein kennwort",
        "passwort habe ich", "kennwort habe ich", "passwort hab ich", "kennwort hab ich", "mein passwort", "mein kennwort", "zugangsdaten bekannt",
    ])
    if password_negative:
        facts["password_known"] = False
    elif password_positive and not _has_any(t, ["nicht", "kein", "keine", "vergessen", "verloren", "falsch"]):
        facts["password_known"] = True

    if _has_any(t, ["passwort geändert", "passwort geaendert", "kennwort geändert", "kennwort geaendert", "neues passwort", "passwort reset", "passwort zurückgesetzt", "passwort zurueckgesetzt"]):
        facts["password_recently_changed"] = True

    # Netzwerk/eduroam
    if _has_any(t, ["wlan funktioniert nicht", "mein wlan funktioniert nicht", "wlan geht nicht", "kein wlan", "wifi geht nicht"]):
        facts["wifi_available"] = False
        facts["problem_area"] = "wlan"
    if _has_any(t, ["wlan geht wieder", "wlan funktioniert wieder", "wifi geht wieder", "wifi funktioniert wieder", "wlan funktioniert", "wifi funktioniert"]) and not _has_any(t, ["nicht", "kein", "keine", "ohne", "problem", "fehler"]):
        facts["wifi_available"] = True
        facts["wifi_enabled"] = True
        facts["wlan_enabled"] = True
        facts["problem_resolved"] = True
        facts["user_problem_resolved"] = True
    if _has_any(t, ["wlan aktiviert", "wlan ist aktiviert", "wlan an", "wifi aktiviert", "wifi ist aktiviert"]):
        facts["wifi_enabled"] = True
        facts["wlan_enabled"] = True
    if _has_any(t, ["wlan deaktiviert", "wlan aus", "wifi aus", "wifi deaktiviert"]):
        facts["wifi_enabled"] = False
        facts["wlan_enabled"] = False
    if _has_any(t, ["eduroam wird angezeigt", "eduroam sichtbar", "eduroam ist sichtbar", "ja wird angezeigt"]):
        facts["eduroam_visible"] = True
    if _has_any(t, ["eduroam nicht sichtbar", "eduroam wird nicht angezeigt", "eduroam fehlt", "nicht in der liste"]):
        facts["eduroam_visible"] = False
    if _has_any(t, ["eduroam verbunden", "bin verbunden", "verbindung erfolgreich", "ich kann mich verbinden", "kann mich verbinden", "verbindung klappt", "verbinden klappt"]):
        facts["eduroam_connected"] = True
        facts["connection_successful"] = True
        facts["connection_attempt_status"] = "success"
    if _has_any(t, ["kann mich nicht verbinden", "kann nicht verbinden", "eduroam verbindet nicht", "verbindung fehlgeschlagen", "verbindung klappt nicht", "login fehlgeschlagen", "anmeldung fehlgeschlagen"]):
        facts["eduroam_connected"] = False
        facts["connection_successful"] = False
        facts["connection_attempt_status"] = "failed"
        facts["problem_type"] = "cannot_connect"

    if _has_any(t, ["internet funktioniert", "internet vorhanden", "internet geht", "internet klappt", "online"]):
        facts["internet_available"] = True
        facts["internet_access_available"] = True
        facts["eduroam_internet_access"] = True
    if _has_any(t, ["kein internet", "ohne internet", "internet geht nicht", "internet funktioniert nicht", "offline"]):
        # In einem eduroam-Troubleshooting-Kontext bedeutet "kein Internet" meistens:
        # WLAN-Verbindung besteht, aber darüber kommt kein Internetzugriff zustande.
        # Das darf nicht den globalen Internet-Blocker auslösen, der für Setup-Downloads
        # gedacht ist. Deshalb wird hier bewusst internet_access_available gesetzt.
        facts["internet_access_available"] = False
        facts["eduroam_internet_access"] = False
        facts["problem_type"] = "no_internet"

    # MFA/VPN
    if _has_any(t, ["mfa eingerichtet", "2fa eingerichtet", "authenticator eingerichtet", "mfa ist eingerichtet"]):
        facts["mfa_configured"] = True
    if _has_any(t, ["mfa nicht eingerichtet", "2fa nicht eingerichtet", "kein mfa", "kein zweiter faktor"]):
        facts["mfa_configured"] = False
    if _has_any(t, ["mfa ist verfuegbar", "mfa ist verfügbar", "code ist verfuegbar", "code ist verfügbar", "mfa verfuegbar", "mfa verfügbar", "aktueller code", "code angezeigt"]):
        facts["mfa_code_status"] = "available"
    if _has_any(t, ["code eingegeben", "mfa code eingegeben", "2fa code eingegeben", "ja eingegeben"]):
        facts["mfa_challenge_approved"] = True
        facts["mfa_code_status"] = "available"
        facts["vpn_auth_status"] = "not_tested"
    if _has_any(t, ["passiert nichts", "nichts passiert", "login passiert nichts", "vpn lehnt ab"]):
        facts["vpn_auth_status"] = "failed"
        facts["mfa_challenge_approved"] = False if facts.get("mfa_challenge_approved") is UNKNOWN else facts.get("mfa_challenge_approved")
    if _has_any(t, ["code abgelaufen", "mfa code abgelaufen"]):
        facts["mfa_code_status"] = "expired"
    if _has_any(t, ["code ungueltig", "code ungültig", "falscher code", "mfa code falsch"]):
        facts["mfa_code_status"] = "invalid"
    if _has_any(t, ["vpn client installiert", "cisco installiert", "secure client installiert"]):
        facts["vpn_client_installed"] = True
    if _has_any(t, ["vpn verbunden", "vpn ist verbunden", "tunnel verbunden"]):
        facts["vpn_connected"] = True
        facts["vpn_tunnel_status"] = "connected"
    if _has_any(t, ["vpn verbindet nicht", "vpn geht nicht", "tunnel fehlgeschlagen"]):
        facts["vpn_connected"] = False
        facts["vpn_tunnel_status"] = "failed"

    if _has_any(t, ["geht wieder", "funktioniert wieder", "hat funktioniert", "klappt wieder", "problem geloest", "problem gelöst", "es funktioniert"]):
        facts["problem_resolved"] = True
        facts["user_problem_resolved"] = True
    if _has_any(t, ["geht immer noch nicht", "funktioniert immer noch nicht", "klappt weiterhin nicht", "weiterhin nicht"]):
        facts["problem_resolved"] = False
        facts["user_problem_resolved"] = False
        facts["problem_unresolved"] = True

    return _sync_aliases(facts)


def contextual_facts_from_answer(
    answer_text: str,
    pending_fact: str | None = None,
    pending_question: str | None = None,
    current_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extrahiert Fakten aus einer Folgeantwort mit Dialogkontext."""
    t = normalize_text(answer_text)
    facts = _base_facts_from_text(answer_text)

    # Folgeantworten wie "Ja, ich habe damit letzte Woche gearbeitet"
    # erwähnen den Dienst oft nicht erneut. Wenn der laufende Dialog bereits
    # einen Dienst kennt, wird trotzdem in den Existing-Service-Troubleshooting-
    # Kontext gewechselt und Basisfragen werden übersprungen.
    current_service = str((current_facts or {}).get("service") or (current_facts or {}).get("topic") or "").lower()
    if current_service in {"eduroam", "vpn", "mfa"} and _detect_previous_service_use(t):
        facts["service"] = current_service
        facts["topic"] = current_service
        _apply_existing_service_assumptions(facts, current_service)

    # Kontextfrage: Nutzer fragt bei einer Rückfrage selbst nach Hilfe.
    # Beispiel: Bot fragt nach Betriebssystem, Nutzer fragt „Wie erkenne ich das?“
    if pending_fact in {"os", "operating_system"} and is_user_question(answer_text):
        if not facts.get("os") and not facts.get("operating_system"):
            facts["explanation_request"] = "operating_system"
            facts["question_target_fact"] = "os"
            facts["user_question"] = True

    # Begriffserklärungen/Meta-Fragen dürfen den abgefragten Fact nicht mit False überschreiben.
    if facts.get("explanation_request"):
        facts.pop(str(pending_fact or ""), None)
        if pending_fact in {"os", "operating_system"}:
            facts.pop("os", None)
            facts.pop("operating_system", None)
        return _sync_aliases(facts)

    if pending_fact:
        pending_fact = str(pending_fact)
        if pending_fact in BOOLEAN_FACTS and _answer_addresses_pending_fact(answer_text, pending_fact):
            if answer_is_yes(answer_text):
                facts[pending_fact] = True
            elif answer_is_no(answer_text):
                facts[pending_fact] = False
            elif answer_is_unknown(answer_text):
                facts[f"{pending_fact}_unknown"] = True

        # Spezialfälle mit mehr als true/false.
        if pending_fact in {"mfa_code_status", "mfa_challenge_approved"}:
            if _has_any(t, ["verfuegbar", "verfügbar", "vorhanden", "aktueller code", "code angezeigt", "ja"]):
                facts["mfa_code_status"] = "available"
                facts["mfa_code_available"] = True
                facts["mfa_totp_available"] = True
            if answer_is_no(answer_text) and not _has_any(t, ["ungueltig", "ungültig", "abgelaufen", "falsch"]):
                facts["mfa_code_status"] = "missing"
                facts["mfa_code_available"] = False
                facts["mfa_totp_available"] = False
            if _has_any(t, ["abgelaufen", "expired"]):
                facts["mfa_code_status"] = "expired"
            if _has_any(t, ["ungueltig", "ungültig", "falsch", "abgelehnt"]):
                facts["mfa_code_status"] = "invalid"
            if answer_is_unknown(answer_text):
                facts["mfa_code_status"] = UNKNOWN
                facts["mfa_code_status_unknown"] = True


        if pending_fact == "vpn_auth_status":
            if _has_any(t, ["akzeptiert", "erfolgreich", "verbunden", "funktioniert", "ja", "klappt"]):
                facts["vpn_auth_status"] = "success"
            if _has_any(t, ["fehlgeschlagen", "failed", "abgelehnt", "passiert nichts", "nichts passiert", "geht nicht", "klappt nicht", "nein"]):
                facts["vpn_auth_status"] = "failed"
                facts["problem_type"] = "mfa_failed"

        if pending_fact in {"connection_attempt_status", "eduroam_connected"}:
            if answer_is_yes(answer_text) and _answer_addresses_pending_fact(answer_text, pending_fact):
                facts["connection_attempt_status"] = "success"
                facts["eduroam_connected"] = True
                facts["connection_successful"] = True
            elif answer_is_no(answer_text) and _answer_addresses_pending_fact(answer_text, pending_fact):
                facts["connection_attempt_status"] = "failed"
                facts["eduroam_connected"] = False
                facts["connection_successful"] = False
                facts["problem_type"] = "cannot_connect"

        if pending_fact in {"internet_access_available", "internet_available", "eduroam_internet_access"}:
            if answer_is_yes(answer_text) and _answer_addresses_pending_fact(answer_text, pending_fact):
                facts["internet_access_available"] = True
                facts["internet_available"] = True
                facts["eduroam_internet_access"] = True
            elif answer_is_no(answer_text) and _answer_addresses_pending_fact(answer_text, pending_fact):
                facts["internet_access_available"] = False
                facts["eduroam_internet_access"] = False
                facts["problem_type"] = "no_internet"

        if pending_fact in {"os", "operating_system"}:
            # Falls nur "was ist ein Betriebssystem" kommt, soll erst erklärt werden.
            if facts.get("explanation_request") == "operating_system":
                facts.pop("os", None)
                facts.pop("operating_system", None)

        if pending_fact in {"username_known", "kuerzel_known"}:
            if _has_any(t, ["daten vergessen", "daten verloren", "zugangsdaten vergessen", "zugangsdaten verloren"]):
                facts["username_known"] = False
                facts["kuerzel_known"] = False
                facts["password_known"] = False
                facts["account_data_lost"] = True
                facts["help_request"] = "account_data_lost"
            elif answer_is_yes(answer_text) and _answer_addresses_pending_fact(answer_text, pending_fact):
                facts["username_known"] = True
                facts["kuerzel_known"] = True
            elif answer_is_no(answer_text) and _answer_addresses_pending_fact(answer_text, pending_fact):
                facts["username_known"] = False
                facts["kuerzel_known"] = False

        if pending_fact == "password_known":
            if _has_any(t, ["reset", "zuruecksetzen", "zurücksetzen", "passwort vergessen", "kennwort vergessen"]):
                facts["password_known"] = False
                facts["help_request"] = "password_reset"
            elif answer_is_yes(answer_text) and _answer_addresses_pending_fact(answer_text, pending_fact):
                facts["password_known"] = True
            elif answer_is_no(answer_text) and _answer_addresses_pending_fact(answer_text, pending_fact):
                facts["password_known"] = False

        if pending_fact == "password_recently_changed":
            if answer_is_yes(answer_text) and _answer_addresses_pending_fact(answer_text, pending_fact):
                facts["password_recently_changed"] = True
            elif answer_is_no(answer_text) and _answer_addresses_pending_fact(answer_text, pending_fact):
                facts["password_recently_changed"] = False

    # Kontextunabhängig: wenn Nutzer mit 'wie gesagt' bestätigt, auf pending_fact anwenden.
    if pending_fact and _has_any(t, ["wie gesagt", "wie oben", "habe ich doch gesagt"]):
        if answer_is_yes(answer_text) and pending_fact in BOOLEAN_FACTS:
            facts[str(pending_fact)] = True
        elif answer_is_no(answer_text) and pending_fact in BOOLEAN_FACTS:
            facts[str(pending_fact)] = False

    return _sync_aliases(facts)


def merge_facts(old_facts: dict[str, Any], new_facts: dict[str, Any], *, keep_sticky: bool = True) -> dict[str, Any]:
    """Führt Fakten zusammen. Neue klare Aussagen dürfen alte blockierende Zustände überschreiben."""
    merged = dict(old_facts or {})
    sticky = {"topic", "service", "os", "operating_system"}
    for key, value in (new_facts or {}).items():
        if is_unknown_value(value):
            # Unknown nur dann setzen, wenn es noch keinen Wert gibt.
            if key not in merged:
                merged[key] = value
            continue
        if keep_sticky and key in sticky and not is_unknown_value(merged.get(key)) and merged.get(key) != value:
            # Thema/OS im laufenden Dialog nicht durch Nebensatz überschreiben.
            continue
        merged[key] = value

    # Wenn eine Problembehebung gemeldet wird, alte blockierende WLAN-Fakten aktiv korrigieren.
    if new_facts.get("wifi_available") is True or new_facts.get("wifi_enabled") is True:
        merged["wifi_available"] = True
        merged["wifi_enabled"] = True
        merged["wlan_enabled"] = True
    if new_facts.get("problem_resolved") is True:
        merged["problem_unresolved"] = False
        merged["needs_human_support"] = False if merged.get("needs_human_support") in {UNKNOWN, None, False} else merged.get("needs_human_support")
    return _sync_aliases(merged)


def facts_from_text(user_text: str) -> dict[str, Any]:
    return _base_facts_from_text(user_text)


def recognize_with_context(
    user_text: str,
    *,
    current_facts: dict[str, Any] | None = None,
    pending_fact: str | None = None,
    pending_question: str | None = None,
) -> dict[str, Any]:
    base = _base_facts_from_text(user_text)
    ctx = contextual_facts_from_answer(user_text, pending_fact, pending_question, current_facts)
    return merge_facts(base, ctx, keep_sticky=False)
