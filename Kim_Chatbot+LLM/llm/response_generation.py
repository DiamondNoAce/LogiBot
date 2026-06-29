"""Antwortformulierung über auswählbare LLM-Anbieter.

Das LLM formuliert nur bereits regelbasiert erzeugte Ausgaben um.
Es darf keine neuen technischen Schritte erfinden.
"""

from __future__ import annotations

from typing import Any

from llm import ollama_client, groq_client


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
    """Formuliert eine Schritt-/Lösungsantwort nutzerfreundlich."""
    return _client(provider).formulate_answer(title, actions, model)


def formulate_rule_result(
    result_summary: str,
    facts: dict[str, Any],
    model: str,
    *,
    provider: str = "ollama",
    title: str = "Regelbasierte Ausgabe",
) -> str:
    """Formuliert ein Inferenz- oder Entscheidungsnetz-Ergebnis nutzerfreundlich."""
    return _client(provider).formulate_rule_result(result_summary, facts, model, title=title)
