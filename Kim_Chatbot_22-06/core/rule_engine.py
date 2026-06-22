# rule_engine.py
# ============================================================
# Kleine JSON-basierte Rule Engine für konkrete Anleitungen.
# Nutzt die austauschbare Rule-Engine-Ordnerstruktur und sucht Dienst/System/Schritt.
# ============================================================

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from storage import kb_loader as kb_json


def norm(text: Any) -> str:
    return str(text).lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


@dataclass
class RecognitionResult:
    service_key: str = "unknown"
    system_key: str = "unknown"
    step_number: Optional[int] = None
    confidence: str = "niedrig"
    reason: str = ""


def detect_service(text: str) -> str:
    t = norm(text)
    services = kb_json.get_services(active_only=True)
    best_key = "unknown"
    best_score = 0
    for service in services:
        score = 0
        key = norm(service.get("key", ""))
        name = norm(service.get("name", ""))
        if key and key in t:
            score += 5
        if name and name in t:
            score += 4
        # einfache Synonyme aus Beschreibung
        desc = norm(service.get("description", ""))
        for token in re.findall(r"[a-z0-9_]+", key + " " + name + " " + desc):
            if len(token) >= 5 and token in t:
                score += 1
        if score > best_score:
            best_score = score
            best_key = service.get("key", "unknown")
    return best_key


def detect_system(text: str, service_key: str) -> str:
    t = norm(text)
    systems = kb_json.get_systems(service_key, active_only=True) if service_key != "unknown" else kb_json.get_systems(active_only=True)
    available = {str(s.get("key", "")) for s in systems}

    def choose(preferred: str, aliases: list[str]) -> str:
        for key in [preferred] + aliases:
            if key in available:
                return key
        return preferred

    if any(x in t for x in ["windows", "win11", "win10"]):
        return choose("windows", [])
    # "pc" ist nur dann eindeutig, wenn es in der Rule Engine als eigenes System existiert.
    if "pc" in t and "pc" in available:
        return "pc"
    if any(x in t for x in ["macos", "mac os", "macbook", "apple", "osx", "mac"]):
        return choose("macos", ["mac"])
    if "linux" in t:
        return choose("linux", [])
    if "android" in t:
        return choose("android", [])
    if "ipad" in t or "ipados" in t:
        return choose("ipados", ["ios"])
    if "ios" in t or "iphone" in t:
        return choose("ios", ["ipados"])
    if "chromeos" in t or "chromebook" in t:
        return choose("chromeos", [])
    if len(systems) == 1:
        return systems[0].get("key", "unknown")
    return "unknown"


def match_step(text: str, service_key: str, system_key: str) -> tuple[Optional[int], str, int]:
    t = norm(text)
    steps = kb_json.get_steps(service_key, system_key, active_only=True)
    best_step = None
    best_reason = ""
    best_score = 0
    for step in steps:
        score = 0
        fields = [step.get("phase", ""), step.get("title", ""), step.get("instruction", "")]
        for kw in step.get("keywords", []):
            if norm(kw) in t:
                score += 8
        for field in fields:
            for token in re.findall(r"[a-z0-9_]+", norm(field)):
                if len(token) >= 4 and token in t:
                    score += 1
        for rule in step.get("rules", []):
            if norm(rule.get("intent", "")) in t:
                score += 2
            for kw in rule.get("keywords", []):
                if norm(kw) in t:
                    score += 10
        if score > best_score:
            best_score = score
            best_step = int(step.get("number"))
            best_reason = f"Bester Keyword-Treffer: {step.get('title')}"
    return best_step, best_reason, best_score


def recognize(text: str) -> RecognitionResult:
    service_key = detect_service(text)
    system_key = detect_system(text, service_key)
    step_number = None
    reason = ""
    score = 0
    if service_key != "unknown" and system_key != "unknown":
        step_number, reason, score = match_step(text, service_key, system_key)
    confidence = "hoch" if score >= 10 else "mittel" if score >= 4 else "niedrig"
    return RecognitionResult(service_key, system_key, step_number, confidence, reason)


def get_solution_for_recognition(rec: RecognitionResult) -> Optional[dict[str, Any]]:
    if rec.service_key == "unknown" or rec.system_key == "unknown" or rec.step_number is None:
        return None
    solution = kb_json.get_solution(rec.service_key, rec.system_key, rec.step_number)
    step = kb_json.get_step(rec.service_key, rec.system_key, rec.step_number)
    service = kb_json.get_service(rec.service_key)
    system = kb_json.get_system(rec.service_key, rec.system_key)
    if not solution or not step:
        return None
    return {
        "service": service,
        "system": system,
        "step": step,
        "solution": solution,
        "recognition": rec,
    }
