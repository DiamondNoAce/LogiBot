# decision_graph_engine.py
# ============================================================
# JSON-basierte Entscheidungsnetz-Engine.
# Interpretiert Knoten und Kanten aus Rule Engine/decision_graphs.json.
# Kein generierter Python-Code: Admin-Eingaben bleiben Daten.
# ============================================================

from __future__ import annotations

from typing import Any, Optional

from storage import kb_loader as kb_json
from core import inference_engine

TERMINAL_NODE_TYPES = {"step", "solution", "redirect", "end"}


def node_by_id(graph: dict[str, Any], node_id: str) -> Optional[dict[str, Any]]:
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


def outgoing_edges(graph: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    edges = [edge for edge in graph.get("edges", []) if edge.get("source") == node_id]
    return sorted(edges, key=lambda e: int(e.get("priority", 100)))


def normalize_condition(condition: Any) -> dict[str, Any]:
    if not condition:
        return {}
    if not isinstance(condition, dict):
        return {}
    # Alias field -> fact, damit der Editor verständlicher bleibt.
    if "field" in condition and "fact" not in condition:
        condition = dict(condition)
        condition["fact"] = condition.pop("field")
    return condition


def condition_matches(condition: Any, facts: dict[str, Any]) -> bool:
    condition = normalize_condition(condition)
    if not condition:
        return True
    if "all" in condition or "any" in condition:
        matched, _trace = inference_engine.evaluate_when(condition, facts)
        return matched
    return inference_engine.evaluate_condition(condition, facts)


def edge_trace(edge: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    condition = normalize_condition(edge.get("condition", {}))
    if not condition:
        return {"edge_id": edge.get("id"), "label": edge.get("label", ""), "matched": True, "condition": {}}
    if "all" in condition or "any" in condition:
        matched, trace = inference_engine.evaluate_when(condition, facts)
        return {"edge_id": edge.get("id"), "label": edge.get("label", ""), "matched": matched, "condition": condition, "trace": trace}
    matched = inference_engine.evaluate_condition(condition, facts)
    actual = facts.get(str(condition.get("fact", "")), "unknown")
    return {"edge_id": edge.get("id"), "label": edge.get("label", ""), "matched": matched, "condition": condition, "actual": actual}


def resolve_terminal_node(node: dict[str, Any]) -> dict[str, Any]:
    node_type = node.get("type")
    resolved: dict[str, Any] = {"node": node, "node_type": node_type}

    if node_type == "step":
        service_key = node.get("service_key")
        system_key = node.get("system_key")
        step_number = node.get("step_number")
        if service_key and system_key and step_number is not None:
            step = kb_json.get_step(str(service_key), str(system_key), int(step_number))
            solution = kb_json.get_solution(str(service_key), str(system_key), int(step_number))
            service = kb_json.get_service(str(service_key))
            system = kb_json.get_system(str(service_key), str(system_key))
            resolved.update({"service": service, "system": system, "step": step, "solution": solution})

    if node_type == "solution":
        resolved["solution_text"] = node.get("solution_text") or node.get("text") or node.get("label")

    if node_type == "redirect":
        resolved["target_service_key"] = node.get("target_service_key")
        resolved["target_graph_id"] = node.get("target_graph_id")

    return resolved


def run_decision_graph(graph: dict[str, Any], facts: dict[str, Any], *, max_steps: int = 50) -> dict[str, Any]:
    """
    Durchläuft einen Entscheidungsgraphen.

    Ergebnis-Typen:
    - terminal: step/solution/redirect/end erreicht
    - question: Frageknoten erreicht, aber keine Kante passt
    - error: Graph ist fehlerhaft
    """
    if not graph:
        return {"status": "error", "message": "Kein Graph übergeben.", "facts": facts}

    start_id = graph.get("start_node_id") or "start"
    current_id = start_id
    path: list[dict[str, Any]] = []
    evaluated_edges: list[dict[str, Any]] = []
    visited: set[str] = set()

    for _ in range(max_steps):
        node = node_by_id(graph, current_id)
        if not node:
            return {"status": "error", "message": f"Knoten nicht gefunden: {current_id}", "path": path, "facts": facts, "evaluated_edges": evaluated_edges}

        path.append({"node_id": node.get("id"), "label": node.get("label"), "type": node.get("type")})

        if node.get("type") in TERMINAL_NODE_TYPES:
            return {"status": "terminal", "graph": graph, "facts": facts, "path": path, "terminal": resolve_terminal_node(node), "evaluated_edges": evaluated_edges}

        if current_id in visited:
            return {"status": "error", "message": f"Zyklus erkannt bei Knoten: {current_id}", "path": path, "facts": facts, "evaluated_edges": evaluated_edges}
        visited.add(current_id)

        candidates = outgoing_edges(graph, current_id)
        if not candidates:
            return {"status": "question", "graph": graph, "facts": facts, "path": path, "current_node": node, "message": node.get("question") or node.get("label"), "evaluated_edges": evaluated_edges}

        selected_edge = None
        for edge in candidates:
            trace = edge_trace(edge, facts)
            evaluated_edges.append(trace)
            if trace.get("matched"):
                selected_edge = edge
                break

        if not selected_edge:
            return {"status": "question", "graph": graph, "facts": facts, "path": path, "current_node": node, "message": node.get("question") or node.get("label"), "evaluated_edges": evaluated_edges}

        current_id = str(selected_edge.get("target"))

    return {"status": "error", "message": "Maximale Schrittzahl erreicht. Möglicherweise enthält der Graph eine Schleife.", "path": path, "facts": facts, "evaluated_edges": evaluated_edges}


def render_summary(result: dict[str, Any]) -> str:
    status = result.get("status")
    if status == "terminal":
        terminal = result.get("terminal", {})
        node = terminal.get("node", {})
        node_type = terminal.get("node_type")
        if node_type == "step":
            step = terminal.get("step") or {}
            solution = terminal.get("solution") or {}
            actions = solution.get("actions") or []
            if actions:
                return "\n".join(f"- {a}" for a in actions)
            return step.get("instruction") or node.get("label", "Schritt erreicht.")
        if node_type == "solution":
            return terminal.get("solution_text") or node.get("label", "Lösung erreicht.")
        if node_type == "redirect":
            return f"Weiterleitung zu Dienst/Graph: {terminal.get('target_service_key') or terminal.get('target_graph_id')}"
        return node.get("label", "Ende erreicht.")
    if status == "question":
        return result.get("message") or "Ich brauche noch eine zusätzliche Information."
    return result.get("message") or "Der Entscheidungsgraph konnte nicht ausgeführt werden."
