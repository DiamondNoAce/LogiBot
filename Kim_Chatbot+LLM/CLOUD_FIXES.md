# Streamlit-Cloud-Fixes

Diese Version enthält Anpassungen, damit der LogiBot auf Streamlit Community Cloud stabiler läuft.

## Geänderte Stellen

- `config.py`
  - `RULE_ENGINE_DIR` wird nun absolut ausgehend vom Projektordner gebildet.
  - Dadurch ist der Pfad unabhängiger vom aktuellen Arbeitsordner der Cloud-Umgebung.

- `core/dialog_manager.py`
  - Der eduroam-Schritt-für-Schritt-Durchlauf wird nicht mehr bei jeder Folgeantwort neu gestartet, wenn bereits ein Durchlauf aktiv ist.
  - Das verhindert, dass der Gruppen-Inferenztest nach mehreren Eingaben wieder auf einen früheren Zustand zurückspringt.
  - Der Fakten-Merge ist robuster gegen leere oder unbekannte Werte.
  - Auch der Entscheidungsnetz-Test startet den eduroam-Durchlauf nicht mehr erneut, wenn bereits ein Durchlauf aktiv ist.

- `ui/user_view.py`
  - Die Eingabefelder im Gruppen-Inferenztest und Entscheidungsnetz-Test verwenden nun dynamische Keys.
  - Nach dem Absenden wird das Eingabefeld sauber neu erzeugt.
  - Leere Eingaben werden abgefangen und nicht mehr an die Inferenzlogik übergeben.

- `requirements.txt`
  - Die Streamlit-Abhängigkeiten sind mit einer Obergrenze `<2.0` versehen, damit die Cloud nicht versehentlich eine inkompatible Major-Version installiert.

## Hinweise für Streamlit Community Cloud

- Das GitHub-Repository muss diese ZIP-Version vollständig enthalten.
- Der Ordner `Rule Engine/` muss mit allen Unterordnern in GitHub liegen.
- Startdatei für Streamlit Community Cloud: `app.py`.
- Ollama funktioniert in Streamlit Community Cloud normalerweise nicht lokal. Für die Cloud-Demo sollte `Ollama nutzen` ausgeschaltet bleiben oder der Fallback aktiv sein.


## Ergänzung v2 – ModuleNotFoundError auf Streamlit Cloud

- `app.py` ergänzt den eigenen App-Ordner nun explizit zu `sys.path`. Dadurch bleiben lokale Projektmodule wie `ui`, `core`, `storage` und `llm` auch dann importierbar, wenn Streamlit die App aus einer Unterordnerstruktur startet.
- Dieses ZIP ist bewusst flach gepackt: `app.py` und `requirements.txt` liegen direkt im ZIP-Hauptverzeichnis. Für GitHub sollte der Inhalt genauso in die Repository-Wurzel hochgeladen werden.
