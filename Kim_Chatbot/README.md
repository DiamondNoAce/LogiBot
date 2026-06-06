# KIM JSON Rule Engine – modulare Projektstruktur

Dieses Projekt nutzt eine JSON-basierte Rule Engine. Die gesamte fachliche Regelbasis liegt im austauschbaren Ordner `Rule Engine/`. Die Python-App ist so modularisiert, dass mehrere Personen parallel an unterschiedlichen Bereichen arbeiten können.

## Projektstruktur

```text
project/
│
├── app.py
│
├── ui/
│   ├── user_view.py
│   ├── admin_services_view.py
│   ├── admin_steps_view.py
│   ├── admin_rules_view.py
│   ├── admin_graph_view.py
│   └── admin_import_export_view.py
│
├── core/
│   ├── rule_engine.py
│   ├── inference_engine.py
│   ├── decision_graph_engine.py
│   └── dialog_manager.py
│
├── storage/
│   ├── kb_loader.py
│   ├── kb_writer.py
│   ├── kb_validator.py
│   └── backups.py
│
├── llm/
│   ├── ollama_client.py
│   ├── fact_extraction.py
│   └── response_generation.py
│
├── docs/
│   ├── Installationsanleitung.docx
│   └── Bedienungsanleitung.docx
│
└── Rule Engine/
```

## Start

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Optional mit Ollama:

```powershell
ollama pull llama3.2:3b
```

## Wichtiges Architekturprinzip

Die App generiert keinen Python-Code aus Admin-Eingaben. Admins bearbeiten Dienste, Systeme, Schritte, Lösungen, Regeln und Entscheidungsnetze über die Oberfläche. Gespeichert wird alles als JSON im Ordner `Rule Engine/`. Die Python-Rule-Engine interpretiert diese JSON-Dateien zur Laufzeit.

## Rule Engine ersetzen

1. App schließen.
2. Den Ordner `Rule Engine/` sichern oder umbenennen.
3. Neue Rule Engine als Ordner mit gleicher Struktur einfügen.
4. App starten.
5. Optional prüfen:

```powershell
py setup_kb.py
```

## Paralleles Arbeiten

- UI-Team: `ui/*.py`
- Rule-Engine-Team: `core/*.py`
- Knowledge-Team: `Rule Engine/**/*.json`
- Storage/Validierung: `storage/*.py`
- LLM-Team: `llm/*.py`
- Doku-Team: `docs/`, `README.md`, `ARCHITEKTUR.md`
