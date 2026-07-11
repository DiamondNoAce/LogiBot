from __future__ import annotations

import json
import re
from typing import Any

import streamlit as st

from storage import kb_loader as kb_json
from ui.common import render_view_info
from ui.admin_steps_view import admin_steps_solutions


AREAS = ["Core", "Eduroam", "VPN", "MFA", "Support", "Allgemein"]
TYPES = ["Pre-Condition-Hilfe", "Setup", "Authentifizierung", "Verbindungstest", "Troubleshooting", "Antwortbaustein", "Abschluss"]


def _safe_key(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(value or "new"))


def admin_functions_answers() -> None:
    st.header("Admin · Funktionen & Antworten")
    render_view_info(
        "Funktionen & Antworten",
        "Regeln lösen nicht nur Anleitungsschritte aus, sondern Funktionen, Antwortbausteine oder technische Actions. Hier pflegst du verständliche Funktionsnamen und die zugehörigen Antworttexte. Die bisherige Schritt-/Lösungsverwaltung bleibt im zweiten Tab erhalten.",
    )

    tab_functions, tab_steps = st.tabs(["Funktionen-Katalog", "Anleitungsschritte & Lösungen"])

    with tab_functions:
        functions = kb_json.load_function_catalog(active_only=False)
        c1, c2, c3 = st.columns(3)
        c1.metric("Funktionen", len(functions))
        c2.metric("Typen", len({x.get("function_type") for x in functions if x.get("function_type")}))
        c3.metric("Wissensbereiche", len({x.get("knowledge_area") for x in functions if x.get("knowledge_area")}))

        area = st.multiselect("Wissensbereich", sorted({x.get("knowledge_area", "Allgemein") for x in functions} | set(AREAS)), key="function_area_filter")
        ftype = st.multiselect("Funktionstyp", sorted({x.get("function_type", "Antwortbaustein") for x in functions} | set(TYPES)), key="function_type_filter")
        search = st.text_input("Suchen", placeholder="z. B. vpn_authenticate, 30-Sekunden-Code, Verbindung", key="function_search")

        visible = functions
        if area:
            visible = [x for x in visible if x.get("knowledge_area") in area]
        if ftype:
            visible = [x for x in visible if x.get("function_type") in ftype]
        if search.strip():
            q = search.lower()
            visible = [x for x in visible if q in json.dumps(x, ensure_ascii=False).lower()]

        st.dataframe(
            [
                {
                    "Technische ID": x.get("id"),
                    "Anzeigename": x.get("display_name"),
                    "Wissensbereich": x.get("knowledge_area"),
                    "Typ": x.get("function_type"),
                    "Kategorie": x.get("category"),
                    "Zweck": x.get("purpose"),
                }
                for x in visible
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Funktion / Antwortbaustein bearbeiten")
        options = [None] + visible
        selected = st.selectbox(
            "Funktion auswählen",
            options,
            format_func=lambda x: "Neue Funktion anlegen" if x is None else f"{x.get('display_name', x.get('id'))} ({x.get('id')})",
            key="function_select",
        )
        suffix = _safe_key(selected.get("id") if selected else "new")
        with st.form(f"function_form_{suffix}"):
            fid = st.text_input("Technische ID", value="" if selected is None else selected.get("id", ""), key=f"function_id_{suffix}")
            display_name = st.text_input("Anzeigename", value="" if selected is None else selected.get("display_name", ""), key=f"function_display_{suffix}")
            area_value = selected.get("knowledge_area", "Core") if selected else "Core"
            knowledge_area = st.selectbox("Wissensbereich", AREAS, index=AREAS.index(area_value) if area_value in AREAS else 0, key=f"function_area_{suffix}")
            type_value = selected.get("function_type", "Antwortbaustein") if selected else "Antwortbaustein"
            function_type = st.selectbox("Funktionstyp", TYPES, index=TYPES.index(type_value) if type_value in TYPES else 5, key=f"function_type_{suffix}")
            category = st.text_input("Kategorie", value="" if selected is None else selected.get("category", ""), key=f"function_category_{suffix}")
            purpose = st.text_area("Zweck", value="" if selected is None else selected.get("purpose", ""), key=f"function_purpose_{suffix}")
            input_facts = st.text_area("Typische Eingangsfacts", value="" if selected is None else selected.get("input_facts", ""), key=f"function_input_{suffix}")
            sets_facts = st.text_area("Setzt / ändert Facts", value="" if selected is None else selected.get("sets_facts", ""), key=f"function_sets_{suffix}")
            response_text = st.text_area("Antwortbaustein / Ausgabe", value="" if selected is None else selected.get("response_text", ""), key=f"function_response_{suffix}")
            note = st.text_area("Hinweis", value="" if selected is None else selected.get("note", ""), key=f"function_note_{suffix}")
            active = st.checkbox("Aktiv", value=True if selected is None else bool(selected.get("active", True)), key=f"function_active_{suffix}")
            with st.expander("Erweiterte technische Konfiguration"):
                raw = st.text_area("Zusätzliche JSON-Metadaten", value=json.dumps({} if selected is None else selected.get("technical_config", {}), ensure_ascii=False, indent=2), height=160, key=f"function_tech_{suffix}")
            col1, col2 = st.columns(2)
            save = col1.form_submit_button("Funktion speichern")
            delete = col2.form_submit_button("Funktion löschen")

        if save:
            try:
                item = {
                    "id": fid.strip(),
                    "display_name": display_name.strip() or fid.strip(),
                    "knowledge_area": knowledge_area,
                    "category": category.strip(),
                    "function_type": function_type,
                    "purpose": purpose.strip(),
                    "input_facts": input_facts.strip(),
                    "sets_facts": sets_facts.strip(),
                    "response_text": response_text.strip(),
                    "note": note.strip(),
                    "active": active,
                    "technical_config": json.loads(raw) if raw.strip() else {},
                    "source": "Adminoberfläche Funktionen & Antworten",
                }
                kb_json.upsert_function_item(item)
                st.success("Funktion gespeichert.")
                st.rerun()
            except Exception as e:
                st.error(f"Speichern fehlgeschlagen: {e}")

        if delete and selected is not None:
            kb_json.delete_function_item(selected.get("id"))
            st.warning("Funktion gelöscht.")
            st.rerun()

        with st.expander("Technische JSON-Vorschau"):
            st.json({"functions": functions})

    with tab_steps:
        admin_steps_solutions()
