# setup_kb.py
# ============================================================
# Prüft die austauschbare Rule-Engine-Ordnerstruktur.
# Es wird keine SQLite-Datenbank erstellt.
# ============================================================

from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RULE_ENGINE_DIR = BASE_DIR / "Rule Engine"
REQUIRED = [
    "engine.json",
    "constants.json",
    "fact_catalog.json",
    "rules",
    "sources",
    "step_packages",
]


def main() -> None:
    if not RULE_ENGINE_DIR.exists():
        RULE_ENGINE_DIR.mkdir()
        print("Ordner 'Rule Engine' wurde erstellt. Lege dort die JSON-Dateien der Rule Engine ab.")
        return

    missing = [name for name in REQUIRED if not (RULE_ENGINE_DIR / name).exists()]
    if missing:
        print("Rule-Engine-Ordner gefunden, aber folgende Elemente fehlen:")
        for item in missing:
            print(f"- {item}")
    else:
        print("Rule-Engine-Ordner ist vollständig vorhanden.")

    # Optionale Dateien anlegen, falls sie fehlen.
    optional_defaults = {
        "services.json": {"services": []},
        "decision_graphs.json": {"graphs": []},
    }
    for filename, default in optional_defaults.items():
        path = RULE_ENGINE_DIR / filename
        if not path.exists():
            path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Optionale Datei angelegt: {filename}")


if __name__ == "__main__":
    main()
