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
    render_view_title,
)

def admin_json_files() -> None:
    render_view_title(
        "Admin · Technische JSON-Dateien",
        "Technische JSON-Dateien",
        "Diese Ansicht ist für technische Kontrolle gedacht. Hier kannst du die Dateien aus dem austauschbaren Rule-Engine-Ordner direkt ansehen, herunterladen oder bearbeiten. Aggregierte Einträge wie inference_rules werden aus den Unterordnern rules/, sources/ und step_packages/ zusammengeführt.",
    )
    extra_files = ["condition_catalog", "functions_catalog", "flow_catalog", "excel_rule_overview", "excel_translation_matrix", "excel_priorities", "regeln_vollstaendig_neu_rule_overview", "regeln_vollstaendig_neu_translation_matrix", "regeln_vollstaendig_neu_condition_catalog", "regeln_vollstaendig_neu_functions", "regeln_vollstaendig_neu_flows"]
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

    elif file_name == "regeln_vollstaendig_neu_rule_overview":
        data = kb_json._read_json_file(kb_json.TECHNICAL_DIR / "regeln_vollstaendig_neu_rule_overview.json", {"items": []})
    elif file_name == "regeln_vollstaendig_neu_translation_matrix":
        data = kb_json._read_json_file(kb_json.TECHNICAL_DIR / "regeln_vollstaendig_neu_translation_matrix.json", {"items": []})
    elif file_name == "regeln_vollstaendig_neu_condition_catalog":
        data = kb_json._read_json_file(kb_json.TECHNICAL_DIR / "regeln_vollstaendig_neu_condition_catalog.json", {"items": []})
    elif file_name == "regeln_vollstaendig_neu_functions":
        data = kb_json._read_json_file(kb_json.TECHNICAL_DIR / "regeln_vollstaendig_neu_functions.json", {"items": []})
    elif file_name == "regeln_vollstaendig_neu_flows":
        data = kb_json._read_json_file(kb_json.TECHNICAL_DIR / "wissensmodell_excel_flows.json", {"items": []})
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
    render_view_title(
        "Admin · Regelprüfung",
        "Regelprüfung",
        "Diese Ansicht prüft die austauschbare Rule Engine automatisch auf formale Fehler, fehlende Verweise und Qualitätsprobleme. Dazu gehören Regeln ohne Aktion, Schritte ohne Inhalt, Abläufe ohne Startpunkt und Entscheidungsnetze ohne Support-Fallback.",
    )

    col_refresh, col_hint = st.columns([1, 3])
    refresh = col_refresh.button("Jetzt erneut prüfen", key="admin_validate_kb")
    if refresh or "admin_validation_result" not in st.session_state:
        st.session_state.admin_validation_result = kb_validator.validate_knowledge_base()
    result = st.session_state.get("admin_validation_result") or kb_validator.validate_knowledge_base()

    error_count = len(result.get("errors", []))
    warning_count = len(result.get("warnings", []))
    quality = int(result.get("quality_score", 0))
    c1, c2, c3 = st.columns(3)
    c1.metric("Fehler", error_count)
    c2.metric("Hinweise", warning_count)
    c3.metric("Qualitätswert", f"{quality}/100")

    if result.get("valid"):
        st.success(result.get("summary"))
    else:
        st.error(result.get("summary"))

    checks = result.get("automatic_checks", []) or []
    with st.expander("Automatisch geprüfte Qualitätsregeln", expanded=True):
        for check in checks:
            st.markdown(f"- {check}")

    by_category = result.get("by_category", {}) or {}
    if by_category:
        st.subheader("Übersicht nach Bereich")
        rows = []
        for category, counts in sorted(by_category.items()):
            rows.append({
                "Bereich": category,
                "Fehler": counts.get("error", 0),
                "Hinweise": counts.get("warning", 0),
                "Gesamt": counts.get("total", 0),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

    issues = result.get("issues", []) or []
    if issues:
        st.subheader("Prüfergebnisse")
        severity_filter = st.multiselect(
            "Schweregrad filtern",
            ["error", "warning", "info"],
            default=["error", "warning"],
            key="admin_validation_severity_filter",
        )
        category_options = sorted({str(i.get("category")) for i in issues if i.get("category")})
        category_filter = st.multiselect(
            "Bereich filtern",
            category_options,
            default=category_options,
            key="admin_validation_category_filter",
        )
        filtered = [
            i for i in issues
            if i.get("severity") in severity_filter and (not category_filter or i.get("category") in category_filter)
        ]
        for issue in filtered[:250]:
            sev = issue.get("severity")
            msg = f"**{issue.get('category', 'Sonstiges')}**: {issue.get('message')}"
            if issue.get("ref"):
                msg += f"  \n`{issue.get('ref')}`"
            if sev == "error":
                st.error(msg)
            elif sev == "warning":
                st.warning(msg)
            else:
                st.info(msg)
        if len(filtered) > 250:
            st.caption(f"Es werden nur die ersten 250 von {len(filtered)} Treffern angezeigt.")
    else:
        st.success("Keine Auffälligkeiten gefunden.")

    with st.expander("Rohes Prüfergebnis"):
        st.json(result)
