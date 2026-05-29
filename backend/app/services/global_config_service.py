import os
from pathlib import Path
from typing import Any


GLOBAL_CONFIG_KEYS = [
    "CONSOLE_ACCESS_KEY_ID",
    "CONSOLE_ACCESS_SECRET",
    "CONSOLE_HOST",
    "FEISHU_WEBHOOK_URL",
    "FEISHU_SECRET",
    "ROBOT_UUID",
    "BRAND",
    "POLL_SECONDS",
    "MAX_RETRIES",
    "MAX_PARALLEL_OSS",
    "MAX_PARALLEL_HASHKEY",
    "MAX_PARALLEL_UPLOAD_MERGED_FILE",
    "PARALLEL_REGIONS",
    "REGION_CATALOG",
    "PRECOMPLETED_TASKS",
    "ACCOUNT_NAMES",
    "SCHEDULER_STRICT_STAGE_ORDER",
    "TASK_STATE_FILE",
    "TASK_EVENT_FILE",
    "LOG_LEVEL",
    "BACKEND_EMBED_SCHEDULER",
    "BACKEND_HOST",
    "BACKEND_PORT",
]


def get_env_path(root_dir: Path) -> Path:
    return root_dir / "backend" / ".env"


def _read_env_lines(env_path: Path) -> list[str]:
    if not env_path.exists():
        return []
    return env_path.read_text(encoding="utf-8").splitlines()


def _parse_env(lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in lines:
        row = line.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        k, v = row.split("=", 1)
        out[k.strip().lstrip("\ufeff")] = v.strip()
    return out


def load_global_config(root_dir: Path) -> dict[str, str]:
    env_path = get_env_path(root_dir)
    current = _parse_env(_read_env_lines(env_path))
    result: dict[str, str] = {}
    for key in GLOBAL_CONFIG_KEYS:
        val = current.get(key)
        if val is None:
            val = os.environ.get(key, "")
        result[key] = val
    return result


def save_global_config(root_dir: Path, values: dict[str, Any]) -> dict[str, str]:
    env_path = get_env_path(root_dir)
    lines = _read_env_lines(env_path)
    updates: dict[str, str] = {}
    for k, v in values.items():
        if k not in GLOBAL_CONFIG_KEYS:
            continue
        updates[k] = str(v).strip()

    # update existing keys in place first
    remaining = set(updates.keys())
    new_lines: list[str] = []
    for line in lines:
        raw = line
        row = line.strip()
        if not row or row.startswith("#") or "=" not in row:
            new_lines.append(raw)
            continue
        k, _ = row.split("=", 1)
        key = k.strip().lstrip("\ufeff")
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            remaining.discard(key)
        else:
            new_lines.append(raw)

    # append missing keys
    if remaining:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        for key in GLOBAL_CONFIG_KEYS:
            if key in remaining:
                new_lines.append(f"{key}={updates[key]}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # make current process pick latest values
    for k, v in updates.items():
        os.environ[k] = v

    return load_global_config(root_dir)


def parse_accounts(raw: str) -> list[str]:
    return [item.strip() for item in str(raw).split(",") if item.strip()]
