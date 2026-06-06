# Architektur der modularen KIM Rule Engine

Das Projekt ist in klare Schichten aufgeteilt, damit mehrere Personen parallel arbeiten können und die fachliche Regelbasis unabhängig vom Python-Code austauschbar bleibt.

## Schichten

```text
Streamlit UI
  ↓
Dialogmanager / Nutzerzustand
  ↓
LLM-Schicht für Texterkennung und Formulierung optional
  ↓
Rule Engine / Inference Engine / Decision Graph Engine
  ↓
Storage-Schicht
  ↓
Rule Engine/ JSON-Ordner
```

## Ordner

```text
project/
│
├── app.py                         # Einstiegspunkt und Routing
│
├── ui/                            # Alle Streamlit-Ansichten
│   ├── user_view.py               # Nutzeroberfläche
│   ├── admin_services_view.py     # Dienste und Systeme
│   ├── admin_steps_view.py        # Schritte und Lösungen
│   ├── admin_rules_view.py        # Inferenzregeln und Inferenztest
│   ├── admin_graph_view.py        # Entscheidungsnetz-Editor
│   └── admin_import_export_view.py# JSON-/Import-/Export-Sicht
│
├── core/                          # Fachliche Logik
│   ├── rule_engine.py             # Anleitungssuche und Schritt-Erkennung
│   ├── inference_engine.py        # Wenn-Dann-Inferenzregeln
│   ├── decision_graph_engine.py   # Entscheidungsnetze durchlaufen
│   └── dialog_manager.py          # Fortlaufende Dialoge und eduroam-Durchlauf
│
├── storage/                       # Zugriff auf die JSON-Wissensbasis
│   ├── kb_loader.py               # Laden und zentrale Datenzugriffe
│   ├── kb_writer.py               # Schreiboperationen
│   ├── kb_validator.py            # Struktur- und Konsistenzprüfung
│   └── backups.py                 # Backup-Hilfen
│
├── llm/                           # Optionale lokale LLM-Schicht über Ollama
│   ├── ollama_client.py           # Technischer Ollama-Client
│   ├── fact_extraction.py         # Freitext → Fakten
│   └── response_generation.py     # Regelantwort → verständliche Ausgabe
│
├── docs/                          # Word-Anleitungen
└── Rule Engine/                   # Austauschbarer JSON-Regelordner
```

## Vorteil für paralleles Arbeiten

Die Teams können getrennt arbeiten: Oberfläche in `ui/`, Regel- und Inferenzlogik in `core/`, Speicherzugriff in `storage/`, LLM-Anbindung in `llm/` und fachliche Inhalte im Ordner `Rule Engine/`.

Der Ordner `Rule Engine/` bleibt bewusst unabhängig vom Python-Code. Er kann bei Änderungen komplett ersetzt werden, solange die erwartete JSON-Struktur erhalten bleibt.
