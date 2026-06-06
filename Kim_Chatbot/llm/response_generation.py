"""Antwortformulierung über das lokale LLM."""

from __future__ import annotations

from llm import ollama_client


def formulate_answer(title: str, actions: list[str], model: str) -> str:
    return ollama_client.formulate_answer(title, actions, model)
