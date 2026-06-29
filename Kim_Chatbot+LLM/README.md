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


## Lokales Open-Source-LLM mit Ollama

Das Projekt unterstützt ein kostenloses lokales LLM über **Ollama**. Die LLM-Schicht liegt in `llm/` und wird bewusst getrennt von der Rule Engine gehalten.

Das LLM wird nur für drei Aufgaben genutzt:

1. **Nutzeroberfläche:** Freitext wird in Dienst, System und Schritt bzw. Fakten übersetzt.
2. **Gruppen-Inferenztest:** Folgeantworten werden im Kontext der letzten Rückfrage als neue Fakten interpretiert.
3. **Antwortformulierung:** Die regelbasierte Ausgabe wird verständlicher formuliert.

Die fachliche Entscheidung bleibt immer in `core/inference_engine.py`, `core/rule_engine.py` und `core/decision_graph_engine.py`.

Ollama installieren und Modell laden:

```powershell
ollama pull llama3.2:3b
```

Danach App starten und links in der Sidebar **Ollama nutzen** aktivieren:

```powershell
py -m streamlit run app.py
```

Wenn Ollama nicht erreichbar ist, kann die App weiterhin über den aktivierten Fallback ohne LLM arbeiten.

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

## Update: Excel-nahe Adminsicht und Wissensmodell-Regeln

Diese Version integriert zusätzlich die Dateien `Regeln_aus_Wissensmodell_nach_Eduroam_Struktur.xlsx` und `Adminsicht_LogiBot_Empfehlung.docx`.

Neu in der Oberfläche:

- **Wissensbereiche** statt rein technischer Dienste/Sys­teme.
- **Conditions / Facts** als zentraler Katalog mit technischer Condition-ID, Anzeigename, Wissensbereich, Kategorie, erlaubten Werten und Regelverwendung.
- **Funktionen & Antworten** als eigener Katalog für technische Funktionen, Antwortbausteine und Step-Packages.
- **Regelverwaltung** mit Excel-naher Struktur: Stammdaten, Pre-Conditions, Trigger-Conditions, Action/Funktion, Post-Conditions und Next-Step.
- **Abläufe** als lesbare Regelketten vor dem grafischen Entscheidungsnetz.
- **Wissensmodell** als Referenz- und Navigationsansicht mit Verweisen auf Conditions, Regeln und Funktionen.
- JSON bleibt erhalten, ist aber stärker in technische Vorschauen und Exportbereiche verschoben.

Neue Rule-Engine-Dateien:

```text
Rule Engine/
├── conditions/condition_catalog.json
├── functions/functions_catalog.json
├── flows/flow_catalog.json
├── rules/wissensmodell_excel_rules.json
└── technical/
    ├── Regeln_aus_Wissensmodell_nach_Eduroam_Struktur.xlsx
    ├── wissensmodell_excel_condition_catalog.json
    ├── wissensmodell_excel_rule_overview.json
    ├── wissensmodell_excel_translation_matrix.json
    ├── wissensmodell_excel_flows.json
    ├── wissensmodell_excel_functions.json
    └── wissensmodell_excel_priorities.json
```

Die globale Bausteinlogik bleibt erhalten. Die neuen Excel-Regeln werden zusätzlich geladen und mit den bestehenden JSON-Regeln zusammengeführt.

## Update: Schnelle LLM-Alternative über Groq

Diese Version unterstützt zusätzlich **Groq Cloud** als schnelle LLM-Option. Ollama bleibt als lokale Offline-Variante erhalten, der regelbasierte Fallback bleibt ebenfalls erhalten.

In der Sidebar kann jetzt gewählt werden:

```text
LLM-Anbieter:
- Kein LLM / Fallback
- Ollama lokal
- Groq Cloud
```

Empfohlene Nutzung für Tests:

```text
LLM-Anbieter: Groq Cloud
Groq-Modell: llama-3.1-8b-instant
Fallback ohne LLM: aktiviert
```

### Groq vorbereiten

1. Kostenlosen Groq API-Key in der Groq Console erstellen.
2. API-Key entweder in der Sidebar eintragen oder als Umgebungsvariable setzen.

Windows PowerShell:

```powershell
setx GROQ_API_KEY "dein_api_key"
```

Danach PowerShell/PyCharm/VS Code neu öffnen und die App starten:

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Alternativ kann lokal eine `.env`-Datei im Projektordner angelegt werden:

```text
GROQ_API_KEY=dein_api_key
```

Wichtig: Der API-Key wird nicht in der Rule Engine gespeichert. Wenn er in der Sidebar eingetragen wird, gilt er nur für die laufende App-Sitzung.

### Architekturprinzip bleibt gleich

```text
LLM erkennt und formuliert.
Rule Engine entscheidet.
JSON-Wissensbasis speichert.
```

Groq wird im Projekt an denselben drei Stellen eingesetzt wie Ollama:

1. Freitext-Erkennung in der Nutzeroberfläche.
2. Kontextbasierte Faktenerkennung im Gruppen-Inferenztest.
3. Freundlichere Formulierung regelbasierter Ausgaben.

Neue Dateien:

```text
llm/groq_client.py
llm/fact_extraction.py        # Provider-Router: Ollama oder Groq
llm/response_generation.py    # Provider-Router: Ollama oder Groq
```

## Erweiterung: Robuster Dialog-Fallback ohne LLM

Diese Version enthält zusätzlich eine deterministische Fallback-Erkennung für laufende Dialoge. Sie verbessert den Gruppen-Inferenztest auch dann, wenn kein LLM aktiviert ist.

Neu ist insbesondere:

- kurze Antworten wie „ja“, „nein“, „Jaa kenn ich“ werden im Kontext der letzten Rückfrage interpretiert,
- verlorene Zugangsdaten, Passwort-Reset-Fragen und unbekannte Benutzerkennung führen nicht mehr zu Endlosschleifen,
- „WLAN geht wieder“ kann alte blockierende WLAN-Fakten überschreiben,
- „was ist ein Betriebssystem?“ wird erklärt, statt dieselbe Frage zu wiederholen,
- pro Inferenzantwort wird nur noch eine zentrale Rückfrage angezeigt,
- LLM-Anbieter wie Groq oder Ollama können weiterhin optional zusätzlich genutzt werden.

Die fachliche Entscheidung bleibt weiterhin in der JSON-Rule-Engine. Das LLM oder der Fallback-Parser liefern nur Fakten aus Nutzersprache.

## Update: Groq-Key pro Nutzer in Streamlit Cloud

Die App unterstützt jetzt eine Cloud-freundliche Groq-Nutzung: Wenn der LogiBot über einen Streamlit-Community-Cloud-Link geteilt wird, kann jeder Nutzer in der Sidebar seinen eigenen Groq API-Key einfügen.

```text
LLM-Anbieter: Groq Cloud
Dein Groq API-Key für diese Sitzung: gsk_...
```

Der Key wird nur sitzungsbezogen in `st.session_state` gespeichert und nicht in die Projektdateien geschrieben. Wenn kein Key vorhanden ist, verweist die Sidebar direkt auf die Groq Console und erklärt kurz, wie ein eigener Key erstellt wird.

Links:

- https://console.groq.com/keys
- https://console.groq.com/docs/quickstart

Für App-Betreiber bleibt zusätzlich die Möglichkeit bestehen, `GROQ_API_KEY` als Streamlit Secret oder lokale Umgebungsvariable zu hinterlegen. Für öffentlich geteilte Links ist der benutzereigene Key jedoch sicherer und flexibler.

## Schnellere LLM-Nutzung im Gruppen-Inferenztest

Die App nutzt nun einen Schnellmodus für Groq/Ollama:

1. Erst lokale regelbasierte Faktenerkennung.
2. Nur bei unsicherem Freitext wird Groq/Ollama aufgerufen.
3. Folgeantworten verwenden einen kompakten Prompt ohne komplette Wissensbasis.
4. Die LLM-Antwortformulierung ist separat abschaltbar, damit pro Dialogschritt nicht unnötig zwei LLM-Aufrufe entstehen.

Für Tests über Streamlit Community Cloud empfiehlt sich:

```text
LLM-Modus: Schnell
LLM-Antwortformulierung: Aus
Fallback ohne LLM: Ein
```

## Update: Schrittpakete im Gruppen-Inferenztest werden jetzt interaktiv fortgeführt

Wenn die Inferenz eine `show_steps`-Action erreicht, bleibt der Dialog nicht mehr bei der Ausgabe
`Schrittpaket: ...` stehen. Stattdessen startet automatisch ein Schritt-für-Schritt-Durchlauf des passenden Pakets.

Das gilt nicht nur für eduroam, sondern auch für andere Dienste wie VPN, MFA und Benutzerkonto. Folgeantworten wie
`ja`, `nein`, `hat funktioniert` oder `ich hänge hier` werden während eines aktiven Durchlaufs direkt auf den aktuellen
Anleitungsschritt bezogen. Die Inferenz wird in diesem Moment nicht erneut gestartet, damit nicht wiederholt dasselbe
Schrittpaket ausgegeben wird.

## Update 2026-06-28: Enter-Eingabe und Nutzer-Rückfragen

- In der Nutzeroberfläche nutzt der Modus **Anleitung suchen** jetzt wie die anderen Modi ein Chat-Eingabefeld.
- Die Suche startet mit normalem **Enter**; **STRG+Enter** ist nicht mehr nötig.
- Rückfragen des Nutzers während einer laufenden Inferenz, z. B. „Wie erkenne ich mein Betriebssystem?“, werden als Rückfrage erkannt und nicht mehr als normale Antwort auf die letzte Frage verarbeitet.
- Wenn ein LLM-Anbieter aktiv ist, wird bei solchen Nutzerfragen nicht automatisch der lokale Schnellpfad bevorzugt. Das LLM darf zur Kontextklärung genutzt werden; die Rule Engine entscheidet danach weiterhin regelbasiert.
- Ohne LLM greift ein deterministischer Erklärpfad, z. B. für Betriebssystem, MFA, VPN oder eduroam.

## Update: Nutzeroberfläche, Adminbereich und Tests getrennt

Die Nutzeroberfläche wurde fachlich vereinfacht. Normale Nutzer sehen jetzt nur noch:

- **Problem schildern**: geführter Dialog ohne technische Regel-/Fact-Debugausgaben
- **Anleitung suchen**: direkte Suche nach passenden Schritten und Lösungen
- **Häufige Themen**: Kacheln für typische Anliegen wie eduroam, VPN, MFA, Passwort und Bibliotheksdatenbanken

Die technischen Prüfwerkzeuge wurden in die neue Ansicht **Tests & Diagnose** verschoben:

- Gruppen-Inferenztest mit Fakten, gematchten Regeln und Regeltrace
- Entscheidungsnetz-Test mit Fakten, Pfad und Kantenprüfung
- Regelprüfung
- LLM-Test

Dadurch bleibt die App für Endnutzer verständlich, während Admins und Projektteam weiterhin alle internen Entscheidungen prüfen können.


## Verbesserung: bereits genutzte Dienste

Wenn Nutzer schreiben, dass ein Dienst bereits funktioniert hat und nun nicht mehr geht, wechselt der Dialog direkt in den Troubleshooting-Kontext. Beispiel: „Ich konnte eduroam bis vor einer Woche normal verwenden, jetzt geht es nicht mehr.“ In diesem Fall fragt der Bot nicht erneut nach Basisvoraussetzungen wie Account-Aktivierung, Benutzerkennung oder Passwortkenntnis, sondern nimmt diese als grundsätzlich vorhanden an und prüft gezielt Änderungen bzw. aktuelle Fehlerursachen.

Umgesetzt für:

- eduroam: Passwortänderung, sichtbares Netzwerk, bestehendes Profil und Verbindungsproblem
- VPN: bestehender Client/Profile/MFA-Kontext und aktueller Login-/Tunnelstatus
- MFA: bestehende Einrichtung und aktueller Authenticator-/Code-Status

## Update: eduroam-Troubleshooting bei bereits genutztem Dienst

Wenn Nutzer angeben, dass eduroam vorher bereits funktioniert hat, überspringt der Assistent jetzt die Basisfragen zu Konto, Kürzel, Passwort, WLAN-Adapter und Betriebssystem. Stattdessen wird der Ablauf stärker am tatsächlichen Fehlerbild ausgerichtet:

1. Wurde seit dem letzten erfolgreichen Zugriff das Passwort geändert?
2. Wird `eduroam` aktuell in der WLAN-Liste angezeigt?
3. Kann sich das Gerät mit `eduroam` verbinden?
4. Falls verbunden: besteht anschließend Internetzugriff?

Erst wenn eine Neuinstallation des Profils sinnvoll wird, ist das Betriebssystem wieder relevant. Dadurch wird der Nutzer nicht zu früh in eine Einrichtungsschrittfolge geleitet, obwohl eigentlich ein Troubleshooting-Fall vorliegt.
