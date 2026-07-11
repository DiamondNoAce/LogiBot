from core import fallback_fact_extraction


def test_username_context_yes():
    facts = fallback_fact_extraction.recognize_with_context(
        "Jaa kenn ich", pending_fact="username_known", current_facts={"topic": "vpn"}
    )
    assert facts["username_known"] is True
    assert facts["kuerzel_known"] is True


def test_account_data_lost():
    facts = fallback_fact_extraction.recognize_with_context(
        "nein ich habe meine daten verloren", pending_fact="username_known", current_facts={"topic": "eduroam"}
    )
    assert facts["username_known"] is False
    assert facts["password_known"] is False
    assert facts["help_request"] == "account_data_lost"


def test_wlan_recovered_overwrites_blocking_fact():
    old = {"topic": "eduroam", "wifi_available": False}
    new = fallback_fact_extraction.recognize_with_context("WLAN geht wieder", current_facts=old)
    merged = fallback_fact_extraction.merge_facts(old, new)
    assert merged["wifi_available"] is True
    assert merged["wifi_enabled"] is True


def test_operating_system_explanation():
    facts = fallback_fact_extraction.recognize_with_context(
        "was ist ein betriebsystem", pending_fact="os", current_facts={"topic": "eduroam"}
    )
    assert facts["explanation_request"] == "operating_system"


def test_operating_system_how_to_recognize_does_not_set_windows():
    facts = fallback_fact_extraction.recognize_with_context(
        "wie erkenne ich mein betriebssystem",
        pending_fact="os",
        pending_question="Welches Betriebssystem nutzt du?",
        current_facts={"topic": "eduroam"},
    )
    assert facts["explanation_request"] == "operating_system"
    assert facts.get("os") is None
    assert facts.get("operating_system") is None
    assert facts["user_question"] is True


def test_generic_question_during_os_prompt_becomes_os_explanation():
    facts = fallback_fact_extraction.recognize_with_context(
        "wie kann ich das erkennen",
        pending_fact="operating_system",
        pending_question="Welches Betriebssystem nutzt du?",
        current_facts={"topic": "eduroam"},
    )
    assert facts["explanation_request"] == "operating_system"
    assert facts["question_target_fact"] == "os"
    assert facts.get("os") is None


def test_existing_eduroam_use_skips_basic_prerequisites():
    facts = fallback_fact_extraction.recognize_with_context(
        "Ich habe ein Problem mit Eduroam. Ich konnte es bis vor einer Woche normal verwenden, jetzt geht es aber nicht mehr"
    )
    assert facts["topic"] == "eduroam"
    assert facts["intent"] == "troubleshooting"
    assert facts["service_previously_used"] is True
    assert facts["account_exists"] is True
    assert facts["account_activated"] is True
    assert facts["username_known"] is True
    assert facts["password_known"] is True
    assert facts["eduroam_profile_configured"] is True


def test_password_change_followup_context():
    facts = fallback_fact_extraction.recognize_with_context(
        "nein",
        pending_fact="password_recently_changed",
        pending_question="Hast du seit dem letzten erfolgreichen eduroam-Zugriff dein Hohenheimer Passwort geändert?",
        current_facts={"topic": "eduroam", "service_previously_used": True},
    )
    assert facts["password_recently_changed"] is False


def test_existing_vpn_use_sets_existing_setup_assumptions():
    facts = fallback_fact_extraction.recognize_with_context(
        "Mein VPN hat bisher funktioniert, jetzt geht es nicht mehr"
    )
    assert facts["topic"] == "vpn"
    assert facts["service_previously_used"] is True
    assert facts["vpn_client_installed"] is True
    assert facts["mfa_configured"] is True
    assert facts["password_known"] is True


def test_existing_eduroam_contextual_previous_use_without_service_word():
    facts = fallback_fact_extraction.recognize_with_context(
        "Ja, ich habe ja letzte Woche damit gearbeitet",
        pending_fact="account_activated",
        current_facts={"topic": "eduroam", "service": "eduroam"},
    )
    assert facts["service_previously_used"] is True
    assert facts["account_activated"] is True
    assert facts["username_known"] is True
    assert facts["eduroam_profile_configured"] is True


def test_existing_eduroam_can_connect_sets_connection_success():
    facts = fallback_fact_extraction.recognize_with_context(
        "Ja ich kann mich verbinden",
        pending_fact="connection_attempt_status",
        current_facts={"topic": "eduroam", "service": "eduroam", "service_previously_used": True},
    )
    assert facts["connection_attempt_status"] == "success"
    assert facts["eduroam_connected"] is True


def test_existing_eduroam_no_internet_sets_access_not_global_blocker():
    facts = fallback_fact_extraction.recognize_with_context(
        "Nein kein Internet",
        pending_fact="internet_access_available",
        current_facts={"topic": "eduroam", "service": "eduroam", "service_previously_used": True, "connection_attempt_status": "success"},
    )
    assert facts["internet_access_available"] is False
    assert facts["eduroam_internet_access"] is False
    assert "internet_available" not in facts or facts.get("internet_available") is not False


def test_eduroam_not_visible_does_not_require_account_first():
    facts = fallback_fact_extraction.recognize_with_context("Mein Handy findet eduroam nicht")
    assert facts["topic"] == "eduroam"
    assert facts["eduroam_visible"] is False
    assert facts["problem_type"] == "eduroam_not_visible"
    assert facts["account_activated"] is True
    assert facts["username_known"] is True


def test_eduroam_other_wlans_visible_context():
    facts = fallback_fact_extraction.recognize_with_context(
        "Andere WLANs sind alle sichtbar",
        pending_fact="other_wifi_visible",
        current_facts={"topic": "eduroam", "service": "eduroam", "eduroam_visible": False},
    )
    assert facts["other_wifi_visible"] is True
    assert facts["eduroam_visible"] is False


def test_vpn_mfa_code_is_not_mixed_topic():
    facts = fallback_fact_extraction.recognize_with_context("Ich bekomme den 2FA-Code für VPN nicht hin.")
    assert facts["topic"] == "vpn"
    assert facts.get("multi_topic_query") is not True
    assert facts["mfa_required_for_vpn_login"] is True


def test_troll_or_nonsense_is_flagged():
    facts = fallback_fact_extraction.recognize_with_context("asdf qwertz blabla lol lol")
    assert facts["invalid_request"] is True
    assert facts["intent"] == "invalid_or_unclear"


def test_ilias_etherpad_is_other_service():
    facts = fallback_fact_extraction.recognize_with_context("Etherpad-Lite für Ilias")
    assert facts["topic"] == "other_service"
    assert facts["user_request"] == "ilias_etherpad"


def test_gemacht_does_not_set_macos():
    facts = fallback_fact_extraction.recognize_with_context(
        "Habe ich gemacht, wie soll ich fortfahren?",
        current_facts={"topic": "eduroam", "service": "eduroam", "password_recently_changed": True},
    )
    assert facts.get("os") is None
    assert facts.get("operating_system") is None
    assert facts["user_question"] is True


def test_mac_still_detected_as_token():
    facts = fallback_fact_extraction.recognize_with_context("Ich nutze einen Mac")
    assert facts["os"] == "macos"


def test_rule_engine_gemacht_does_not_set_macos():
    from core import rule_engine
    assert rule_engine.detect_system("Habe ich gemacht, wie soll ich fortfahren?", "eduroam") == "unknown"


def test_rule_engine_windows_answer_detected_as_windows():
    from core import rule_engine
    assert rule_engine.detect_system("Ich habe Windows", "eduroam") == "windows"
