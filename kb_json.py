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

BASE_DIR = Path(__file__).resolve().parent
RULE_ENGINE_DIR = BASE_DIR / "Rule Engine"
LEGACY_KB_DIR = BASE_DIR / "knowledge_base"

# Fallback: alte Projektstruktur weiterhin lesen, falls kein Rule-Engine-Ordner existiert.
KB_DIR = RULE_ENGINE_DIR if RULE_ENGINE_DIR.exists() else LEGACY_KB_DIR
BACKUP_DIR = KB_DIR / "backups"
RULES_DIR = KB_DIR / "rules"
STEP_PACKAGES_DIR = KB_DIR / "step_packages"
SOURCES_DIR = KB_DIR / "sources"

FILES = {
    "services": KB_DIR / "services.json",
    "engine": KB_DIR / "engine.json",
    "constants": KB_DIR / "constants.json",
    "fact_catalog": KB_DIR / "fact_catalog.json",
    "decision_graphs": KB_DIR / "decision_graphs.json",
    "source_index": SOURCES_DIR / "source_index.json",
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
    path = FILES.get(name)
    if not path:
        raise ValueError(f"Unbekannte JSON-Datei: {name}")
    _write_json_file(path, data, backup=backup)


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
    graphs = data.get("graphs", []) if isinstance(data, dict) else []
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
