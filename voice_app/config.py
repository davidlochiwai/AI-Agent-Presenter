from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = ROOT / ".env"
_preexisting_api_key = os.environ.get("RETELL_API_KEY", "").strip()
load_dotenv(_ENV_PATH, override=True)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "1" if default else "0").lower()
    return raw in {"1", "true", "yes", "on"}


RETELL_API_KEY = _env("RETELL_API_KEY")
RETELL_AGENT_ID = _env("RETELL_AGENT_ID")
PUBLIC_BASE_URL = _env("PUBLIC_BASE_URL").rstrip("/")
if PUBLIC_BASE_URL.endswith("/mcp"):
    PUBLIC_BASE_URL = PUBLIC_BASE_URL[: -len("/mcp")].rstrip("/")
APP_HOST = _env("APP_HOST", "127.0.0.1")
APP_PORT = int(_env("APP_PORT", "8787") or "8787")
VERIFY_RETELL_SIGNATURE = _bool("VERIFY_RETELL_SIGNATURE", True)
AUTO_TUNNEL = _bool("AUTO_TUNNEL", True)
NGROK_AUTHTOKEN = _env("NGROK_AUTHTOKEN")
N8N_SESSION_WEBHOOK_URL = _env("N8N_SESSION_WEBHOOK_URL")
N8N_DELIVER_NEXT_WEBHOOK_URL = _env("N8N_DELIVER_NEXT_WEBHOOK_URL")
N8N_PUBLIC_WEBHOOK_URL = _env("N8N_PUBLIC_WEBHOOK_URL").rstrip("/")
N8N_AUTO_TUNNEL = _bool("N8N_AUTO_TUNNEL", False)
N8N_WEBHOOK_TOKEN = _env("N8N_WEBHOOK_TOKEN")
N8N_BRIDGE_URL = _env("N8N_BRIDGE_URL").rstrip("/")
DIRECTOR_PUBLIC_URL = (_env("DIRECTOR_PUBLIC_URL") or PUBLIC_BASE_URL).rstrip("/")
DIRECTOR_AUTO_TUNNEL = _bool(
    "DIRECTOR_AUTO_TUNNEL",
    AUTO_TUNNEL or N8N_AUTO_TUNNEL,
)
_director_env_token = _env("DIRECTOR_WEBHOOK_TOKEN")
DIRECTOR_WEBHOOK_TOKEN = (
    _director_env_token or N8N_WEBHOOK_TOKEN or secrets.token_urlsafe(32)
)
SAMPLE_DECK_PATH = ROOT / "data" / "sample_talk.pptx"
SAMPLE_SCRIPT_PATH = ROOT / "data" / "script.xlsx"
_qa_knowledge_dir = Path(_env("QA_KNOWLEDGE_DIR", "data/knowledge_sources")).expanduser()
QA_KNOWLEDGE_DIR = _qa_knowledge_dir if _qa_knowledge_dir.is_absolute() else ROOT / _qa_knowledge_dir
SAMPLE_KNOWLEDGE_PATH = QA_KNOWLEDGE_DIR / "knowledge.xlsx"
AZURE_OPENAI_ENDPOINT = _env("AZURE_OPENAI_ENDPOINT").rstrip("/")
AZURE_OPENAI_API_KEY = _env("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = _env("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_CHAT_DEPLOYMENT = _env("AZURE_OPENAI_CHAT_DEPLOYMENT")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = _env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
QDRANT_URL = _env("QDRANT_URL", "http://127.0.0.1:6333").rstrip("/")
QDRANT_COLLECTION = _env("QDRANT_COLLECTION", "presenter_knowledge")
QA_AUTO_INDEX = _bool("QA_AUTO_INDEX", True)
QA_ALWAYS_SELECT_SLIDE = _bool("QA_ALWAYS_SELECT_SLIDE", True)


def _int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# Primary-monitor desktop layout for the PowerPoint and AIRA app windows.
PRESENTER_SPLIT_LAYOUT = _bool("PRESENTER_SPLIT_LAYOUT", True)
PRESENTER_SLIDE_RATIO = max(0.5, min(0.8, _float("PRESENTER_SLIDE_RATIO", 0.67)))


# Silence after a line before the next spoken_text. Also used as the Retell reminder
# unless RETELL_REMINDER_TRIGGER_MS is set.
N8N_LOCAL_PORT = max(1, min(65535, _int("N8N_LOCAL_PORT", 5678)))
SLIDE_PAUSE_MS = max(0, _int("SLIDE_PAUSE_MS", 800))
_reminder = _env("RETELL_REMINDER_TRIGGER_MS")
RETELL_REMINDER_TRIGGER_MS = max(0, int(_reminder) if _reminder else SLIDE_PAUSE_MS)
RETELL_REMINDER_MAX_COUNT = max(1, _int("RETELL_REMINDER_MAX_COUNT", 50))
QA_TOP_K_KNOWLEDGE = max(1, min(12, _int("QA_TOP_K_KNOWLEDGE", 6)))
QA_TOP_K_SLIDES = max(1, min(8, _int("QA_TOP_K_SLIDES", 3)))
QA_CHUNK_SIZE = max(300, min(4000, _int("QA_CHUNK_SIZE", 1200)))
QA_CHUNK_OVERLAP = max(0, min(QA_CHUNK_SIZE // 2, _int("QA_CHUNK_OVERLAP", 180)))
QA_EMBED_BATCH_SIZE = max(1, min(64, _int("QA_EMBED_BATCH_SIZE", 16)))
QA_MAX_ANSWER_CHARS = max(80, min(1200, _int("QA_MAX_ANSWER_CHARS", 420)))
QA_MAX_COMPLETION_TOKENS = max(200, min(4000, _int("QA_MAX_COMPLETION_TOKENS", 1200)))
QA_AZURE_TIMEOUT_S = max(3.0, min(18.0, _float("QA_AZURE_TIMEOUT_S", 12.0)))
QA_MIN_ANSWER_CONFIDENCE = max(0.0, min(1.0, _float("QA_MIN_ANSWER_CONFIDENCE", 0.35)))
QA_MIN_SLIDE_CONFIDENCE = max(0.0, min(1.0, _float("QA_MIN_SLIDE_CONFIDENCE", 0.45)))


def n8n_bridge_url(public_base: str = "") -> str:
    """Return the bridge address n8n should call.

    A local n8n container uses host.docker.internal. Cloud n8n falls back to
    the app's public tunnel.
    """
    if N8N_BRIDGE_URL:
        return N8N_BRIDGE_URL
    base = public_base.rstrip("/")
    return f"{base}/api/bridge" if base else ""


def n8n_deliver_next_url() -> str:
    if N8N_DELIVER_NEXT_WEBHOOK_URL:
        return N8N_DELIVER_NEXT_WEBHOOK_URL.rstrip("/")
    session = N8N_SESSION_WEBHOOK_URL.rstrip("/")
    if session.endswith("/presenter/session"):
        return session[: -len("/presenter/session")] + "/presenter/deliver-next"
    return ""


def n8n_handle_question_url() -> str:
    if session := N8N_SESSION_WEBHOOK_URL.rstrip("/"):
        if session.endswith("/presenter/session"):
            return session[: -len("/presenter/session")] + "/presenter/handle-question"
    deliver = n8n_deliver_next_url()
    if deliver.endswith("/presenter/deliver-next"):
        return deliver[: -len("/presenter/deliver-next")] + "/presenter/handle-question"
    return ""

_env_token = _env("PRESENTER_TOOL_TOKEN")
PRESENTER_TOOL_TOKEN = _env_token or secrets.token_urlsafe(24)
USED_PROJECT_ENV_OVER_PROCESS = bool(
    _preexisting_api_key and RETELL_API_KEY and _preexisting_api_key != RETELL_API_KEY
)


def _upsert_env_value(text: str, name: str, value: str) -> str:
    line = f"{name}={value}"
    prefix = f"{name}="
    alt = f"{name} ="
    lines = text.splitlines()
    found = False
    out: list[str] = []
    for raw in lines:
        if raw.startswith(prefix) or raw.startswith(alt):
            out.append(line)
            found = True
        else:
            out.append(raw)
    if not found:
        if out and out[-1] != "":
            out.append("")
        out.append(line)
    return "\n".join(out) + "\n"


def persist_env_value(name: str, value: str) -> None:
    """Write one .env key without touching the rest of the file."""
    env_path = ROOT / ".env"
    if env_path.exists():
        current = env_path.read_text(encoding="utf-8")
    else:
        example = ROOT / ".env.example"
        current = example.read_text(encoding="utf-8") if example.exists() else ""
    env_path.write_text(_upsert_env_value(current, name, value), encoding="utf-8")


def persist_generated_token() -> None:
    """Keep generated or migrated service tokens stable across restarts."""
    if not _env_token:
        persist_env_value("PRESENTER_TOOL_TOKEN", PRESENTER_TOOL_TOKEN)
    if not _director_env_token:
        persist_env_value("DIRECTOR_WEBHOOK_TOKEN", DIRECTOR_WEBHOOK_TOKEN)

