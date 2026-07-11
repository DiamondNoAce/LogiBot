from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

APP_TITLE = "IT-Anleitungsassistent"
APP_ICON = "🧠"

# LLM-Defaults
DEFAULT_OLLAMA_MODEL = "llama3.2:1b"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
DEFAULT_MODEL = DEFAULT_OLLAMA_MODEL  # Rückwärtskompatibilität

RULE_ENGINE_DIR = BASE_DIR / "Rule Engine"
