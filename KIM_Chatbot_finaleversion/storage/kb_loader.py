# kb_json.py
# ============================================================
# JSON-Zugriff für eine austauschbare Rule-Engine-Ordnerstruktur.
#
# Standardstruktur im Projekt:
# Rule Engine/
#   engine.json
#   constants.json
#   fact_catalog.json
#   services.json                  optional/abgeleitet für UI
#   decision_graphs.json            optional für grafische Entscheidungsnetze
#   rules/*.json
#   step_packages/*.json
#   sources/*.json
#   backups/
#
# Vorteil: Der komplette Ordner "Rule Engine" kann durch eine neue Version
# ersetzt werden, ohne dass Python-Code angepasst werden muss.
# ============================================================

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
RULE_ENGINE_DIR = BASE_DIR / "Rule Engine"
LEGACY_KB_DIR = BASE_DIR / "knowledge_base"

# Fallback: alte Projektstruktur weiterhin lesen, falls kein Rule-Engine-Ordner existiert.
KB_DIR = RULE_ENGINE_DIR if RULE_ENGINE_DIR.exists() else LEGACY_KB_DIR
BACKUP_DIR = KB_DIR / "backups"
RULES_DIR = KB_DIR / "rules"
STEP_PACKAGES_DIR = KB_DIR / "step_packages"
SOURCES_DIR = KB_DIR / "sources"
GLOBAL_DIR = KB_DIR / "global"
TECHNICAL_DIR = KB_DIR / "technical"
KNOWLEDGE_MODEL_DIR = KB_DIR / "knowledge_model"

FILES = {
    "services": KB_DIR / "services.json",
    "engine": KB_DIR / "engine.json",
    "constants": KB_DIR / "constants.json",
    "fact_catalog": KB_DIR / "fact_catalog.json",
    "decision_graphs": KB_DIR / "decision_graphs.json",
    "source_index": SOURCES_DIR / "source_index.json",
    "global_blocks": GLOBAL_DIR / "global_blocks.json",
    "technical_eduroam_conditions": TECHNICAL_DIR / "eduroam_condition_matrix.json",
    "technical_eduroam_overview": TECHNICAL_DIR / "eduroam_rule_overview.json",
    "technical_eduroam_flow": TECHNICAL_DIR / "eduroam_flow.json",
    "technical_eduroam_functions": TECHNICAL_DIR / "eduroam_functions.json",
    "technical_priority_model": TECHNICAL_DIR / "priority_model.json",
    "knowledge_model_overview": KNOWLEDGE_MODEL_DIR / "wissensmodell_gesamtprojekt.json",
    # Aggregierte logische Dateien. Physisch liegen sie in Unterordnern.
    "inference_rules": RULES_DIR / "custom_rules.json",
    "step_packages": STEP_PACKAGES_DIR / "custom_steps.json",
    "sources": SOURCES_DIR / "custom_sources.json",
}


def ensure_dirs() -> None:
    KB_DIR.mkdir(exist_ok=True)
    BACKUP_DIR.mkdir(exist_ok=True)
    RULES_DIR.mkdir(exist_ok=True)
    STEP_PACKAGES_DIR.mkdir(exist_ok=True)
    SOURCES_DIR.mkdir(exist_ok=True)
    GLOBAL_DIR.mkdir(exist_ok=True)
    TECHNICAL_DIR.mkdir(exist_ok=True)
    KNOWLEDGE_MODEL_DIR.mkdir(exist_ok=True)


def rel_path(path: Path) -> str:
    try:
        return str(path.relative_to(KB_DIR)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _read_json_file(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _backup_file(path: Path) -> None:
    if not path.exists():
        return
    ensure_dirs()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe_name = rel_path(path).replace("/", "__")
    backup_path = BACKUP_DIR / f"{safe_name}_{stamp}.bak.json"
    shutil.copy2(path, backup_path)


def _write_json_file(path: Path, data: Any, *, backup: bool = True) -> None:
    ensure_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup:
        _backup_file(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(_strip_internal_fields(data), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _strip_internal_fields(data: Any) -> Any:
    if isinstance(data, list):
        return [_strip_internal_fields(x) for x in data]
    if isinstance(data, dict):
        return {k: _strip_internal_fields(v) for k, v in data.items() if not str(k).startswith("__")}
    return data


def _load_many_json_lists(folder: Path) -> list[dict[str, Any]]:
    ensure_dirs()
    items: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        data = _read_json_file(path, [])
        if isinstance(data, dict) and "items" in data:
            data = data.get("items", [])
        if isinstance(data, dict) and "rules" in data:
            data = data.get("rules", [])
        if isinstance(data, dict) and "sources" in data:
            data = data.get("sources", [])
        if not isinstance(data, list):
            continue
        for item in data:
            if isinstance(item, dict):
                item = dict(item)
                item["__file__"] = rel_path(path)
                items.append(item)
    return items


def _group_by_source_file(items: list[dict[str, Any]], default_path: Path) -> dict[Path, list[dict[str, Any]]]:
    grouped: dict[Path, list[dict[str, Any]]] = {}
    for item in items:
        raw_file = item.get("__file__")
        path = KB_DIR / raw_file if raw_file else default_path
        grouped.setdefault(path, []).append(item)
    return grouped


# ============================================================
# Allgemeines Laden/Speichern für Admin-JSON-Ansicht
# ============================================================


def load_json(name: str, default: Any) -> Any:
    ensure_dirs()
    if name == "inference_rules":
        return load_inference_rules(active_only=False)
    if name == "step_packages":
        return load_step_packages()
    if name == "sources":
        return load_sources()
    if name == "global_blocks":
        return {"global_blocks": load_global_blocks(active_only=False)}
    path = FILES.get(name)
    if not path:
        return default
    if not path.exists():
        save_json(name, default, backup=False)
        return default
    return _read_json_file(path, default)


def save_json(name: str, data: Any, *, backup: bool = True) -> None:
    ensure_dirs()
    if name == "inference_rules":
        save_inference_rules(data if isinstance(data, list) else [])
        return
    if name == "step_packages":
        save_step_packages(data if isinstance(data, list) else [])
        return
    if name == "sources":
        save_sources(data if isinstance(data, list) else [])
        return
    if name == "global_blocks":
        if isinstance(data, dict):
            save_global_blocks(data.get("global_blocks", []))
        elif isinstance(data, list):
            save_global_blocks(data)
        else:
            save_global_blocks([])
        return
    path = FILES.get(name)
    if not path:
        raise ValueError(f"Unbekannte JSON-Datei: {name}")
    _write_json_file(path, data, backup=backup)



# ============================================================
# Globale Bausteine / dienstübergreifende Regeln
# ============================================================


def load_global_blocks(active_only: bool = False) -> list[dict[str, Any]]:
    """Lädt globale Bausteine aus Rule Engine/global/global_blocks.json.

    Globale Bausteine sind wiederverwendbare Themen wie Internet, Benutzerkonto,
    Betriebssystem, MFA oder Campusnetz/VPN. Dienste können über
    required_global_blocks festlegen, welche Bausteine für sie relevant sind.
    """
    ensure_dirs()
    path = FILES["global_blocks"]
    if not path.exists():
        save_global_blocks([], backup=False)
        return []
    data = _read_json_file(path, {"global_blocks": []})
    if isinstance(data, dict):
        blocks = data.get("global_blocks", [])
    elif isinstance(data, list):
        blocks = data
    else:
        blocks = []
    blocks = [b for b in blocks if isinstance(b, dict)]
    if active_only:
        blocks = [b for b in blocks if b.get("active", True)]
    return sorted(blocks, key=lambda b: (int(b.get("priority", 100)), str(b.get("id", ""))))


def save_global_blocks(blocks: list[dict[str, Any]], *, backup: bool = True) -> None:
    _write_json_file(FILES["global_blocks"], {"global_blocks": blocks}, backup=backup)


def get_global_block(block_id: str) -> Optional[dict[str, Any]]:
    for block in load_global_blocks(active_only=False):
        if block.get("id") == block_id:
            return block
    return None


def upsert_global_block(block: dict[str, Any]) -> None:
    blocks = load_global_blocks(active_only=False)
    block_id = str(block.get("id", "")).strip()
    if not block_id:
        raise ValueError("Global-Block-ID darf nicht leer sein.")
    block["id"] = block_id
    block.setdefault("active", True)
    block.setdefault("scope", "global")
    block.setdefault("facts", [])
    block.setdefault("rules", [])
    for idx, existing in enumerate(blocks):
        if existing.get("id") == block_id:
            merged = dict(existing)
            merged.update(block)
            merged.setdefault("facts", existing.get("facts", []))
            merged.setdefault("rules", existing.get("rules", []))
            blocks[idx] = merged
            save_global_blocks(blocks)
            return
    blocks.append(block)
    save_global_blocks(blocks)


def delete_global_block(block_id: str) -> None:
    blocks = [b for b in load_global_blocks(active_only=False) if b.get("id") != block_id]
    save_global_blocks(blocks)


def get_required_global_blocks_for_service(service_key: str) -> list[dict[str, Any]]:
    service = get_service(service_key)
    if not service:
        return []
    required_ids = service.get("required_global_blocks", []) or []
    if not isinstance(required_ids, list):
        required_ids = []
    blocks_by_id = {b.get("id"): b for b in load_global_blocks(active_only=True)}
    return [blocks_by_id[b_id] for b_id in required_ids if b_id in blocks_by_id]


def load_global_inference_rules(active_only: bool = True) -> list[dict[str, Any]]:
    """Konvertiert Regeln aus globalen Bausteinen in normale Inferenzregeln."""
    rules: list[dict[str, Any]] = []
    for block in load_global_blocks(active_only=True):
        block_id = str(block.get("id", "global"))
        block_priority = int(block.get("priority", 100))
        for raw_rule in block.get("rules", []) or []:
            if not isinstance(raw_rule, dict):
                continue
            if active_only and not raw_rule.get("active", True):
                continue
            rule = dict(raw_rule)
            rule.setdefault("id", f"{block_id}.rule")
            rule.setdefault("module", "global")
            rule.setdefault("rule_group", block_id)
            rule.setdefault("description", block.get("name", block_id))
            rule.setdefault("priority", block_priority + int(raw_rule.get("priority", 0)))
            rule["scope"] = "global"
            rule["global_block_id"] = block_id
            # Global-Block-Regeln dürfen conditions/result heißen; Inferenz nutzt when/then.
            if "when" not in rule:
                rule["when"] = rule.get("conditions", {})
            if "then" not in rule:
                result = rule.get("result", [])
                if isinstance(result, dict):
                    result = [result]
                rule["then"] = result if isinstance(result, list) else []
            rules.append(rule)
    return sorted(rules, key=lambda r: (int(r.get("priority", 100)), str(r.get("id", ""))))


def first_missing_required_global_fact(facts: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Findet die erste noch unbekannte Pflichtinformation aus globalen Bausteinen.

    Berücksichtigt nur den aktuell erkannten Dienst aus facts['topic']. Dadurch werden
    globale Bausteine nicht unnötig für alle Dienste abgefragt.
    """
    topic = str(facts.get("topic", "unknown")).strip()
    if topic in {"", "unknown", "None"}:
        return None
    blocks = get_required_global_blocks_for_service(topic)
    candidates: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    for block in blocks:
        for fact_def in block.get("facts", []) or []:
            if not isinstance(fact_def, dict) or fact_def.get("optional"):
                continue
            key = str(fact_def.get("key", "")).strip()
            if not key:
                continue
            priority = int(fact_def.get("priority", block.get("priority", 100)))
            candidates.append((priority, block, fact_def))

    for _priority, block, fact_def in sorted(candidates, key=lambda x: (x[0], str(x[1].get("id", "")), str(x[2].get("key", "")))):
        key = str(fact_def.get("key", "")).strip()
        value = facts.get(key, "unknown")
        if value in {None, "", "unknown"}:
            return {
                "type": "ask",
                "fact": key,
                "text": fact_def.get("question", f"Bitte ergänze den Wert für {key}."),
                "global_block_id": block.get("id"),
                "global_block_name": block.get("name"),
                "priority": int(fact_def.get("priority", block.get("priority", 100))),
            }
    return None

# ============================================================
# Services / Systeme / Schritte
# ============================================================


def load_services() -> dict[str, Any]:
    data = load_json("services", {"services": []})
    if isinstance(data, dict) and data.get("services"):
        return data
    return {"services": _derive_services_from_step_packages()}


def save_services(data: dict[str, Any]) -> None:
    save_json("services", data)


def get_services(active_only: bool = True) -> list[dict[str, Any]]:
    services = load_services().get("services", [])
    if active_only:
        services = [s for s in services if s.get("active", True)]
    return sorted(services, key=lambda s: str(s.get("name", s.get("key", ""))).lower())


def get_service(service_key: str) -> Optional[dict[str, Any]]:
    for service in load_services().get("services", []):
        if service.get("key") == service_key:
            return service
    return None


def get_systems(service_key: Optional[str] = None, active_only: bool = True) -> list[dict[str, Any]]:
    systems: list[dict[str, Any]] = []
    for service in load_services().get("services", []):
        if service_key and service.get("key") != service_key:
            continue
        for system in service.get("systems", []):
            if active_only and not system.get("active", True):
                continue
            item = dict(system)
            item["service_key"] = service.get("key")
            item["service_name"] = service.get("name")
            systems.append(item)
    return sorted(systems, key=lambda s: (str(s.get("service_name", "")).lower(), str(s.get("name", "")).lower()))


def get_system(service_key: str, system_key: str) -> Optional[dict[str, Any]]:
    service = get_service(service_key)
    if not service:
        return None
    aliases = {"mac": "macos", "macos": "macos"}
    normalized_key = aliases.get(system_key, system_key)
    for system in service.get("systems", []):
        if system.get("key") == normalized_key or system.get("key") == system_key:
            item = dict(system)
            item["service_key"] = service_key
            item["service_name"] = service.get("name")
            return item
    return None


def get_steps(service_key: str, system_key: str, active_only: bool = True) -> list[dict[str, Any]]:
    system = get_system(service_key, system_key)
    if not system:
        return []
    steps = system.get("steps", [])
    if active_only:
        steps = [s for s in steps if s.get("active", True)]
    return sorted(steps, key=lambda s: int(s.get("number", 0)))


def get_step(service_key: str, system_key: str, number: int) -> Optional[dict[str, Any]]:
    for step in get_steps(service_key, system_key, active_only=False):
        if int(step.get("number", -1)) == int(number):
            return step
    return None


def get_solution(service_key: str, system_key: str, step_number: int) -> Optional[dict[str, Any]]:
    step = get_step(service_key, system_key, step_number)
    if not step:
        return None
    solution = step.get("solution")
    if solution:
        return solution
    return {
        "problem_title": step.get("title", f"Schritt {step_number}"),
        "description": "Automatisch aus dem Anleitungsschritt erzeugte Lösung.",
        "actions": [step.get("instruction", "Prüfe diesen Schritt erneut.")],
        "source_refs": step.get("source_refs", []),
    }


def upsert_service(service: dict[str, Any]) -> None:
    data = load_services()
    services = data.setdefault("services", [])
    key = service["key"].strip().lower()
    service["key"] = key
    for idx, existing in enumerate(services):
        if existing.get("key") == key:
            merged = dict(existing)
            merged.update(service)
            merged.setdefault("systems", existing.get("systems", []))
            services[idx] = merged
            save_services(data)
            return
    service.setdefault("systems", [])
    service.setdefault("active", True)
    services.append(service)
    save_services(data)


def upsert_system(service_key: str, system: dict[str, Any]) -> None:
    data = load_services()
    for service in data.setdefault("services", []):
        if service.get("key") != service_key:
            continue
        systems = service.setdefault("systems", [])
        key = system["key"].strip().lower()
        if key == "mac":
            key = "macos"
        system["key"] = key
        for idx, existing in enumerate(systems):
            if existing.get("key") == key:
                merged = dict(existing)
                merged.update(system)
                merged.setdefault("steps", existing.get("steps", []))
                systems[idx] = merged
                save_services(data)
                return
        system.setdefault("steps", [])
        system.setdefault("active", True)
        systems.append(system)
        save_services(data)
        return
    raise ValueError(f"Dienst nicht gefunden: {service_key}")


def upsert_step(service_key: str, system_key: str, step: dict[str, Any]) -> None:
    data = load_services()
    system_key = "macos" if system_key == "mac" else system_key
    for service in data.setdefault("services", []):
        if service.get("key") != service_key:
            continue
        for system in service.setdefault("systems", []):
            if system.get("key") != system_key:
                continue
            steps = system.setdefault("steps", [])
            number = int(step["number"])
            step["number"] = number
            for idx, existing in enumerate(steps):
                if int(existing.get("number", -1)) == number:
                    merged = dict(existing)
                    merged.update(step)
                    steps[idx] = merged
                    save_services(data)
                    return
            step.setdefault("active", True)
            steps.append(step)
            system["steps"] = sorted(steps, key=lambda s: int(s.get("number", 0)))
            save_services(data)
            return
    raise ValueError("System oder Dienst nicht gefunden")


def delete_step(service_key: str, system_key: str, number: int) -> None:
    data = load_services()
    system_key = "macos" if system_key == "mac" else system_key
    for service in data.setdefault("services", []):
        if service.get("key") != service_key:
            continue
        for system in service.setdefault("systems", []):
            if system.get("key") != system_key:
                continue
            system["steps"] = [s for s in system.get("steps", []) if int(s.get("number", -1)) != int(number)]
            save_services(data)
            return


# ============================================================
# Inferenzregeln im Unterordner rules/
# ============================================================


def _rule_sort_key(rule: dict[str, Any]) -> tuple[int, int, str]:
    engine = load_engine_config()
    order = engine.get("rule_order", []) if isinstance(engine, dict) else []
    file_name = str(rule.get("__file__", ""))
    file_stem = Path(file_name).stem.replace("_rules", "")
    try:
        group_index = order.index(file_stem)
    except ValueError:
        group_index = 999
    return (group_index, int(rule.get("priority", 1000)), str(rule.get("id", "")))


def load_inference_rules(active_only: bool = False) -> list[dict[str, Any]]:
    rules = _load_many_json_lists(RULES_DIR)
    for rule in rules:
        if "module" not in rule:
            stem = Path(rule.get("__file__", "custom")).stem.replace("_rules", "")
            rule["module"] = stem
    if active_only:
        rules = [r for r in rules if r.get("active", True)]
    return sorted(rules, key=_rule_sort_key)


def save_inference_rules(rules: list[dict[str, Any]]) -> None:
    grouped = _group_by_source_file(rules, RULES_DIR / "custom_rules.json")
    for path, items in grouped.items():
        _write_json_file(path, sorted(items, key=_rule_sort_key))


def upsert_inference_rule(rule: dict[str, Any]) -> None:
    rules = load_inference_rules(active_only=False)
    rid = rule["id"]
    for idx, existing in enumerate(rules):
        if existing.get("id") == rid:
            merged = dict(existing)
            merged.update(rule)
            merged.setdefault("__file__", existing.get("__file__"))
            rules[idx] = merged
            save_inference_rules(rules)
            return
    rule.setdefault("active", True)
    rule.setdefault("priority", 100)
    rule.setdefault("when", {})
    rule.setdefault("then", [])
    rule.setdefault("__file__", "rules/custom_rules.json")
    rules.append(rule)
    save_inference_rules(rules)


def delete_inference_rule(rule_id: str) -> None:
    rules = [r for r in load_inference_rules(active_only=False) if r.get("id") != rule_id]
    save_inference_rules(rules)


# ============================================================
# Step Packages / Quellen / Konfiguration
# ============================================================


def load_step_packages() -> list[dict[str, Any]]:
    return sorted(_load_many_json_lists(STEP_PACKAGES_DIR), key=lambda p: str(p.get("id", "")))


def save_step_packages(packages: list[dict[str, Any]]) -> None:
    grouped = _group_by_source_file(packages, STEP_PACKAGES_DIR / "custom_steps.json")
    for path, items in grouped.items():
        _write_json_file(path, sorted(items, key=lambda p: str(p.get("id", ""))))


def get_step_package(package_id: str) -> Optional[dict[str, Any]]:
    for package in load_step_packages():
        if package.get("id") == package_id or package.get("package_key") == package_id:
            return package
    return None


def load_sources() -> list[dict[str, Any]]:
    return sorted(_load_many_json_lists(SOURCES_DIR), key=lambda s: str(s.get("id", "")))


def save_sources(sources: list[dict[str, Any]]) -> None:
    grouped = _group_by_source_file(sources, SOURCES_DIR / "custom_sources.json")
    for path, items in grouped.items():
        _write_json_file(path, sorted(items, key=lambda s: str(s.get("id", ""))))



# ============================================================
# Wissensmodell / semantischer Kern
# ============================================================


def load_knowledge_model() -> dict[str, Any]:
    """Lädt das aus den Wissensmodell-Grafiken abgeleitete semantische Modell.

    Das Modell ist kein Python-Code, sondern eine JSON-Beschreibung von
    Namespaces, Knoten, Fakten und Beziehungen. Es dient als übergeordnete
    Dokumentation, als Prompt-Kontext für die Faktenerkennung und als Grundlage
    für globale Bausteine, Cross-Service-Regeln und Entscheidungsnetze.
    """
    ensure_dirs()
    return load_json("knowledge_model_overview", {"id": "missing", "nodes": [], "edges": [], "namespaces": []})


def save_knowledge_model(model: dict[str, Any]) -> None:
    save_json("knowledge_model_overview", model)


def knowledge_model_context_for_prompt(max_nodes: int = 50, max_edges: int = 80) -> str:
    model = load_knowledge_model()
    lines: list[str] = []
    if model.get("name"):
        lines.append(f"Wissensmodell: {model.get('name')}")
    for ns in model.get("namespaces", []) or []:
        lines.append(f"Namespace {ns.get('label', ns.get('id'))}: {ns.get('description', '')}")
    lines.append("Knoten/Facts:")
    for node in (model.get("nodes", []) or [])[:max_nodes]:
        facts = ", ".join(node.get("fact_keys", []) or [])
        lines.append(f"- {node.get('id')}: {node.get('label')} | Facts: {facts}")
    lines.append("Wichtige Beziehungen:")
    for edge in (model.get("edges", []) or [])[:max_edges]:
        lines.append(f"- {edge.get('source')} -> {edge.get('target')}: {edge.get('label')} ({edge.get('relation_type', '')})")
    return "\n".join(lines)


def knowledge_model_stats() -> dict[str, Any]:
    model = load_knowledge_model()
    nodes = model.get("nodes", []) or []
    edges = model.get("edges", []) or []
    namespaces = model.get("namespaces", []) or []
    return {
        "id": model.get("id"),
        "name": model.get("name"),
        "namespaces": len(namespaces),
        "nodes": len(nodes),
        "edges": len(edges),
        "global_blocks": len({n.get("global_block") for n in nodes if n.get("global_block")}),
    }

def load_fact_catalog() -> dict[str, Any]:
    return load_json("fact_catalog", {})


def save_fact_catalog(catalog: dict[str, Any]) -> None:
    save_json("fact_catalog", catalog)


def load_constants() -> dict[str, Any]:
    return load_json("constants", {})


def save_constants(constants: dict[str, Any]) -> None:
    save_json("constants", constants)


def load_engine_config() -> dict[str, Any]:
    return load_json("engine", {})


def save_engine_config(config: dict[str, Any]) -> None:
    save_json("engine", config)


def export_all() -> dict[str, Any]:
    return {name: load_json(name, [] if name in {"inference_rules", "step_packages", "sources"} else {}) for name in FILES}


# ============================================================
# Ableitung von UI-Services aus Step Packages, falls services.json fehlt
# ============================================================


def _derive_services_from_step_packages() -> list[dict[str, Any]]:
    packages = load_step_packages()
    services: dict[str, dict[str, Any]] = {}
    service_names = {"eduroam": "eduroam", "vpn": "VPN", "mfa": "MFA / 2FA", "account": "Benutzerkonto", "user_account": "Benutzerkonto"}

    def service_key_from_package(package_id: str) -> str:
        parts = str(package_id).split(".")
        if len(parts) >= 2:
            key = parts[1]
            return "user_account" if key == "account" else key
        return "general"

    def system_key_from_package(package: dict[str, Any]) -> str:
        text = f"{package.get('id', '')} {package.get('title', '')}".lower()
        if "windows" in text:
            return "windows"
        if "macos" in text or "mac" in text:
            return "macos"
        if "linux" in text:
            return "linux"
        if "android" in text:
            return "android"
        if "ipados" in text or "ipad" in text:
            return "ipados"
        if "ios" in text or "iphone" in text:
            return "ios"
        if "chromeos" in text:
            return "chromeos"
        if "pc" in text or "laptop" in text:
            return "pc"
        return "general"

    for package in packages:
        p_id = str(package.get("id", ""))
        s_key = service_key_from_package(p_id)
        service = services.setdefault(s_key, {"key": s_key, "name": service_names.get(s_key, s_key.title()), "description": "Aus Step Packages abgeleiteter Dienst.", "active": True, "systems": {}})
        sys_key = system_key_from_package(package)
        system = service["systems"].setdefault(sys_key, {"key": sys_key, "name": sys_key.title(), "prerequisite": package.get("title", ""), "guide_url": ", ".join(package.get("source_refs", [])), "active": True, "steps": []})
        for text in package.get("steps", []):
            number = len(system["steps"]) + 1
            title = str(text).split(".")[0][:60] or f"Schritt {number}"
            system["steps"].append({"number": number, "phase": "step_package", "title": title, "instruction": text, "keywords": [], "active": True, "source_refs": package.get("source_refs", []), "package_id": p_id, "solution": {"problem_title": f"Hilfe zu: {title}", "description": f"Schritt aus {package.get('title', p_id)}", "actions": [text], "source_refs": package.get("source_refs", [])}})

    output = []
    for service in services.values():
        service["systems"] = list(service["systems"].values())
        output.append(service)
    return sorted(output, key=lambda s: s["key"])


# ============================================================
# Entscheidungsnetz-/Graph-Funktionen
# ============================================================


def load_decision_graphs(active_only: bool = False) -> list[dict[str, Any]]:
    data = load_json("decision_graphs", {"graphs": []})
    if isinstance(data, dict):
        # Unterstützt beide Dateiformate, damit ältere und neuere Rule-Engine-Ordner
        # ohne Datenverlust geladen werden können. Standard der App bleibt "graphs".
        graphs = data.get("graphs")
        if graphs is None:
            graphs = data.get("decision_graphs", [])
    elif isinstance(data, list):
        graphs = data
    else:
        graphs = []
    if active_only:
        graphs = [g for g in graphs if g.get("active", True)]
    return sorted(graphs, key=lambda g: str(g.get("name", g.get("id", ""))).lower())


def save_decision_graphs(graphs: list[dict[str, Any]]) -> None:
    save_json("decision_graphs", {"graphs": graphs})


def get_decision_graph(graph_id: str) -> Optional[dict[str, Any]]:
    for graph in load_decision_graphs(active_only=False):
        if graph.get("id") == graph_id:
            return graph
    return None


def upsert_decision_graph(graph: dict[str, Any]) -> None:
    graphs = load_decision_graphs(active_only=False)
    graph_id = str(graph.get("id", "")).strip()
    if not graph_id:
        raise ValueError("Graph-ID darf nicht leer sein.")
    graph["id"] = graph_id
    graph.setdefault("active", True)
    graph.setdefault("start_node_id", "start")
    graph.setdefault("nodes", [])
    graph.setdefault("edges", [])
    for idx, existing in enumerate(graphs):
        if existing.get("id") == graph_id:
            merged = dict(existing)
            merged.update(graph)
            merged.setdefault("nodes", existing.get("nodes", []))
            merged.setdefault("edges", existing.get("edges", []))
            graphs[idx] = merged
            save_decision_graphs(graphs)
            return
    graphs.append(graph)
    save_decision_graphs(graphs)


def delete_decision_graph(graph_id: str) -> None:
    graphs = [g for g in load_decision_graphs(active_only=False) if g.get("id") != graph_id]
    save_decision_graphs(graphs)


def upsert_graph_node(graph_id: str, node: dict[str, Any]) -> None:
    graph = get_decision_graph(graph_id)
    if not graph:
        raise ValueError(f"Graph nicht gefunden: {graph_id}")
    node_id = str(node.get("id", "")).strip()
    if not node_id:
        raise ValueError("Node-ID darf nicht leer sein.")
    node["id"] = node_id
    node.setdefault("type", "condition")
    node.setdefault("label", node_id)
    node.setdefault("position", {"x": 0, "y": 0})
    nodes = graph.setdefault("nodes", [])
    for idx, existing in enumerate(nodes):
        if existing.get("id") == node_id:
            merged = dict(existing)
            merged.update(node)
            nodes[idx] = merged
            upsert_decision_graph(graph)
            return
    nodes.append(node)
    upsert_decision_graph(graph)


def delete_graph_node(graph_id: str, node_id: str) -> None:
    graph = get_decision_graph(graph_id)
    if not graph:
        return
    graph["nodes"] = [n for n in graph.get("nodes", []) if n.get("id") != node_id]
    graph["edges"] = [e for e in graph.get("edges", []) if e.get("source") != node_id and e.get("target") != node_id]
    if graph.get("start_node_id") == node_id:
        graph["start_node_id"] = "start"
    upsert_decision_graph(graph)


def upsert_graph_edge(graph_id: str, edge: dict[str, Any]) -> None:
    graph = get_decision_graph(graph_id)
    if not graph:
        raise ValueError(f"Graph nicht gefunden: {graph_id}")
    edge_id = str(edge.get("id", "")).strip()
    if not edge_id:
        source = str(edge.get("source", "")).strip()
        target = str(edge.get("target", "")).strip()
        edge_id = f"{source}__to__{target}"
    edge["id"] = edge_id
    edge.setdefault("label", "")
    edge.setdefault("priority", 100)
    edge.setdefault("condition", {})
    edges = graph.setdefault("edges", [])
    for idx, existing in enumerate(edges):
        if existing.get("id") == edge_id:
            merged = dict(existing)
            merged.update(edge)
            edges[idx] = merged
            upsert_decision_graph(graph)
            return
    edges.append(edge)
    upsert_decision_graph(graph)


def delete_graph_edge(graph_id: str, edge_id: str) -> None:
    graph = get_decision_graph(graph_id)
    if not graph:
        return
    graph["edges"] = [e for e in graph.get("edges", []) if e.get("id") != edge_id]
    upsert_decision_graph(graph)

# ============================================================
# Excel-nahe Fachstruktur: Conditions/Facts, Funktionen, Abläufe
# ============================================================

CONDITIONS_DIR = KB_DIR / "conditions"
FUNCTIONS_DIR = KB_DIR / "functions"
FLOWS_DIR = KB_DIR / "flows"


def _read_catalog(path: Path, root_key: str) -> list[dict[str, Any]]:
    ensure_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _write_json_file(path, {root_key: []}, backup=False)
        return []
    data = _read_json_file(path, {root_key: []})
    if isinstance(data, dict):
        items = data.get(root_key, [])
    elif isinstance(data, list):
        items = data
    else:
        items = []
    return [x for x in items if isinstance(x, dict)]


def _write_catalog(path: Path, root_key: str, items: list[dict[str, Any]], *, backup: bool = True) -> None:
    _write_json_file(path, {root_key: items}, backup=backup)


def load_condition_catalog(active_only: bool = False) -> list[dict[str, Any]]:
    """Zentraler Conditions-/Facts-Katalog aus Rule Engine/conditions/condition_catalog.json."""
    items = _read_catalog(CONDITIONS_DIR / "condition_catalog.json", "conditions")
    if active_only:
        items = [x for x in items if x.get("active", True)]
    return sorted(items, key=lambda x: (str(x.get("knowledge_area", "")), str(x.get("category", "")), str(x.get("key", ""))))


def save_condition_catalog(items: list[dict[str, Any]], *, backup: bool = True) -> None:
    _write_catalog(CONDITIONS_DIR / "condition_catalog.json", "conditions", items, backup=backup)


def get_condition_fact(key: str) -> Optional[dict[str, Any]]:
    for item in load_condition_catalog(active_only=False):
        if item.get("key") == key:
            return item
    return None


def upsert_condition_fact(item: dict[str, Any]) -> None:
    items = load_condition_catalog(active_only=False)
    key = str(item.get("key", "")).strip()
    if not key:
        raise ValueError("Technische Condition-ID darf nicht leer sein.")
    item["key"] = key
    item.setdefault("display_name", key.replace("_", " ").title())
    item.setdefault("active", True)
    for idx, existing in enumerate(items):
        if existing.get("key") == key:
            merged = dict(existing)
            merged.update(item)
            items[idx] = merged
            save_condition_catalog(items)
            return
    items.append(item)
    save_condition_catalog(items)


def delete_condition_fact(key: str) -> None:
    save_condition_catalog([x for x in load_condition_catalog(active_only=False) if x.get("key") != key])


def rules_using_condition(key: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for rule in load_inference_rules(active_only=False):
        blob = json.dumps(rule, ensure_ascii=False)
        if key and key in blob:
            hits.append({"id": rule.get("id"), "description": rule.get("description", ""), "module": rule.get("module", ""), "priority": rule.get("priority")})
    return hits


def load_function_catalog(active_only: bool = False) -> list[dict[str, Any]]:
    """Funktionen und Antwortbausteine aus Rule Engine/functions/functions_catalog.json."""
    items = _read_catalog(FUNCTIONS_DIR / "functions_catalog.json", "functions")
    if active_only:
        items = [x for x in items if x.get("active", True)]
    return sorted(items, key=lambda x: (str(x.get("knowledge_area", "")), str(x.get("function_type", "")), str(x.get("id", ""))))


def save_function_catalog(items: list[dict[str, Any]], *, backup: bool = True) -> None:
    _write_catalog(FUNCTIONS_DIR / "functions_catalog.json", "functions", items, backup=backup)


def get_function_item(function_id: str) -> Optional[dict[str, Any]]:
    for item in load_function_catalog(active_only=False):
        if item.get("id") == function_id:
            return item
    return None


def upsert_function_item(item: dict[str, Any]) -> None:
    items = load_function_catalog(active_only=False)
    function_id = str(item.get("id", "")).strip()
    if not function_id:
        raise ValueError("Funktions-ID darf nicht leer sein.")
    item["id"] = function_id
    item.setdefault("display_name", function_id.replace("_", " ").title())
    item.setdefault("active", True)
    for idx, existing in enumerate(items):
        if existing.get("id") == function_id:
            merged = dict(existing)
            merged.update(item)
            items[idx] = merged
            save_function_catalog(items)
            return
    items.append(item)
    save_function_catalog(items)


def delete_function_item(function_id: str) -> None:
    save_function_catalog([x for x in load_function_catalog(active_only=False) if x.get("id") != function_id])


def load_flow_catalog(active_only: bool = False) -> list[dict[str, Any]]:
    items = _read_catalog(FLOWS_DIR / "flow_catalog.json", "flows")
    if active_only:
        items = [x for x in items if x.get("active", True)]
    return sorted(items, key=lambda x: str(x.get("name", x.get("id", ""))).lower())


def save_flow_catalog(items: list[dict[str, Any]], *, backup: bool = True) -> None:
    _write_catalog(FLOWS_DIR / "flow_catalog.json", "flows", items, backup=backup)


def load_technical_excel_rule_overview() -> list[dict[str, Any]]:
    data = _read_json_file(TECHNICAL_DIR / "wissensmodell_excel_rule_overview.json", {"items": []})
    return data.get("items", []) if isinstance(data, dict) else []


def load_technical_excel_translation_matrix() -> list[dict[str, Any]]:
    data = _read_json_file(TECHNICAL_DIR / "wissensmodell_excel_translation_matrix.json", {"items": []})
    return data.get("items", []) if isinstance(data, dict) else []


def load_technical_excel_priorities() -> list[dict[str, Any]]:
    data = _read_json_file(TECHNICAL_DIR / "wissensmodell_excel_priorities.json", {"items": []})
    return data.get("items", []) if isinstance(data, dict) else []
