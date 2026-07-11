"""Antwortformulierung über auswählbare LLM-Anbieter.

Das LLM formuliert nur bereits regelbasiert erzeugte Ausgaben um.
Es darf keine neuen technischen Schritte erfinden.
"""

from __future__ import annotations

from typing import Any
import re

from llm import ollama_client, groq_client
from llm import safety as llm_safety




def _remove_leading_greeting(text: str) -> str:
    """Entfernt generische Begrüßungen aus LLM-Formulierungen.

    Im Chatverlauf wirkt ein wiederholtes "Hallo" vor jeder Botnachricht unnatürlich.
    Die fachliche Rule-Engine-Ausgabe bleibt erhalten; es wird nur der Einstieg geglättet.
    """
    out = str(text or "").strip()
    out = re.sub(
        r"^(?:hallo(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß-]+)?|hi|hey|guten\s+(?:tag|morgen|abend)|servus|moin)\s*[!,.:-]?\s+",
        "",
        out,
        flags=re.IGNORECASE,
    ).strip()
    # Häufige LLM-Formulierung: "Hallo! Da ..." -> "Da ...".
    out = re.sub(r"^(?:hallo|hi|hey)\s*[!,.:-]\s*", "", out, flags=re.IGNORECASE).strip()
    if out.startswith("ich "):
        out = "Ich " + out[4:]
    if out.startswith("du "):
        out = "Du " + out[3:]
    return out


def _client(provider: str):
    normalized = (provider or "ollama").strip().lower()
    if normalized == "groq":
        return groq_client
    return ollama_client


def provider_label(provider: str) -> str:
    normalized = (provider or "ollama").strip().lower()
    if normalized == "groq":
        return "Groq"
    if normalized == "ollama":
        return "Ollama"
    return "LLM"


def formulate_answer(title: str, actions: list[str], model: str, provider: str = "ollama") -> str:
    """Formuliert eine Schritt-/Lösungsantwort nutzerfreundlich.

    Sicherheitsgrenze: Falls das LLM neue URLs, technische Befehle oder sensible
    Eingabeaufforderungen erfindet, wird automatisch die regelbasierte Fallback-
    Ausgabe verwendet.
    """
    source_text = f"{title}\n" + "\n".join(f"- {a}" for a in actions if str(a).strip())
    candidate = _client(provider).formulate_answer(title, actions, model)
    guarded, _notes = llm_safety.guard_formulated_response(candidate, source_text, fallback_text=source_text)
    return _remove_leading_greeting(guarded)


def formulate_rule_result(
    result_summary: str,
    facts: dict[str, Any],
    model: str,
    *,
    provider: str = "ollama",
    title: str = "Regelbasierte Ausgabe",
) -> str:
    """Formuliert ein Inferenz- oder Entscheidungsnetz-Ergebnis nutzerfreundlich."""
    candidate = _client(provider).formulate_rule_result(result_summary, facts, model, title=title)
    guarded, _notes = llm_safety.guard_formulated_response(candidate, result_summary, fallback_text=result_summary)
    return _remove_leading_greeting(guarded)
