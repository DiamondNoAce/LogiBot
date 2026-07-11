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


## Globale Bausteine

Die Rule Engine enthält jetzt den Ordner `Rule Engine/global/` mit `global_blocks.json`. Dort liegen dienstübergreifende Bausteine wie Internetverbindung, Benutzerkonto, Betriebssystem, MFA und Campusnetz/VPN. Dienste können diese Bausteine über `required_global_blocks` wiederverwenden. Im Inferenzlauf werden zuerst globale Regeln geprüft, danach fehlende Pflichtinformationen aus globalen Bausteinen abgefragt und anschließend die dienstspezifischen Regeln ausgewertet. Dadurch müssen gemeinsame Themen nicht in jedem Dienst doppelt gepflegt werden.

In der App gibt es dafür die Ansicht `Admin: Globale Bausteine`. Dort können Bausteine bearbeitet und Diensten zugeordnet werden.

## Technische Eduroam-Condition-Matrix

Die Datei `Eduroam_Regeln_technische_Sicht.xlsx` wurde in die Rule Engine übernommen. Daraus wurden zusätzliche technische JSON-Artefakte erzeugt:

```text
Rule Engine/
├── rules/
│   └── eduroam_technical_rules.json
└── technical/
    ├── eduroam_condition_matrix.json
    ├── eduroam_rule_overview.json
    ├── eduroam_preconditions.json
    ├── eduroam_flow.json
    ├── eduroam_functions.json
    └── priority_model.json
```

Die technischen Regeln unterscheiden zwischen:

- `Pre-Conditions`: Voraussetzungen, die erfüllt sein müssen
- `Trigger-Conditions`: Auslöser, warum eine Regel jetzt greift
- `Post-Conditions`: Zielzustände nach erfolgreicher oder fehlgeschlagener Ausführung
- `Next`: nächste Regel bzw. nächster Schritt

Die Inferenz-Engine unterstützt jetzt zusätzlich verschachtelte Conditions mit `all`, `any` und `not` sowie erweiterte Operatoren wie `equals`, `not_equals`, `in`, `not_in`, `contains`, `contains_any`, `regex`, `is_unknown`, `is_known`, `is_true` und `is_false`.

## Regelprüfung

In der App gibt es die neue Ansicht `Admin: Regelprüfung`. Dort wird geprüft, ob:

- Regel-IDs doppelt vorkommen
- Conditions gültige Operatoren verwenden
- verwendete Facts im Fact-Katalog gepflegt sind
- technische `Next`-Verweise plausibel sind
- Entscheidungsnetze auf existierende Knoten zeigen

Diese Prüfung sollte vor dem Austausch des gesamten Ordners `Rule Engine/` ausgeführt werden.

## Wissensmodell-Erweiterung

Dieses Projekt enthält zusätzlich ein aus zwei Wissensmodell-Grafiken abgeleitetes JSON-Modell. Es liegt unter:

```text
Rule Engine/knowledge_model/wissensmodell_gesamtprojekt.json
```

Die neue Ansicht `Admin: Wissensmodell` zeigt die fachliche und technische Gesamtlogik mit Namespaces, Knoten und Verbindungen. Diese Ebene verbessert die Rule Engine, weil wiederkehrende Themen wie Benutzerkonto, Zugangsdaten, Netzwerk-Kontext, MFA und Support als gemeinsame Bausteine über alle Dienste hinweg verwendet werden können.

Nach Änderungen im Rule-Engine-Ordner sollte die Ansicht `Admin: Regelprüfung` genutzt werden, um Regeln, Entscheidungsnetze und Wissensmodell-Verweise zu prüfen.


## Aktualisierung: Wissensmodell v2

Das aktualisierte Wissensmodell trennt den gemeinsamen Wissenskern noch deutlicher von den Dienstpfaden. Neu bzw. stärker modelliert sind:

- `core.source`: Quelle, Anleitung, Setup-/Troubleshooting-Journey.
- `core.credentials`: Benutzername, Passwort, Kennungsformat und Passwortänderungen als gemeinsamer Abhängigkeitspunkt.
- `core.network_context`: Campusnetz, Internet, externes Netz, Firewall/Proxy.
- `core.status_goal`: Zielzustand wie Verbindung erfolgreich, Problem gelöst oder Support nötig.
- `service.mfa.*`: MFA als zeitbasierter Code aus der Authenticator-App; keine Push-Benachrichtigung als Standardannahme.
- `service.vpn.*`: Installation, Client, Profil/Gateway, Login+MFA, Tunnel und interne Ressourcen.
- `service.eduroam.*`: Campus/WLAN-Sichtbarkeit, Profil/CAT, Zertifikat und Verbindung/Internet.

Die daraus abgeleiteten Regeln liegen in `Rule Engine/rules/knowledge_model_v2_cross_service_rules.json`. Die neue strukturierte Sicht liegt in `Rule Engine/knowledge_model/wissensmodell_gesamtprojekt.json`, inklusive der aktualisierten Modellgrafiken im Ordner `Rule Engine/knowledge_model/evidence/`.


## Hohenheim-inspirierter Look

Die Oberfläche wurde optisch an die Website der Universität Hohenheim angenähert. Dazu gehören ein heller Kopfbereich mit Uni-Branding, eine dunkelblaue Navigationsleiste, weiße Inhaltskarten, blaue Akzentlinien und ein einheitliches Farbschema. Die zentralen Styles liegen in `ui/common.py`, die Streamlit-Theme-Werte in `.streamlit/config.toml`.


## Hohenheim-Design und klickbare Kopfnavigation

Die Oberfläche nutzt jetzt einen Hohenheim-inspirierten Header mit eingebundenem Uni-Siegel, dunkelblauer Navigationsleiste und klickbaren Bereichen direkt unter dem Logo-Bereich. Die Navigation synchronisiert sich mit der Sidebar-Auswahl, sodass die Ansichten sowohl links als auch über die Kopfzeile gewechselt werden können.

Wenn die Kopfzeile nicht korrekt angezeigt wird, prüfe, ob der Ordner `assets/` mit der Datei `hohenheim_seal.png` im Projekt enthalten ist.
