"""Backup-Hilfen für den Rule-Engine-Ordner."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from storage.kb_loader import KB_DIR


def create_rule_engine_backup(target_dir: Path | None = None) -> Path:
    """Erstellt eine vollständige Kopie des aktuellen Rule-Engine-Ordners."""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target_dir = target_dir or (KB_DIR.parent / "Rule Engine Backups")
    target_dir.mkdir(parents=True, exist_ok=True)
    backup_path = target_dir / f"Rule Engine Backup {stamp}"
    shutil.copytree(KB_DIR, backup_path)
    return backup_path
