from __future__ import annotations

from typing import Any
import time

import streamlit as st

from storage import kb_loader as kb_json
from core import rule_engine
from core import inference_engine
from core import fallback_fact_extraction
from llm import fact_extraction, response_generation
from core import decision_graph_engine

def _wizard_system_from_facts(facts: dict[str, Any]) -> str:
    """Normalisiert Betriebssystem-Fakten auf die System-Keys der Wissensbasis."""
    os_value = str(
        facts.get("os")
        or facts.get("operating_system")
        or facts.get("system")
        or "unknown"
    ).strip().lower()
    aliases = {
        "windows": "windows", "win": "windows", "win10": "windows", "win11": "windows", "pc": "windows",
        "mac": "macos", "macos": "macos", "mac os": "macos", "osx": "macos", "os x": "macos", "macbook": "macos",
        "ios": "ios", "iphone": "ios",
        "ipados": "ipados", "ipad": "ipados",
        "android": "android",
        "linux": "linux",
        "chromeos": "chromeos", "chrome os": "chromeos", "chromebook": "chromeos",
        "general": "general", "allgemein": "general",
    }
    return aliases.get(os_value, "unknown")


def _step_by_phase(service_key: str, system_key: str, phase_contains: str) -> int | None:
    for step in kb_json.get_steps(service_key, system_key, active_only=True):
        phase = str(step.get("phase", "")).lower()
        title = str(step.get("title", "")).lower()
        if phase_contains.lower() in phase or phase_contains.lower() in title:
            return int(step.get("number"))
    return None


def _service_display_name(service_key: str) -> str:
    service = kb_json.get_service(service_key) or {}
    return str(service.get("name") or service_key or "Dienst")


def _system_display_name(service_key: str, system_key: str) -> str:
    system = kb_json.get_system(service_key, system_key) or {}
    return str(system.get("name") or system_key or "allgemein")


def _package_service_from_id(package_id: str) -> str:
    parts = str(package_id or "").split(".")
    if len(parts) >= 2:
        key = parts[1]
        return "user_account" if key == "account" else key
    return "general"


def _package_locations(package_id: str) -> list[tuple[str, str, int]]:
    """Findet Service/System/Startschritt für ein Schrittpaket in services.json."""
    locations: list[tuple[str, str, int]] = []
    for service in kb_json.get_services(active_only=False):
        service_key = str(service.get("key", ""))
        for system in service.get("systems", []) or []:
            system_key = str(system.get("key", "general"))
            numbers = [
                int(step.get("number", 0))
                for step in system.get("steps", []) or []
                if str(step.get("package_id", "")) == str(package_id)
            ]
            if numbers:
                locations.append((service_key, system_key, min(numbers)))
    return locations


def _find_package_location(package_id: str, facts: dict[str, Any] | None = None) -> tuple[str, str, int] | None:
    locations = _package_locations(package_id)
    if not locations:
        return None
    facts = facts or {}
    wanted_service = str(facts.get("topic") or facts.get("service") or "").lower()
    wanted_system = _wizard_system_from_facts(facts)
    for loc in locations:
        if wanted_service and loc[0] == wanted_service and wanted_system != "unknown" and loc[1] == wanted_system:
            return loc
    for loc in locations:
        if wanted_system != "unknown" and loc[1] == wanted_system:
            return loc
    for loc in locations:
        if wanted_service and loc[0] == wanted_service:
            return loc
    return locations[0]


def _pseudo_steps_from_package(package_id: str) -> list[dict[str, Any]]:
    package = kb_json.get_step_package(package_id) or {}
    steps = package.get("steps", []) or []
    pseudo: list[dict[str, Any]] = []
    for index, raw_step in enumerate(steps, start=1):
        instruction = str(raw_step if not isinstance(raw_step, dict) else raw_step.get("instruction") or raw_step.get("text") or raw_step.get("title") or "").strip()
        title = instruction.split(".")[0].strip()[:90] or f"Schritt {index}"
        pseudo.append({
            "number": index,
            "phase": f"package_step_{index}",
            "title": title,
            "instruction": instruction,
            "active": True,
            "package_id": package_id,
            "solution": {
                "problem_title": f"Hilfe zu: {title}",
                "description": f"Dieser Schritt stammt aus dem Schrittpaket '{package.get('title', package_id)}'.",
                "actions": [instruction or "Prüfe diesen Schritt erneut und wende dich bei Bedarf an den KIM-IT-Service-Desk."],
                "source_refs": package.get("source_refs", []),
            },
        })
    return pseudo


def get_walkthrough_steps(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Liefert die Schritte des aktiven Durchlaufs, gefiltert auf das Schrittpaket."""
    if not state:
        return []
    service_key = str(state.get("service_key") or "")
    system_key = str(state.get("system_key") or "")
    package_id = str(state.get("package_id") or "")

    steps: list[dict[str, Any]] = []
    if service_key and system_key:
        steps = kb_json.get_steps(service_key, system_key, active_only=True)
        if package_id:
            filtered = [s for s in steps if str(s.get("package_id", "")) == package_id]
            if filtered:
                steps = filtered
    if not steps and package_id:
        steps = _pseudo_steps_from_package(package_id)
    return sorted(steps, key=lambda s: int(s.get("number", 0)))


def get_walkthrough_step(state: dict[str, Any], number: int | None = None) -> dict[str, Any] | None:
    steps = get_walkthrough_steps(state)
    if not steps:
        return None
    target = int(number if number is not None else state.get("current_step", steps[0].get("number", 1)))
    for step in steps:
        if int(step.get("number", -1)) == target:
            return step
    return steps[0]


def get_walkthrough_title(state: dict[str, Any]) -> str:
    package_title = str(state.get("package_title") or "").strip()
    if package_title:
        return package_title
    package_id = str(state.get("package_id") or "")
    package = kb_json.get_step_package(package_id) if package_id else None
    if package:
        return str(package.get("title") or package_id)
    service = _service_display_name(str(state.get("service_key") or ""))
    system = _system_display_name(str(state.get("service_key") or ""), str(state.get("system_key") or ""))
    return f"{service} unter {system} einrichten"


def walkthrough_status_summary(state: dict[str, Any]) -> str:
    if not state or not state.get("active"):
        return "Es ist kein Schritt-für-Schritt-Durchlauf aktiv."
    if state.get("done"):
        return f"Schritt-für-Schritt-Durchlauf abgeschlossen: {get_walkthrough_title(state)}"
    step = get_walkthrough_step(state)
    if not step:
        return f"Schritt-für-Schritt-Durchlauf gestartet: {get_walkthrough_title(state)}"
    return (
        f"Schritt-für-Schritt-Durchlauf läuft: {get_walkthrough_title(state)}\n"
        f"- Schritt {step.get('number')}: {step.get('title')}\n"
        f"{step.get('instruction', '')}"
    )


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


def _walkthrough_followup_question(service_key: str, system_key: str, step: dict[str, Any]) -> str:
    """Erzeugt eine passende Folgefrage für beliebige Schrittpakete."""
    service = str(service_key or "").lower()
    phase = str(step.get("phase", "")).lower()
    title = str(step.get("title", "")).lower()
    instruction = str(step.get("instruction", "")).lower()
    text = f"{phase} {title} {instruction}"

    if service == "eduroam":
        return _eduroam_followup_question(system_key, step)
    if service == "vpn":
        if "install" in text or "client" in text:
            return "Konntest du den VPN-Client wie beschrieben installieren bzw. öffnen?"
        if "profil" in text or "gateway" in text or "server" in text:
            return "Konntest du das VPN-Profil bzw. Gateway wie beschrieben eintragen?"
        if "mfa" in text or "code" in text or "authenticator" in text:
            return "Konntest du den aktuellen 30-Sekunden-Code aus der Authenticator-App beim VPN-Login eingeben?"
        if "verbinden" in text or "tunnel" in text:
            return "Wurde der VPN-Tunnel jetzt aufgebaut bzw. zeigt der Client eine aktive Verbindung an?"
        return "Konntest du diesen VPN-Schritt durchführen?"
    if service == "mfa":
        if "code" in text or "token" in text or "authenticator" in text or "2fas" in text:
            return "Konntest du den aktuellen Code bzw. Token wie beschrieben prüfen oder einrichten?"
        if "qr" in text or "scan" in text:
            return "Konntest du den QR-Code mit deiner Authenticator-App scannen?"
        return "Konntest du diesen MFA-Schritt durchführen?"
    if service in {"user_account", "account"}:
        if "passwort" in text or "kennwort" in text:
            return "Konntest du den Schritt zur Passwort- bzw. Account-Klärung durchführen?"
        return "Konntest du diesen Schritt zum Hohenheimer Benutzerkonto durchführen?"
    return "Hat dieser Schritt funktioniert?"


def _next_step_number(service_key: str, system_key: str, current_number: int, package_id: str | None = None) -> int | None:
    state = {"service_key": service_key, "system_key": system_key}
    if package_id:
        state["package_id"] = package_id
    numbers = [int(s.get("number")) for s in get_walkthrough_steps(state)]
    for number in numbers:
        if number > int(current_number):
            return number
    return None


def _previous_step_number(service_key: str, system_key: str, current_number: int, package_id: str | None = None) -> int | None:
    state = {"service_key": service_key, "system_key": system_key}
    if package_id:
        state["package_id"] = package_id
    numbers = [int(s.get("number")) for s in get_walkthrough_steps(state)]
    previous = None
    for number in numbers:
        if number >= int(current_number):
            return previous
        previous = number
    return previous


def start_step_walkthrough(
    service_key: str,
    system_key: str,
    step_number: int,
    reason: str = "",
    *,
    package_id: str | None = None,
    package_title: str | None = None,
) -> None:
    """Startet einen generischen Schritt-für-Schritt-Durchlauf für jedes Schrittpaket."""
    package = kb_json.get_step_package(package_id) if package_id else None
    st.session_state.eduroam_walkthrough = {
        "active": True,
        "done": False,
        "service_key": service_key,
        "system_key": system_key,
        "package_id": package_id,
        "package_title": package_title or (package.get("title") if package else None),
        "current_step": int(step_number),
        "started_from": int(step_number),
        "reason": reason,
        "show_solution": False,
        "history": [],
    }


def start_step_package_walkthrough(package_id: str, facts: dict[str, Any] | None = None, reason: str = "") -> str | None:
    package = kb_json.get_step_package(package_id)
    if not package:
        return None
    location = _find_package_location(package_id, facts)
    if location:
        service_key, system_key, step_number = location
    else:
        service_key = _package_service_from_id(package_id)
        system_key = _wizard_system_from_facts(facts or {})
        if system_key == "unknown":
            system_key = "general"
        step_number = 1
    start_step_walkthrough(
        service_key,
        system_key,
        int(step_number),
        reason or "Einstieg aus einer show_steps-Regel",
        package_id=package_id,
        package_title=str(package.get("title") or package_id),
    )
    return f"Schrittpaket-Durchlauf gestartet: {package.get('title', package_id)}"


def start_eduroam_walkthrough(system_key: str, step_number: int, reason: str = "") -> None:
    package_id = None
    for step in kb_json.get_steps("eduroam", system_key, active_only=True):
        if int(step.get("number", -1)) == int(step_number) and step.get("package_id"):
            package_id = str(step.get("package_id"))
            break
    start_step_walkthrough("eduroam", system_key, step_number, reason, package_id=package_id)


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

    if fallback_fact_extraction.is_user_question(answer_text):
        step = get_walkthrough_step(state, current) or {}
        question = _walkthrough_followup_question(
            str(state.get("service_key", "")),
            str(state.get("system_key", "")),
            step,
        )
        local_facts = fallback_fact_extraction.contextual_facts_from_answer(
            answer_text,
            pending_fact="os" if "betriebssystem" in question.lower() else None,
            pending_question=question,
        )
        if local_facts.get("explanation_request") == "operating_system":
            state["last_free_answer_hint"] = (
                "Du hast eine Rückfrage gestellt. Das Betriebssystem ist die Grundsoftware deines Geräts. "
                "Typische Beispiele sind Windows auf einem Laptop/PC, macOS auf einem MacBook, "
                "iOS auf einem iPhone, Android auf einem Smartphone oder Linux. Wähle danach das passende System aus bzw. antworte z. B. mit 'Windows' oder 'macOS'."
            )
        else:
            state["last_free_answer_hint"] = (
                "Ich habe erkannt, dass du gerade eine Rückfrage gestellt hast. Ich gehe deshalb nicht automatisch zum nächsten Schritt weiter. "
                "Beantworte danach bitte, ob der aktuelle Schritt funktioniert hat, z. B. mit 'Ja, weiter' oder 'Nein, ich hänge hier'."
            )
        st.session_state.eduroam_walkthrough = state
        return

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


def _sync_credential_aliases(facts: dict[str, Any]) -> dict[str, Any]:
    """Hält username_known und kuerzel_known in laufenden Dialogen synchron."""
    synced = dict(facts or {})
    if synced.get("kuerzel_known") is True:
        synced["username_known"] = True
    if synced.get("username_known") is True:
        synced["kuerzel_known"] = True
    if synced.get("kuerzel_known") is False and _is_unknown_value(synced.get("username_known")):
        synced["username_known"] = False
    if synced.get("username_known") is False and _is_unknown_value(synced.get("kuerzel_known")):
        synced["kuerzel_known"] = False
    return synced


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
    return _sync_credential_aliases(merged)


def _normalise_llm_mode(llm_mode: str | None) -> str:
    value = str(llm_mode or "fast").strip().lower()
    aliases = {
        "schnell": "fast",
        "fast": "fast",
        "ausgewogen": "balanced",
        "balanced": "balanced",
        "qualität": "quality",
        "qualitaet": "quality",
        "quality": "quality",
    }
    return aliases.get(value, "fast")


def _elapsed_seconds(start: float) -> str:
    return f"{time.perf_counter() - start:.2f}s"


def _value_is_known(value: Any) -> bool:
    return not fallback_fact_extraction.is_unknown_value(value)


def _local_resolves_pending_fact(local_facts: dict[str, Any], pending_fact: str | None) -> bool:
    """Prüft, ob der lokale Fallback die aktuell gestellte Frage sicher beantwortet hat."""
    if not pending_fact:
        return False
    pf = str(pending_fact)
    aliases: set[str] = {pf}
    if pf in {"username_known", "kuerzel_known"}:
        aliases.update({"username_known", "kuerzel_known", "account_data_lost", "help_request"})
    if pf in {"os", "operating_system"}:
        aliases.update({"os", "operating_system", "explanation_request"})
    if pf in {"mfa_code_status", "mfa_challenge_approved", "mfa_code_available", "mfa_totp_available"}:
        aliases.update({"mfa_code_status", "mfa_code_available", "mfa_totp_available", "mfa_challenge_approved"})
    if pf in {"wifi_available", "wifi_enabled", "wlan_enabled"}:
        aliases.update({"wifi_available", "wifi_enabled", "wlan_enabled", "problem_resolved"})
    if pf in {"vpn_auth_status", "vpn_connected", "vpn_tunnel_status"}:
        aliases.update({"vpn_auth_status", "vpn_connected", "vpn_tunnel_status", "problem_resolved", "problem_unresolved"})
    if pf in {"connection_attempt_status", "eduroam_connected"}:
        aliases.update({"connection_attempt_status", "eduroam_connected", "connection_successful", "problem_type"})
    if pf in {"internet_access_available", "internet_available", "eduroam_internet_access"}:
        aliases.update({"internet_access_available", "internet_available", "eduroam_internet_access", "problem_type"})

    for key in aliases:
        if key in local_facts and _value_is_known(local_facts.get(key)):
            return True
        unknown_key = f"{key}_unknown"
        if local_facts.get(unknown_key) is True:
            return True
    return False


def _local_fallback_confident(
    user_text: str,
    local_facts: dict[str, Any],
    *,
    current_facts: dict[str, Any] | None = None,
    pending_fact: str | None = None,
    pending_question: str | None = None,
) -> bool:
    """Heuristik für den Schnellmodus: Groq nur nutzen, wenn lokal unsicher.

    Der lokale Parser ist bei kurzen Folgeantworten wie "ja", "nein", "Windows",
    "WLAN geht wieder" oder "Passwort vergessen" schneller und deterministischer.
    """
    if not local_facts:
        return False

    # Nutzer stellt selbst eine Rück-/Verständnisfrage. Dann soll bei aktivem LLM
    # nicht blind mit dem nächsten Schritt weitergemacht werden. Im Schnellmodus
    # wird deshalb Groq/Ollama zur Kontextklärung zugelassen. Ohne LLM liefert der
    # Fallback trotzdem einen festen Erklärpfad.
    if local_facts.get("user_question"):
        return False

    # Hilfsintents ohne echte Nutzerfrage sind deterministisch abbildbar.
    if local_facts.get("explanation_request") or local_facts.get("help_request"):
        return True

    if _local_resolves_pending_fact(local_facts, pending_fact):
        return True

    # Erste Nachricht: Dienst + Absicht/OS/konkretes Problem reichen meist aus.
    topic = local_facts.get("topic") or local_facts.get("service")
    if topic and str(topic).lower() != "unknown":
        strong_keys = {
            "intent", "os", "operating_system", "problem_area", "problem_type",
            "user_request", "vpn_needed", "internal_service_access_required",
            "account_data_lost", "password_known", "username_known", "kuerzel_known",
            "wifi_available", "eduroam_visible", "mfa_code_status", "vpn_auth_status",
            "service_previously_used", "service_previously_worked", "skip_initial_prerequisites",
            "eduroam_previously_worked", "vpn_previously_worked", "mfa_previously_worked",
            "password_recently_changed",
        }
        if any(k in local_facts and _value_is_known(local_facts.get(k)) for k in strong_keys):
            return True

    # Betriebssystem oder klare Ja/Nein-Antworten auf eine konkrete Frage nicht unnötig über Groq schicken.
    if pending_question and any(k in local_facts for k in {"os", "operating_system", "problem_resolved"}):
        return True

    return False


def _protect_pending_fact_from_meta_question(
    llm_facts: dict[str, Any],
    local_facts: dict[str, Any],
    pending_fact: str | None,
) -> dict[str, Any]:
    """Verhindert, dass eine Nutzer-Rückfrage als Antwort gespeichert wird.

    Beispiel: Wenn der Bot nach dem Betriebssystem fragt und der Nutzer
    „Wie erkenne ich das?“ schreibt, darf ein LLM nicht einfach `os=windows`
    setzen. Die Rückfrage wird stattdessen als explanation_request behandelt.
    """
    protected = dict(llm_facts or {})
    if not local_facts.get("user_question"):
        return protected
    target = str(local_facts.get("question_target_fact") or pending_fact or "").lower()
    if target in {"os", "operating_system"}:
        # Nur entfernen, wenn der lokale Parser KEIN konkretes OS erkannt hat.
        if not local_facts.get("os") and not local_facts.get("operating_system"):
            protected.pop("os", None)
            protected.pop("operating_system", None)
    return protected


def _recognize_facts_for_session(
    user_text: str,
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    *,
    current_facts: dict[str, Any] | None = None,
    pending_fact: str | None = None,
    pending_question: str | None = None,
    previous_result_summary: str | None = None,
    llm_mode: str = "fast",
) -> tuple[dict[str, Any], str]:
    """Erkennt Fakten aus Nutzertext.

    Schnellmodus:
    - zuerst deterministischer Fallback-Parser
    - Groq/Ollama nur, wenn der lokale Parser unsicher ist
    - bei Folgeantworten kompakter Prompt ohne komplette Wissensbasis
    """
    start = time.perf_counter()
    mode = _normalise_llm_mode(llm_mode)

    local_facts = fallback_fact_extraction.recognize_with_context(
        user_text,
        current_facts=current_facts,
        pending_fact=pending_fact,
        pending_question=pending_question,
    )

    if not use_llm:
        return local_facts, f"Verbesserte regelbasierte Faktenerkennung ohne LLM · Dauer {_elapsed_seconds(start)}"

    provider_name = fact_extraction.provider_label(llm_provider)
    local_confident = fallback and _local_fallback_confident(
        user_text,
        local_facts,
        current_facts=current_facts,
        pending_fact=pending_fact,
        pending_question=pending_question,
    )

    # Schnell und Ausgewogen: sichere lokale Antworten überspringen den API-Aufruf.
    if mode in {"fast", "balanced"} and local_confident:
        return local_facts, (
            f"Schnellmodus: lokale Faktenerkennung war sicher, {provider_name}-Aufruf übersprungen "
            f"· Dauer {_elapsed_seconds(start)}"
        )

    try:
        compact_prompt = mode in {"fast", "balanced"}
        if current_facts or pending_fact or pending_question:
            if compact_prompt:
                llm_facts = fact_extraction.recognize_facts_in_context_fast(
                    user_text,
                    model,
                    provider=llm_provider,
                    current_facts=current_facts,
                    pending_fact=pending_fact,
                    pending_question=pending_question,
                    previous_result_summary=previous_result_summary,
                )
                prompt_label = "kompakter Dialogprompt"
            else:
                llm_facts = fact_extraction.recognize_facts_in_context(
                    user_text,
                    model,
                    provider=llm_provider,
                    current_facts=current_facts,
                    pending_fact=pending_fact,
                    pending_question=pending_question,
                    previous_result_summary=previous_result_summary,
                )
                prompt_label = "voller Dialogprompt"
        else:
            if mode == "fast":
                llm_facts = fact_extraction.recognize_facts_fast(user_text, model, provider=llm_provider)
                prompt_label = "kompakter Erstprompt"
            else:
                llm_facts = fact_extraction.recognize_facts(user_text, model, provider=llm_provider)
                prompt_label = "voller Erstprompt"

        llm_facts = _protect_pending_fact_from_meta_question(llm_facts, local_facts, pending_fact)
        merged = fallback_fact_extraction.merge_facts(llm_facts, local_facts, keep_sticky=False)
        question_note = " · Nutzerfrage erkannt" if local_facts.get("user_question") else ""
        return merged, (
            f"{provider_name}-Faktenerkennung genutzt ({prompt_label}) + lokaler Guard-Fallback"
            f"{question_note} · Modus {mode} · Dauer {_elapsed_seconds(start)}"
        )
    except Exception as e:
        if not fallback:
            raise
        return local_facts, (
            f"LLM nicht verfügbar, verbesserter regelbasierter Fallback genutzt: {e} "
            f"· Dauer {_elapsed_seconds(start)}"
        )


def _pending_ask_fact(result: dict[str, Any]) -> str | None:
    """Liest aus dem letzten Inferenzergebnis, welche Information gerade abgefragt wurde.

    Dadurch kann eine kurze Folgeantwort wie "Ja" oder "Nein" korrekt als Fakt
    gespeichert werden, statt den Dialog wieder von vorne zu beginnen.
    """
    for action in result.get("actions", []) or []:
        if action.get("type") == "ask" and action.get("fact"):
            return str(action.get("fact"))
    return None


def _pending_question_text(result: dict[str, Any]) -> str | None:
    for action in result.get("actions", []) or []:
        if action.get("type") == "ask":
            return str(action.get("text") or action.get("question") or "")
    return None


def _formulate_inference_reply(
    result: dict[str, Any],
    facts: dict[str, Any],
    use_llm: bool,
    llm_provider: str,
    model: str,
    *,
    llm_formulation: bool = False,
) -> tuple[str, str]:
    raw_summary = inference_engine.renderable_summary(result)
    if not use_llm:
        return raw_summary, "Regelbasierte Ausgabe ohne LLM-Formulierung"
    if not llm_formulation:
        return raw_summary, "Schnellmodus: LLM-Antwortformulierung deaktiviert"
    start = time.perf_counter()
    try:
        text = response_generation.formulate_rule_result(raw_summary, facts, model, provider=llm_provider, title="IT-Assistent")
        return text, f"{response_generation.provider_label(llm_provider)}-Antwortformulierung genutzt · Dauer {_elapsed_seconds(start)}"
    except Exception as e:
        return raw_summary, f"LLM-Formulierung nicht verfügbar, regelbasierte Ausgabe genutzt: {e} · Dauer {_elapsed_seconds(start)}"


def _formulate_graph_reply(
    result: dict[str, Any],
    facts: dict[str, Any],
    use_llm: bool,
    llm_provider: str,
    model: str,
    *,
    llm_formulation: bool = False,
) -> tuple[str, str]:
    raw_summary = decision_graph_engine.render_summary(result)
    if not use_llm:
        return raw_summary, "Regelbasierte Graph-Ausgabe ohne LLM-Formulierung"
    if not llm_formulation:
        return raw_summary, "Schnellmodus: LLM-Antwortformulierung deaktiviert"
    start = time.perf_counter()
    try:
        text = response_generation.formulate_rule_result(raw_summary, facts, model, provider=llm_provider, title="Entscheidungsnetz-Test")
        return text, f"{response_generation.provider_label(llm_provider)}-Antwortformulierung für Entscheidungsnetz genutzt · Dauer {_elapsed_seconds(start)}"
    except Exception as e:
        return raw_summary, f"LLM-Formulierung nicht verfügbar, Graph-Ausgabe genutzt: {e} · Dauer {_elapsed_seconds(start)}"


def _answer_is_yes(text: str) -> bool:
    t = _normalize_response_text(text)
    yes_words = ["ja", "jep", "yes", "genau", "stimmt", "korrekt", "aktiviert", "vorhanden", "eingerichtet", "funktioniert", "klappt", "online"]
    no_words = ["nein", "nicht", "kein", "keine", "fehlt", "ohne", "problem", "fehler", "klappt nicht", "funktioniert nicht"]
    return any(word in t for word in yes_words) and not any(word in t for word in no_words)


def _answer_is_no(text: str) -> bool:
    t = _normalize_response_text(text)
    no_words = ["nein", "nicht", "kein", "keine", "fehlt", "ohne", "problem", "fehler", "klappt nicht", "funktioniert nicht"]
    return any(word in t for word in no_words)


def _is_simple_confirmation_answer(text: str) -> bool:
    """Erkennt kurze Ja/Nein-Antworten ohne eigenen Sachkontext.

    Antworten wie "Mein Benutzerkonto ist aktiviert" sind zwar positiv,
    enthalten aber einen eigenen Sachkontext und dürfen deshalb nicht automatisch
    auf die zuletzt gestellte, eventuell andere Rückfrage gemappt werden.
    """
    t = _normalize_response_text(text)
    words = [w for w in t.replace(",", " ").replace(".", " ").split() if w]
    if len(words) > 4:
        return False
    content_markers = [
        "konto", "account", "benutzerkonto", "benutzername", "benutzernamen",
        "kuerzel", "kürzel", "kennung", "passwort", "kennwort", "zugangsdaten",
        "mfa", "2fa", "code", "authenticator", "vpn", "eduroam", "wlan", "wifi",
        "internet", "profil", "zertifikat", "client", "cisco",
    ]
    if any(marker in t for marker in content_markers):
        return False
    return _answer_is_yes(text) or _answer_is_no(text)


_BOOLEAN_PENDING_FACTS = {
    "account_exists",
    "account_activated",
    "username_known",
    "kuerzel_known",
    "password_known",
    "password_recently_changed",
    "internet_available",
    "internet_access_available",
    "campus_network_available",
    "vpn_client_installed",
    "mfa_configured",
    "two_fa_ready",
    "wifi_available",
    "wifi_enabled",
    "wlan_enabled",
    "eduroam_visible",
    "eduroam_profile_configured",
    "eduroam_profile_installed",
    "eduroam_connected",
    "connection_successful",
    "username_format_correct",
    "certificate_warning_shown",
    "certificate_checked",
    "needs_human_support",
    "human_support_needed",
    "account_locked",
    "credentials_valid",
    "mfa_app_available",
    "mfa_code_available",
    "mfa_recovery_available",
    "mfa_challenge_approved",
    "vpn_client_version_healthy",
    "vpn_endpoint_reachable",
    "login_form_requested",
    "vpn_connected",
    "internal_resource_accessible",
    "setup_source_checked",
    "external_network",
    "problem_resolved",
    "support_needed",
}


_PENDING_FACT_CONTEXT_KEYWORDS = {
    "username_known": ["benutzername", "benutzernamen", "kuerzel", "kürzel", "kennung", "benutzerkennung", "zugangsdaten"],
    "kuerzel_known": ["benutzername", "benutzernamen", "kuerzel", "kürzel", "kennung", "benutzerkennung", "zugangsdaten"],
    "password_known": ["passwort", "kennwort", "zugangsdaten"],
    "password_recently_changed": ["passwort", "kennwort", "geaendert", "geändert", "neues passwort", "seitdem"],
    "account_exists": ["konto", "account", "benutzerkonto", "aktiv", "aktiviert", "freigeschaltet"],
    "account_activated": ["konto", "account", "benutzerkonto", "aktiv", "aktiviert", "freigeschaltet"],
    "mfa_challenge_approved": ["mfa", "2fa", "code", "authenticator", "token", "login", "anmeldung"],
    "two_fa_ready": ["mfa", "2fa", "code", "authenticator", "token"],
    "mfa_code_available": ["mfa", "2fa", "code", "authenticator", "token"],
    "vpn_client_installed": ["vpn", "cisco", "secure client", "client", "installiert"],
    "vpn_connected": ["vpn", "tunnel", "verbunden"],
    "internet_available": ["internet", "online", "offline"],
    "internet_access_available": ["internet", "online", "offline"],
    "wifi_available": ["wlan", "wifi", "funknetz"],
    "wifi_enabled": ["wlan", "wifi", "aktiviert", "an", "aus"],
    "wlan_enabled": ["wlan", "wifi", "aktiviert", "an", "aus"],
    "eduroam_visible": ["eduroam", "sichtbar", "angezeigt", "liste"],
    "eduroam_connected": ["eduroam", "verbunden", "verbindung", "verbinden"],
    "connection_attempt_status": ["eduroam", "verbinden", "verbindung", "verbunden", "login", "anmeldung"],
    "internet_access_available": ["internet", "online", "offline", "zugriff"],
    "eduroam_internet_access": ["internet", "online", "offline", "zugriff"],
    "eduroam_profile_configured": ["eduroam", "profil", "installiert", "eingerichtet"],
    "eduroam_profile_installed": ["eduroam", "profil", "installiert", "eingerichtet"],
}


def _answer_addresses_pending_fact(text: str, pending_fact: str | None) -> bool:
    """Verhindert falsche Ja-Zuordnungen zu alten Rückfragen.

    Beispiel: Wenn gerade nach dem MFA-Code gefragt wurde, darf
    "Mein Benutzerkonto ist aktiviert" nicht als `mfa_challenge_approved=True`
    interpretiert werden. Eine Zuordnung erfolgt nur bei kurzer Ja/Nein-Antwort
    oder wenn die Antwort Begriffe aus dem Kontext des abgefragten Facts enthält.
    """
    if not pending_fact:
        return False
    if _is_simple_confirmation_answer(text):
        return True
    t = _normalize_response_text(text)
    keywords = _PENDING_FACT_CONTEXT_KEYWORDS.get(str(pending_fact), [])
    return any(keyword in t for keyword in keywords)


def _contextual_facts_from_answer(answer_text: str, pending_fact: str | None) -> dict[str, Any]:
    """Ergänzt Fakten aus kurzen Folgeantworten mit robustem Fallback-Parser."""
    return fallback_fact_extraction.contextual_facts_from_answer(
        answer_text,
        pending_fact=pending_fact,
        current_facts=st.session_state.get("group_inference_session", {}).get("facts", {}),
    )


def _merge_facts_contextual(old_facts: dict[str, Any], new_facts: dict[str, Any]) -> dict[str, Any]:
    """Merge für laufende Dialoge mit Überschreiben gelöster blockierender Fakten."""
    return fallback_fact_extraction.merge_facts(old_facts, new_facts, keep_sticky=True)


def _maybe_start_eduroam_walkthrough_from_facts(user_text: str, facts: dict[str, Any], *, force: bool = False) -> str | None:
    """Fallback: startet einen eduroam-Durchlauf aus Fakten, wenn keine show_steps-Regel vorliegt."""
    existing_walkthrough = st.session_state.get("eduroam_walkthrough") or {}
    if existing_walkthrough.get("active") and not force:
        return None

    topic = str(facts.get("topic", "unknown")).lower()
    if topic != "eduroam" and not force:
        return None
    system_key, step_number, reason = _guess_eduroam_step_from_facts(user_text, facts)
    if system_key != "unknown" and step_number is not None:
        start_eduroam_walkthrough(system_key, int(step_number), reason)
        return f"eduroam-Durchlauf gestartet: {system_key}, Schritt {step_number} ({reason})"
    return "eduroam erkannt, aber Betriebssystem oder konkreter Schritt ist noch unklar."


def _first_show_steps_action(result: dict[str, Any]) -> dict[str, Any] | None:
    for action in result.get("actions", []) or []:
        if action.get("type") == "show_steps":
            return action
    return None


def _maybe_start_walkthrough_from_inference_result(result: dict[str, Any], facts: dict[str, Any]) -> str | None:
    """Startet bei show_steps automatisch den passenden Schrittpaket-Durchlauf.

    Wichtig für den Gruppen-Inferenztest: Wenn die Regelbasis ein Schrittpaket
    erreicht, soll der Dialog nicht immer wieder nur "Schrittpaket: ..."
    ausgeben, sondern in die konkrete Anleitung wechseln.
    """
    existing_walkthrough = st.session_state.get("eduroam_walkthrough") or {}
    if existing_walkthrough.get("active"):
        return None
    action = _first_show_steps_action(result)
    if not action:
        return None
    package_id = action.get("step_package_id") or action.get("package_id")
    package = action.get("step_package") or (kb_json.get_step_package(str(package_id)) if package_id else None)
    if not package_id or not package:
        return None
    return start_step_package_walkthrough(
        str(package_id),
        facts,
        reason="Automatisch aus der gematchten show_steps-Regel gestartet",
    )


def _handle_active_walkthrough_answer(answer_text: str, session: dict[str, Any] | None = None) -> bool:
    """Leitet freie Chat-Antworten an den aktiven Schrittpaket-Durchlauf weiter.

    Dadurch kann der Nutzer im Gruppen-Inferenztest nach "Schrittpaket: ..."
    einfach oben weiter mit "ja", "nein" oder "hat funktioniert" antworten,
    ohne dass die Inferenz erneut dasselbe Schrittpaket ausgibt.
    """
    state = st.session_state.get("eduroam_walkthrough") or {}
    if not state.get("active") or state.get("done"):
        return False
    _handle_walkthrough_free_answer(answer_text)
    new_state = st.session_state.get("eduroam_walkthrough") or state
    if session is not None:
        session["reply_text"] = walkthrough_status_summary(new_state)
        session["reply_status"] = "Aktiver Schrittpaket-Durchlauf fortgesetzt; Inferenz wurde nicht erneut gestartet."
        session.setdefault("history", []).append({"role": "user", "text": answer_text, "handled_by": "step_walkthrough"})
        session["history"].append({"role": "engine", "text": session["reply_text"], "raw_text": session["reply_text"]})
        st.session_state.group_inference_session = session
    return True


def start_group_inference_session(
    user_text: str,
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str = "fast",
    llm_formulation: bool = False,
) -> None:
    facts, status = _recognize_facts_for_session(
        user_text,
        use_llm,
        llm_provider,
        model,
        fallback,
        llm_mode=llm_mode,
    )
    facts = _sync_credential_aliases(facts)
    result = inference_engine.run_inference(facts)
    reply_text, reply_status = _formulate_inference_reply(
        result, facts, use_llm, llm_provider, model, llm_formulation=llm_formulation
    )
    st.session_state.group_inference_session = {
        "active": True,
        "initial_text": user_text,
        "facts": facts,
        "result": result,
        "reply_text": reply_text,
        "reply_status": reply_status,
        "raw_summary": inference_engine.renderable_summary(result),
        "status": status,
        "llm_mode": _normalise_llm_mode(llm_mode),
        "llm_formulation": bool(llm_formulation),
        "pending_fact": _pending_ask_fact(result),
        "pending_question": _pending_question_text(result),
        "history": [
            {"role": "user", "text": user_text},
            {"role": "engine", "text": reply_text, "raw_text": inference_engine.renderable_summary(result)},
        ],
    }
    walkthrough_status = _maybe_start_walkthrough_from_inference_result(result, facts)
    if not walkthrough_status:
        walkthrough_status = _maybe_start_eduroam_walkthrough_from_facts(user_text, facts)
    if walkthrough_status:
        st.session_state.group_inference_session["reply_status"] = " · ".join(
            x for x in [st.session_state.group_inference_session.get("reply_status", ""), walkthrough_status] if x
        )


def update_group_inference_session(
    answer_text: str,
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str = "fast",
    llm_formulation: bool = False,
) -> None:
    session = st.session_state.get("group_inference_session") or {}
    if not session or not answer_text.strip():
        return

    # Wenn bereits ein Schrittpaket-Durchlauf aktiv ist, gehört die nächste
    # Freitextantwort zu diesem Durchlauf. Dann nicht erneut die Inferenz ausführen,
    # sonst würde immer wieder dieselbe show_steps-Regel gematcht.
    if _handle_active_walkthrough_answer(answer_text, session):
        return

    pending_fact = _pending_ask_fact(session.get("result", {}))
    pending_question = _pending_question_text(session.get("result", {}))
    previous_summary = session.get("raw_summary") or inference_engine.renderable_summary(session.get("result", {}))
    new_facts, status = _recognize_facts_for_session(
        answer_text,
        use_llm,
        llm_provider,
        model,
        fallback,
        current_facts=session.get("facts", {}),
        pending_fact=pending_fact,
        pending_question=pending_question,
        previous_result_summary=previous_summary,
        llm_mode=llm_mode,
    )
    contextual_facts = _contextual_facts_from_answer(answer_text, pending_fact)
    combined_new_facts = _merge_facts_contextual(new_facts, contextual_facts)
    facts = _merge_facts_contextual(session.get("facts", {}), combined_new_facts)
    result = inference_engine.run_inference(facts)
    reply_text, reply_status = _formulate_inference_reply(
        result, facts, use_llm, llm_provider, model, llm_formulation=llm_formulation
    )
    session["facts"] = facts
    session["result"] = result
    session["reply_text"] = reply_text
    session["reply_status"] = reply_status
    session["raw_summary"] = inference_engine.renderable_summary(result)
    session["status"] = status
    session["llm_mode"] = _normalise_llm_mode(llm_mode)
    session["llm_formulation"] = bool(llm_formulation)
    session["pending_fact"] = _pending_ask_fact(result)
    session["pending_question"] = _pending_question_text(result)
    session.setdefault("history", []).append({"role": "user", "text": answer_text, "new_facts": combined_new_facts, "answered_fact": pending_fact})
    session["history"].append({"role": "engine", "text": reply_text, "raw_text": inference_engine.renderable_summary(result)})
    st.session_state.group_inference_session = session
    walkthrough_status = _maybe_start_walkthrough_from_inference_result(result, facts)
    if not walkthrough_status:
        walkthrough_status = _maybe_start_eduroam_walkthrough_from_facts(answer_text, facts)
    if walkthrough_status:
        session["reply_status"] = " · ".join(x for x in [session.get("reply_status", ""), walkthrough_status] if x)
        st.session_state.group_inference_session = session


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
    if terminal.get("node_type") != "step":
        return None

    package_id = node.get("step_package_id") or node.get("package_id")
    if package_id:
        return start_step_package_walkthrough(str(package_id), result.get("facts", {}), "Einstieg aus dem Entscheidungsnetz-Test")

    service_key = str(node.get("service_key") or node.get("topic") or "eduroam")
    system_key = str(node.get("system_key") or node.get("os") or "general")
    step_number = int(node.get("step_number", 1))
    start_step_walkthrough(service_key, system_key, step_number, "Einstieg aus dem Entscheidungsnetz-Test")
    return f"{_service_display_name(service_key)}-Durchlauf aus Entscheidungsnetz gestartet: Schritt {step_number}."


def start_graph_test_session(
    graph: dict[str, Any],
    user_text: str,
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str = "fast",
    llm_formulation: bool = False,
) -> None:
    facts, status = _recognize_facts_for_session(
        user_text,
        use_llm,
        llm_provider,
        model,
        fallback,
        llm_mode=llm_mode,
    )
    result = decision_graph_engine.run_decision_graph(graph, facts)
    reply_text, reply_status = _formulate_graph_reply(
        result, facts, use_llm, llm_provider, model, llm_formulation=llm_formulation
    )
    st.session_state.graph_test_session = {
        "active": True,
        "graph_id": graph.get("id"),
        "graph_name": graph.get("name"),
        "initial_text": user_text,
        "facts": facts,
        "result": result,
        "reply_text": reply_text,
        "reply_status": reply_status,
        "raw_summary": decision_graph_engine.render_summary(result),
        "status": status,
        "llm_mode": _normalise_llm_mode(llm_mode),
        "llm_formulation": bool(llm_formulation),
        "history": [
            {"role": "user", "text": user_text},
            {"role": "graph", "text": reply_text, "raw_text": decision_graph_engine.render_summary(result)},
        ],
    }
    _maybe_start_eduroam_walkthrough_from_graph_result(result)


def update_graph_test_session(
    answer_text: str,
    use_llm: bool,
    llm_provider: str,
    model: str,
    fallback: bool,
    llm_mode: str = "fast",
    llm_formulation: bool = False,
) -> None:
    session = st.session_state.get("graph_test_session") or {}
    if not session or not answer_text.strip():
        return
    active_walkthrough = st.session_state.get("eduroam_walkthrough") or {}
    if active_walkthrough.get("active") and not active_walkthrough.get("done"):
        _handle_walkthrough_free_answer(answer_text)
        new_state = st.session_state.get("eduroam_walkthrough") or active_walkthrough
        session.setdefault("history", []).append({"role": "user", "text": answer_text, "handled_by": "step_walkthrough"})
        session["reply_text"] = walkthrough_status_summary(new_state)
        session["reply_status"] = "Aktiver Schrittpaket-Durchlauf fortgesetzt; Graph wurde nicht erneut ausgeführt."
        session["history"].append({"role": "graph", "text": session["reply_text"], "raw_text": session["reply_text"]})
        st.session_state.graph_test_session = session
        return
    graph = _graph_by_id(session.get("graph_id"))
    if not graph:
        return
    result_before = session.get("result", {})
    pending_fact = result_before.get("fact") or result_before.get("expected_fact")
    pending_question = result_before.get("message")
    previous_summary = session.get("raw_summary") or decision_graph_engine.render_summary(result_before)
    new_facts, status = _recognize_facts_for_session(
        answer_text,
        use_llm,
        llm_provider,
        model,
        fallback,
        current_facts=session.get("facts", {}),
        pending_fact=pending_fact,
        pending_question=pending_question,
        previous_result_summary=previous_summary,
        llm_mode=llm_mode,
    )
    contextual_facts = _contextual_facts_from_answer(answer_text, pending_fact)
    combined_new_facts = _merge_facts_contextual(new_facts, contextual_facts)
    facts = _merge_facts_contextual(session.get("facts", {}), combined_new_facts)
    result = decision_graph_engine.run_decision_graph(graph, facts)
    reply_text, reply_status = _formulate_graph_reply(
        result, facts, use_llm, llm_provider, model, llm_formulation=llm_formulation
    )
    session["facts"] = facts
    session["result"] = result
    session["reply_text"] = reply_text
    session["reply_status"] = reply_status
    session["raw_summary"] = decision_graph_engine.render_summary(result)
    session["status"] = status
    session["llm_mode"] = _normalise_llm_mode(llm_mode)
    session["llm_formulation"] = bool(llm_formulation)
    session.setdefault("history", []).append({"role": "user", "text": answer_text, "new_facts": combined_new_facts, "answered_fact": pending_fact})
    session["history"].append({"role": "graph", "text": reply_text, "raw_text": decision_graph_engine.render_summary(result)})
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

    next_number = _next_step_number(service_key, system_key, current, state.get("package_id"))
    if next_number is None:
        state["done"] = True
        state["show_solution"] = False
    else:
        state["current_step"] = next_number
        state["show_solution"] = False
    st.session_state.eduroam_walkthrough = state


