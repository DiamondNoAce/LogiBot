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
    file_name = st.selectbox("Datei", list(kb_json.FILES.keys()), key="admin_json_file_select")
    data = kb_json.load_json(file_name, [] if file_name in {"inference_rules", "step_packages", "sources"} else {})
    raw = st.text_area("JSON-Inhalt", value=json.dumps(data, ensure_ascii=False, indent=2), height=520, key=f"admin_json_raw_{file_name}")
    col1, col2 = st.columns(2)
    if col1.button("JSON speichern", key=f"admin_json_save_{file_name}"):
        try:
            parsed = json.loads(raw)
            kb_json.save_json(file_name, parsed)
            st.success("JSON gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(f"Ungültiges JSON: {e}")
    col2.download_button("Datei herunterladen", data=json.dumps(data, ensure_ascii=False, indent=2), file_name=f"{file_name}.json", mime="application/json", key=f"admin_json_download_{file_name}")
