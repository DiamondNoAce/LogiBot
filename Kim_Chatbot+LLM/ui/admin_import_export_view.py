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

def admin_json_files() -> None:
    st.header("Admin · JSON-Dateien")
    render_view_info(
        "JSON-Dateien",
        "Diese Ansicht ist für technische Kontrolle gedacht. Hier kannst du die Dateien aus dem austauschbaren Rule-Engine-Ordner direkt ansehen, herunterladen oder bearbeiten. Aggregierte Einträge wie inference_rules werden aus den Unterordnern rules/, sources/ und step_packages/ zusammengeführt.",
    )
    extra_files = ["condition_catalog", "functions_catalog", "flow_catalog", "excel_rule_overview", "excel_translation_matrix", "excel_priorities"]
    file_options = list(kb_json.FILES.keys()) + extra_files
    file_name = st.selectbox("Datei", file_options, key="admin_json_file_select")
    if file_name == "condition_catalog":
        data = {"conditions": kb_json.load_condition_catalog(active_only=False)}
    elif file_name == "functions_catalog":
        data = {"functions": kb_json.load_function_catalog(active_only=False)}
    elif file_name == "flow_catalog":
        data = {"flows": kb_json.load_flow_catalog(active_only=False)}
    elif file_name == "excel_rule_overview":
        data = {"items": kb_json.load_technical_excel_rule_overview()}
    elif file_name == "excel_translation_matrix":
        data = {"items": kb_json.load_technical_excel_translation_matrix()}
    elif file_name == "excel_priorities":
        data = {"items": kb_json.load_technical_excel_priorities()}
    else:
        data = kb_json.load_json(file_name, [] if file_name in {"inference_rules", "step_packages", "sources"} else {})
    raw = st.text_area("JSON-Inhalt", value=json.dumps(data, ensure_ascii=False, indent=2), height=520, key=f"admin_json_raw_{file_name}")
    col1, col2 = st.columns(2)
    if col1.button("JSON speichern", key=f"admin_json_save_{file_name}"):
        try:
            parsed = json.loads(raw)
            if file_name == "condition_catalog":
                kb_json.save_condition_catalog(parsed.get("conditions", []) if isinstance(parsed, dict) else parsed)
            elif file_name == "functions_catalog":
                kb_json.save_function_catalog(parsed.get("functions", []) if isinstance(parsed, dict) else parsed)
            elif file_name == "flow_catalog":
                kb_json.save_flow_catalog(parsed.get("flows", []) if isinstance(parsed, dict) else parsed)
            elif file_name in {"excel_rule_overview", "excel_translation_matrix", "excel_priorities"}:
                st.warning("Diese aus Excel abgeleiteten technischen Dateien sind in dieser Ansicht nur Vorschau. Bitte über die fachlichen Ansichten bearbeiten.")
            else:
                kb_json.save_json(file_name, parsed)
            st.success("JSON gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(f"Ungültiges JSON: {e}")
    col2.download_button("Datei herunterladen", data=json.dumps(data, ensure_ascii=False, indent=2), file_name=f"{file_name}.json", mime="application/json", key=f"admin_json_download_{file_name}")


def admin_rule_validation() -> None:
    from storage import kb_validator
    st.header("Admin · Regelprüfung")
    render_view_info(
        "Regelprüfung",
        "Diese Ansicht prüft die austauschbare Rule Engine auf formale Fehler, fehlende Verweise und mögliche Inkonsistenzen. Sie berücksichtigt auch die technische Eduroam-Condition-Matrix aus der Excel-Datei.",
    )
    if st.button("Rule Engine prüfen", key="admin_validate_kb"):
        result = kb_validator.validate_knowledge_base()
        if result.get("valid"):
            st.success(result.get("summary"))
        else:
            st.error(result.get("summary"))
        if result.get("errors"):
            st.subheader("Fehler")
            for err in result.get("errors", []):
                st.error(err)
        if result.get("warnings"):
            st.subheader("Hinweise")
            for warn in result.get("warnings", []):
                st.warning(warn)
        with st.expander("Rohes Prüfergebnis"):
            st.json(result)
