from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "mailmate-cli"
DEFAULT_STATE_DIR = Path.home() / ".local" / "state" / "mailmate-cli"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"


@dataclass(frozen=True)
class ProfilePaths:
    profile: str
    config_dir: Path
    state_dir: Path
    config_file: Path
    env_file: Path
    cookie_jar: Path
    audit_log: Path
    lock_file: Path


def resolve_profile_paths(
    profile: str | None = None,
    *,
    base_config_dir: Path | str | None = None,
    base_state_dir: Path | str | None = None,
) -> ProfilePaths:
    clean_profile = (profile or "").strip() or "default"
    root_config = Path(base_config_dir).expanduser() if base_config_dir else DEFAULT_CONFIG_DIR
    root_state = Path(base_state_dir).expanduser() if base_state_dir else DEFAULT_STATE_DIR

    if clean_profile == "default":
        cfg_dir = root_config
        st_dir = root_state
    else:
        cfg_dir = root_config / "profiles" / clean_profile
        st_dir = root_state / "profiles" / clean_profile

    return ProfilePaths(
        profile=clean_profile,
        config_dir=cfg_dir,
        state_dir=st_dir,
        config_file=cfg_dir / "config.json",
        env_file=cfg_dir / "env",
        cookie_jar=st_dir / "cookies.txt",
        audit_log=st_dir / "audit.jsonl",
        lock_file=st_dir / "run.lock",
    )


@dataclass(frozen=True)
class RunConfig:
    inbox_id: str = "82433"
    limit: int = 20
    sender_contains: list[str] = field(default_factory=list)
    mail_ids: list[str] = field(default_factory=list)
    apply: bool = False
    confirmed_paper_discard: bool = False


def load_run_config(path: Path | str) -> RunConfig:
    config_path = Path(path).expanduser()
    if not config_path.exists():
        return RunConfig()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a JSON object.")
    config = RunConfig(
        inbox_id=str(data.get("inboxId", data.get("inbox_id", "82433"))),
        limit=_positive_int(data.get("limit", 20), field_name="limit"),
        sender_contains=_string_list(data.get("senderContains", data.get("sender_contains", []))),
        mail_ids=_string_list(data.get("mailIds", data.get("mail_ids", []))),
        apply=bool(data.get("apply", False)),
        confirmed_paper_discard=bool(data.get("confirmedPaperDiscard", data.get("confirmed_paper_discard", False))),
    )
    if config.apply and not config.confirmed_paper_discard:
        raise ValueError("Config apply=true requires confirmedPaperDiscard=true.")
    return config


def _string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _positive_int(value: Any, *, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive integer.") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")
    return parsed
