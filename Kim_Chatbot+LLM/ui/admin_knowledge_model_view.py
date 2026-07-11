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

    tab_blocks, tab_nodes, tab_edges, tab_refs, tab_graph, tab_json = st.tabs([
        "Farbblöcke & Namespaces",
        "Knoten / Facts",
        "Verbindungen",
        "Referenz & Navigation",
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

    with tab_refs:
        st.markdown("### Knoten als Navigationspunkt")
        st.caption("Wähle einen Wissensmodell-Knoten aus. Die Ansicht zeigt verknüpfte Conditions, Regeln und Funktionen und bietet direkte Sprungmarken in die Pflegeansichten.")
        nodes = model.get("nodes", []) or []
        if not nodes:
            st.info("Keine Knoten im Wissensmodell vorhanden.")
        else:
            selected_node = st.selectbox(
                "Knoten auswählen",
                nodes,
                format_func=lambda n: f"{n.get('label', n.get('id'))} ({n.get('id')})",
                key="knowledge_model_node_ref_select",
            )
            fact_keys = selected_node.get("fact_keys", []) or []
            st.write(f"**Namespace:** {selected_node.get('namespace', '')}")
            st.write(f"**Beschreibung:** {selected_node.get('description', '')}")
            st.write("**Verwendete Conditions / Facts:**")
            if fact_keys:
                st.write(", ".join(f"`{x}`" for x in fact_keys))
            else:
                st.info("Für diesen Knoten sind keine Fact-Keys hinterlegt.")

            rule_hits = []
            for fact in fact_keys:
                rule_hits.extend(kb_json.rules_using_condition(fact))
            # Duplikate entfernen
            seen = set()
            rule_hits_unique = []
            for item in rule_hits:
                rid = item.get("id")
                if rid not in seen:
                    seen.add(rid)
                    rule_hits_unique.append(item)

            function_hits = []
            functions = kb_json.load_function_catalog(active_only=False)
            for func in functions:
                blob = json.dumps(func, ensure_ascii=False).lower()
                if any(str(f).lower() in blob for f in fact_keys):
                    function_hits.append({
                        "id": func.get("id"),
                        "display_name": func.get("display_name"),
                        "type": func.get("function_type"),
                        "knowledge_area": func.get("knowledge_area"),
                    })

            st.markdown("#### Verwendete Regeln")
            if rule_hits_unique:
                st.dataframe(rule_hits_unique, use_container_width=True, hide_index=True)
            else:
                st.info("Keine direkt verknüpften Regeln gefunden.")

            st.markdown("#### Verwendete Funktionen")
            if function_hits:
                st.dataframe(function_hits, use_container_width=True, hide_index=True)
            else:
                st.info("Keine direkt verknüpften Funktionen gefunden.")

            c1, c2, c3 = st.columns(3)
            if c1.button("Condition anzeigen", key="km_go_conditions"):
                st.session_state["active_view"] = "Admin: Conditions / Facts"
                st.session_state["sidebar_view"] = "Admin: Conditions / Facts"
                st.rerun()
            if c2.button("Regel öffnen", key="km_go_rules"):
                st.session_state["active_view"] = "Admin: Regelverwaltung"
                st.session_state["sidebar_view"] = "Admin: Regelverwaltung"
                st.rerun()
            if c3.button("Funktion bearbeiten", key="km_go_functions"):
                st.session_state["active_view"] = "Admin: Funktionen & Antworten"
                st.session_state["sidebar_view"] = "Admin: Funktionen & Antworten"
                st.rerun()

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
