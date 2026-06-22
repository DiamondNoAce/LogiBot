"""Texterkennung/Faktenextraktion über das lokale LLM."""

from __future__ import annotations

from typing import Any

from llm import ollama_client


def recognize_instruction_request(user_text: str, model: str) -> dict[str, Any]:
    return ollama_client.recognize_instruction_request(user_text, model)


def recognize_facts(user_text: str, model: str) -> dict[str, Any]:
    return ollama_client.recognize_facts(user_text, model)
