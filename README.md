# KIM JSON Rule Engine Projekt

Dieses Projekt nutzt **keine SQLite-Datenbank** mehr. Die gesamte Regelbasis liegt in einem austauschbaren Ordner:

```text
Rule Engine/
├── engine.json
├── constants.json
├── fact_catalog.json
├── services.json                 # UI-Struktur, aus Step Packages ableitbar
├── decision_graphs.json           # grafische Entscheidungsnetze
├── rules/
│   ├── core_router_rules.json
│   ├── eduroam_rules.json
│   ├── vpn_rules.json
│   └── ...
├── step_packages/
│   ├── eduroam_steps.json
│   ├── vpn_steps.json
│   └── ...
└── sources/
    ├── source_index.json
    ├── eduroam_sources.json
    └── ...
```

Der Vorteil: Wenn eine neue Version der Rule Engine entsteht, kann der Ordner **Rule Engine** einfach ersetzt werden. Die App liest Regeln, Quellen und Schrittpakete zur Laufzeit wieder ein.

## Link zum Testserver
...

## Start

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Optional mit Ollama:

```powershell
ollama pull llama3.2:3b
```

## Ansichten

- **Nutzeroberfläche**: Freitext eingeben, Regel-Engine oder Inferenz testen und eduroam-Schritt-für-Schritt-Durchlauf starten.
- **Admin · Dienste & Systeme**: Service-Struktur für die UI pflegen.
- **Admin · Schritte & Lösungen**: Anleitungsschritte und Hilfetexte bearbeiten.
- **Admin · Inferenzregeln**: Regeln aus dem Ordner `Rule Engine/rules/` bearbeiten.
- **Admin · Entscheidungsnetz**: Grafische Entscheidungsnetze als Knoten und Pfade bearbeiten.
- **Admin · JSON-Dateien**: Aggregierte JSON-Dateien technisch prüfen und herunterladen.
- **Admin · Inferenz-Test**: Fakten manuell eingeben und Regeltrace prüfen.

## Interaktive Tests

In der Nutzeroberfläche können der **Gruppen-Inferenztest** und der **Entscheidungsnetz-Test** jetzt als fortlaufender Dialog genutzt werden:

1. Erste Freitexteingabe machen.
2. Die App erkennt Fakten und führt Regeln bzw. Entscheidungsnetz aus.
3. Falls Informationen fehlen, kann unten eine weitere Antwort eingegeben werden.
4. Neue Fakten werden mit den bisherigen Fakten zusammengeführt.
5. Bei eduroam startet automatisch ein Schritt-für-Schritt-Durchlauf der Installationsanleitung.

Dadurch lässt sich eine Anleitung nicht nur einmalig testen, sondern vollständig durchspielen.

## Rule Engine ersetzen

1. App schließen.
2. Den Ordner `Rule Engine` sichern oder umbenennen.
3. Neue Rule Engine als Ordner mit dieser Struktur einfügen.
4. App starten.
5. Optional ausführen:

```powershell
py setup_kb.py
```

Die App erstellt automatisch `services.json` und `decision_graphs.json`, falls diese fehlen. Wenn `services.json` fehlt, versucht die App eine UI-Struktur aus den Step Packages abzuleiten.

## Hinweise

- Es wird **kein Python-Code** aus Admin-Eingaben generiert.
- Die App interpretiert die JSON-Regeln zur Laufzeit.
- Beim Speichern werden Backups im Ordner `Rule Engine/backups/` angelegt.
- Quellen sollten als echte URLs in den Dateien unter `Rule Engine/sources/` gepflegt werden.


## Update: Interaktive Tests fortführen

Im Gruppen-Inferenztest und Entscheidungsnetz-Test wird eine bestehende Sitzung jetzt fortgeführt, statt bei jeder Eingabe neu zu starten. Sobald eine Inferenz- oder Graph-Sitzung aktiv ist, wird die Eingabe als weitere Antwort interpretiert. Kurze Antworten wie `Ja`, `Nein` oder `mein Benutzerkonto ist aktiviert` werden im Kontext der zuletzt gestellten Rückfrage als Fakten gespeichert.

Beispiel:

1. Eingabe: `Ich möchte eduroam unter Windows installieren`
2. System fragt: `Ist dein Hohenheimer Benutzerkonto bereits aktiviert?`
3. Weitere Antwort: `Ja, mein Benutzerkonto ist aktiviert`
4. Die vorhandenen Fakten bleiben erhalten und die Inferenz läuft mit `account_activated = true` weiter.
