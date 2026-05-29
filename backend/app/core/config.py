import os
from dataclasses import dataclass
from pathlib import Path


def parse_env_bool(raw: str, default: bool) -> bool:
    if raw is None:
        return default
    val = str(raw).strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    if val in {"0", "false", "no", "off"}:
        return False
    return default


def parse_env_int(raw: str, default: int) -> int:
    if raw is None:
        return default
    val = str(raw).strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        row = line.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        key, value = row.split("=", 1)
        clean_key = key.strip().lstrip("\ufeff")
        clean_value = value.strip()
        os.environ.setdefault(clean_key, clean_value)


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    backend_dir: Path
    env_file: Path
    state_file: Path
    event_file: Path
    poll_seconds: int
    api_host: str
    api_port: int
    cors_origins: list[str]
    embed_scheduler: bool


def get_settings() -> Settings:
    root_dir = Path(__file__).resolve().parents[3]
    backend_dir = root_dir / "backend"
    env_file = backend_dir / ".env"
    load_dotenv(env_file)

    state_file = Path(os.environ.get("TASK_STATE_FILE", ".task_state.json"))
    event_file = Path(os.environ.get("TASK_EVENT_FILE", ".task_events.jsonl"))
    if not state_file.is_absolute():
        state_file = root_dir / state_file
    if not event_file.is_absolute():
        event_file = root_dir / event_file

    cors_raw = os.environ.get("BACKEND_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    cors_origins = [item.strip() for item in cors_raw.split(",") if item.strip()]

    return Settings(
        root_dir=root_dir,
        backend_dir=backend_dir,
        env_file=env_file,
        state_file=state_file,
        event_file=event_file,
        poll_seconds=parse_env_int(os.environ.get("POLL_SECONDS"), 20),
        api_host=os.environ.get("BACKEND_HOST", "0.0.0.0"),
        api_port=parse_env_int(os.environ.get("BACKEND_PORT"), 8000),
        cors_origins=cors_origins,
        embed_scheduler=parse_env_bool(os.environ.get("BACKEND_EMBED_SCHEDULER"), True),
    )
