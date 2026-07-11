# LLM-Setup für LogiBot

Das Projekt kann ohne LLM, mit lokalem Ollama oder mit Groq Cloud laufen.

## Variante 1: Ohne LLM

In der Sidebar:

```text
LLM-Anbieter: Kein LLM / Fallback
```

Die App nutzt dann nur die regelbasierten Erkennungs- und Inferenzfunktionen.

## Variante 2: Ollama lokal

Vorteil: kostenlos und offline. Nachteil: je nach Rechner langsamer.

```powershell
ollama pull llama3.2:1b
py -m streamlit run app.py
```

In der Sidebar:

```text
LLM-Anbieter: Ollama lokal
Ollama-Modell: llama3.2:1b
```

## Variante 3: Groq Cloud

Vorteil: meist deutlich schneller. Nachteil: API-Key und Internetverbindung nötig.

Abhängigkeiten installieren:

```powershell
py -m pip install -r requirements.txt
```

API-Key setzen:

```powershell
setx GROQ_API_KEY "dein_api_key"
```

Danach Terminal neu öffnen und starten:

```powershell
py -m streamlit run app.py
```

In der Sidebar:

```text
LLM-Anbieter: Groq Cloud
Groq-Modell: llama-3.1-8b-instant
Fallback ohne LLM: aktiviert
```

Alternativ kannst du den Groq API-Key direkt in der Sidebar eingeben. Er wird nicht in JSON-Dateien gespeichert.

## Fachliches Prinzip

Das LLM erkennt nur Nutzereingaben und formuliert Antworten. Die Entscheidung, welche Regel greift, trifft weiterhin die Rule Engine.

## Groq-Key direkt durch Nutzer in Streamlit Cloud

Für eine öffentliche Nutzung über einen Streamlit-Community-Cloud-Link muss nicht zwingend ein gemeinsamer API-Key im Projekt hinterlegt werden. Jeder Nutzer kann in der Sidebar seinen eigenen Groq API-Key eintragen:

```text
LLM-Anbieter: Groq Cloud
Dein Groq API-Key für diese Sitzung: gsk_...
Groq-Modell: llama-3.1-8b-instant
```

Der benutzereigene Key wird nur im `st.session_state` der aktuellen Browsersitzung gehalten. Er wird nicht in `os.environ`, nicht in JSON-Dateien, nicht in GitHub und nicht in die ZIP-Datei geschrieben. Dadurch eignet sich die App besser für geteilte Streamlit-Cloud-Links.

Wenn kein Key vorhanden ist, zeigt die Sidebar direkt eine kurze Anleitung und Links zur Groq Console:

```text
1. Groq Console öffnen und anmelden oder kostenlos registrieren.
2. API Keys öffnen.
3. Create API Key wählen.
4. Key kopieren und in der Sidebar einfügen.
```

Direkte Links:

- Groq API Keys: https://console.groq.com/keys
- Groq Quickstart: https://console.groq.com/docs/quickstart

Für interne Demos kann alternativ weiterhin ein App-weiter Key als Streamlit Secret gesetzt werden:

```toml
GROQ_API_KEY = "dein_groq_api_key"
```

Bei öffentlich geteilten Links ist der benutzereigene Key vorzuziehen, damit kein gemeinsamer Schlüssel verteilt oder missbraucht wird.

## Performance-Modus für Groq/Ollama

Ab dieser Version gibt es in der Sidebar einen **LLM-Modus**:

- **Schnell**: Der lokale regelbasierte Parser prüft zuerst die Eingabe. Groq/Ollama wird nur aufgerufen, wenn die lokale Erkennung unsicher ist. Folgeantworten wie „ja“, „nein“, „Windows“, „WLAN geht wieder“ oder „Passwort vergessen“ werden dadurch meist ohne API-Aufruf verarbeitet.
- **Ausgewogen**: Nutzt ebenfalls kompakte Prompts für Folgeantworten, greift aber etwas häufiger auf das LLM zurück.
- **Qualität**: Nutzt stärker den vollständigen LLM-Kontext. Das kann genauer sein, ist aber langsamer.

Für den Gruppen-Inferenztest ist die empfohlene Einstellung:

```text
LLM-Anbieter: Groq Cloud
LLM-Modus: Schnell
LLM-Antwortformulierung nutzen: Aus
Fallback ohne LLM nutzen: Ein
```

Die Antwortformulierung ist bewusst optional. Wenn sie aktiviert ist, entsteht nach der Faktenerkennung häufig ein zweiter LLM-Aufruf, wodurch die zweite und dritte Dialogantwort spürbar langsamer werden können.

## Nutzer-Rückfragen im Schnellmodus

Im Schnellmodus wird der lokale Parser weiterhin zuerst ausgeführt. Neu ist jedoch: Wenn die Eingabe als echte Rückfrage erkannt wird, z. B. „Wie erkenne ich das?“ bei der Betriebssystemfrage, wird bei aktivem LLM ein LLM-Aufruf zugelassen. Dadurch wird verhindert, dass die App eine Rückfrage versehentlich als Antwort interpretiert oder mit einem beliebigen Schritt weitermacht.

Ohne LLM bleibt der Fallback stabil: Bei der Betriebssystemfrage erklärt die App, was ein Betriebssystem ist, und fragt danach erneut nach Windows, macOS, Linux, Android oder iOS/iPadOS.
