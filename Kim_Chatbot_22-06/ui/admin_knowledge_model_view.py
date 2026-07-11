from __future__ import annotations

from typing import Any
import json

import streamlit as st

from storage import kb_loader as kb_json
from ui.common import render_view_info


def _edge_condition_hint(edge: dict[str, Any]) -> str:
    relation = edge.get("relation_type", "")
    color = edge.get("color_block", "")
    return " · ".join([x for x in [relation, color] if x])


def admin_knowledge_model() -> None:
    st.header("Admin · Wissensmodell")
    render_view_info(
        "Wissensmodell",
        "Diese Ansicht zeigt die aus den zwei Wissensmodell-Grafiken abgeleitete Gesamtlogik. "
        "Der graue gemeinsame Wissenskern wird als globale Bausteine genutzt; MFA, eduroam und VPN "
        "bauen darauf auf. Das Modell dient als Brücke zwischen fachlicher Darstellung und technischen Fact-Keys.",
    )

    model = kb_json.load_knowledge_model()
    stats = kb_json.knowledge_model_stats()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Namespaces", stats.get("namespaces", 0))
    c2.metric("Knoten", stats.get("nodes", 0))
    c3.metric("Verbindungen", stats.get("edges", 0))
    c4.metric("verknüpfte globale Bausteine", stats.get("global_blocks", 0))

    st.subheader(model.get("name", "Wissensmodell"))
    st.write(model.get("description", ""))

    tab_blocks, tab_nodes, tab_edges, tab_graph, tab_json = st.tabs([
        "Farbblöcke & Namespaces",
        "Knoten / Facts",
        "Verbindungen",
        "Graph-Vorschau",
        "JSON",
    ])

    with tab_blocks:
        st.markdown("### Farbblöcke")
        st.table([
            {"ID": b.get("id"), "Name": b.get("name"), "Bedeutung": b.get("meaning")}
            for b in model.get("color_blocks", []) or []
        ])
        st.markdown("### Namespaces")
        st.table([
            {"ID": n.get("id"), "Label": n.get("label"), "Beschreibung": n.get("description")}
            for n in model.get("namespaces", []) or []
        ])

    with tab_nodes:
        rows = []
        for node in model.get("nodes", []) or []:
            rows.append({
                "ID": node.get("id"),
                "Namespace": node.get("namespace"),
                "Label": node.get("label"),
                "Fact-Keys": ", ".join(node.get("fact_keys", []) or []),
                "Globaler Baustein": node.get("global_block", ""),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

    with tab_edges:
        rows = []
        for edge in model.get("edges", []) or []:
            rows.append({
                "ID": edge.get("id"),
                "Quelle": edge.get("source"),
                "Ziel": edge.get("target"),
                "Label": edge.get("label"),
                "Typ": _edge_condition_hint(edge),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

    with tab_graph:
        st.caption("Vereinfachte Graphviz-Vorschau des Wissensmodells. Die ausführliche Bearbeitung erfolgt weiterhin im Entscheidungsnetz-Editor.")
        dot_lines = ["digraph G {", "rankdir=LR;", "node [shape=box, style=rounded, fontsize=10];"]
        ns_colors = {
            "core": "#F3F4F6",
            "service.mfa": "#FFF7ED",
            "service.eduroam": "#EFF6FF",
            "service.vpn": "#ECFDF5",
            "service.support": "#FEF2F2",
        }
        for node in model.get("nodes", []) or []:
            node_id = str(node.get("id"))
            label = str(node.get("label", node_id)).replace('"', "'")
            fill = ns_colors.get(str(node.get("namespace")), "#FFFFFF")
            dot_lines.append(f'"{node_id}" [label="{label}", fillcolor="{fill}", style="rounded,filled"];')
        for edge in model.get("edges", []) or []:
            src = edge.get("source")
            tgt = edge.get("target")
            label = str(edge.get("label", "")).replace('"', "'")
            dot_lines.append(f'"{src}" -> "{tgt}" [label="{label}"];')
        dot_lines.append("}")
        st.graphviz_chart("\n".join(dot_lines), use_container_width=True)

    with tab_json:
        st.json(model)
        st.download_button(
            "Wissensmodell herunterladen",
            data=json.dumps(model, ensure_ascii=False, indent=2),
            file_name="wissensmodell_gesamtprojekt.json",
            mime="application/json",
        )
