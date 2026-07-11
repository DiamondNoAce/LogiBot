"""Validierung der JSON-Wissensbasis.

Die Prüfung ist bewusst verständlich gehalten und eignet sich für die Admin-
Ansicht oder für Tests vor dem Austausch des kompletten Rule-Engine-Ordners.

Geprüft werden neben formalen Fehlern jetzt auch Qualitätskriterien, die für
regelbasierte Support-Dialoge wichtig sind:
- Regeln ohne sichtbare Aktion
- Schritte ohne Titel/Anweisung/Lösung
- Abläufe ohne Startpunkt oder ohne Support-Fallback
- Entscheidungsnetze ohne erreichbare Endknoten
- doppelte IDs und ungültige Verweise
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from storage import kb_loader
from core.condition_parser import SUPPORTED_OPERATORS, normalize_operator


Issue = dict[str, Any]


def _issue(issues: list[Issue], severity: str, category: str, message: str, *, ref: str | None = None) -> None:
    issues.append({
        "severity": severity,
        "category": category,
        "message": message,
        "ref": ref or "",
    })


def _collect_fact_keys(catalog: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for section in catalog.values():
        if isinstance(section, dict):
            keys.update(str(k) for k in section.keys())
    return keys


def _iter_conditions(obj: Any):
    if not isinstance(obj, dict):
        return
    if "fact" in obj or "field" in obj:
        yield obj
    for key in ("all", "any"):
        for child in obj.get(key, []) or []:
            yield from _iter_conditions(child)
    child_not = obj.get("not")
    if isinstance(child_not, dict):
        yield from _iter_conditions(child_not)
    elif isinstance(child_not, list):
        for child in child_not:
            yield from _iter_conditions(child)


def _validate_condition(condition: dict[str, Any], rule_id: str, fact_keys: set[str], issues: list[Issue]) -> None:
    fact = str(condition.get("fact") or condition.get("field") or "").strip()
    operator = normalize_operator(condition.get("operator", "equals"))
    if not fact:
        _issue(issues, "error", "Bedingungen", f"Regel {rule_id}: Condition ohne fact/field.", ref=rule_id)
    elif fact_keys and fact not in fact_keys:
        _issue(issues, "warning", "Bedingungen", f"Regel {rule_id}: Fact `{fact}` ist nicht im fact_catalog/Wissensbaustein-Katalog gepflegt.", ref=rule_id)
    if operator not in SUPPORTED_OPERATORS:
        _issue(issues, "warning", "Bedingungen", f"Regel {rule_id}: Operator `{condition.get('operator')}` wird nicht ausdrücklich unterstützt.", ref=rule_id)


def _action_is_user_visible(action: dict[str, Any]) -> bool:
    return str(action.get("type", "")) in {"ask", "answer", "recommend", "redirect_topic", "show_steps", "function", "support_contact"}


def _action_is_support(action: dict[str, Any]) -> bool:
    text = " ".join(str(action.get(k, "")) for k in ["type", "topic", "text", "function_id", "id"]).lower()
    return any(x in text for x in ["support", "service-desk", "servicedesk", "kim it-service", "eskal"])


def _validate_actions(actions: Any, owner_id: str, package_ids: set[str], issues: list[Issue]) -> None:
    if not isinstance(actions, list):
        _issue(issues, "error", "Regelaktionen", f"{owner_id}: then/result muss eine Liste sein.", ref=owner_id)
        return
    if not actions:
        _issue(issues, "warning", "Regelaktionen", f"{owner_id}: Regel ohne Aktion. Diese Regel kann keine Nutzerreaktion erzeugen.", ref=owner_id)
        return
    if not any(isinstance(a, dict) and _action_is_user_visible(a) for a in actions):
        _issue(issues, "warning", "Regelaktionen", f"{owner_id}: Keine nutzerseitig sichtbare Aktion vorhanden.", ref=owner_id)
    for idx, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            _issue(issues, "error", "Regelaktionen", f"{owner_id}: Aktion {idx} ist kein Objekt.", ref=owner_id)
            continue
        typ = str(action.get("type", "")).strip()
        if not typ:
            _issue(issues, "error", "Regelaktionen", f"{owner_id}: Aktion {idx} hat keinen type.", ref=owner_id)
            continue
        if typ == "ask":
            if not action.get("fact"):
                _issue(issues, "error", "Regelaktionen", f"{owner_id}: ask-Aktion ohne fact.", ref=owner_id)
            if not action.get("text") and not action.get("question"):
                _issue(issues, "warning", "Regelaktionen", f"{owner_id}: ask-Aktion ohne Rückfragetext.", ref=owner_id)
        elif typ in {"answer", "recommend", "redirect_topic", "support_contact"}:
            if not action.get("text"):
                _issue(issues, "warning", "Regelaktionen", f"{owner_id}: {typ}-Aktion ohne Text.", ref=owner_id)
        elif typ == "show_steps":
            package_id = str(action.get("step_package_id") or action.get("package_id") or "").strip()
            if not package_id:
                _issue(issues, "error", "Regelaktionen", f"{owner_id}: show_steps ohne step_package_id/package_id.", ref=owner_id)
            elif package_ids and package_id not in package_ids:
                _issue(issues, "error", "Regelaktionen", f"{owner_id}: show_steps verweist auf unbekanntes Schrittpaket `{package_id}`.", ref=owner_id)
        elif typ == "set_fact":
            if not action.get("fact"):
                _issue(issues, "warning", "Regelaktionen", f"{owner_id}: set_fact ohne fact.", ref=owner_id)


def _step_has_text(step: dict[str, Any]) -> bool:
    solution = step.get("solution") or {}
    actions = solution.get("actions", []) if isinstance(solution, dict) else []
    return any(str(step.get(k, "")).strip() for k in ["title", "instruction", "phase"]) or any(str(a).strip() for a in actions)


def _validate_services(services: list[dict[str, Any]], package_ids: set[str], issues: list[Issue]) -> set[str]:
    service_keys: set[str] = set()
    for service in services:
        key = service.get("key")
        if not key:
            _issue(issues, "error", "Dienste", "Ein Dienst hat keinen key.")
            continue
        if key in service_keys:
            _issue(issues, "error", "Dienste", f"Doppelter Dienst-Key: {key}", ref=str(key))
        service_keys.add(str(key))

        systems = service.get("systems", []) or []
        if not systems:
            _issue(issues, "warning", "Dienste", f"Dienst {key}: Keine Systeme/Geräte gepflegt.", ref=str(key))
        system_keys: set[str] = set()
        for system in systems:
            sys_key = system.get("key")
            if not sys_key:
                _issue(issues, "error", "Dienste", f"Dienst {key}: Ein System hat keinen key.", ref=str(key))
                continue
            if sys_key in system_keys:
                _issue(issues, "error", "Dienste", f"Dienst {key}: Doppelter System-Key: {sys_key}", ref=f"{key}/{sys_key}")
            system_keys.add(str(sys_key))

            steps = system.get("steps", []) or []
            if not steps:
                _issue(issues, "warning", "Schritte", f"{key}/{sys_key}: Keine Schritte gepflegt.", ref=f"{key}/{sys_key}")
            step_numbers: set[int] = set()
            for step in steps:
                number = step.get("number")
                ref = f"{key}/{sys_key}/Schritt {number}"
                if number is None:
                    _issue(issues, "error", "Schritte", f"{key}/{sys_key}: Ein Schritt hat keine number.", ref=f"{key}/{sys_key}")
                    continue
                try:
                    number_int = int(number)
                except Exception:
                    _issue(issues, "error", "Schritte", f"{key}/{sys_key}: Ungültige Schrittnummer: {number}", ref=f"{key}/{sys_key}")
                    continue
                if number_int in step_numbers:
                    _issue(issues, "error", "Schritte", f"{key}/{sys_key}: Doppelte Schrittnummer: {number_int}", ref=ref)
                step_numbers.add(number_int)
                if not step.get("title"):
                    _issue(issues, "warning", "Schritte", f"{ref}: Kein Titel gepflegt.", ref=ref)
                if not str(step.get("instruction", "")).strip():
                    _issue(issues, "warning", "Schritte", f"{ref}: Kein Anweisungstext gepflegt.", ref=ref)
                if not step.get("solution"):
                    _issue(issues, "warning", "Schritte", f"{ref}: Keine Lösung gepflegt.", ref=ref)
                if not _step_has_text(step):
                    _issue(issues, "error", "Schritte", f"{ref}: Schritt hat keinen sichtbaren Inhalt.", ref=ref)
                package_id = str(step.get("package_id") or "").strip()
                if package_id and package_ids and package_id not in package_ids:
                    _issue(issues, "warning", "Schritte", f"{ref}: Verweist auf unbekanntes Schrittpaket `{package_id}`.", ref=ref)
    return service_keys


def _validate_step_packages(packages: list[dict[str, Any]], issues: list[Issue]) -> set[str]:
    ids: set[str] = set()
    for package in packages:
        pid = str(package.get("id") or package.get("package_key") or "").strip()
        if not pid:
            _issue(issues, "error", "Schrittpakete", "Ein Schrittpaket hat keine id/package_key.")
            continue
        if pid in ids:
            _issue(issues, "error", "Schrittpakete", f"Doppeltes Schrittpaket: {pid}", ref=pid)
        ids.add(pid)
        steps = package.get("steps", []) or []
        if not steps:
            _issue(issues, "error", "Schrittpakete", f"Schrittpaket {pid}: Keine Schritte gepflegt.", ref=pid)
        for idx, step in enumerate(steps, start=1):
            if isinstance(step, dict):
                text = step.get("instruction") or step.get("text") or step.get("title") or ""
            else:
                text = step
            if not str(text).strip():
                _issue(issues, "warning", "Schrittpakete", f"Schrittpaket {pid}: Schritt {idx} ist leer.", ref=pid)
    return ids


def _validate_global_blocks(blocks: list[dict[str, Any]], fact_keys: set[str], package_ids: set[str], issues: list[Issue]) -> set[str]:
    block_ids: set[str] = set()
    for block in blocks:
        bid = block.get("id")
        if not bid:
            _issue(issues, "error", "Globale Bausteine", "Ein globaler Baustein hat keine id.")
            continue
        if bid in block_ids:
            _issue(issues, "error", "Globale Bausteine", f"Doppelter globaler Baustein: {bid}", ref=str(bid))
        block_ids.add(str(bid))
        for fact_def in block.get("facts", []) or []:
            if not fact_def.get("key"):
                _issue(issues, "error", "Globale Bausteine", f"Globaler Baustein {bid}: Ein Fakt hat keinen key.", ref=str(bid))
            if not fact_def.get("question") and not fact_def.get("optional"):
                _issue(issues, "warning", "Globale Bausteine", f"Globaler Baustein {bid}: Pflicht-Fakt `{fact_def.get('key')}` hat keine Frage.", ref=str(bid))
        for rule in block.get("rules", []) or []:
            rid = str(rule.get("id", f"{bid}.<ohne id>"))
            when = rule.get("when", rule.get("conditions", {}))
            for condition in _iter_conditions(when):
                _validate_condition(condition, rid, fact_keys, issues)
            if "conditions" not in rule and "when" not in rule:
                _issue(issues, "warning", "Bedingungen", f"Globaler Baustein {bid}, Regel {rid}: keine conditions/when gepflegt.", ref=rid)
            actions = rule.get("then", rule.get("result", []))
            if isinstance(actions, dict):
                actions = [actions]
            _validate_actions(actions, f"Globaler Baustein {bid}, Regel {rid}", package_ids, issues)
    return block_ids


def _validate_rules(rules: list[dict[str, Any]], fact_keys: set[str], package_ids: set[str], issues: list[Issue]) -> tuple[set[str], set[str]]:
    rule_ids: set[str] = set()
    original_rule_ids: set[str] = set()
    services_with_rules: set[str] = set()
    services_with_support: set[str] = set()

    for rule in rules:
        rid = rule.get("id")
        if not rid:
            _issue(issues, "error", "Regeln", "Eine Inferenzregel hat keine id.")
            continue
        rid_s = str(rid)
        if rid_s in rule_ids:
            _issue(issues, "error", "Regeln", f"Doppelte Regel-ID: {rid_s}", ref=rid_s)
        rule_ids.add(rid_s)
        tech_meta = rule.get("technical_metadata", {}) or {}
        if tech_meta.get("original_rule_id"):
            original_rule_ids.add(str(tech_meta.get("original_rule_id")))
        if not isinstance(rule.get("when", {}), dict):
            _issue(issues, "error", "Bedingungen", f"Regel {rid_s}: when muss ein Objekt sein.", ref=rid_s)
        if not isinstance(rule.get("then", []), list):
            _issue(issues, "error", "Regelaktionen", f"Regel {rid_s}: then muss eine Liste sein.", ref=rid_s)
        for condition in _iter_conditions(rule.get("when", {})):
            _validate_condition(condition, rid_s, fact_keys, issues)
        actions = rule.get("then", [])
        _validate_actions(actions, f"Regel {rid_s}", package_ids, issues)

        service = str(rule.get("module") or rule.get("service") or "").lower()
        if service and service not in {"general", "global", "dialog_guard", "fallback", "cross_module", "core_router"}:
            services_with_rules.add(service)
            if any(isinstance(a, dict) and _action_is_support(a) for a in actions):
                services_with_support.add(service)
        if any(isinstance(a, dict) and _action_is_support(a) for a in actions):
            services_with_support.add(service)

    for service in sorted(s for s in services_with_rules if s not in services_with_support):
        _issue(issues, "warning", "Support-Fallback", f"Dienst/Modul `{service}` hat Regeln, aber keine eindeutig erkennbare Support-Fallback-Aktion.", ref=service)

    # Prüfe technische Next-Verweise aus Excel-Metadaten.
    allowed_virtual_targets = {
        "ende", "end", "passende regel nach klärung", "passende regel nach klaerung",
        "os-spezifische setup-regel", "service_specific_chain", "affected_service_troubleshooting",
        "core_clarify_topic", "support_or_wait_until_on_campus", "eduroam_setup_os_specific",
        "eduroam_recreate_profile_or_retry", "vpn_troubleshoot_client", "vpn_auth_or_profile_fix",
        "vpn_reconnect_or_support", "mfa_troubleshoot_code", "support_or_permission_check",
    }
    for rule in rules:
        rid = str(rule.get("id"))
        tech_meta = rule.get("technical_metadata", {}) or {}
        for label in ("next_success", "next_failure"):
            target = tech_meta.get(label)
            if not target:
                continue
            raw_targets = [t.strip() for t in str(target).replace(" oder ", "/").split("/") if t.strip()]
            for t in raw_targets:
                if t.lower() in allowed_virtual_targets:
                    continue
                if t not in original_rule_ids and f"tech.{t}" not in rule_ids:
                    _issue(issues, "warning", "Regelverweise", f"Technische Regel {rid}: {label} verweist auf `{t}`, dazu wurde keine Regel-ID gefunden.", ref=rid)
    return rule_ids, original_rule_ids


def _validate_knowledge_model(fact_keys: set[str], block_ids: set[str], issues: list[Issue]) -> None:
    model = kb_loader.load_knowledge_model()
    if not model or model.get("id") == "missing":
        _issue(issues, "warning", "Wissensmodell", "Kein Wissensmodell gefunden oder id=missing.")
        return
    km_nodes = model.get("nodes", []) or []
    km_edges = model.get("edges", []) or []
    km_node_ids = {str(n.get("id")) for n in km_nodes if n.get("id")}
    for node in km_nodes:
        if not node.get("id"):
            _issue(issues, "error", "Wissensmodell", "Ein Knoten hat keine id.")
        for fk in node.get("fact_keys", []) or []:
            if fact_keys and str(fk) not in fact_keys:
                _issue(issues, "warning", "Wissensmodell", f"Wissensmodell-Knoten {node.get('id')}: Fact `{fk}` ist nicht im fact_catalog gepflegt.", ref=str(node.get("id")))
        block = node.get("global_block")
        if block and block not in block_ids:
            _issue(issues, "warning", "Wissensmodell", f"Wissensmodell-Knoten {node.get('id')}: global_block `{block}` existiert nicht in global_blocks.json.", ref=str(node.get("id")))
    for edge in km_edges:
        if edge.get("source") not in km_node_ids:
            _issue(issues, "error", "Wissensmodell", f"Edge {edge.get('id')} verweist auf unbekannte Quelle {edge.get('source')}.", ref=str(edge.get("id")))
        if edge.get("target") not in km_node_ids:
            _issue(issues, "error", "Wissensmodell", f"Edge {edge.get('id')} verweist auf unbekanntes Ziel {edge.get('target')}.", ref=str(edge.get("id")))


def _validate_graphs(graphs: list[dict[str, Any]], service_keys: set[str], fact_keys: set[str], package_ids: set[str], issues: list[Issue]) -> None:
    graph_ids: set[str] = set()
    terminal_types = {"solution", "step", "end", "terminal", "support"}
    for graph in graphs:
        gid = str(graph.get("id") or "<ohne id>")
        if not graph.get("id"):
            _issue(issues, "error", "Entscheidungsnetze", "Ein Entscheidungsnetz hat keine id.")
        if gid in graph_ids:
            _issue(issues, "error", "Entscheidungsnetze", f"Doppelte Graph-ID: {gid}", ref=gid)
        graph_ids.add(gid)
        nodes = graph.get("nodes", []) or []
        edges = graph.get("edges", []) or []
        node_ids = {node.get("id") for node in nodes if node.get("id")}
        start_id = graph.get("start_node_id") or "start"
        if not nodes:
            _issue(issues, "error", "Entscheidungsnetze", f"Graph {gid}: Keine Knoten gepflegt.", ref=gid)
            continue
        if start_id not in node_ids:
            _issue(issues, "error", "Entscheidungsnetze", f"Graph {gid}: Startknoten `{start_id}` existiert nicht.", ref=gid)

        adjacency: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            eid = str(edge.get("id") or f"{edge.get('source')}->{edge.get('target')}")
            source = edge.get("source")
            target = edge.get("target")
            if source not in node_ids:
                _issue(issues, "error", "Entscheidungsnetze", f"Graph {gid}: Edge {eid} verweist auf unbekannte Quelle {source}.", ref=gid)
            if target not in node_ids:
                _issue(issues, "error", "Entscheidungsnetze", f"Graph {gid}: Edge {eid} verweist auf unbekanntes Ziel {target}.", ref=gid)
            if source in node_ids and target in node_ids:
                adjacency[str(source)].append(str(target))
            for condition in _iter_conditions(edge.get("condition", {})):
                _validate_condition(condition, f"Graph {gid}/Edge {eid}", fact_keys, issues)

        reachable: set[str] = set()
        if start_id in node_ids:
            q: deque[str] = deque([str(start_id)])
            while q:
                node_id = q.popleft()
                if node_id in reachable:
                    continue
                reachable.add(node_id)
                for nxt in adjacency.get(node_id, []):
                    if nxt not in reachable:
                        q.append(nxt)
        for node_id in sorted(str(n) for n in node_ids if str(n) not in reachable):
            _issue(issues, "warning", "Entscheidungsnetze", f"Graph {gid}: Knoten `{node_id}` ist vom Startknoten nicht erreichbar.", ref=gid)

        reachable_terminal = False
        has_support = False
        for node in nodes:
            node_id = str(node.get("id") or "")
            ntype = str(node.get("type") or "").lower()
            if ntype == "question":
                if not node.get("question"):
                    _issue(issues, "warning", "Entscheidungsnetze", f"Graph {gid}: Frageknoten `{node_id}` hat keinen Fragetext.", ref=gid)
                if not node.get("fact_key") and not node.get("fact"):
                    _issue(issues, "warning", "Entscheidungsnetze", f"Graph {gid}: Frageknoten `{node_id}` hat keinen fact_key.", ref=gid)
            if ntype == "step":
                service = str(node.get("service_key") or node.get("topic") or "").lower()
                if service and service not in service_keys:
                    _issue(issues, "warning", "Entscheidungsnetze", f"Graph {gid}: Step-Knoten `{node_id}` verweist auf unbekannten Dienst `{service}`.", ref=gid)
                package_id = str(node.get("step_package_id") or node.get("package_id") or "").strip()
                if package_id and package_ids and package_id not in package_ids:
                    _issue(issues, "warning", "Entscheidungsnetze", f"Graph {gid}: Step-Knoten `{node_id}` verweist auf unbekanntes Schrittpaket `{package_id}`.", ref=gid)
            if ntype in terminal_types or not adjacency.get(node_id):
                if node_id in reachable:
                    reachable_terminal = True
                text = " ".join(str(node.get(k, "")) for k in ["type", "label", "solution_text", "description"]).lower()
                if any(x in text for x in ["support", "service-desk", "servicedesk", "eskal"]):
                    has_support = True
        if not reachable_terminal:
            _issue(issues, "error", "Entscheidungsnetze", f"Graph {gid}: Kein erreichbarer End-/Lösungsknoten vorhanden.", ref=gid)
        if not has_support:
            _issue(issues, "warning", "Support-Fallback", f"Graph {gid}: Kein klarer Support-/Fallback-Knoten erkennbar.", ref=gid)


def _validate_flows(flows: list[dict[str, Any]], issues: list[Issue]) -> None:
    flow_ids: set[str] = set()
    for flow in flows:
        fid = str(flow.get("id") or "<ohne id>")
        if not flow.get("id"):
            _issue(issues, "error", "Abläufe", "Ein Ablauf hat keine id.")
        if fid in flow_ids:
            _issue(issues, "error", "Abläufe", f"Doppelte Ablauf-ID: {fid}", ref=fid)
        flow_ids.add(fid)
        steps = flow.get("steps", []) or []
        if not steps:
            _issue(issues, "error", "Abläufe", f"Ablauf {fid}: Keine Schritte gepflegt.", ref=fid)
            continue
        seen_steps: set[int] = set()
        has_start = False
        has_support_path = False
        for raw_step in steps:
            try:
                number = int(raw_step.get("step"))
            except Exception:
                number = -1
            if number == 1:
                has_start = True
            if number in seen_steps:
                _issue(issues, "error", "Abläufe", f"Ablauf {fid}: Doppelte Step-Nummer {number}.", ref=fid)
            seen_steps.add(number)
            if not str(raw_step.get("condition", "")).strip():
                _issue(issues, "warning", "Abläufe", f"Ablauf {fid}/Step {number}: Keine Bedingung gepflegt.", ref=fid)
            if not str(raw_step.get("action", "")).strip():
                _issue(issues, "warning", "Abläufe", f"Ablauf {fid}/Step {number}: Keine Aktion gepflegt.", ref=fid)
            path_text = " ".join(str(raw_step.get(k, "")) for k in ["if_true", "if_false", "if_false_unknown", "action", "note"]).lower()
            if any(x in path_text for x in ["support", "fallback", "eskal", "service-desk", "servicedesk"]):
                has_support_path = True
        if not has_start:
            _issue(issues, "error", "Abläufe", f"Ablauf {fid}: Kein Startschritt mit step=1 vorhanden.", ref=fid)
        if not has_support_path:
            _issue(issues, "warning", "Support-Fallback", f"Ablauf {fid}: Kein klarer Support-/Fallback-Pfad erkennbar.", ref=fid)


def validate_knowledge_base() -> dict[str, Any]:
    issues: list[Issue] = []

    fact_catalog = kb_loader.load_fact_catalog()
    fact_keys = _collect_fact_keys(fact_catalog)
    try:
        fact_keys.update(str(x.get("key")) for x in kb_loader.load_condition_catalog(active_only=False) if x.get("key"))
    except Exception:
        pass

    packages = kb_loader.load_step_packages()
    package_ids = _validate_step_packages(packages, issues)
    services = kb_loader.get_services(active_only=False)
    service_keys = _validate_services(services, package_ids, issues)

    global_blocks = kb_loader.load_global_blocks(active_only=False)
    block_ids = _validate_global_blocks(global_blocks, fact_keys, package_ids, issues)
    for service in services:
        for required in service.get("required_global_blocks", []) or []:
            if required not in block_ids:
                _issue(issues, "error", "Globale Bausteine", f"Dienst {service.get('key')}: required_global_blocks verweist auf unbekannten globalen Baustein {required}.", ref=str(service.get("key")))

    rules = kb_loader.load_inference_rules(active_only=False)
    _validate_rules(rules, fact_keys, package_ids, issues)
    _validate_knowledge_model(fact_keys, block_ids, issues)
    _validate_graphs(kb_loader.load_decision_graphs(active_only=False), service_keys, fact_keys, package_ids, issues)
    _validate_flows(kb_loader.load_flow_catalog(active_only=False), issues)

    errors = [i["message"] for i in issues if i.get("severity") == "error"]
    warnings = [i["message"] for i in issues if i.get("severity") == "warning"]
    infos = [i["message"] for i in issues if i.get("severity") == "info"]

    by_category: dict[str, dict[str, int]] = {}
    for issue in issues:
        cat = str(issue.get("category") or "Sonstiges")
        sev = str(issue.get("severity") or "info")
        by_category.setdefault(cat, {"error": 0, "warning": 0, "info": 0, "total": 0})
        by_category[cat][sev] = by_category[cat].get(sev, 0) + 1
        by_category[cat]["total"] += 1

    quality_score = 100
    quality_score -= min(60, len(errors) * 10)
    quality_score -= min(35, len(warnings) * 2)
    quality_score = max(0, quality_score)

    automatic_checks = [
        "Doppelte IDs in Diensten, Regeln, Schrittpaketen, Abläufen und Graphen",
        "Regeln ohne Aktion oder ohne sichtbare Nutzerreaktion",
        "Ask-/Show-Steps-/Support-Aktionen mit fehlenden Pflichtfeldern",
        "Schritte ohne Titel, Anweisung oder Lösung",
        "Schrittpakete ohne Schritte oder mit leeren Einträgen",
        "Abläufe ohne Startschritt oder ohne Support-/Fallback-Pfad",
        "Entscheidungsnetze ohne Startknoten, erreichbaren Endknoten oder Support-Fallback",
        "Unbekannte Fact-Keys, Operatoren und technische Next-Verweise",
    ]

    return {
        "valid": not errors,
        "quality_score": quality_score,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "issues": issues,
        "by_category": by_category,
        "automatic_checks": automatic_checks,
        "summary": f"{len(errors)} Fehler, {len(warnings)} Hinweise · Qualitätswert {quality_score}/100",
    }
