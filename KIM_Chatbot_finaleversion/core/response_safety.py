"""Antwort-Nachbearbeitung für nutzerfreundliche und datenschutzsichere Chat-Ausgaben.

Die Rule Engine bleibt fachlich zuständig. Dieses Modul räumt nur Formulierungen auf:
- keine Aufforderung, Passwörter oder konkrete Benutzerkennungen in den Chat zu schreiben
- keine internen Begriffe wie Rule Engine/Gruppen-Inferenztest in Nutzerantworten
- konsistenter Du-Stil
- technische/holprige Begriffe entschärfen
- einfache Duplikate entfernen
"""
from __future__ import annotations

import re
from typing import Iterable




def _strip_leading_greeting(text: str) -> str:
    """Entfernt generische Einstiegsbegrüßungen aus Botantworten.

    Die Nutzeroberfläche zeigt einen laufenden Dialog. Deshalb soll die optionale
    LLM-Formulierung nicht jede einzelne Nachricht mit "Hallo" beginnen.
    """
    out = str(text or "").strip()
    out = re.sub(
        r"^(?:hallo(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß-]+)?|hi|hey|guten\s+(?:tag|morgen|abend)|servus|moin)\s*[!,.:-]?\s+",
        "",
        out,
        flags=re.IGNORECASE,
    ).strip()
    out = re.sub(r"^(?:hallo|hi|hey)\s*[!,.:-]\s*", "", out, flags=re.IGNORECASE).strip()
    if out.startswith("ich "):
        out = "Ich " + out[4:]
    if out.startswith("du "):
        out = "Du " + out[3:]
    return out


def _dedupe_sentences(text: str) -> str:
    """Entfernt direkt wiederholte identische Sätze/Zeilen, ohne Inhalt hart zu verändern."""
    if not text:
        return text
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    cleaned: list[str] = []
    seen_recent: set[str] = set()
    for chunk in chunks:
        part = chunk.strip()
        if not part:
            continue
        key = re.sub(r"\s+", " ", part.lower())
        # Nur kurze Wiederholungen im direkten Kontext entfernen, damit Listen nicht beschädigt werden.
        if key in seen_recent:
            continue
        cleaned.append(part)
        seen_recent.add(key)
        if len(seen_recent) > 6:
            seen_recent = set(list(seen_recent)[-3:])
    # Bei Listen nicht alles in Fließtext zwingen.
    joined = "\n".join(cleaned) if any(line.strip().startswith("-") for line in text.splitlines()) else " ".join(cleaned)
    return joined.strip()


def _replace_many(text: str, replacements: Iterable[tuple[str, str]]) -> str:
    out = text
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def sanitize_user_response(text: str) -> str:
    """Bereinigt eine Botantwort für die normale Nutzeroberfläche."""
    if text is None:
        return ""
    out = str(text)

    # Keine internen Begriffe/Debug-Sprache in Nutzerantworten.
    out = _replace_many(out, [
        ("Um den Gruppen-Inferenztest zu durchführen", "Um die Fehlersuche fortzusetzen"),
        ("Um den Gruppen-Inferenztest durchzuführen", "Um die Fehlersuche fortzusetzen"),
        ("Um den Gruppen-Inferenztest zu durchlaufen", "Um die Fehlersuche fortzusetzen"),
        ("Gruppen-Inferenztest", "Fehlersuche"),
        ("Die Rule Engine hat mir gesagt, dass", "Ich benötige noch"),
        ("Die Rule Engine hat bereits entschieden.", ""),
        ("Rule Engine", "Assistent"),
        ("regelbasierte Ausgabe", "Antwort"),
        ("Regelbasierte Ausgabe", "Antwort"),
        ("Account-/Passwortpfad", "Zugangsdaten- oder Passwortklärung"),
        ("Account-/IDM-Verwaltung", "Account-Verwaltung/IDM"),
        ("Führe Funktion aus:", ""),
        ("Funktion ausführen:", ""),
        ("function_id", "Funktion"),
    ])

    # Konsistenter Du-Stil. Einfach gehalten, damit die Semantik stabil bleibt.
    out = re.sub(r"\bSie\b", "du", out)
    out = re.sub(r"\bIhnen\b", "dir", out)
    out = re.sub(r"\bIhrem\b", "deinem", out)
    out = re.sub(r"\bIhren\b", "deinen", out)
    out = re.sub(r"\bIhrer\b", "deiner", out)
    out = re.sub(r"\bIhre\b", "deine", out)
    out = re.sub(r"\bIhr\b", "dein", out)
    out = re.sub(r"\bKönnen Sie\b", "Kannst du", out)
    out = re.sub(r"\bkönnen Sie\b", "kannst du", out)

    # Niemals konkrete private Zugangsdaten im Chat anfordern.
    privacy_patterns = [
        (r"Kannst du mir bitte dein(?:en)? Hohenheimer (?:Benutzernamen|Benutzername|Kürzel|Kuerzel|Benutzerkennung) (?:nennen|mitteilen|sagen)\??",
         "Kennst du dein Hohenheimer Kürzel bzw. deine Benutzerkennung? Bitte gib sie hier nicht ein."),
        (r"Kannst du mir bitte sagen, was dein(?:e|en)? Hohenheimer (?:Benutzerkennung|Benutzername|Benutzernamen|Kürzel|Kuerzel) ist\??",
         "Prüfe bitte nur, ob du deine Hohenheimer Benutzerkennung kennst. Bitte gib sie hier nicht ein."),
        (r"Kannst du mir bitte dein(?:e|en)? (?:Kürzel|Kuerzel|Benutzerkennung|Benutzernamen|Benutzername) nennen\??",
         "Kennst du dein Kürzel bzw. deine Hohenheimer Benutzerkennung? Bitte gib sie hier nicht ein."),
        (r"Kannst du mir bitte dein Passwort nennen\??",
         "Kennst du dein Hohenheimer Passwort bzw. funktioniert die Anmeldung damit? Bitte gib dein Passwort hier nicht ein."),
        (r"Kannst du mir bitte dein Hohenheimer Passwort nennen\??",
         "Kennst du dein Hohenheimer Passwort bzw. funktioniert die Anmeldung damit? Bitte gib dein Passwort hier nicht ein."),
        (r"Kannst du mir bitte mitteilen, ob du dein Hohenheimer Passwort kennst\??",
         "Kennst du dein Hohenheimer Passwort? Bitte gib es hier nicht ein."),
        (r"Kannst du mir bitte mitteilen, wie du dich bei der Universität Hohenheim identifizierst\??",
         "Prüfe bitte nur, ob du deine Hohenheimer Benutzerkennung kennst. Bitte gib sie hier nicht ein."),
        (r"Kannst du mir bitte dein(?:e|en)? Hohenheimer Zugangsdaten .*?\?",
         "Kennst du deine Hohenheimer Zugangsdaten? Bitte gib Benutzerkennung oder Passwort hier nicht ein."),
    ]
    for pattern, replacement in privacy_patterns:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE | re.DOTALL)

    # Einzelne problematische Fragmente entschärfen.
    out = re.sub(r"Kannst du mir bitte dein Hohenheimer Kürzel bzw\. deine Hohenheimer Benutzerkennung (?:nennen|mitteilen|sagen)\??", "Kennst du dein Hohenheimer Kürzel bzw. deine Benutzerkennung? Bitte gib sie hier nicht ein.", out, flags=re.IGNORECASE)
    out = re.sub(r"Kannst du mir bitte dein Hohenheimer Kürzel oder deine Hohenheimer Benutzerkennung (?:nennen|mitteilen|sagen)\??", "Kennst du dein Hohenheimer Kürzel bzw. deine Benutzerkennung? Bitte gib sie hier nicht ein.", out, flags=re.IGNORECASE)
    out = re.sub(r"Kannst du mir bitte sagen, ob du dein Hohenheimer Kürzel kennst\??", "Kennst du dein Hohenheimer Kürzel? Bitte gib es hier nicht ein.", out, flags=re.IGNORECASE)
    out = re.sub(r"Kannst du mir bitte sagen, ob du dein Hohenheimer Kürzel bzw\. deine Hohenheimer Benutzerkennung kennst\??", "Kennst du dein Hohenheimer Kürzel bzw. deine Benutzerkennung? Bitte gib sie hier nicht ein.", out, flags=re.IGNORECASE)
    out = re.sub(r"Benutzerkennung und Passwort sind gemeinsame Voraussetzungen.*?geklärt werden\.", "Falls die Anmeldung mit Benutzerkennung und Passwort nicht funktioniert, kläre zuerst die Zugangsdaten oder setze das Passwort zurück.", out, flags=re.IGNORECASE | re.DOTALL)

    # Keine falsche Bezeichnung "Kennwort" für Benutzerkennung.
    out = out.replace("ein separates Kennwort, das du von uns erhalten hast", "dein Hohenheimer Kürzel bzw. deine Benutzerkennung")
    out = out.replace("separates Kennwort", "separate Benutzerkennung")

    # Überflüssige Begrüßungen und Doppelungen glätten.
    out = _strip_leading_greeting(out)
    out = re.sub(r"^(Hallo!\s*){2,}", "Hallo! ", out.strip())
    out = re.sub(r"Hallo!\s*Hallo!", "Hallo!", out)
    out = re.sub(r"\s+", " ", out).strip() if "\n" not in out else re.sub(r"[ \t]+", " ", out).strip()
    out = _dedupe_sentences(out)

    # Nach der Du-Umstellung ggf. Satzanfänge korrigieren.
    out = out.replace("du hast", "Du hast") if out.startswith("du hast") else out
    return out.strip()
