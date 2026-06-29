from __future__ import annotations

import json
from typing import Any

import streamlit as st

from storage import kb_loader as kb_json
from ui.common import render_view_info


def _render_flow_step(row: dict[str, Any]) -> None:
    st.markdown(
        f"""
        <div class="step-card">
            <div class="step-number">{row.get('step')}</div>
            <div>
                <div class="step-title">{row.get('condition', '')}</div>
                <div class="step-phase">Regel: <code>{row.get('rule_id', '')}</code> · Ziel: {row.get('post_condition', '')}</div>
                <div class="step-text"><b>Wenn erfüllt:</b> {row.get('if_true', '')}<br><b>Wenn nicht erfüllt / unknown:</b> {row.get('if_false_unknown', '')}<br><b>Notiz:</b> {row.get('note', '')}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def admin_flows() -> None:
    st.header("Admin · Abläufe")
    render_view_info(
        "Abläufe",
        "Diese Ansicht zeigt die Regelketten lesbar vor dem grafischen Entscheidungsnetz. Admins sehen hier, in welcher Reihenfolge Conditions geprüft werden und welche Regel bzw. Funktion als nächstes ausgelöst wird.",
    )

    flows = kb_json.load_flow_catalog(active_only=False)
    if not flows:
        st.warning("Keine Abläufe vorhanden.")
        return

    selected = st.selectbox(
        "Ablauf auswählen",
        flows,
        format_func=lambda f: f"{f.get('name', f.get('id'))} ({f.get('id')})",
        key="flow_select",
    )
    st.write(selected.get("description", ""))

    steps = selected.get("steps", []) or []
    st.subheader("Lesbare Regelkette")
    for row in steps:
        _render_flow_step(row)

    st.subheader("Tabellarische Ablaufansicht")
    st.dataframe(
        [
            {
                "Schritt": x.get("step"),
                "Prüfung / Condition": x.get("condition"),
                "Wenn erfüllt": x.get("if_true"),
                "Wenn nicht erfüllt / unknown": x.get("if_false_unknown"),
                "Regel": x.get("rule_id"),
                "Ziel / Post-Condition": x.get("post_condition"),
                "Notiz": x.get("note"),
            }
            for x in steps
        ],
        use_container_width=True,
        hide_index=True,
    )

    c1, c2 = st.columns(2)
    if c1.button("Zum grafischen Entscheidungsnetz wechseln", key="flow_to_graph"):
        st.session_state["active_view"] = "Admin: Entscheidungsnetz"
        st.session_state["sidebar_view"] = "Admin: Entscheidungsnetz"
        st.rerun()
    if c2.button("Zur Regelverwaltung wechseln", key="flow_to_rules"):
        st.session_state["active_view"] = "Admin: Regelverwaltung"
        st.session_state["sidebar_view"] = "Admin: Regelverwaltung"
        st.rerun()

    with st.expander("Technische JSON-Vorschau"):
        st.json(selected)
