"""Validierung der JSON-Wissensbasis.

Die Prüfung ist bewusst verständlich gehalten und eignet sich für eine Admin-
Ansicht oder für Tests vor dem Austausch des kompletten Rule-Engine-Ordners.

Neu: Die Validierung prüft zusätzlich die technische Condition-Matrix aus der
Eduroam-Excel-Sicht: Operatoren, Regel-IDs, Next-Verweise und Post-Conditions.
"""

from __future__ import annotations

from typing import Any

from storage import kb_loader
from core.condition_parser import SUPPORTED_OPERATORS, normalize_operator


def _collect_fact_keys(catalog: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for section in catalog.values():
        if isinstance(section, dict):
            keys.update(str(k) for k in section.keys())
    return keys


def _iter_conditions(obj: Any):
    if not isinstance(obj, dict):
        return
    if "fact" in obj or "field" in obj:
        yield obj
    for key in ("all", "any", "not"):
        for child in obj.get(key, []) or []:
            yield from _iter_conditions(child)


def _validate_condition(condition: dict[str, Any], rule_id: str, fact_keys: set[str], errors: list[str], warnings: list[str]) -> None:
    fact = str(condition.get("fact") or condition.get("field") or "").strip()
    operator = normalize_operator(condition.get("operator", "equals"))
    if not fact:
        errors.append(f"Regel {rule_id}: Condition ohne fact/field.")
    elif fact_keys and fact not in fact_keys:
        warnings.append(f"Regel {rule_id}: Fact `{fact}` ist nicht im fact_catalog gepflegt.")
    if operator not in SUPPORTED_OPERATORS:
        warnings.append(f"Regel {rule_id}: Operator `{condition.get('operator')}` wird nicht ausdrücklich unterstützt.")


def validate_knowledge_base() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    fact_catalog = kb_loader.load_fact_catalog()
    fact_keys = _collect_fact_keys(fact_catalog)

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

    global_blocks = kb_loader.load_global_blocks(active_only=False)
    block_ids: set[str] = set()
    for block in global_blocks:
        bid = block.get("id")
        if not bid:
            errors.append("Ein globaler Baustein hat keine id.")
            continue
        if bid in block_ids:
            errors.append(f"Doppelter globaler Baustein: {bid}")
        block_ids.add(bid)
        for fact_def in block.get("facts", []) or []:
            if not fact_def.get("key"):
                errors.append(f"Globaler Baustein {bid}: Ein Fakt hat keinen key.")
        for rule in block.get("rules", []) or []:
            rid = rule.get("id", f"{bid}.<ohne id>")
            when = rule.get("when", rule.get("conditions", {}))
            for condition in _iter_conditions(when):
                _validate_condition(condition, str(rid), fact_keys, errors, warnings)
            if "conditions" not in rule and "when" not in rule:
                warnings.append(f"Globaler Baustein {bid}, Regel {rid}: keine conditions/when gepflegt.")
            if "result" not in rule and "then" not in rule:
                warnings.append(f"Globaler Baustein {bid}, Regel {rid}: kein result/then gepflegt.")

    for service in services:
        for required in service.get("required_global_blocks", []) or []:
            if required not in block_ids:
                errors.append(f"Dienst {service.get('key')}: required_global_blocks verweist auf unbekannten globalen Baustein {required}.")

    rules = kb_loader.load_inference_rules(active_only=False)
    rule_ids: set[str] = set()
    original_rule_ids: set[str] = set()
    for rule in rules:
        rid = rule.get("id")
        if not rid:
            errors.append("Eine Inferenzregel hat keine id.")
            continue
        if rid in rule_ids:
            errors.append(f"Doppelte Regel-ID: {rid}")
        rule_ids.add(str(rid))
        tech_meta = rule.get("technical_metadata", {}) or {}
        if tech_meta.get("original_rule_id"):
            original_rule_ids.add(str(tech_meta.get("original_rule_id")))
        if not isinstance(rule.get("when", {}), dict):
            errors.append(f"Regel {rid}: when muss ein Objekt sein.")
        if not isinstance(rule.get("then", []), list):
            errors.append(f"Regel {rid}: then muss eine Liste sein.")
        for condition in _iter_conditions(rule.get("when", {})):
            _validate_condition(condition, str(rid), fact_keys, errors, warnings)

    # Prüfe technische Next-Verweise aus Excel-Metadaten.
    for rule in rules:
        rid = str(rule.get("id"))
        tech_meta = rule.get("technical_metadata", {}) or {}
        for label in ("next_success", "next_failure"):
            target = tech_meta.get(label)
            if not target:
                continue
            raw_targets = [t.strip() for t in str(target).replace(" oder ", "/").split("/") if t.strip()]
            for t in raw_targets:
                if t.lower() in {"ende", "passende regel nach klärung", "passende regel nach klaerung", "os-spezifische setup-regel"}:
                    continue
                if t not in original_rule_ids and f"tech.{t}" not in rule_ids:
                    warnings.append(f"Technische Regel {rid}: {label} verweist auf `{t}`, dazu wurde keine Regel-ID gefunden.")


    # Prüfe Wissensmodell-Knoten und Beziehungen.
    model = kb_loader.load_knowledge_model()
    if model and model.get("id") != "missing":
        km_nodes = model.get("nodes", []) or []
        km_edges = model.get("edges", []) or []
        km_node_ids = {str(n.get("id")) for n in km_nodes if n.get("id")}
        for node in km_nodes:
            if not node.get("id"):
                errors.append("Wissensmodell: Ein Knoten hat keine id.")
            for fk in node.get("fact_keys", []) or []:
                if fact_keys and str(fk) not in fact_keys:
                    warnings.append(f"Wissensmodell-Knoten {node.get('id')}: Fact `{fk}` ist nicht im fact_catalog gepflegt.")
            block = node.get("global_block")
            if block and block not in block_ids:
                warnings.append(f"Wissensmodell-Knoten {node.get('id')}: global_block `{block}` existiert nicht in global_blocks.json.")
        for edge in km_edges:
            if edge.get("source") not in km_node_ids:
                errors.append(f"Wissensmodell: Edge {edge.get('id')} verweist auf unbekannte Quelle {edge.get('source')}.")
            if edge.get("target") not in km_node_ids:
                errors.append(f"Wissensmodell: Edge {edge.get('id')} verweist auf unbekanntes Ziel {edge.get('target')}.")

    graphs = kb_loader.load_decision_graphs()
    for graph in graphs:
        gid = graph.get("id", "<ohne id>")
        node_ids = {node.get("id") for node in graph.get("nodes", [])}
        for edge in graph.get("edges", []):
            if edge.get("source") not in node_ids:
                errors.append(f"Graph {gid}: Edge {edge.get('id')} verweist auf unbekannte Quelle {edge.get('source')}.")
            if edge.get("target") not in node_ids:
                errors.append(f"Graph {gid}: Edge {edge.get('id')} verweist auf unbekanntes Ziel {edge.get('target')}.")
            for condition in _iter_conditions(edge.get("condition", {})):
                _validate_condition(condition, f"Graph {gid}/Edge {edge.get('id')}", fact_keys, errors, warnings)

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": f"{len(errors)} Fehler, {len(warnings)} Hinweise",
    }
