from __future__ import annotations

import json
import re
from typing import Any

import streamlit as st

from storage import kb_loader as kb_json
from core import decision_graph_engine

from ui.common import esc, json_area, render_answer, render_view_info

try:
    from streamlit_flow import streamlit_flow
    from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
    from streamlit_flow.state import StreamlitFlowState
    from streamlit_flow.layouts import TreeLayout
    STREAMLIT_FLOW_AVAILABLE = True
except Exception:
    streamlit_flow = None
    StreamlitFlowNode = None
    StreamlitFlowEdge = None
    StreamlitFlowState = None
    TreeLayout = None
    STREAMLIT_FLOW_AVAILABLE = False

# ============================================================

NODE_TYPES = ["start", "question", "condition", "step", "solution", "redirect", "end"]
EDGE_OPERATORS = ["equals", "not_equals", "contains", "in", "exists", "not_exists"]


def _node_format(node: dict[str, Any] | None) -> str:
    if node is None:
        return "Kein Knoten ausgewählt"
    return f"{node.get('id')} · {node.get('type')} · {node.get('label','')}"


def _edge_format(edge: dict[str, Any] | None) -> str:
    if edge is None:
        return "Keine Verbindung ausgewählt"
    return f"{edge.get('id')} · {edge.get('source')} → {edge.get('target')} · {edge.get('label','')}"


def _slugify(value: Any, default: str = "item") -> str:
    text = str(value or "").strip().lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = re.sub(r"[^a-z0-9_\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or default


def _unique_id(existing: set[str], base: str) -> str:
    base = _slugify(base)
    if base not in existing:
        return base
    idx = 2
    while f"{base}_{idx}" in existing:
        idx += 1
    return f"{base}_{idx}"


def _find_node(graph: dict[str, Any], node_id: str | None) -> dict[str, Any] | None:
    if not node_id:
        return None
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


def _find_edge(graph: dict[str, Any], edge_id: str | None) -> dict[str, Any] | None:
    if not edge_id:
        return None
    for edge in graph.get("edges", []):
        if edge.get("id") == edge_id:
            return edge
    return None


def _current_selection(graph_id: str) -> tuple[str | None, str | None]:
    return (
        st.session_state.get(f"graph_selected_type_{graph_id}"),
        st.session_state.get(f"graph_selected_id_{graph_id}"),
    )


def _set_selection(graph_id: str, selected_type: str | None, selected_id: str | None, *, from_canvas: bool = False) -> None:
    """Speichert die aktuelle Auswahl im Session-State.

    from_canvas=True wird gesetzt, wenn die Auswahl direkt aus dem
    streamlit-flow-Canvas kommt. Dadurch kann das manuelle Dropdown im
    Eigenschaften-Panel im nächsten Render-Schritt sauber synchronisiert
    werden. Ohne diese Synchronisierung würde Streamlit wegen des stabilen
    Widget-Keys oft den alten Dropdown-Wert behalten und die Canvas-Auswahl
    direkt wieder überschreiben.
    """
    st.session_state[f"graph_selected_type_{graph_id}"] = selected_type
    st.session_state[f"graph_selected_id_{graph_id}"] = selected_id
    if from_canvas:
        st.session_state[f"graph_canvas_selection_dirty_{graph_id}"] = True


def _get_obj_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _extract_position(node_obj: Any) -> dict[str, int]:
    pos = _get_obj_attr(node_obj, "pos", None)
    if pos is None:
        pos = _get_obj_attr(node_obj, "position", None)
    if isinstance(pos, dict):
        return {"x": int(pos.get("x", 0)), "y": int(pos.get("y", 0))}
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        return {"x": int(pos[0]), "y": int(pos[1])}
    return {"x": 0, "y": 0}


def _graph_node_ids(graph: dict[str, Any]) -> list[str]:
    return [str(n.get("id")) for n in graph.get("nodes", []) if n.get("id")]


def _graph_edge_ids(graph: dict[str, Any]) -> list[str]:
    return [str(e.get("id")) for e in graph.get("edges", []) if e.get("id")]


def graphviz_dot(graph: dict[str, Any]) -> str:
    def q(value: Any) -> str:
        return str(value).replace('"', '\\"')
    lines = ["digraph G {", "rankdir=LR;", "node [shape=box, style=rounded, fontname=Arial];"]
    for node in graph.get("nodes", []):
        node_id = node.get("id")
        node_type = node.get("type", "condition")
        label = f"{node.get('label', node_id)}\\n[{node_type}]"
        shape = "oval" if node_type == "start" else "diamond" if node_type in {"question", "condition"} else "box"
        lines.append(f'"{q(node_id)}" [label="{q(label)}", shape={shape}];')
    for edge in graph.get("edges", []):
        label = edge.get("label", "")
        lines.append(f'"{q(edge.get("source"))}" -> "{q(edge.get("target"))}" [label="{q(label)}"];')
    lines.append("}")
    return "\n".join(lines)


def graph_to_flow_state(graph: dict[str, Any]):
    nodes = []
    edges = []
    graph_id = graph.get("id")
    selected_type, selected_id = _current_selection(graph_id) if graph_id else (None, None)
    for node in graph.get("nodes", []):
        pos = node.get("position") or {}
        x = pos.get("x", 0) if isinstance(pos, dict) else 0
        y = pos.get("y", 0) if isinstance(pos, dict) else 0
        node_type = node.get("type", "condition")
        flow_type = "input" if node_type == "start" else "output" if node_type in {"step", "solution", "redirect", "end"} else "default"
        content = f"**{node.get('label', node.get('id'))}**\n\n`{node_type}`"
        if node_type == "step":
            content += f"\n\n{node.get('service_key','')} / {node.get('system_key','')} / Schritt {node.get('step_number','')}"
        if node_type == "solution" and node.get("solution_text"):
            content += f"\n\n{str(node.get('solution_text'))[:70]}"
        nodes.append(
            StreamlitFlowNode(
                str(node.get("id")),
                (x, y),
                {"content": content},
                flow_type,
                "right",
                "left",
                selected=(selected_type == "node" and selected_id == str(node.get("id"))),
                selectable=True,
                connectable=True,
                deletable=True,
            )
        )
    for edge in graph.get("edges", []):
        edges.append(
            StreamlitFlowEdge(
                str(edge.get("id")),
                str(edge.get("source")),
                str(edge.get("target")),
                label=str(edge.get("label", "")),
                animated=True,
                selected=(selected_type == "edge" and selected_id == str(edge.get("id"))),
                deletable=True,
                focusable=True,
                marker_end={"type": "arrowclosed"},
            )
        )
    return StreamlitFlowState(nodes, edges)


def _read_canvas_selection(flow_state: Any) -> tuple[str | None, str | None]:
    """Versucht, einen Klick/Selection aus streamlit-flow zu erkennen.

    In aktuellen streamlit-flow-Versionen wird die angeklickte Node/Edge vor
    allem als ``selected_id`` im zurückgegebenen StreamlitFlowState gespeichert.
    Ältere Versionen bzw. Beispiele verwenden teils andere Feldnamen. Deshalb
    prüfen wir mehrere Varianten und klassifizieren die ID anhand der vorhandenen
    Node- und Edge-Listen.
    """

    def _clean_id(value: Any) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, dict):
            value = (
                value.get("id")
                or value.get("node")
                or value.get("node_id")
                or value.get("edge")
                or value.get("edge_id")
                or value.get("selected_id")
                or value.get("selectedId")
            )
        if value is None or value == "":
            return None
        return str(value)

    node_ids = {str(_get_obj_attr(node_obj, "id", "")) for node_obj in (_get_obj_attr(flow_state, "nodes", []) or [])}
    edge_ids = {str(_get_obj_attr(edge_obj, "id", "")) for edge_obj in (_get_obj_attr(flow_state, "edges", []) or [])}

    # Wichtigster Fall bei streamlit-flow >= 1.x: selected_id.
    for attr in ["selected_id", "selectedId"]:
        selected = _clean_id(_get_obj_attr(flow_state, attr, None))
        if selected:
            if selected in node_ids:
                return "node", selected
            if selected in edge_ids:
                return "edge", selected

    # Fallback-Feldnamen aus älteren Versionen / Beispielen.
    for attr in ["selected_node", "selected_node_id", "clicked_node", "clicked_node_id", "node_on_click"]:
        value = _clean_id(_get_obj_attr(flow_state, attr, None))
        if value:
            return "node", value
    for attr in ["selected_edge", "selected_edge_id", "clicked_edge", "clicked_edge_id", "edge_on_click"]:
        value = _clean_id(_get_obj_attr(flow_state, attr, None))
        if value:
            return "edge", value

    # Weitere Fallbacks, falls ausgewählte Elemente als Flag markiert sind.
    for node_obj in _get_obj_attr(flow_state, "nodes", []) or []:
        if bool(_get_obj_attr(node_obj, "selected", False)):
            return "node", str(_get_obj_attr(node_obj, "id", ""))
    for edge_obj in _get_obj_attr(flow_state, "edges", []) or []:
        if bool(_get_obj_attr(edge_obj, "selected", False)):
            return "edge", str(_get_obj_attr(edge_obj, "id", ""))
    return None, None


def apply_flow_state_to_graph(graph: dict[str, Any], flow_state: Any) -> dict[str, Any]:
    graph = dict(graph)
    nodes = [dict(n) for n in graph.get("nodes", [])]
    edges = [dict(e) for e in graph.get("edges", [])]
    node_by = {n.get("id"): n for n in nodes}
    edge_ids = {e.get("id") for e in edges}

    for node_obj in _get_obj_attr(flow_state, "nodes", []) or []:
        node_id = str(_get_obj_attr(node_obj, "id", ""))
        if not node_id:
            continue
        if node_id in node_by:
            node_by[node_id]["position"] = _extract_position(node_obj)
        else:
            nodes.append({"id": node_id, "type": "condition", "label": node_id, "position": _extract_position(node_obj)})

    for edge_obj in _get_obj_attr(flow_state, "edges", []) or []:
        edge_id = str(_get_obj_attr(edge_obj, "id", ""))
        source = str(_get_obj_attr(edge_obj, "source", ""))
        target = str(_get_obj_attr(edge_obj, "target", ""))
        if not source or not target:
            continue
        if not edge_id:
            edge_id = f"{source}__to__{target}"
        if edge_id not in edge_ids:
            edges.append({"id": edge_id, "source": source, "target": target, "label": "neu", "priority": 100, "condition": {}})
            edge_ids.add(edge_id)

    graph["nodes"] = nodes
    graph["edges"] = edges
    return graph


def _auto_layout_graph(graph: dict[str, Any]) -> dict[str, Any]:
    graph = dict(graph)
    nodes = [dict(n) for n in graph.get("nodes", [])]
    edges = graph.get("edges", [])
    start = graph.get("start_node_id") or "start"
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        outgoing.setdefault(str(edge.get("source")), []).append(str(edge.get("target")))
    levels: dict[str, int] = {}
    queue = [(start, 0)]
    while queue:
        node_id, level = queue.pop(0)
        if node_id in levels and levels[node_id] <= level:
            continue
        levels[node_id] = level
        for target in outgoing.get(node_id, []):
            queue.append((target, level + 1))
    for node in nodes:
        levels.setdefault(str(node.get("id")), 0)
    by_level: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        by_level.setdefault(levels.get(str(node.get("id")), 0), []).append(node)
    for level, level_nodes in by_level.items():
        for idx, node in enumerate(sorted(level_nodes, key=lambda n: str(n.get("id")))):
            node["position"] = {"x": int(level * 260), "y": int(idx * 135)}
    graph["nodes"] = nodes
    return graph


def _condition_to_simple(condition: Any) -> tuple[str, str, str, str]:
    if not isinstance(condition, dict) or not condition:
        return "none", "", "equals", ""
    if "all" in condition or "any" in condition:
        return "json", "", "equals", json.dumps(condition, ensure_ascii=False, indent=2)
    fact = condition.get("fact", condition.get("field", ""))
    operator = condition.get("operator", "equals")
    value = condition.get("value", "")
    return "simple", str(fact), str(operator), str(value)


def _build_condition(mode: str, fact: str, operator: str, value: str, raw_json: str) -> dict[str, Any]:
    if mode == "none":
        return {}
    if mode == "json":
        return json.loads(raw_json) if raw_json.strip() else {}
    cond: dict[str, Any] = {"fact": fact.strip(), "operator": operator}
    if operator not in {"exists", "not_exists"}:
        # Komma-getrennte Liste für operator=in komfortabel unterstützen.
        if operator == "in":
            cond["value"] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            cond["value"] = value.strip()
    return cond


def _graph_quick_add_node(graph: dict[str, Any], node_type: str = "question", source_id: str | None = None) -> dict[str, Any]:
    graph = dict(graph)
    nodes = [dict(n) for n in graph.get("nodes", [])]
    existing = {str(n.get("id")) for n in nodes}
    node_id = _unique_id(existing, f"{node_type}_node")
    base_x, base_y = 120, 120
    source = _find_node(graph, source_id)
    if source and isinstance(source.get("position"), dict):
        base_x = int(source["position"].get("x", 0)) + 280
        base_y = int(source["position"].get("y", 0))
    else:
        base_y = len(nodes) * 95
    nodes.append({"id": node_id, "type": node_type, "label": f"Neuer {node_type}-Knoten", "question": "", "position": {"x": base_x, "y": base_y}})
    graph["nodes"] = nodes
    return graph


def _graph_quick_add_path(graph: dict[str, Any], source_id: str | None, target_type: str = "question") -> tuple[dict[str, Any], str, str]:
    graph = dict(graph)
    if not source_id:
        source_id = graph.get("start_node_id") or (graph.get("nodes", [{}])[0].get("id") if graph.get("nodes") else "start")
    graph = _graph_quick_add_node(graph, target_type, source_id=source_id)
    target_id = str(graph["nodes"][-1]["id"])
    edge_existing = {str(e.get("id")) for e in graph.get("edges", [])}
    edge_id = _unique_id(edge_existing, f"{source_id}_to_{target_id}")
    graph.setdefault("edges", []).append({"id": edge_id, "source": source_id, "target": target_id, "label": "neuer Pfad", "priority": 100, "condition": {}})
    return graph, target_id, edge_id


def _rename_node_in_graph(graph: dict[str, Any], old_id: str, new_id: str) -> dict[str, Any]:
    if old_id == new_id:
        return graph
    graph = dict(graph)
    for node in graph.get("nodes", []):
        if node.get("id") == old_id:
            node["id"] = new_id
    for edge in graph.get("edges", []):
        if edge.get("source") == old_id:
            edge["source"] = new_id
        if edge.get("target") == old_id:
            edge["target"] = new_id
    if graph.get("start_node_id") == old_id:
        graph["start_node_id"] = new_id
    return graph


def render_graph_canvas_interactive(graph: dict[str, Any]) -> Any:
    st.markdown('<div class="canvas-help">Klicke einen Knoten oder eine Verbindung an, bearbeite die Auswahl rechts und speichere. Neue Knoten/Pfade kannst du über die Plus-Buttons anlegen.</div>', unsafe_allow_html=True)
    if STREAMLIT_FLOW_AVAILABLE:
        state_key = f"flow_state_{graph.get('id')}"
        graph_signature = json.dumps({"id": graph.get("id"), "nodes": graph.get("nodes", []), "edges": graph.get("edges", [])}, sort_keys=True, ensure_ascii=False)
        sig_key = f"flow_sig_{graph.get('id')}"
        if state_key not in st.session_state or st.session_state.get(sig_key) != graph_signature:
            st.session_state[state_key] = graph_to_flow_state(graph)
            st.session_state[sig_key] = graph_signature
        try:
            st.session_state[state_key] = streamlit_flow(
                f"decision_flow_visual_editor_{graph.get('id')}",
                st.session_state[state_key],
                layout=TreeLayout(direction="right") if TreeLayout else None,
                fit_view=True,
                height=650,
                enable_node_menu=True,
                enable_edge_menu=True,
                enable_pane_menu=True,
                get_edge_on_click=True,
                get_node_on_click=True,
                show_minimap=True,
                hide_watermark=True,
                allow_new_edges=True,
                min_zoom=0.1,
            )
        except TypeError:
            # Fallback für ältere streamlit-flow-Versionen mit weniger Parametern.
            st.session_state[state_key] = streamlit_flow(
                f"decision_flow_visual_editor_{graph.get('id')}",
                st.session_state[state_key],
                height=650,
                fit_view=True,
            )
        sel_type, sel_id = _read_canvas_selection(st.session_state[state_key])
        if sel_type and sel_id:
            _set_selection(graph.get("id"), sel_type, sel_id, from_canvas=True)
        return st.session_state[state_key]
    st.info("Für den interaktiven Canvas installiere: py -m pip install streamlit-flow-component. Bis dahin wird eine Graphviz-Vorschau angezeigt.")
    st.graphviz_chart(graphviz_dot(graph), use_container_width=True)
    return None


def _node_properties_panel(graph: dict[str, Any], node: dict[str, Any]) -> None:
    graph_id = graph.get("id")
    st.markdown('<div class="selection-pill">Knoten ausgewählt</div>', unsafe_allow_html=True)
    st.markdown(f"**{node.get('label', node.get('id'))}**")
    st.caption(f"ID: {node.get('id')} · Typ: {node.get('type')}")

    with st.form(f"node_prop_form_{graph_id}_{node.get('id')}"):
        old_id = str(node.get("id"))
        node_id = st.text_input("Knoten-ID", value=old_id, key=f"node_prop_id_{graph_id}_{old_id}")
        node_type = st.selectbox("Knotentyp", NODE_TYPES, index=NODE_TYPES.index(node.get("type", "condition")) if node.get("type") in NODE_TYPES else 2, key=f"node_prop_type_{graph_id}_{old_id}")
        label = st.text_input("Label", value=node.get("label", ""), key=f"node_prop_label_{graph_id}_{old_id}")
        question = st.text_area("Frage / Beschreibung / Lösungstext", value=node.get("question", node.get("solution_text", "")), height=120, key=f"node_prop_question_{graph_id}_{old_id}")

        service_options = [""] + [s.get("key") for s in kb_json.get_services(active_only=False)]
        current_service = node.get("service_key", "")
        service_index = service_options.index(current_service) if current_service in service_options else 0
        service_key = st.selectbox("Service-Key", service_options, index=service_index, key=f"node_prop_service_{graph_id}_{old_id}")

        system_options = [""]
        if service_key:
            system_options += [s.get("key") for s in kb_json.get_systems(service_key, active_only=False)]
        current_system = node.get("system_key", "")
        system_index = system_options.index(current_system) if current_system in system_options else 0
        system_key = st.selectbox("System-Key", system_options, index=system_index, key=f"node_prop_system_{graph_id}_{old_id}")

        step_options = [0]
        if service_key and system_key:
            step_options += [int(s.get("number")) for s in kb_json.get_steps(service_key, system_key, active_only=False)]
        current_step = int(node.get("step_number", 0) or 0)
        step_index = step_options.index(current_step) if current_step in step_options else 0
        step_number = st.selectbox("Schritt", step_options, index=step_index, format_func=lambda x: "Kein Schritt" if x == 0 else f"Schritt {x}", key=f"node_prop_step_{graph_id}_{old_id}")

        target_service_key = st.text_input("Redirect: Ziel-Service-Key", value=node.get("target_service_key", ""), key=f"node_prop_target_service_{graph_id}_{old_id}")
        target_graph_id = st.text_input("Redirect: Ziel-Graph-ID", value=node.get("target_graph_id", ""), key=f"node_prop_target_graph_{graph_id}_{old_id}")

        col1, col2 = st.columns(2)
        save = col1.form_submit_button("Knoten speichern")
        delete = col2.form_submit_button("Knoten löschen")

    if save:
        try:
            node_id_clean = _slugify(node_id, "node")
            existing_ids = {n.get("id") for n in graph.get("nodes", []) if n.get("id") != old_id}
            if node_id_clean in existing_ids:
                st.error("Diese Knoten-ID existiert bereits.")
                return
            updated_graph = _rename_node_in_graph(graph, old_id, node_id_clean)
            updated_node = _find_node(updated_graph, node_id_clean) or {}
            updated_node.update({"id": node_id_clean, "type": node_type, "label": label or node_id_clean})
            updated_node.pop("question", None)
            updated_node.pop("solution_text", None)
            if question:
                if node_type == "solution":
                    updated_node["solution_text"] = question
                else:
                    updated_node["question"] = question
            for key in ["service_key", "system_key", "step_number", "target_service_key", "target_graph_id"]:
                updated_node.pop(key, None)
            if service_key:
                updated_node["service_key"] = service_key
            if system_key:
                updated_node["system_key"] = system_key
            if step_number:
                updated_node["step_number"] = int(step_number)
            if target_service_key:
                updated_node["target_service_key"] = target_service_key.strip()
            if target_graph_id:
                updated_node["target_graph_id"] = target_graph_id.strip()
            # Replace node in graph.
            updated_nodes = []
            for n in updated_graph.get("nodes", []):
                updated_nodes.append(updated_node if n.get("id") == node_id_clean else n)
            updated_graph["nodes"] = updated_nodes
            kb_json.upsert_decision_graph(updated_graph)
            _set_selection(graph_id, "node", node_id_clean)
            st.success("Knoten gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(f"Knoten konnte nicht gespeichert werden: {e}")

    if delete:
        if node.get("id") == graph.get("start_node_id"):
            st.error("Der Start-Knoten kann nicht gelöscht werden. Ändere zuerst den Start-Knoten in den Graph-Stammdaten.")
        else:
            kb_json.delete_graph_node(graph_id, node.get("id"))
            _set_selection(graph_id, None, None)
            st.warning("Knoten gelöscht.")
            st.rerun()

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("+ Pfad von hier", key=f"quick_path_from_{graph_id}_{node.get('id')}"):
        updated, target_id, edge_id = _graph_quick_add_path(graph, node.get("id"), "question")
        kb_json.upsert_decision_graph(updated)
        _set_selection(graph_id, "edge", edge_id)
        st.rerun()
    if c2.button("+ Ziel-Lösung", key=f"quick_solution_from_{graph_id}_{node.get('id')}"):
        updated, target_id, edge_id = _graph_quick_add_path(graph, node.get("id"), "solution")
        # Make label clearer for the new solution node.
        for n in updated.get("nodes", []):
            if n.get("id") == target_id:
                n["label"] = "Neue Lösung"
                n["solution_text"] = "Hier Lösungstext eintragen."
        kb_json.upsert_decision_graph(updated)
        _set_selection(graph_id, "node", target_id)
        st.rerun()


def _edge_properties_panel(graph: dict[str, Any], edge: dict[str, Any]) -> None:
    graph_id = graph.get("id")
    st.markdown('<div class="selection-pill">Verbindung ausgewählt</div>', unsafe_allow_html=True)
    st.markdown(f"**{edge.get('source')} → {edge.get('target')}**")
    st.caption(f"ID: {edge.get('id')}")
    node_ids = _graph_node_ids(graph)
    mode, fact, operator, value_or_raw = _condition_to_simple(edge.get("condition", {}))

    with st.form(f"edge_prop_form_{graph_id}_{edge.get('id')}"):
        old_id = str(edge.get("id"))
        edge_id = st.text_input("Edge-ID", value=old_id, key=f"edge_prop_id_{graph_id}_{old_id}")
        source = st.selectbox("Quelle", node_ids, index=node_ids.index(edge.get("source")) if edge.get("source") in node_ids else 0, key=f"edge_prop_source_{graph_id}_{old_id}")
        target = st.selectbox("Ziel", node_ids, index=node_ids.index(edge.get("target")) if edge.get("target") in node_ids else 0, key=f"edge_prop_target_{graph_id}_{old_id}")
        label = st.text_input("Pfad-Label", value=edge.get("label", ""), key=f"edge_prop_label_{graph_id}_{old_id}")
        priority = st.number_input("Priorität", min_value=0, step=1, value=int(edge.get("priority", 100)), key=f"edge_prop_priority_{graph_id}_{old_id}")
        condition_mode = st.radio("Bedingung", ["none", "simple", "json"], index=["none", "simple", "json"].index(mode), format_func=lambda x: {"none":"Keine Bedingung", "simple":"Einfache Bedingung", "json":"Erweiterte JSON-Bedingung"}[x], key=f"edge_prop_cond_mode_{graph_id}_{old_id}")
        cond_fact = fact
        cond_operator = operator if operator in EDGE_OPERATORS else "equals"
        cond_value = value_or_raw if mode == "simple" else ""
        raw_json = value_or_raw if mode == "json" else json.dumps(edge.get("condition", {}), ensure_ascii=False, indent=2)
        if condition_mode == "simple":
            cond_fact = st.text_input("Fakt/Feld", value=cond_fact, placeholder="z. B. topic, service, os, intent", key=f"edge_prop_fact_{graph_id}_{old_id}")
            cond_operator = st.selectbox("Operator", EDGE_OPERATORS, index=EDGE_OPERATORS.index(cond_operator), key=f"edge_prop_operator_{graph_id}_{old_id}")
            if cond_operator not in {"exists", "not_exists"}:
                cond_value = st.text_input("Wert", value=cond_value, placeholder="z. B. eduroam oder windows", key=f"edge_prop_value_{graph_id}_{old_id}")
        elif condition_mode == "json":
            raw_json = st.text_area("Condition JSON", value=raw_json, height=160, key=f"edge_prop_raw_{graph_id}_{old_id}")
        col1, col2 = st.columns(2)
        save = col1.form_submit_button("Verbindung speichern")
        delete = col2.form_submit_button("Verbindung löschen")

    if save:
        try:
            new_edge_id = _slugify(edge_id or f"{source}_to_{target}", "edge")
            condition = _build_condition(condition_mode, cond_fact, cond_operator, cond_value, raw_json)
            updated_edges = []
            replaced = False
            for e in graph.get("edges", []):
                if e.get("id") == old_id:
                    updated_edges.append({"id": new_edge_id, "source": source, "target": target, "label": label, "priority": int(priority), "condition": condition})
                    replaced = True
                else:
                    updated_edges.append(e)
            if not replaced:
                updated_edges.append({"id": new_edge_id, "source": source, "target": target, "label": label, "priority": int(priority), "condition": condition})
            updated_graph = dict(graph)
            updated_graph["edges"] = updated_edges
            kb_json.upsert_decision_graph(updated_graph)
            _set_selection(graph_id, "edge", new_edge_id)
            st.success("Verbindung gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(f"Verbindung konnte nicht gespeichert werden: {e}")

    if delete:
        kb_json.delete_graph_edge(graph_id, edge.get("id"))
        _set_selection(graph_id, None, None)
        st.warning("Verbindung gelöscht.")
        st.rerun()


def _empty_properties_panel(graph: dict[str, Any]) -> None:
    graph_id = graph.get("id")
    st.markdown('<div class="prop-title">Eigenschaften</div>', unsafe_allow_html=True)
    st.markdown('<div class="prop-muted">Wähle im Canvas einen Knoten oder Pfad aus. Alternativ kannst du über die Schnellaktionen neue Elemente erzeugen.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("+ Knoten", key=f"empty_add_node_{graph_id}"):
        updated = _graph_quick_add_node(graph, "question")
        kb_json.upsert_decision_graph(updated)
        _set_selection(graph_id, "node", updated["nodes"][-1]["id"])
        st.rerun()
    start_id = graph.get("start_node_id") or (graph.get("nodes", [{}])[0].get("id") if graph.get("nodes") else None)
    if c2.button("+ Pfad", key=f"empty_add_path_{graph_id}"):
        updated, target_id, edge_id = _graph_quick_add_path(graph, start_id, "question")
        kb_json.upsert_decision_graph(updated)
        _set_selection(graph_id, "edge", edge_id)
        st.rerun()


def render_graph_properties_panel(graph: dict[str, Any]) -> None:
    graph_id = graph.get("id")
    selected_type, selected_id = _current_selection(graph_id)

    # Manuelle Auswahl bleibt als Fallback vorhanden, aber kompakt im Eigenschaftenbereich.
    selection_options = ["Keine Auswahl"] + [f"node::{n}" for n in _graph_node_ids(graph)] + [f"edge::{e}" for e in _graph_edge_ids(graph)]
    current_value = "Keine Auswahl"
    if selected_type and selected_id:
        candidate = f"{selected_type}::{selected_id}"
        if candidate in selection_options:
            current_value = candidate
    manual_key = f"graph_manual_selection_{graph_id}"

    # Wenn die Auswahl gerade aus dem Canvas kam, muss der Selectbox-Wert
    # vor dem Erzeugen des Widgets synchronisiert werden. Sonst behält
    # Streamlit den alten Wert der Selectbox und überschreibt die Canvas-Auswahl.
    if st.session_state.pop(f"graph_canvas_selection_dirty_{graph_id}", False):
        st.session_state[manual_key] = current_value

    selected_raw = st.selectbox(
        "Auswahl",
        selection_options,
        index=selection_options.index(current_value),
        format_func=lambda x: "Keine Auswahl" if x == "Keine Auswahl" else ("Knoten: " + x.split("::",1)[1] if x.startswith("node::") else "Pfad: " + x.split("::",1)[1]),
        key=manual_key,
    )
    if selected_raw == "Keine Auswahl":
        selected_type, selected_id = None, None
        _set_selection(graph_id, None, None)
    else:
        selected_type, selected_id = selected_raw.split("::", 1)
        _set_selection(graph_id, selected_type, selected_id)

    if selected_type == "node":
        node = _find_node(graph, selected_id)
        if node:
            _node_properties_panel(graph, node)
        else:
            _empty_properties_panel(graph)
    elif selected_type == "edge":
        edge = _find_edge(graph, selected_id)
        if edge:
            _edge_properties_panel(graph, edge)
        else:
            _empty_properties_panel(graph)
    else:
        _empty_properties_panel(graph)


def _graph_toolbar(graph: dict[str, Any], flow_state: Any = None) -> None:
    graph_id = graph.get("id")
    selected_type, selected_id = _current_selection(graph_id)
    st.markdown('<div class="graph-toolbar">', unsafe_allow_html=True)
    cols = st.columns([1, 1, 1, 1, 1, 1.2])
    if cols[0].button("+ Knoten", key=f"toolbar_add_node_{graph_id}"):
        updated = _graph_quick_add_node(graph, "question", source_id=selected_id if selected_type == "node" else None)
        kb_json.upsert_decision_graph(updated)
        _set_selection(graph_id, "node", updated["nodes"][-1]["id"])
        st.rerun()
    if cols[1].button("+ Pfad", key=f"toolbar_add_path_{graph_id}"):
        source_id = selected_id if selected_type == "node" else graph.get("start_node_id")
        updated, target_id, edge_id = _graph_quick_add_path(graph, source_id, "question")
        kb_json.upsert_decision_graph(updated)
        _set_selection(graph_id, "edge", edge_id)
        st.rerun()
    if cols[2].button("Duplizieren", key=f"toolbar_duplicate_{graph_id}"):
        if selected_type == "node" and selected_id:
            source = _find_node(graph, selected_id)
            if source:
                updated = dict(graph)
                nodes = [dict(n) for n in graph.get("nodes", [])]
                new_node = dict(source)
                new_node["id"] = _unique_id({n.get("id") for n in nodes}, f"{source.get('id')}_copy")
                new_node["label"] = f"{source.get('label', source.get('id'))} Kopie"
                pos = dict(new_node.get("position", {})) if isinstance(new_node.get("position"), dict) else {"x": 0, "y": 0}
                new_node["position"] = {"x": int(pos.get("x", 0)) + 80, "y": int(pos.get("y", 0)) + 80}
                nodes.append(new_node)
                updated["nodes"] = nodes
                kb_json.upsert_decision_graph(updated)
                _set_selection(graph_id, "node", new_node["id"])
                st.rerun()
        elif selected_type == "edge" and selected_id:
            source_edge = _find_edge(graph, selected_id)
            if source_edge:
                updated = dict(graph)
                edges = [dict(e) for e in graph.get("edges", [])]
                new_edge = dict(source_edge)
                new_edge["id"] = _unique_id({e.get("id") for e in edges}, f"{source_edge.get('id')}_copy")
                new_edge["label"] = f"{source_edge.get('label', '')} Kopie".strip()
                edges.append(new_edge)
                updated["edges"] = edges
                kb_json.upsert_decision_graph(updated)
                _set_selection(graph_id, "edge", new_edge["id"])
                st.rerun()
        else:
            st.warning("Wähle zuerst einen Knoten oder Pfad aus.")
    if cols[3].button("Löschen", key=f"toolbar_delete_{graph_id}"):
        if selected_type == "node" and selected_id:
            if selected_id == graph.get("start_node_id"):
                st.error("Start-Knoten kann nicht gelöscht werden.")
            else:
                kb_json.delete_graph_node(graph_id, selected_id)
                _set_selection(graph_id, None, None)
                st.rerun()
        elif selected_type == "edge" and selected_id:
            kb_json.delete_graph_edge(graph_id, selected_id)
            _set_selection(graph_id, None, None)
            st.rerun()
    if cols[4].button("Auto-Layout", key=f"toolbar_auto_layout_{graph_id}"):
        kb_json.upsert_decision_graph(_auto_layout_graph(graph))
        st.rerun()
    if cols[5].button("Canvas speichern", key=f"toolbar_apply_canvas_{graph_id}"):
        if flow_state is None:
            st.info("Kein Canvas-State verfügbar.")
        else:
            try:
                updated = apply_flow_state_to_graph(graph, flow_state)
                kb_json.upsert_decision_graph(updated)
                st.success("Canvas-Änderungen gespeichert.")
                st.rerun()
            except Exception as e:
                st.error(f"Canvas konnte nicht gespeichert werden: {e}")
    st.markdown('</div>', unsafe_allow_html=True)


def _graph_meta_editor(selected_graph: dict[str, Any] | None) -> None:
    with st.expander("Graph-Stammdaten", expanded=selected_graph is None):
        with st.form("admin_graph_meta_form"):
            graph_id = st.text_input("Graph-ID", value="" if selected_graph is None else selected_graph.get("id", ""), key="admin_graph_id")
            name = st.text_input("Name", value="" if selected_graph is None else selected_graph.get("name", ""), key="admin_graph_name")
            description = st.text_area("Beschreibung", value="" if selected_graph is None else selected_graph.get("description", ""), key="admin_graph_description")
            start_node_id = st.text_input("Start-Knoten-ID", value="start" if selected_graph is None else selected_graph.get("start_node_id", "start"), key="admin_graph_start")
            active = st.checkbox("Aktiv", value=True if selected_graph is None else bool(selected_graph.get("active", True)), key="admin_graph_active")
            col_save, col_delete = st.columns(2)
            save_meta = col_save.form_submit_button("Graph speichern")
            delete_meta = col_delete.form_submit_button("Graph löschen")
        if save_meta:
            try:
                graph = selected_graph or {"nodes": [], "edges": []}
                graph = dict(graph)
                graph.update({"id": _slugify(graph_id, "graph"), "name": name, "description": description, "start_node_id": start_node_id.strip() or "start", "active": active})
                if not graph.get("nodes"):
                    graph["nodes"] = [{"id": "start", "type": "start", "label": "Start", "position": {"x": 0, "y": 0}}]
                kb_json.upsert_decision_graph(graph)
                st.success("Graph gespeichert.")
                st.rerun()
            except Exception as e:
                st.error(f"Speichern fehlgeschlagen: {e}")
        if delete_meta and selected_graph is not None:
            kb_json.delete_decision_graph(selected_graph.get("id"))
            st.warning("Graph gelöscht.")
            st.rerun()


def _graph_test_panel(graph: dict[str, Any]) -> None:
    with st.expander("Graph testen", expanded=False):
        sample = {"topic": "eduroam", "os": "windows", "intent": "login", "internet_available": True}
        facts_raw = st.text_area("Fakten als JSON", value=json.dumps(sample, ensure_ascii=False, indent=2), height=190, key=f"graph_test_facts_{graph.get('id')}")
        if st.button("Graph ausführen", key=f"graph_test_run_{graph.get('id')}"):
            try:
                facts = json.loads(facts_raw)
                result = decision_graph_engine.run_decision_graph(graph, facts)
                render_answer("Graph-Ausgabe", decision_graph_engine.render_summary(result))
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Pfad")
                    st.json(result.get("path", []))
                with col2:
                    st.subheader("Terminal / Status")
                    st.json({k: v for k, v in result.items() if k not in {"graph", "facts", "evaluated_edges", "path"}})
                with st.expander("Kanten-Trace"):
                    st.json(result.get("evaluated_edges", []))
            except Exception as e:
                st.error(f"Graph-Test fehlgeschlagen: {e}")


def _graph_json_panel(graph: dict[str, Any]) -> None:
    with st.expander("Graph-JSON anzeigen / bearbeiten", expanded=False):
        raw = st.text_area("Graph-JSON", value=json.dumps(graph, ensure_ascii=False, indent=2), height=520, key=f"admin_graph_json_raw_{graph.get('id')}")
        if st.button("Graph-JSON speichern", key=f"admin_graph_json_save_{graph.get('id')}"):
            try:
                parsed = json.loads(raw)
                kb_json.upsert_decision_graph(parsed)
                st.success("Graph-JSON gespeichert.")
                st.rerun()
            except Exception as e:
                st.error(f"Ungültiges Graph-JSON: {e}")


def admin_decision_graphs() -> None:
    st.header("Admin · Grafischer Entscheidungsnetz-Editor")
    render_view_info(
        "Grafischer Entscheidungsnetz-Editor",
        "Hier baust du Entscheidungswege als Knoten und Verbindungen. Klicke einen Knoten oder Pfad im Canvas an, bearbeite die Eigenschaften rechts und speichere anschließend. Die Struktur wird als JSON gespeichert und von der Rule Engine interpretiert.",
    )
    st.markdown("Wähle einen Graphen aus, klicke Knoten oder Pfade im Canvas an und bearbeite sie rechts im Eigenschaften-Panel. Gespeichert wird in `Rule Engine/decision_graphs.json`.")

    graphs = kb_json.load_decision_graphs(active_only=False)
    graph_options = [None] + graphs
    selected_graph = st.selectbox(
        "Entscheidungsnetz auswählen",
        graph_options,
        format_func=lambda g: "Neues Entscheidungsnetz anlegen" if g is None else f"{g.get('name')} ({g.get('id')})",
        key="admin_graph_select",
    )

    _graph_meta_editor(selected_graph)

    if selected_graph is None:
        st.info("Lege zuerst ein Entscheidungsnetz an oder wähle ein vorhandenes aus.")
        return

    graph = kb_json.get_decision_graph(selected_graph.get("id")) or selected_graph
    graph_id = graph.get("id")
    if f"graph_selected_type_{graph_id}" not in st.session_state:
        _set_selection(graph_id, "node", graph.get("start_node_id") or (graph.get("nodes", [{}])[0].get("id") if graph.get("nodes") else None))

    # Canvas links, Eigenschaften rechts.
    left, right = st.columns([2.15, 1], gap="large")

    with left:
        flow_state = render_graph_canvas_interactive(graph)
        _graph_toolbar(graph, flow_state)

    with right:
        st.markdown('<div class="prop-panel">', unsafe_allow_html=True)
        render_graph_properties_panel(graph)
        st.markdown('</div>', unsafe_allow_html=True)

    _graph_test_panel(kb_json.get_decision_graph(graph_id) or graph)
