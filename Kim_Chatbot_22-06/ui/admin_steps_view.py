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

def admin_steps_solutions() -> None:
    st.header("Admin · Schritte & Lösungen")
    render_view_info(
        "Schritte & Lösungen",
        "Hier pflegst du die konkreten Anleitungsschritte und die dazugehörigen Hilfen. Diese Einträge sind die Grundlage dafür, dass Nutzer bei einem erkannten Problem eine passende Empfehlung erhalten.",
    )
    service = select_service("admin_steps_service", active_only=False)
    if not service:
        return
    system = select_system(service.get("key"), "admin_steps_system", active_only=False)
    if not system:
        return

    steps = kb_json.get_steps(service.get("key"), system.get("key"), active_only=False)
    options = [None] + steps
    selected = st.selectbox("Schritt auswählen", options, format_func=lambda s: "Neuen Schritt anlegen" if s is None else f"{s.get('number')} · {s.get('title')}", key=f"admin_step_select_{service.get('key')}_{system.get('key')}")
    selected_step_key = "new" if selected is None else str(selected.get("number", "new"))
    form_suffix = f"{service.get('key')}_{system.get('key')}_{selected_step_key}"
    if selected is not None:
        st.caption(f"Aktuell ausgewählt: Schritt {selected.get('number')} · {selected.get('title')}")

    with st.form(f"admin_step_form_{form_suffix}"):
        number = st.number_input("Schrittnummer", min_value=1, step=1, value=1 if selected is None else int(selected.get("number", 1)), key=f"admin_step_number_{form_suffix}")
        phase = st.text_input("Phase / Intent", value="" if selected is None else selected.get("phase", ""), key=f"admin_step_phase_{form_suffix}")
        title = st.text_input("Titel", value="" if selected is None else selected.get("title", ""), key=f"admin_step_title_{form_suffix}")
        instruction = st.text_area("Anleitungstext", value="" if selected is None else selected.get("instruction", ""), key=f"admin_step_instruction_{form_suffix}")
        keywords = st.text_area("Keywords / Synonyme, ein Begriff pro Zeile", value="" if selected is None else "\n".join(selected.get("keywords", [])), key=f"admin_step_keywords_{form_suffix}")
        active = st.checkbox("Aktiv", value=True if selected is None else bool(selected.get("active", True)), key=f"admin_step_active_{form_suffix}")
        st.markdown("**Lösung zum Schritt**")
        sol = {} if selected is None else selected.get("solution", {}) or {}
        problem_title = st.text_input("Problemtyp/Titel", value=sol.get("problem_title", ""), key=f"admin_solution_title_{form_suffix}")
        summary = st.text_area("Kurzbeschreibung", value=sol.get("summary", ""), key=f"admin_solution_summary_{form_suffix}")
        actions = st.text_area("Aktionen, eine Aktion pro Zeile", value="\n".join(sol.get("actions", [])), key=f"admin_solution_actions_{form_suffix}")
        rules_json = st.text_area("Optionale Schritt-Regeln als JSON-Liste", value=json.dumps([] if selected is None else selected.get("rules", []), ensure_ascii=False, indent=2), height=150, key=f"admin_step_rules_{form_suffix}")
        col_save, col_delete = st.columns(2)
        save_clicked = col_save.form_submit_button("Schritt speichern")
        delete_clicked = col_delete.form_submit_button("Schritt löschen")

    if save_clicked:
        try:
            rules = json.loads(rules_json) if rules_json.strip() else []
            step = {
                "number": int(number),
                "phase": phase,
                "title": title,
                "instruction": instruction,
                "keywords": split_lines(keywords),
                "active": active,
                "solution": {"problem_title": problem_title, "summary": summary, "actions": split_lines(actions)},
                "rules": rules,
            }
            kb_json.upsert_step(service.get("key"), system.get("key"), step)
            st.success("Schritt gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(f"Speichern fehlgeschlagen: {e}")

    if delete_clicked and selected is not None:
        kb_json.delete_step(service.get("key"), system.get("key"), int(selected.get("number")))
        st.warning("Schritt gelöscht.")
        st.rerun()

    st.subheader("Aktuelle Schritte")
    for step in kb_json.get_steps(service.get("key"), system.get("key"), active_only=False):
        render_step_card(step)
