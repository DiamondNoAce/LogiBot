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

def admin_inference_rules() -> None:
    st.header("Admin · Inferenzregeln")
    render_view_info(
        "Inferenzregeln",
        "Hier werden Wenn-Dann-Regeln gepflegt. Die Regeln werten erkannte Fakten aus, setzen neue Fakten oder erzeugen Antworten. Das eignet sich für allgemeine Schlussfolgerungen vor oder neben dem Entscheidungsnetz.",
    )
    rules = kb_json.load_inference_rules(active_only=False)
    options = [None] + rules
    selected = st.selectbox("Regel auswählen", options, format_func=lambda r: "Neue Regel anlegen" if r is None else f"{r.get('id')} · {r.get('description','')}", key="admin_rule_select")
    selected_rule_key = "new" if selected is None else re.sub(r"[^a-zA-Z0-9_-]", "_", str(selected.get("id", "new")))
    if selected is not None:
        st.caption(f"Aktuell ausgewählt: {selected.get('id')} · {selected.get('description','')}")
    with st.form(f"admin_rule_form_{selected_rule_key}"):
        rid = st.text_input("Regel-ID", value="" if selected is None else selected.get("id", ""), key=f"admin_rule_id_{selected_rule_key}")
        module = st.text_input("Modul", value="general" if selected is None else selected.get("module", "general"), key=f"admin_rule_module_{selected_rule_key}")
        group = st.text_input("Regelgruppe", value="general" if selected is None else selected.get("rule_group", "general"), key=f"admin_rule_group_{selected_rule_key}")
        description = st.text_area("Beschreibung", value="" if selected is None else selected.get("description", ""), key=f"admin_rule_desc_{selected_rule_key}")
        priority = st.number_input("Priorität", min_value=0, step=1, value=100 if selected is None else int(selected.get("priority", 100)), key=f"admin_rule_priority_{selected_rule_key}")
        active = st.checkbox("Aktiv", value=True if selected is None else bool(selected.get("active", True)), key=f"admin_rule_active_{selected_rule_key}")
        stop = st.checkbox("Nach Treffer stoppen", value=False if selected is None else bool(selected.get("stop_after_match", False)), key=f"admin_rule_stop_{selected_rule_key}")
        when_raw = st.text_area("WHEN als JSON", value=json.dumps({"all": [], "any": []} if selected is None else selected.get("when", {}), ensure_ascii=False, indent=2), height=220, key=f"admin_rule_when_{selected_rule_key}")
        then_raw = st.text_area("THEN als JSON-Liste", value=json.dumps([] if selected is None else selected.get("then", []), ensure_ascii=False, indent=2), height=220, key=f"admin_rule_then_{selected_rule_key}")
        col_save, col_delete = st.columns(2)
        save_clicked = col_save.form_submit_button("Regel speichern")
        delete_clicked = col_delete.form_submit_button("Regel löschen")

    if save_clicked:
        try:
            rule = {
                "id": rid,
                "module": module,
                "rule_group": group,
                "description": description,
                "priority": int(priority),
                "active": active,
                "stop_after_match": stop,
                "when": json.loads(when_raw),
                "then": json.loads(then_raw),
            }
            kb_json.upsert_inference_rule(rule)
            st.success("Regel gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(f"Regel konnte nicht gespeichert werden: {e}")

    if delete_clicked and selected is not None:
        kb_json.delete_inference_rule(selected.get("id"))
        st.warning("Regel gelöscht.")
        st.rerun()


    with st.expander("Operatoren und technische Condition-Struktur"):
        st.markdown("""
        Die Inferenzregeln unterstützen jetzt die Condition-Struktur aus der technischen Eduroam-Excel:
        - `when.all`: alle Bedingungen müssen passen
        - `when.any`: mindestens eine Bedingung muss passen
        - `when.not`: diese Bedingungen dürfen nicht passen
        - `technical_metadata`: enthält Pre-, Trigger- und Post-Conditions aus der Excel-Übersetzung

        Unterstützte Operatoren: `equals`, `not_equals`, `in`, `not_in`, `contains`, `contains_any`,
        `contains_all`, `starts_with`, `ends_with`, `regex`, `is_unknown`, `is_known`, `is_true`,
        `is_false`, `greater_than`, `less_than`, `greater_or_equal`, `less_or_equal`.
        """)

    with st.expander("Regel-Beispiel"):
        st.code(json.dumps({
            "when": {"all": [{"fact": "topic", "operator": "equals", "value": "eduroam"}], "any": [{"fact": "os", "operator": "equals", "value": "windows"}]},
            "then": [{"type": "answer", "text": "Beispielantwort"}],
        }, ensure_ascii=False, indent=2), language="json")

def admin_inference_test() -> None:
    st.header("Admin · Inferenz-Test")
    render_view_info(
        "Inferenz-Test",
        "Hier testest du die Inferenzregeln mit manuell eingegebenen Fakten. So kannst du prüfen, welche Regeln matchen, welche Antworten erzeugt werden und ob der Regeltrace plausibel ist.",
    )
    facts_raw = st.text_area("Fakten als JSON", value=json.dumps({"topic": "eduroam", "intent": "setup", "os": "windows", "internet_available": False}, ensure_ascii=False, indent=2), height=250, key="admin_test_facts")
    if st.button("Test ausführen", key="admin_test_run"):
        try:
            facts = json.loads(facts_raw)
            result = inference_engine.run_inference(facts)
            st.subheader("Ausgabe")
            st.write(inference_engine.renderable_summary(result))
            st.subheader("Gematchte Regeln")
            st.json(result.get("matched_rules", []))
            with st.expander("Trace"):
                st.json(result.get("evaluated_rules", []))
        except Exception as e:
            st.error(f"Test fehlgeschlagen: {e}")
