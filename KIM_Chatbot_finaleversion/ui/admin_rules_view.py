from __future__ import annotations

import json
import re
from typing import Any

import streamlit as st

from storage import kb_loader as kb_json
from core import inference_engine
from ui.common import render_view_title, split_lines


def _safe_key(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(value or "new"))


def _condition_to_line(cond: dict[str, Any]) -> str:
    if not isinstance(cond, dict):
        return str(cond)
    fact = cond.get("fact") or cond.get("field") or ""
    op = cond.get("operator", "equals")
    val = cond.get("value", "")
    if isinstance(val, list):
        val = ", ".join(str(v) for v in val)
    return f"{fact} | {op} | {val}"


def _conditions_to_text(conditions: list[dict[str, Any]]) -> str:
    return "\n".join(_condition_to_line(c) for c in conditions or [])


def _parse_scalar(value: str) -> Any:
    value = str(value).strip()
    low = value.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in {"null", "none"}:
        return None
    if low == "unknown":
        return "unknown"
    return value


def _parse_conditions(text: str) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    for line in split_lines(text):
        if "|" in line:
            parts = [p.strip() for p in line.split("|", 2)]
            if len(parts) == 3:
                fact, op, value = parts
            else:
                continue
        elif " in " in line:
            fact, value = line.split(" in ", 1)
            op = "in"
        elif "=" in line:
            fact, value = line.split("=", 1)
            op = "equals"
        else:
            fact, op, value = line, "is_known", "true"
        fact = fact.strip()
        op = (op or "equals").strip()
        op = {"eq": "equals", "=": "equals", "==": "equals", "maybe": "metadata", "sets": "metadata"}.get(op.lower(), op)
        raw_value = str(value).strip()
        if op in {"in", "not_in", "contains_any", "contains_all"}:
            parsed_value = [_parse_scalar(v.strip()) for v in re.split(r",| oder ", raw_value) if v.strip()]
        elif op in {"is_unknown", "is_known", "is_true", "is_false"}:
            parsed_value = True
        elif op == "metadata":
            parsed_value = raw_value
        else:
            parsed_value = _parse_scalar(raw_value)
        if fact:
            conditions.append({"fact": fact, "operator": op, "value": parsed_value})
    return conditions


def _extract_pre(rule: dict[str, Any]) -> list[dict[str, Any]]:
    return (rule.get("technical_metadata") or {}).get("pre_conditions") or (rule.get("when") or {}).get("all", []) or []


def _extract_trigger(rule: dict[str, Any]) -> list[dict[str, Any]]:
    meta = rule.get("technical_metadata") or {}
    if meta.get("trigger_conditions"):
        return meta.get("trigger_conditions") or []
    when = rule.get("when") or {}
    return when.get("any") or []


def _extract_post(rule: dict[str, Any]) -> list[dict[str, Any]]:
    meta = rule.get("technical_metadata") or {}
    return meta.get("post_conditions") or meta.get("post_conditions_success") or []


def _action_from_rule(rule: dict[str, Any]) -> str:
    meta = rule.get("technical_metadata") or {}
    if meta.get("action_function"):
        return str(meta.get("action_function"))
    for item in rule.get("then", []) or []:
        if item.get("type") in {"function", "action"}:
            return str(item.get("function_id") or item.get("action") or "")
    return ""


def _next_from_rule(rule: dict[str, Any]) -> tuple[str, str]:
    meta = rule.get("technical_metadata") or {}
    return str(meta.get("next_success") or rule.get("next", "")), str(meta.get("next_failure") or meta.get("next_failure_alternative") or "")


def _display_condition_group(conditions: list[dict[str, Any]]) -> str:
    return "; ".join(_condition_to_line(c) for c in conditions) if conditions else "—"


def admin_inference_rules() -> None:
    render_view_title(
        "Admin · Regelverwaltung",
        "Regelverwaltung",
        "Diese Ansicht ist an die Excel-Struktur angelehnt: Stammdaten, Pre-Conditions, Trigger-Conditions, Action/Funktion, Post-Conditions und Next-Step. JSON bleibt als technische Vorschau erhalten, muss aber nicht direkt bearbeitet werden.",
    )

    rules = kb_json.load_inference_rules(active_only=False)
    functions = kb_json.load_function_catalog(active_only=False)
    conditions = kb_json.load_condition_catalog(active_only=False)
    condition_keys = [c.get("key") for c in conditions if c.get("key")]
    function_options = [""] + [f.get("id") for f in functions if f.get("id")]
    function_lookup = {f.get("id"): f for f in functions if f.get("id")}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Regeln", len(rules))
    c2.metric("aktive Regeln", len([r for r in rules if r.get("active", True)]))
    c3.metric("Wissensbausteine", len(conditions))
    c4.metric("Funktionen", len(functions))

    tab_table, tab_editor, tab_help = st.tabs(["Regeltabelle", "Regel bearbeiten", "Operatoren & Hilfe"])

    with tab_table:
        module_filter = st.multiselect("Modul/Wissensbereich", sorted({str(r.get("module", "")) for r in rules if r.get("module")}), key="rule_module_filter")
        namespace_filter = st.multiselect("Namespace", sorted({str((r.get("technical_metadata") or {}).get("namespace", "")) for r in rules if (r.get("technical_metadata") or {}).get("namespace")}), key="rule_namespace_filter")
        status_filter = st.multiselect("Status", ["aktiv", "inaktiv"], default=[], key="rule_status_filter")
        search = st.text_input("Suchen", key="rule_search", placeholder="Regel-ID, Wissensbaustein, Funktion oder Beschreibung")
        visible = rules
        if module_filter:
            visible = [r for r in visible if str(r.get("module", "")) in module_filter]
        if namespace_filter:
            visible = [r for r in visible if str((r.get("technical_metadata") or {}).get("namespace", "")) in namespace_filter]
        if status_filter:
            visible = [r for r in visible if ("aktiv" if r.get("active", True) else "inaktiv") in status_filter]
        if search.strip():
            q = search.lower()
            visible = [r for r in visible if q in json.dumps(r, ensure_ascii=False).lower()]
        st.dataframe(
            [
                {
                    "Prio": r.get("priority"),
                    "Status": "aktiv" if r.get("active", True) else "inaktiv",
                    "Regel-ID": r.get("id"),
                    "Namespace": (r.get("technical_metadata") or {}).get("namespace", r.get("module", "")),
                    "Regeltyp": r.get("rule_group"),
                    "Pre-Conditions": _display_condition_group(_extract_pre(r)),
                    "Trigger-Conditions": _display_condition_group(_extract_trigger(r)),
                    "Action / Funktion": (function_lookup.get(_action_from_rule(r), {}) or {}).get("display_name", _action_from_rule(r)),
                    "Action-ID": _action_from_rule(r),
                    "Post-Conditions": _display_condition_group(_extract_post(r)),
                    "Next": " / ".join(x for x in _next_from_rule(r) if x),
                    "Beschreibung": r.get("description", ""),
                }
                for r in visible
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Die Tabelle folgt der Regel-Excel: Stammdaten → Pre-Conditions → Trigger → Action/Funktion → Post-Conditions → Next.")

    with tab_editor:
        options = [None] + rules
        selected = st.selectbox(
            "Regel auswählen",
            options,
            format_func=lambda r: "Neue Regel anlegen" if r is None else f"{r.get('id')} · {r.get('description','')}",
            key="admin_rule_select",
        )
        suffix = _safe_key(selected.get("id") if selected else "new")
        if selected:
            st.caption(f"Ausgewählt: {selected.get('id')} · Priorität {selected.get('priority')}")

        pre_default = _conditions_to_text(_extract_pre(selected or {}))
        trigger_default = _conditions_to_text(_extract_trigger(selected or {}))
        post_default = _conditions_to_text(_extract_post(selected or {}))
        action_default = _action_from_rule(selected or {})
        next_success, next_failure = _next_from_rule(selected or {})

        with st.form(f"admin_rule_form_excel_{suffix}"):
            st.markdown("### 1. Stammdaten")
            rid = st.text_input("Regel-ID", value="" if selected is None else selected.get("id", ""), key=f"admin_rule_id_{suffix}")
            description = st.text_area("Regelname / Beschreibung", value="" if selected is None else selected.get("description", ""), key=f"admin_rule_desc_{suffix}")
            module = st.text_input("Wissensbereich / Modul", value="general" if selected is None else selected.get("module", "general"), key=f"admin_rule_module_{suffix}")
            rule_type = st.text_input("Regeltyp", value="technical_rule" if selected is None else selected.get("rule_group", "technical_rule"), key=f"admin_rule_type_{suffix}")
            priority = st.number_input("Priorität", min_value=0, step=1, value=100 if selected is None else int(selected.get("priority", 100)), key=f"admin_rule_priority_{suffix}")
            active = st.checkbox("Aktiv", value=True if selected is None else bool(selected.get("active", True)), key=f"admin_rule_active_{suffix}")
            stop = st.checkbox("Nach Treffer stoppen", value=False if selected is None else bool(selected.get("stop_after_match", False)), key=f"admin_rule_stop_{suffix}")

            st.markdown("### 2. Pre-Conditions")
            st.caption("Eine Condition pro Zeile: `fact | operator | value`, z. B. `service | equals | eduroam` oder `account_exists | equals | true`.")
            pre_text = st.text_area("Pre-Conditions", value=pre_default, height=150, key=f"admin_rule_pre_{suffix}")

            st.markdown("### 3. Trigger-Conditions")
            trigger_text = st.text_area("Trigger-Conditions", value=trigger_default, height=150, key=f"admin_rule_trigger_{suffix}")

            st.markdown("### 4. Action / Funktion")
            action = st.selectbox(
                "Action / Funktion",
                function_options,
                index=function_options.index(action_default) if action_default in function_options else 0,
                format_func=lambda x: "Keine / manuell" if not x else f"{(kb_json.get_function_item(x) or {}).get('display_name', x)} ({x})",
                key=f"admin_rule_action_select_{suffix}",
            )
            action_manual = st.text_input("Oder technische Funktions-ID manuell", value="" if action else action_default, key=f"admin_rule_action_manual_{suffix}")
            answer_text = st.text_area("Antworttext / Hinweis", value="" if selected is None else "\n".join(t.get("text", "") for t in selected.get("then", []) if t.get("type") == "answer"), key=f"admin_rule_answer_{suffix}")

            st.markdown("### 5. Post-Conditions")
            post_text = st.text_area("Post-Conditions", value=post_default, height=150, key=f"admin_rule_post_{suffix}")

            st.markdown("### 6. Next-Step")
            next_success_value = st.text_input("Next bei Erfolg", value=next_success, key=f"admin_rule_next_success_{suffix}")
            next_failure_value = st.text_input("Next bei Fehler / Alternative", value=next_failure, key=f"admin_rule_next_failure_{suffix}")

            with st.expander("Erweiterte technische Konfiguration / JSON-Vorschau"):
                st.caption("Diese Vorschau wird automatisch aus den Feldern erzeugt. Sie kann bei Bedarf manuell ergänzt werden.")
                raw_existing = selected or {}
                raw = st.text_area("Roh-JSON der Regel", value=json.dumps(raw_existing, ensure_ascii=False, indent=2), height=260, key=f"admin_rule_raw_{suffix}")

            col_save, col_delete = st.columns(2)
            save_clicked = col_save.form_submit_button("Regel speichern")
            delete_clicked = col_delete.form_submit_button("Regel löschen")

        if save_clicked:
            try:
                pre_conditions = _parse_conditions(pre_text)
                trigger_conditions = _parse_conditions(trigger_text)
                post_conditions = _parse_conditions(post_text)
                action_id = (action_manual or action or "").strip()
                then = []
                if action_id:
                    then.append({"type": "function", "function_id": action_id})
                if answer_text.strip():
                    then.append({"type": "answer", "text": answer_text.strip()})
                for c in post_conditions:
                    if c.get("operator") == "equals":
                        then.append({"type": "set_fact", "fact": c.get("fact"), "value": c.get("value")})

                rule = {
                    "id": rid.strip(),
                    "module": module.strip(),
                    "rule_group": rule_type.strip(),
                    "description": description.strip(),
                    "priority": int(priority),
                    "active": active,
                    "stop_after_match": stop,
                    "when": {"all": pre_conditions, "any": trigger_conditions},
                    "then": then,
                    "technical_metadata": {
                        "pre_conditions": pre_conditions,
                        "trigger_conditions": trigger_conditions,
                        "post_conditions": post_conditions,
                        "action_function": action_id,
                        "next_success": next_success_value.strip(),
                        "next_failure": next_failure_value.strip(),
                        "editor": "excel_structured_admin_view",
                    },
                }
                # Preserve non-conflicting advanced keys from raw JSON.
                try:
                    raw_rule = json.loads(raw) if raw.strip() else {}
                    for k, v in raw_rule.items():
                        if k not in rule and not str(k).startswith("__"):
                            rule[k] = v
                except Exception:
                    pass
                kb_json.upsert_inference_rule(rule)
                st.success("Regel gespeichert.")
                st.rerun()
            except Exception as e:
                st.error(f"Regel konnte nicht gespeichert werden: {e}")

        if delete_clicked and selected is not None:
            kb_json.delete_inference_rule(selected.get("id"))
            st.warning("Regel gelöscht.")
            st.rerun()

        with st.expander("Wissensbausteine und Funktionen als Hilfe"):
            st.caption("Nutze diese Listen, um technische IDs konsistent zu verwenden. Pre-, Trigger- und Post-Conditions referenzieren immer Fact-IDs aus den Wissensbausteinen.")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Wissensbausteine / Facts**")
                st.write(", ".join(condition_keys[:120]))
            with c2:
                st.markdown("**Funktionen**")
                st.write(", ".join([x for x in function_options if x][:120]))

    with tab_help:
        st.markdown("""
        **Editor-Logik**
        - **Pre-Conditions**: Voraussetzungen, die erfüllt sein müssen, bevor eine Regel sinnvoll greift.
        - **Trigger-Conditions**: konkrete Auslöser, warum diese Regel jetzt ausgeführt wird.
        - **Action / Funktion**: auszuführende Funktion, Antwortbaustein oder technisches Step-Package.
        - **Post-Conditions**: Facts, die nach der Regel gesetzt werden.
        - **Next-Step**: Folgeschritt bei Erfolg oder Fehler.

        Unterstützte Operatoren: `equals`, `not_equals`, `in`, `not_in`, `contains`, `contains_any`, `contains_all`,
        `regex`, `is_unknown`, `is_known`, `is_true`, `is_false`, `greater_than`, `less_than`, `greater_or_equal`, `less_or_equal`. Excel-Kurzformen wie `eq`, `maybe` und `sets` werden akzeptiert und technisch normalisiert.
        """)
        with st.expander("Prioritätsmodell aus Excel"):
            st.dataframe(kb_json.load_technical_excel_priorities(), use_container_width=True, hide_index=True)


def admin_inference_test() -> None:
    render_view_title(
        "Admin · Inferenz-Test",
        "Inferenz-Test",
        "Hier testest du die Inferenzregeln mit manuell eingegebenen Fakten. So kannst du prüfen, welche Regeln matchen, welche Antworten erzeugt werden und ob der Regeltrace plausibel ist.",
    )
    facts_raw = st.text_area("Fakten als JSON", value=json.dumps({"topic": "eduroam", "service": "eduroam", "intent": "setup", "os": "windows", "operating_system": "windows", "internet_available": False}, ensure_ascii=False, indent=2), height=250, key="admin_test_facts")
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
