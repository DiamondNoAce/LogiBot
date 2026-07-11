"""Texterkennung/Faktenextraktion über auswählbare LLM-Anbieter.

Unterstützt:
- Ollama lokal/offline
- Groq Cloud über GROQ_API_KEY oder benutzereigenen Streamlit-Session-Key

Die Rule Engine bleibt verantwortlich für die fachliche Entscheidung.
Dieses Modul routet nur die Sprach-/Faktenerkennung.
"""

from __future__ import annotations

from typing import Any

from llm import ollama_client, groq_client
from llm import safety as llm_safety


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


def recognize_instruction_request(user_text: str, model: str, provider: str = "ollama") -> dict[str, Any]:
    """Nutzeroberfläche: Freitext -> Dienst/System/Schritt."""
    data = _client(provider).recognize_instruction_request(user_text, model)
    cleaned, _notes = llm_safety.filter_instruction_recognition(data, user_text=user_text)
    return cleaned


def recognize_facts(user_text: str, model: str, provider: str = "ollama") -> dict[str, Any]:
    """Gruppen-Inferenztest: erste Freitexteingabe -> Fakten."""
    data = _client(provider).recognize_facts(user_text, model)
    cleaned, _notes = llm_safety.filter_llm_facts(data, user_text=user_text)
    return cleaned


def recognize_facts_fast(user_text: str, model: str, provider: str = "ollama") -> dict[str, Any]:
    """Kompakte Erstfaktenerkennung für den Schnellmodus.

    Groq nutzt einen deutlich kleineren Prompt. Andere Provider fallen auf die
    normale Erkennung zurück, damit die Schnittstelle rückwärtskompatibel bleibt.
    """
    client = _client(provider)
    fn = getattr(client, "recognize_facts_fast", None)
    if callable(fn):
        data = fn(user_text, model)
        cleaned, _notes = llm_safety.filter_llm_facts(data, user_text=user_text)
        return cleaned
    data = client.recognize_facts(user_text, model)
    cleaned, _notes = llm_safety.filter_llm_facts(data, user_text=user_text)
    return cleaned


def recognize_facts_in_context(
    user_text: str,
    model: str,
    *,
    provider: str = "ollama",
    current_facts: dict[str, Any] | None = None,
    pending_fact: str | None = None,
    pending_question: str | None = None,
    previous_result_summary: str | None = None,
) -> dict[str, Any]:
    """Gruppen-Inferenztest/Graph-Test: Folgeantwort -> ergänzende Fakten."""
    data = _client(provider).recognize_facts_in_context(
        user_text,
        model,
        current_facts=current_facts,
        pending_fact=pending_fact,
        pending_question=pending_question,
        previous_result_summary=previous_result_summary,
    )
    cleaned, _notes = llm_safety.filter_llm_facts(
        data,
        user_text=user_text,
        current_facts=current_facts,
        pending_fact=pending_fact,
    )
    return cleaned


def recognize_facts_in_context_fast(
    user_text: str,
    model: str,
    *,
    provider: str = "ollama",
    current_facts: dict[str, Any] | None = None,
    pending_fact: str | None = None,
    pending_question: str | None = None,
    previous_result_summary: str | None = None,
) -> dict[str, Any]:
    """Kompakte Folgeantwort-Erkennung für den Schnell-/Ausgewogen-Modus.

    Der Prompt enthält nur letzte Rückfrage, erwarteten Fact und die wichtigsten
    bekannten Fakten. Dadurch werden zweite und dritte Dialogantworten deutlich
    schneller verarbeitet.
    """
    client = _client(provider)
    fn = getattr(client, "recognize_facts_in_context_fast", None)
    if callable(fn):
        data = fn(
            user_text,
            model,
            current_facts=current_facts,
            pending_fact=pending_fact,
            pending_question=pending_question,
            previous_result_summary=previous_result_summary,
        )
        cleaned, _notes = llm_safety.filter_llm_facts(
            data,
            user_text=user_text,
            current_facts=current_facts,
            pending_fact=pending_fact,
        )
        return cleaned
    data = client.recognize_facts_in_context(
        user_text,
        model,
        current_facts=current_facts,
        pending_fact=pending_fact,
        pending_question=pending_question,
        previous_result_summary=previous_result_summary,
    )
    cleaned, _notes = llm_safety.filter_llm_facts(
        data,
        user_text=user_text,
        current_facts=current_facts,
        pending_fact=pending_fact,
    )
    return cleaned
