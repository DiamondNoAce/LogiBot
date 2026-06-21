# Systemarchitektur — LogiBot

Diese Datei beschreibt die Systemarchitektur von LogiBot und enthält ein grafisches Diagramm (Mermaid), das die Hauptkomponenten, Datenflüsse und Deploy-Optionen zeigt. Die Architektur basiert auf der vorhandenen Projektstruktur (Streamlit-UI, core, storage, llm, Rule Engine).

## Mermaid-Diagramm

Füge den folgenden Block in eine Markdown-Datei ein oder nutze mermaid.live, um das Diagramm zu rendern:

```mermaid name=architecture.mmd
%% Systemarchitektur LogiBot (Container / Komponenten)
graph LR
  Browser[Browser<br/>(User)] --> Streamlit[Streamlit App<br/>(app.py)]

  subgraph "Streamlit App"
    UI[UI (ui/*.py)]
    DM[Dialog Manager<br/>(dialog_manager.py)]
    IE[Inference Engine<br/>(inference_engine.py)]
    RE[Rule Engine JSON<br/>(Rule Engine/)]
    RG[Rule Engine Executor<br/>(rule_engine.py)]
    DG[Decision Graph Engine<br/>(decision_graph_engine.py)]
    LLM[LLM Adapter<br/>(ollama_client.py)]
    FE[Fact Extraction<br/>(fact_extraction.py)]
    RG2[Response Generation<br/>(response_generation.py)]
    STG[Storage Layer<br/>(kb_loader/kb_writer/kb_validator/backups)]
    UI --> DM
    DM --> FE
    FE --> DM
    DM --> IE
    IE --> RG
    RG --> RE
    IE --> DG
    DM --> LLM
    LLM --> RG2
    DM --> STG
    STG --> RE
  end

  Streamlit -->|Optional: HTTP| API[Optional API (FastAPI) für Core]
  API -->|calls| DM

  subgraph "Infrastruktur"
    NGINX[Reverse Proxy / TLS (nginx)]
    DOCKER[Container Host / Docker Compose / Kubernetes]
    OBJECT[Object Storage / S3 (Backups)]
    MON[Monitoring (Prometheus / Grafana)]
    LOGS[Logging / Audit-Logs]
  end

  NGINX --> Streamlit
  NGINX --> API
  Streamlit --> DOCKER
  API --> DOCKER
  STG --> OBJECT
  DOCKER --> MON
  DOCKER --> LOGS
  LLM -->|local| OLLAMA[Ollama server (optional, lokal)]
  LLM -->|remote| LLMAPI[Remote LLM API]

  classDef infra fill:#f3f4f6,stroke:#999,stroke-width:1px;
  class NGINX,DOCKER,OBJECT,MON,LOGS infra;
```

## Kurzbeschreibung

- Browser: Nutzerinteraktion (Freitext, Admin-Oberflächen).
- Streamlit App: UI-Module + Dialog-Manager; startet Inferenzläufe.
- Dialog Manager: Session-Handling, Fakten-Merge, Orchestrierung.
- Inference / Rule Engine: Führt JSON-Regeln aus, erzeugt Trace/Next.
- Decision Graph Engine: Interaktive Schritt-für-Schritt-Flows (z.B. eduroam).
- LLM-Schicht: Optionale Unterstützung für Fact-Extraction und Antwort-Generierung (Ollama lokal oder Remote-API).
- Storage: Lädt/speichert Rule Engine, validiert KB, erstellt Backups (S3 möglich).
- Infrastruktur: Reverse Proxy, Container-Host, Monitoring und Logs.

## Hinweise zur Nutzung

- Du kannst den Mermaid-Code direkt in `README.md` oder `ARCHITEKTUR.md` einfügen, GitHub rendert Mermaid-Diagramme in Markdown-Previews nicht immer; nutze in diesem Fall https://mermaid.live zum Exportieren als PNG/SVG.
- Wenn du möchtest, kann ich zusätzlich eine gerenderte SVG/PNG-Datei erzeugen und in das Repository hochladen.

## Nächste Schritte (optional)
- Ich kann eine gerenderte SVG/PNG des Diagramms erzeugen und zum Repo hinzufügen.
- Oder ich erstelle eine GitHub Action, die JSON-Schema-Validierung für den Rule Engine-Ordner ausführt.

---

Datei erstellt von GitHub Copilot (Assistant) — ARCHITEKTUR.md
