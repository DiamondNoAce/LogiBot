"""Schreiboperationen für die JSON-Wissensbasis.

Die eigentliche Datei-/Backup-Logik liegt zentral in kb_loader.py. Dieses Modul
bietet bewusst eine eigene Import-Adresse für UI- und Admin-Code, damit Lese-,
Schreib- und Validierungslogik im Projekt klar getrennt werden können.
"""

from __future__ import annotations

from typing import Any

from storage import kb_loader


def save_json(name: str, data: Any, *, backup: bool = True) -> None:
    kb_loader.save_json(name, data, backup=backup)


def upsert_service(service: dict[str, Any]) -> None:
    kb_loader.upsert_service(service)


def upsert_system(service_key: str, system: dict[str, Any]) -> None:
    kb_loader.upsert_system(service_key, system)


def upsert_step(service_key: str, system_key: str, step: dict[str, Any]) -> None:
    kb_loader.upsert_step(service_key, system_key, step)


def delete_step(service_key: str, system_key: str, step_number: int) -> None:
    kb_loader.delete_step(service_key, system_key, step_number)


def upsert_inference_rule(rule: dict[str, Any]) -> None:
    kb_loader.upsert_inference_rule(rule)


def delete_inference_rule(rule_id: str) -> None:
    kb_loader.delete_inference_rule(rule_id)


def save_decision_graphs(graphs: list[dict[str, Any]]) -> None:
    kb_loader.save_decision_graphs(graphs)
