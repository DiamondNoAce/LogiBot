from llm import safety


def test_llm_guard_drops_unmentioned_operating_system():
    facts, notes = safety.filter_llm_facts(
        {"service": "eduroam", "os": "windows", "answer": "Mach dies und das."},
        user_text="Wie erkenne ich das?",
        current_facts={"service": "eduroam"},
        pending_fact="os",
    )
    assert facts.get("service") == "eduroam"
    assert "os" not in facts
    assert "answer" not in facts
    assert notes


def test_instruction_guard_drops_guessed_system():
    data, notes = safety.filter_instruction_recognition(
        {"service_key": "eduroam", "system_key": "macos", "confidence": "hoch"},
        user_text="Hilf mir eduroam neu zu installieren",
    )
    assert data["service_key"] == "eduroam"
    assert data["system_key"] == "unknown"
    assert data["confidence"] == "niedrig"
    assert notes


def test_formulated_response_guard_rejects_new_url():
    text, notes = safety.guard_formulated_response(
        "Öffne https://example.com und installiere das Profil.",
        "Öffne cat.eduroam.org im Browser.",
        fallback_text="Öffne cat.eduroam.org im Browser.",
    )
    assert text == "Öffne cat.eduroam.org im Browser."
    assert notes


def test_response_generation_strips_repeated_llm_greeting():
    from llm.response_generation import _remove_leading_greeting

    assert _remove_leading_greeting("Hallo! Da du eduroam nutzt, prüfe bitte dein Passwort.") == "Da du eduroam nutzt, prüfe bitte dein Passwort."
    assert _remove_leading_greeting("Hallo, ich kann Eduroam neu einrichten.") == "Ich kann Eduroam neu einrichten."


def test_user_response_sanitizer_strips_leading_greeting():
    from core.response_safety import sanitize_user_response

    assert sanitize_user_response("Hallo! Ich kann Eduroam gern neu einrichten.") == "Ich kann Eduroam gern neu einrichten."
