from __future__ import annotations

import json
import re
from typing import Any

import streamlit as st

from storage import kb_loader as kb_json
from core import inference_engine

from ui.common import (
    select_service,
    select_system,
    select_step,
    split_lines,
    render_step_card,
    render_view_info,
)

def admin_services_systems() -> None:
    st.header("Admin · Wissensbereiche")
    render_view_info(
        "Wissensbereiche",
        "Hier pflegst du die fachlichen Wissensbereiche der Rule Engine. Core, Eduroam, VPN und MFA sind Wissensbereiche mit eigenen Conditions/Facts, Funktionen, Regeln und Schrittpaketen.",
    )
    tab_service, tab_system = st.tabs(["Wissensbereich bearbeiten", "System / Unterbereich bearbeiten"])

    with tab_service:
        services = kb_json.get_services(active_only=False)
        options = [None] + services
        selected = st.selectbox("Bestehenden Wissensbereich auswählen", options, format_func=lambda s: "Neuen Wissensbereich anlegen" if s is None else f"{s.get('name')} ({s.get('key')})", key="admin_service_select")
        selected_service_key = "new" if selected is None else str(selected.get("key", "new"))
        if selected is not None:
            st.caption(f"Aktuell ausgewählt: {selected.get('name')} ({selected.get('key')})")
        with st.form(f"admin_service_form_{selected_service_key}"):
            key = st.text_input("Technischer Wissensbereich-Key", value="" if selected is None else selected.get("key", ""), key=f"admin_service_key_{selected_service_key}")
            name = st.text_input("Anzeigename", value="" if selected is None else selected.get("name", ""), key=f"admin_service_name_{selected_service_key}")
            desc = st.text_area("Beschreibung / Inhalt", value="" if selected is None else selected.get("description", ""), key=f"admin_service_desc_{selected_service_key}")
            global_blocks = kb_json.load_global_blocks(active_only=False)
            block_ids = [b.get("id") for b in global_blocks if b.get("id")]
            required_blocks = st.multiselect(
                "Verknüpfte Conditions/Facts",
                block_ids,
                default=[] if selected is None else [x for x in selected.get("required_global_blocks", []) if x in block_ids],
                key=f"admin_service_global_blocks_{selected_service_key}",
            )
            active = st.checkbox("Aktiv", value=True if selected is None else bool(selected.get("active", True)), key=f"admin_service_active_{selected_service_key}")
            if st.form_submit_button("Wissensbereich speichern"):
                if not key.strip() or not name.strip():
                    st.error("Key und Anzeigename sind Pflichtfelder.")
                else:
                    kb_json.upsert_service({"key": key, "name": name, "description": desc, "active": active, "required_global_blocks": required_blocks})
                    st.success("Wissensbereich gespeichert.")
                    st.rerun()

    with tab_system:
        service = select_service("admin_system_service_select", active_only=False)
        if service:
            systems = kb_json.get_systems(service.get("key"), active_only=False)
            options = [None] + systems
            selected = st.selectbox("Bestehendes System auswählen", options, format_func=lambda s: "Neues System anlegen" if s is None else f"{s.get('name')} ({s.get('key')})", key=f"admin_system_select_{service.get('key')}")
            selected_system_key = "new" if selected is None else str(selected.get("key", "new"))
            form_suffix = f"{service.get('key')}_{selected_system_key}"
            if selected is not None:
                st.caption(f"Aktuell ausgewählt: {selected.get('name')} ({selected.get('key')})")
            with st.form(f"admin_system_form_{form_suffix}"):
                key = st.text_input("System-Key", value="" if selected is None else selected.get("key", ""), key=f"admin_system_key_{form_suffix}")
                name = st.text_input("System-Anzeigename", value="" if selected is None else selected.get("name", ""), key=f"admin_system_name_{form_suffix}")
                prerequisite = st.text_area("Voraussetzung", value="" if selected is None else selected.get("prerequisite", ""), key=f"admin_system_prereq_{form_suffix}")
                guide_url = st.text_input("Anleitungs-URL", value="" if selected is None else selected.get("guide_url", ""), key=f"admin_system_url_{form_suffix}")
                active = st.checkbox("Aktiv", value=True if selected is None else bool(selected.get("active", True)), key=f"admin_system_active_{form_suffix}")
                if st.form_submit_button("System speichern"):
                    if not key.strip() or not name.strip():
                        st.error("Key und Anzeigename sind Pflichtfelder.")
                    else:
                        kb_json.upsert_system(service.get("key"), {"key": key, "name": name, "prerequisite": prerequisite, "guide_url": guide_url, "active": active})
                        st.success("System gespeichert.")
                        st.rerun()
