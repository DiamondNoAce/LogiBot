# Adminsicht- und Regelmodell-Update

Dieses Update integriert die Dateien `Regeln_vollständig_neu.xlsx` und `Adminsicht_LogiBot_Konzept_verbessert.docx` in das LogiBot-Projekt.

## Umgesetzte Punkte

- Navigation fachlich umbenannt:
  - `Conditions / Facts` → `Wissensbausteine`
  - `Abläufe` → `Abläufe & Netz`
  - `JSON-Dateien` → `Technische JSON-Dateien`
- Wissensbausteine als zentraler Fact-Katalog mit Namespace, erlaubten Werten, Rückfrage bei unknown, Synonymen und Qualitätsregel.
- Funktionen & Antworten als eigener Katalog für Actions, Antwortbausteine und gesetzte Facts.
- Regelverwaltung stärker im Stil der Regel-Excel:
  - Stammdaten
  - Pre-Conditions
  - Trigger-Conditions
  - Action / Funktion
  - Post-Conditions
  - Next-Step
  - eingeklappte JSON-Vorschau
- Abläufe & Netz zeigt lesbare Regelketten vor dem grafischen Entscheidungsnetz.
- Wissensmodell-Navigation verweist nun auf Wissensbausteine, Regeln und Funktionen.
- Neue Excel-Inhalte wurden als JSON in `Rule Engine/technical/` übernommen.
- Neue technische Regeln wurden aus `04_Regelverwaltung` und `05_Regelbedingungen` erzeugt.
- Operatoren `eq`, `maybe` und `sets` werden nun sauber normalisiert.
- Regelvalidierung berücksichtigt den neuen Wissensbaustein-Katalog und meldet keine Fehler/Hinweise.

## Prüfung

- Python-Kompilierung erfolgreich.
- 17 bestehende Tests erfolgreich.
- Rule-Engine-Validierung: 0 Fehler, 0 Hinweise.
