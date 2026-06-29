from __future__ import annotations

import json
import re
from typing import Any

import streamlit as st

from storage import kb_loader as kb_json
from ui.common import render_view_info, split_lines


AREAS = ["Core", "Eduroam", "VPN", "MFA", "Support", "Allgemein"]


def _safe_key(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(value or "new"))


def _value_lines(values: Any) -> str:
    if isinstance(values, list):
        return "\n".join(str(v) for v in values)
    if values is None:
        return ""
    return str(values)


def _parse_values(text: str) -> list[Any]:
    out: list[Any] = []
    for line in split_lines(text):
        low = line.lower().strip()
        if low == "true":
            out.append(True)
        elif low == "false":
            out.append(False)
        elif low in {"null", "none"}:
            out.append(None)
        else:
            out.append(line)
    return out


def admin_conditions_facts() -> None:
    st.header("Admin · Conditions / Facts")
    render_view_info(
        "Conditions / Facts",
        "Diese Ansicht ist der zentrale Condition-Katalog. Hier pflegst du technische Fact-IDs, verständliche Anzeigenamen, Wissensbereiche, Kategorien und erlaubte Werte. Damit können Admins Regeln erstellen, ohne direkt JSON schreiben zu müssen.",
    )

    conditions = kb_json.load_condition_catalog(active_only=False)
    rules = kb_json.load_inference_rules(active_only=False)

    with st.expander("Kurzüberblick aus dem Wissensmodell", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Conditions/Facts", len(conditions))
        c2.metric("Wissensbereiche", len({x.get("knowledge_area") for x in conditions if x.get("knowledge_area")}))
        c3.metric("Kategorien", len({x.get("category") for x in conditions if x.get("category")}))
        c4.metric("Regeln", len(rules))

    area_filter = st.multiselect(
        "Nach Wissensbereich filtern",
        sorted({x.get("knowledge_area", "Allgemein") for x in conditions} | set(AREAS)),
        default=[],
        key="conditions_area_filter",
    )
    search = st.text_input("Suchen", placeholder="z. B. mfa_code_status, WLAN, Account", key="conditions_search")

    visible = conditions
    if area_filter:
        visible = [x for x in visible if x.get("knowledge_area") in area_filter]
    if search.strip():
        q = search.lower()
        visible = [x for x in visible if q in json.dumps(x, ensure_ascii=False).lower()]

    st.dataframe(
        [
            {
                "Technische Condition-ID": x.get("key"),
                "Anzeigename": x.get("display_name"),
                "Wissensbereich": x.get("knowledge_area"),
                "Kategorie": x.get("category"),
                "Mögliche Werte": ", ".join(str(v) for v in x.get("allowed_values", [])),
                "Verwendet in": x.get("used_in"),
            }
            for x in visible
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Condition / Fact bearbeiten")
    options = [None] + visible
    selected = st.selectbox(
        "Condition auswählen",
        options,
        format_func=lambda x: "Neue Condition anlegen" if x is None else f"{x.get('display_name', x.get('key'))} ({x.get('key')})",
        key="condition_select",
    )
    suffix = _safe_key(selected.get("key") if selected else "new")

    if selected:
        with st.expander("Verwendung in Regeln", expanded=False):
            hits = kb_json.rules_using_condition(selected.get("key"))
            if hits:
                st.dataframe(hits, use_container_width=True, hide_index=True)
            else:
                st.info("Diese Condition wurde in den aktuell geladenen Regeln noch nicht gefunden.")

    with st.form(f"condition_form_{suffix}"):
        key = st.text_input("Technische Condition-ID", value="" if selected is None else selected.get("key", ""), key=f"condition_key_{suffix}")
        display_name = st.text_input("Anzeigename", value="" if selected is None else selected.get("display_name", ""), key=f"condition_display_{suffix}")
        knowledge_area = st.selectbox(
            "Wissensbereich",
            AREAS,
            index=AREAS.index(selected.get("knowledge_area", "Core")) if selected and selected.get("knowledge_area") in AREAS else 0,
            key=f"condition_area_{suffix}",
        )
        category = st.text_input("Kategorie", value="" if selected is None else selected.get("category", ""), key=f"condition_category_{suffix}")
        allowed_values = st.text_area("Mögliche Werte, ein Wert pro Zeile", value="" if selected is None else _value_lines(selected.get("allowed_values", [])), key=f"condition_values_{suffix}")
        description = st.text_area("Beschreibung", value="" if selected is None else selected.get("description", ""), key=f"condition_desc_{suffix}")
        used_in = st.text_area("Verwendet in Regeln / Kontext", value="" if selected is None else selected.get("used_in", ""), key=f"condition_used_{suffix}")
        translation_hint = st.text_area("Hinweis zur Übersetzung", value="" if selected is None else selected.get("translation_hint", ""), key=f"condition_hint_{suffix}")
        active = st.checkbox("Aktiv", value=True if selected is None else bool(selected.get("active", True)), key=f"condition_active_{suffix}")
        col1, col2 = st.columns(2)
        save = col1.form_submit_button("Condition speichern")
        delete = col2.form_submit_button("Condition löschen")

    if save:
        try:
            item = {
                "id": selected.get("id", "") if selected else "",
                "key": key.strip(),
                "display_name": display_name.strip() or key.strip(),
                "knowledge_area": knowledge_area,
                "category": category.strip(),
                "allowed_values": _parse_values(allowed_values),
                "description": description.strip(),
                "used_in": used_in.strip(),
                "translation_hint": translation_hint.strip(),
                "active": active,
                "source": "Adminoberfläche Conditions/Facts",
            }
            kb_json.upsert_condition_fact(item)
            st.success("Condition gespeichert.")
            st.rerun()
        except Exception as e:
            st.error(f"Speichern fehlgeschlagen: {e}")

    if delete and selected is not None:
        kb_json.delete_condition_fact(selected.get("key"))
        st.warning("Condition gelöscht.")
        st.rerun()

    with st.expander("Technische JSON-Vorschau"):
        st.json({"conditions": conditions})
