from __future__ import annotations

import json
import re
from typing import Any

import streamlit as st

from storage import kb_loader as kb_json
from ui.common import render_view_title, split_lines


AREAS = ["Core", "Eduroam", "VPN", "MFA", "Support", "Allgemein"]
NAMESPACES = ["core", "service.eduroam", "service.vpn", "service.mfa", "service.support", "allgemein"]


def _safe_key(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(value or "new"))


def _value_lines(values: Any) -> str:
    if isinstance(values, list):
        return "\n".join(str(v).lower() if isinstance(v, bool) else str(v) for v in values)
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


def _area_from_namespace(ns: str) -> str:
    ns_l = str(ns or "").lower()
    if ns_l == "core":
        return "Core"
    if "eduroam" in ns_l:
        return "Eduroam"
    if "vpn" in ns_l:
        return "VPN"
    if "mfa" in ns_l:
        return "MFA"
    if "support" in ns_l:
        return "Support"
    return "Allgemein"


def admin_conditions_facts() -> None:
    render_view_title(
        "Admin · Wissensbausteine",
        "Wissensbausteine",
        "Dies ist der zentrale Katalog für Facts: technische ID, verständlicher Name, erlaubte Werte, Rückfrage und Synonyme. "
        "Conditions entstehen erst in der Regelverwaltung, wenn ein Wissensbaustein mit Operator und Wert geprüft wird. "
        "Pre-Conditions gehören deshalb nicht in diesen Katalog, sondern in die jeweilige Regel.",
    )

    conditions = kb_json.load_condition_catalog(active_only=False)
    rules = kb_json.load_inference_rules(active_only=False)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Wissensbausteine", len(conditions))
    c2.metric("Wissensbereiche", len({x.get("knowledge_area") for x in conditions if x.get("knowledge_area")}))
    c3.metric("Kategorien", len({x.get("category") for x in conditions if x.get("category")}))
    c4.metric("Regeln", len(rules))

    tab_catalog, tab_editor, tab_preview = st.tabs(["Katalog", "Wissensbaustein bearbeiten", "Technische Vorschau"])

    with tab_catalog:
        area_filter = st.multiselect(
            "Nach Wissensbereich filtern",
            sorted({x.get("knowledge_area", "Allgemein") for x in conditions} | set(AREAS)),
            default=[],
            key="conditions_area_filter",
        )
        category_filter = st.multiselect(
            "Nach Kategorie filtern",
            sorted({x.get("category", "") for x in conditions if x.get("category")}),
            default=[],
            key="conditions_category_filter",
        )
        search = st.text_input("Suchen", placeholder="z. B. mfa_code_status, WLAN, Account, Campus", key="conditions_search")

        visible = conditions
        if area_filter:
            visible = [x for x in visible if x.get("knowledge_area") in area_filter]
        if category_filter:
            visible = [x for x in visible if x.get("category") in category_filter]
        if search.strip():
            q = search.lower()
            visible = [x for x in visible if q in json.dumps(x, ensure_ascii=False).lower()]

        st.dataframe(
            [
                {
                    "Fact-ID": x.get("key"),
                    "Anzeigename": x.get("display_name"),
                    "Namespace": x.get("namespace", ""),
                    "Wissensbereich": x.get("knowledge_area"),
                    "Kategorie": x.get("category"),
                    "Datentyp": x.get("data_type", ""),
                    "Mögliche Werte": ", ".join(str(v) for v in x.get("allowed_values", [])),
                    "Frage bei unknown": x.get("question_unknown", ""),
                    "Nutzung": x.get("used_in", ""),
                }
                for x in visible
            ],
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Warum heißt diese Ansicht nicht mehr Conditions / Facts?"):
            st.markdown(
                """
                **Fact / Wissensbaustein:** Ein Zustand, den der Bot kennen kann, z. B. `mfa_code_status`.  
                **Condition:** Eine Prüfung auf einem Fact, z. B. `mfa_code_status = valid`.  
                **Pre-Condition:** Eine Voraussetzung innerhalb einer Regel.  

                Deshalb werden hier nur die wiederverwendbaren Wissensbausteine gepflegt. Die konkrete Nutzung als
                Pre-, Trigger- oder Post-Condition passiert in der Regelverwaltung.
                """
            )

    with tab_editor:
        options = [None] + conditions
        selected = st.selectbox(
            "Wissensbaustein auswählen",
            options,
            format_func=lambda x: "Neuen Wissensbaustein anlegen" if x is None else f"{x.get('display_name', x.get('key'))} ({x.get('key')})",
            key="condition_select",
        )
        suffix = _safe_key(selected.get("key") if selected else "new")

        if selected:
            with st.expander("Verwendung in Regeln", expanded=False):
                hits = kb_json.rules_using_condition(selected.get("key"))
                if hits:
                    st.dataframe(hits, use_container_width=True, hide_index=True)
                else:
                    st.info("Dieser Wissensbaustein wurde in den aktuell geladenen Regeln noch nicht gefunden.")

        with st.form(f"condition_form_{suffix}"):
            st.markdown("### Stammdaten")
            key = st.text_input("Fact-ID / technische ID", value="" if selected is None else selected.get("key", ""), key=f"condition_key_{suffix}")
            display_name = st.text_input("Anzeigename", value="" if selected is None else selected.get("display_name", ""), key=f"condition_display_{suffix}")
            ns_value = selected.get("namespace", "core") if selected else "core"
            namespace = st.selectbox("Namespace", NAMESPACES, index=NAMESPACES.index(ns_value) if ns_value in NAMESPACES else 0, key=f"condition_namespace_{suffix}")
            area_value = selected.get("knowledge_area") if selected else _area_from_namespace(namespace)
            knowledge_area = st.selectbox(
                "Wissensbereich",
                AREAS,
                index=AREAS.index(area_value) if area_value in AREAS else AREAS.index(_area_from_namespace(namespace)),
                key=f"condition_area_{suffix}",
            )
            category = st.text_input("Kategorie", value="" if selected is None else selected.get("category", ""), key=f"condition_category_{suffix}")
            data_type = st.text_input("Datentyp", value="" if selected is None else selected.get("data_type", ""), key=f"condition_data_type_{suffix}")

            st.markdown("### Werte und Rückfragen")
            allowed_values = st.text_area("Mögliche Werte, ein Wert pro Zeile", value="" if selected is None else _value_lines(selected.get("allowed_values", [])), key=f"condition_values_{suffix}")
            question_unknown = st.text_area("Frage, wenn der Wert unbekannt ist", value="" if selected is None else selected.get("question_unknown", ""), key=f"condition_question_{suffix}")
            synonyms = st.text_area("Synonyme / typische Formulierungen", value="" if selected is None else _value_lines(selected.get("synonyms", [])), key=f"condition_synonyms_{suffix}")

            st.markdown("### Beschreibung und Qualität")
            description = st.text_area("Beschreibung", value="" if selected is None else selected.get("description", ""), key=f"condition_desc_{suffix}")
            used_in = st.text_area("Verwendet in Regeln / Kontext", value="" if selected is None else selected.get("used_in", ""), key=f"condition_used_{suffix}")
            quality_rule = st.text_area("Qualitätsregel / Hinweis", value="" if selected is None else selected.get("quality_rule", selected.get("translation_hint", "")), key=f"condition_quality_{suffix}")
            active = st.checkbox("Aktiv", value=True if selected is None else bool(selected.get("active", True)), key=f"condition_active_{suffix}")
            col1, col2 = st.columns(2)
            save = col1.form_submit_button("Wissensbaustein speichern")
            delete = col2.form_submit_button("Wissensbaustein löschen")

        if save:
            try:
                item = {
                    "id": selected.get("id", "") if selected else "",
                    "key": key.strip(),
                    "display_name": display_name.strip() or key.strip(),
                    "namespace": namespace,
                    "knowledge_area": knowledge_area,
                    "category": category.strip(),
                    "data_type": data_type.strip(),
                    "allowed_values": _parse_values(allowed_values),
                    "question_unknown": question_unknown.strip(),
                    "synonyms": split_lines(synonyms),
                    "description": description.strip(),
                    "used_in": used_in.strip(),
                    "quality_rule": quality_rule.strip(),
                    "active": active,
                    "source": "Adminoberfläche Wissensbausteine",
                }
                kb_json.upsert_condition_fact(item)
                st.success("Wissensbaustein gespeichert.")
                st.rerun()
            except Exception as e:
                st.error(f"Speichern fehlgeschlagen: {e}")

        if delete and selected is not None:
            kb_json.delete_condition_fact(selected.get("key"))
            st.warning("Wissensbaustein gelöscht.")
            st.rerun()

    with tab_preview:
        st.caption("Technische JSON-Vorschau. Für normale Pflege ist dieser Bereich nicht notwendig.")
        st.json({"conditions": conditions})
