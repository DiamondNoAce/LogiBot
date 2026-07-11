from __future__ import annotations

from typing import Any

import streamlit as st

from storage import kb_loader as kb_json
from ui.common import render_view_title


def _render_flow_step(row: dict[str, Any]) -> None:
    st.markdown(
        f"""
        <div class="step-card">
            <div class="step-number">{row.get('step')}</div>
            <div>
                <div class="step-title">{row.get('condition', '')}</div>
                <div class="step-phase">Regel: <code>{row.get('rule_id', '')}</code> · Action: <code>{row.get('action', '')}</code></div>
                <div class="step-text">
                    <b>Wenn erfüllt:</b> {row.get('if_true', '')}<br>
                    <b>Wenn nicht erfüllt / unknown:</b> {row.get('if_false_unknown', '')}<br>
                    <b>Post-Condition:</b> {row.get('post_condition', '')}<br>
                    <b>Notiz:</b> {row.get('note', '')}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def admin_flows() -> None:
    render_view_title(
        "Admin · Abläufe & Netz",
        "Abläufe & Netz",
        "Diese Ansicht zeigt zuerst eine lesbare Regelkette und verweist danach auf das grafische Entscheidungsnetz. "
        "So können Admins den Ablauf prüfen, bevor sie den Graph bearbeiten.",
    )

    flows = kb_json.load_flow_catalog(active_only=False)
    if not flows:
        st.warning("Keine Abläufe vorhanden.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Abläufe", len(flows))
    c2.metric("aktive Abläufe", len([f for f in flows if f.get("active", True)]))
    c3.metric("Regelschritte", sum(len(f.get("steps", []) or []) for f in flows))

    selected = st.selectbox(
        "Ablauf auswählen",
        flows,
        format_func=lambda f: f"{f.get('name', f.get('id'))} ({f.get('id')})",
        key="flow_select",
    )
    st.write(selected.get("description", ""))

    steps = selected.get("steps", []) or []
    tab_chain, tab_table, tab_graph_link, tab_json = st.tabs([
        "Lesbare Regelkette",
        "Tabelle",
        "Grafisches Netz",
        "Technische Vorschau",
    ])

    with tab_chain:
        if not steps:
            st.info("Dieser Ablauf enthält noch keine Schritte.")
        for row in steps:
            _render_flow_step(row)

    with tab_table:
        st.dataframe(
            [
                {
                    "Schritt": x.get("step"),
                    "Prüfung / Condition": x.get("condition"),
                    "Action": x.get("action"),
                    "Wenn erfüllt": x.get("if_true"),
                    "Wenn nicht erfüllt / unknown": x.get("if_false_unknown"),
                    "Regel": x.get("rule_id"),
                    "Post-Condition": x.get("post_condition"),
                    "Notiz": x.get("note"),
                }
                for x in steps
            ],
            use_container_width=True,
            hide_index=True,
        )

    with tab_graph_link:
        st.info(
            "Der grafische Editor bleibt erhalten, ist aber nicht mehr der erste Einstieg. "
            "Öffne ihn erst, nachdem die Regelkette fachlich plausibel ist."
        )
        c1, c2 = st.columns(2)
        if c1.button("Zum grafischen Entscheidungsnetz wechseln", key="flow_to_graph"):
            st.session_state["pending_view"] = "Admin: Entscheidungsnetz"
            st.rerun()
        if c2.button("Zur Regelverwaltung wechseln", key="flow_to_rules"):
            st.session_state["pending_view"] = "Admin: Regelverwaltung"
            st.rerun()

    with tab_json:
        st.caption("Technische JSON-Vorschau des ausgewählten Ablaufs.")
        st.json(selected)
