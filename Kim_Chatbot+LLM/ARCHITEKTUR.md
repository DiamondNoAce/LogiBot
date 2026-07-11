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


## Globale Bausteine

Die Rule Engine enthält jetzt den Ordner `Rule Engine/global/` mit `global_blocks.json`. Dort liegen dienstübergreifende Bausteine wie Internetverbindung, Benutzerkonto, Betriebssystem, MFA und Campusnetz/VPN. Dienste können diese Bausteine über `required_global_blocks` wiederverwenden. Im Inferenzlauf werden zuerst globale Regeln geprüft, danach fehlende Pflichtinformationen aus globalen Bausteinen abgefragt und anschließend die dienstspezifischen Regeln ausgewertet. Dadurch müssen gemeinsame Themen nicht in jedem Dienst doppelt gepflegt werden.

In der App gibt es dafür die Ansicht `Admin: Globale Bausteine`. Dort können Bausteine bearbeitet und Diensten zugeordnet werden.

## Erweiterung: technische Condition-Matrix

Die Eduroam-Regeln wurden zusätzlich aus der Excel-Datei `Eduroam_Regeln_technische_Sicht.xlsx` in eine technische Regelstruktur übersetzt. Dadurch besitzt die Rule Engine nicht nur einfache Wenn-Dann-Regeln, sondern eine nachvollziehbare Trennung aus Pre-Conditions, Trigger-Conditions, Post-Conditions und Next-Verweisen.

Die technische Matrix liegt in `Rule Engine/technical/`; die daraus abgeleiteten ausführbaren Regeln liegen in `Rule Engine/rules/eduroam_technical_rules.json`. Die Datei kann durch eine aktualisierte Version ersetzt oder neu generiert werden, ohne die Python-Inferenzlogik zu ändern.

Die globalen, dienstübergreifenden Bausteine bleiben erhalten. Der Inferenzablauf ist jetzt:

1. Globale Blocker-Regeln prüfen.
2. Technische dienstspezifische Regeln ausführen.
3. Falls keine spezifische Regel passt, fehlende globale Pflichtinformationen abfragen.
4. Fallback-Regeln nutzen.

Damit blockieren globale Bausteine keine spezifischen Troubleshooting-Fälle mehr, z. B. „eduroam verbunden, aber kein Internet“.

## Erweiterung: Wissensmodell mit Namespaces

Die aktuelle Version enthält zusätzlich eine semantische Wissensmodell-Schicht, die aus den beiden bereitgestellten Wissensmodell-Grafiken abgeleitet wurde. Diese Schicht liegt unter:

```text
Rule Engine/knowledge_model/
├── wissensmodell_gesamtprojekt.json
└── evidence/
```

Das Wissensmodell trennt zwischen einem gemeinsamen Kern und dienstspezifischen Bereichen:

```text
core.*              Gemeinsamer Wissenskern: Account, Gerät, Netzwerk, Zugangsdaten, Auth-Status
service.mfa.*       MFA-spezifische Zustände: App, Recovery, Challenge, Freigabe
service.eduroam.*   eduroam-spezifische Zustände: WLAN sichtbar, Profil, Zertifikat, Verbindung
service.vpn.*       VPN-spezifische Zustände: Client, Endpoint, Auth, Tunnel, Ressourcen
service.support.*   Support und Eskalation
```

Dadurch müssen gemeinsame Logiken wie Benutzerkonto, Passwort, Netzwerk-Kontext oder MFA nicht mehrfach in eduroam, VPN und Drucker modelliert werden. Die Inferenz nutzt diese Ebene für globale Bausteine, Cross-Service-Regeln und Entscheidungsnetze.

Neu ist außerdem die Admin-Ansicht:

```text
Admin: Wissensmodell
```

Dort werden Namespaces, Knoten, Fact-Keys, Verbindungen und eine vereinfachte Graph-Vorschau angezeigt.

## Verbesserte Inferenz durch das Wissensmodell

Die Inferenz berücksichtigt nun zusätzlich:

- blockierende Account-Zustände, z. B. gesperrt oder nicht aktiviert
- gemeinsame Zugangsdaten-Logik für eduroam, VPN und MFA
- Netzwerk-Kontext: Campus, zuhause, fremdes Netz, VPN
- MFA-Zustände: App vorhanden, Recovery verfügbar, Challenge bestätigt
- VPN-Zustände: Client installiert, Endpoint erreichbar, Tunnel verbunden, interne Ressourcen erreichbar
- eduroam-Zustände: WLAN sichtbar, Profil/Zertifikat geprüft, Verbindung ohne Internet

Die Regelprüfung validiert auch das Wissensmodell und prüft, ob alle dort referenzierten Fact-Keys im `fact_catalog.json` vorhanden sind.


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

## Erweiterung: Fachliche Adminsicht nach Excel-Struktur

Die Adminsicht wurde um eine fachliche Ebene ergänzt. Ziel ist, dass Admins Regeln nicht mehr über sichtbares WHEN/THEN-JSON pflegen müssen, sondern über die aus der Excel abgeleitete Struktur:

```text
Stammdaten
Pre-Conditions
Trigger-Conditions
Action / Funktion
Post-Conditions
Next-Step
Technische Vorschau
```

Die technische Übersetzung bleibt weiterhin JSON-basiert. Beim Speichern erzeugt die Oberfläche automatisch eine Inferenzregel mit `when`, `then` und `technical_metadata`.

Zusätzlich gibt es nun eigene Kataloge für:

- Conditions / Facts
- Funktionen & Antwortbausteine
- Lesbare Abläufe

Diese Kataloge ergänzen den austauschbaren Ordner `Rule Engine/` und können weiterhin komplett versioniert oder ersetzt werden.

## Ergänzung: LLM-Provider-Schicht mit Groq

Die LLM-Schicht unterstützt nun zwei Anbieter:

- `llm/ollama_client.py` für lokale Offline-Tests mit Ollama.
- `llm/groq_client.py` für schnellere Cloud-Inferenz über Groq.

Die Module `llm/fact_extraction.py` und `llm/response_generation.py` dienen als Provider-Router. Dadurch müssen Nutzeroberfläche und Dialogmanager nicht wissen, ob Ollama oder Groq verwendet wird. Die Rule Engine bleibt deterministisch und entscheidet weiterhin ausschließlich anhand der JSON-Regeln.

## Dialog-Fallback-Schicht

Zusätzlich zur optionalen LLM-Schicht gibt es jetzt `core/fallback_fact_extraction.py`.

Ablauf ohne LLM:

```text
Nutzerantwort
  ↓
core/fallback_fact_extraction.py
  ↓
kontextbezogene Fakten
  ↓
core/inference_engine.py
  ↓
JSON-Regeln + dialog_guard_rules.json
  ↓
eine nächste Rückfrage oder konkrete Empfehlung
```

Die Datei `Rule Engine/rules/dialog_guard_rules.json` enthält frühe Schutzregeln für häufige Dialogprobleme, z. B. Passwort-Reset, unbekannte Benutzerkennung, MFA-Code-Status, Bibliotheksdatenbanken/VPN und Begriffserklärungen. Diese Regeln werden über `engine.json` direkt nach den globalen Bausteinen ausgeführt.

## Ergänzung: Sitzungsbezogener Groq-Key für Cloud-Nutzer

Für Streamlit Community Cloud wurde die Groq-Anbindung so angepasst, dass ein Nutzer seinen eigenen API-Key direkt in der Sidebar eintragen kann. Der Key wird nur in `st.session_state["session_groq_api_key"]` gehalten und nicht in `os.environ` geschrieben. Das ist wichtig, weil Umgebungsvariablen im Cloud-Prozess appweit gelten können, während `st.session_state` pro Browsersitzung getrennt ist.

Priorität der Key-Auflösung in `llm/groq_client.py`:

```text
1. explizit übergebener API-Key
2. benutzereigener Key aus st.session_state
3. lokale oder serverseitige Umgebungsvariable GROQ_API_KEY
4. Streamlit Secret GROQ_API_KEY
```

Wenn kein Groq-Key verfügbar ist, deaktiviert die Sidebar die Groq-LLM-Nutzung für diese Sitzung und nutzt den regelbasierten Fallback. Zusätzlich wird ein Hilfebereich mit Links zur Groq Console und einer kurzen Schritt-für-Schritt-Anleitung angezeigt.

## Update: Trennung von Nutzeroberfläche und Diagnosewerkzeugen

Die Oberfläche ist jetzt stärker nach Rollen getrennt:

```text
Nutzeroberfläche
├── Problem schildern
├── Anleitung suchen
└── Häufige Themen

Tests & Diagnose
├── Gruppen-Inferenztest
├── Entscheidungsnetz-Test
├── Regelprüfung
└── LLM-Test

Adminbereich
├── Wissensbereiche
├── Conditions / Facts
├── Funktionen & Antworten
├── Regelverwaltung
├── Abläufe
├── Entscheidungsnetz
├── Wissensmodell
├── Globale Bausteine
└── JSON-Dateien
```

Gruppen-Inferenztest und Entscheidungsnetz-Test wurden nicht entfernt. Sie sind jetzt in `ui/diagnostics_view.py` gebündelt und nutzen weiterhin die gleichen Kernfunktionen aus `core/dialog_manager.py`. Die produktive Nutzeroberfläche nutzt dieselbe Rule-Engine-Logik, zeigt aber keine technischen Details wie Fact-JSON, Regeltraces oder Kantenprüfungen.


## Dialoglogik für bereits genutzte Dienste

Die Datei `core/fallback_fact_extraction.py` erkennt Formulierungen wie „hat bisher funktioniert“, „konnte ich vorher verwenden“, „geht nicht mehr“ oder „bis vor einer Woche“. Daraus werden `service_previously_used`, `service_previously_worked` und `skip_initial_prerequisites` gesetzt. Zusätzlich werden die gemeinsamen Grundvoraussetzungen als vorhanden markiert, damit die Inferenz nicht unnötig bei Account- oder Zugangsdatenfragen startet.

Die Datei `Rule Engine/rules/dialog_guard_rules.json` enthält dazu frühe Guard-Regeln, die vor den technischen Dienstregeln laufen und eine passende erste Troubleshooting-Frage stellen.

## Update: fachlicher eduroam-Troubleshooting-Flow

Für den Fall `service_previously_used=true` wurde die Dialoglogik angepasst. Die Rule Engine setzt bei früher funktionierendem eduroam die Basisvoraussetzungen als plausibel vorhanden und führt nicht mehr über den normalen Erstinstallationspfad. Die neuen Dialog-Guard-Regeln prüfen zuerst Passwortänderung, Sichtbarkeit, Verbindungsstatus und Internetzugriff. Betriebssystemabhängige Schrittpakete werden erst relevant, wenn eine Profil-Neueinrichtung fachlich sinnvoll ist.
