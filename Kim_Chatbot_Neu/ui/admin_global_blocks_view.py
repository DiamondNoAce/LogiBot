from __future__ import annotations

import json
import re
from typing import Any

import streamlit as st

from storage import kb_loader as kb_json
from ui.common import render_view_info


def _safe_key(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(value or "new"))


def admin_global_blocks() -> None:
    st.header("Admin · Globale Bausteine")
    render_view_info(
        "Globale Bausteine",
        "Hier pflegst du dienstübergreifende Themen wie Benutzerkonto, Internetverbindung, Betriebssystem, MFA oder Campusnetz/VPN. Dienste können diese Bausteine wiederverwenden, statt dieselben Fragen und Regeln mehrfach zu speichern.",
    )

    blocks = kb_json.load_global_blocks(active_only=False)
    services = kb_json.get_services(active_only=False)

    tab_blocks, tab_usage, tab_preview = st.tabs([
        "Bausteine bearbeiten",
        "Diensten zuordnen",
        "Vorschau / JSON",
    ])

    with tab_blocks:
        options = [None] + blocks
        selected = st.selectbox(
            "Globalen Baustein auswählen",
            options,
            format_func=lambda b: "Neuen Baustein anlegen" if b is None else f"{b.get('name')} ({b.get('id')})",
            key="admin_global_block_select",
        )
        suffix = _safe_key("new" if selected is None else selected.get("id", "new"))
        with st.form(f"admin_global_block_form_{suffix}"):
            block_id = st.text_input("Baustein-ID", value="" if selected is None else selected.get("id", ""), key=f"global_block_id_{suffix}")
            name = st.text_input("Name", value="" if selected is None else selected.get("name", ""), key=f"global_block_name_{suffix}")
            description = st.text_area("Beschreibung", value="" if selected is None else selected.get("description", ""), key=f"global_block_desc_{suffix}")
            priority = st.number_input("Priorität", min_value=0, step=1, value=100 if selected is None else int(selected.get("priority", 100)), key=f"global_block_priority_{suffix}")
            active = st.checkbox("Aktiv", value=True if selected is None else bool(selected.get("active", True)), key=f"global_block_active_{suffix}")
            facts_raw = st.text_area(
                "Fakten als JSON-Liste",
                value=json.dumps([] if selected is None else selected.get("facts", []), ensure_ascii=False, indent=2),
                height=220,
                key=f"global_block_facts_{suffix}",
            )
            rules_raw = st.text_area(
                "Regeln als JSON-Liste",
                value=json.dumps([] if selected is None else selected.get("rules", []), ensure_ascii=False, indent=2),
                height=260,
                key=f"global_block_rules_{suffix}",
            )
            col_save, col_delete = st.columns(2)
            save_clicked = col_save.form_submit_button("Baustein speichern")
            delete_clicked = col_delete.form_submit_button("Baustein löschen")

        if save_clicked:
            try:
                block = {
                    "id": block_id.strip(),
                    "name": name.strip(),
                    "description": description.strip(),
                    "active": bool(active),
                    "scope": "global",
                    "priority": int(priority),
                    "facts": json.loads(facts_raw or "[]"),
                    "rules": json.loads(rules_raw or "[]"),
                }
                kb_json.upsert_global_block(block)
                st.success("Globaler Baustein gespeichert.")
                st.rerun()
            except Exception as e:
                st.error(f"Baustein konnte nicht gespeichert werden: {e}")

        if delete_clicked and selected is not None:
            kb_json.delete_global_block(str(selected.get("id")))
            st.warning("Globaler Baustein gelöscht.")
            st.rerun()

        with st.expander("Beispiel für einen Fakt"):
            st.code(json.dumps({
                "key": "account_activated",
                "type": "boolean",
                "question": "Ist dein Hohenheimer Benutzerkonto bereits aktiviert?"
            }, ensure_ascii=False, indent=2), language="json")

        with st.expander("Beispiel für eine globale Regel"):
            st.code(json.dumps({
                "id": "global.account.not_activated",
                "active": True,
                "priority": 20,
                "conditions": {"all": [{"fact": "account_activated", "operator": "equals", "value": False}]},
                "result": [{"type": "answer", "text": "Aktiviere zuerst dein Benutzerkonto."}],
                "stop_after_match": True,
            }, ensure_ascii=False, indent=2), language="json")

    with tab_usage:
        st.markdown("### Dienst nutzt globale Bausteine")
        st.caption("Wähle pro Dienst aus, welche globalen Bausteine im Inferenzlauf als Pflichtbausteine gelten sollen.")
        if not services:
            st.info("Es sind noch keine Dienste vorhanden.")
        else:
            service = st.selectbox(
                "Dienst auswählen",
                services,
                format_func=lambda s: f"{s.get('name')} ({s.get('key')})",
                key="admin_global_usage_service",
            )
            available_ids = [b.get("id") for b in blocks if b.get("id")]
            current = service.get("required_global_blocks", []) or []
            selected_ids = st.multiselect(
                "Benötigte globale Bausteine",
                available_ids,
                default=[x for x in current if x in available_ids],
                key=f"admin_global_usage_multiselect_{service.get('key')}",
            )
            if st.button("Zuordnung speichern", key=f"admin_global_usage_save_{service.get('key')}"):
                updated = dict(service)
                updated["required_global_blocks"] = selected_ids
                kb_json.upsert_service(updated)
                st.success("Zuordnung gespeichert.")
                st.rerun()

            st.markdown("#### Aktive Bausteine für diesen Dienst")
            for block_id in selected_ids:
                block = kb_json.get_global_block(block_id) or {"id": block_id}
                st.markdown(f"- **{block.get('name', block_id)}** (`{block_id}`)")

    with tab_preview:
        st.markdown("### Geladene globale Bausteine")
        st.json({"global_blocks": blocks})
        st.markdown("### Aus globalen Bausteinen erzeugte Inferenzregeln")
        st.json(kb_json.load_global_inference_rules(active_only=False))
