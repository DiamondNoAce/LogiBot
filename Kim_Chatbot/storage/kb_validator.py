"""Einfache Validierung der JSON-Wissensbasis.

Die Prüfung ist bewusst verständlich gehalten und eignet sich für eine Admin-
Ansicht oder für Tests vor dem Austausch des kompletten Rule-Engine-Ordners.
"""

from __future__ import annotations

from typing import Any

from storage import kb_loader


def validate_knowledge_base() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    services = kb_loader.get_services(active_only=False)
    service_keys: set[str] = set()

    for service in services:
        key = service.get("key")
        if not key:
            errors.append("Ein Dienst hat keinen key.")
            continue
        if key in service_keys:
            errors.append(f"Doppelter Dienst-Key: {key}")
        service_keys.add(key)

        system_keys: set[str] = set()
        for system in service.get("systems", []):
            sys_key = system.get("key")
            if not sys_key:
                errors.append(f"Dienst {key}: Ein System hat keinen key.")
                continue
            if sys_key in system_keys:
                errors.append(f"Dienst {key}: Doppelter System-Key: {sys_key}")
            system_keys.add(sys_key)

            step_numbers: set[int] = set()
            for step in system.get("steps", []):
                number = step.get("number")
                if number is None:
                    errors.append(f"{key}/{sys_key}: Ein Schritt hat keine number.")
                    continue
                try:
                    number = int(number)
                except Exception:
                    errors.append(f"{key}/{sys_key}: Ungültige Schrittnummer: {number}")
                    continue
                if number in step_numbers:
                    errors.append(f"{key}/{sys_key}: Doppelte Schrittnummer: {number}")
                step_numbers.add(number)
                if not step.get("title"):
                    warnings.append(f"{key}/{sys_key}/Schritt {number}: Kein Titel gepflegt.")
                if not step.get("solution"):
                    warnings.append(f"{key}/{sys_key}/Schritt {number}: Keine Lösung gepflegt.")

    rules = kb_loader.load_inference_rules(active_only=False)
    rule_ids: set[str] = set()
    for rule in rules:
        rid = rule.get("id")
        if not rid:
            errors.append("Eine Inferenzregel hat keine id.")
            continue
        if rid in rule_ids:
            errors.append(f"Doppelte Regel-ID: {rid}")
        rule_ids.add(rid)
        if not isinstance(rule.get("when", {}), dict):
            errors.append(f"Regel {rid}: when muss ein Objekt sein.")
        if not isinstance(rule.get("then", []), list):
            errors.append(f"Regel {rid}: then muss eine Liste sein.")

    graphs = kb_loader.load_decision_graphs()
    for graph in graphs:
        gid = graph.get("id", "<ohne id>")
        node_ids = {node.get("id") for node in graph.get("nodes", [])}
        for edge in graph.get("edges", []):
            if edge.get("source") not in node_ids:
                errors.append(f"Graph {gid}: Edge {edge.get('id')} verweist auf unbekannte Quelle {edge.get('source')}.")
            if edge.get("target") not in node_ids:
                errors.append(f"Graph {gid}: Edge {edge.get('id')} verweist auf unbekanntes Ziel {edge.get('target')}.")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": f"{len(errors)} Fehler, {len(warnings)} Hinweise",
    }
