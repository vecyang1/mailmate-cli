from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_AUDIT_LOG = Path.home() / ".local" / "state" / "mailmate-cli" / "audit.jsonl"
DEFAULT_LOCK_FILE = Path.home() / ".local" / "state" / "mailmate-cli" / "run.lock"


def append_audit_log(path: Path | str, event: dict[str, Any]) -> None:
    log_path = Path(path).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    try:
        log_path.chmod(0o600)
    except OSError:
        pass


def build_status_report(path: Path | str) -> dict[str, Any]:
    log_path = Path(path).expanduser()
    if not log_path.exists():
        return {"ok": False, "auditLog": str(log_path), "runs": 0, "latest": None}
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    latest = records[-1] if records else None
    if latest is not None:
        latest = {**latest, "counts": _decision_counts(latest.get("rows", []))}
    return {"ok": bool(latest), "auditLog": str(log_path), "runs": len(records), "latest": latest}


def scaffold_local_setup(config_path: Path | str, env_sample_path: Path | str, state_dir: Path | str) -> dict[str, Any]:
    config_file = Path(config_path).expanduser()
    env_sample_file = Path(env_sample_path).expanduser()
    state_directory = Path(state_dir).expanduser()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    env_sample_file.parent.mkdir(parents=True, exist_ok=True)
    state_directory.mkdir(parents=True, exist_ok=True)

    created_config = False
    created_env_sample = False
    if not config_file.exists():
        config_file.write_text(
            json.dumps(
                {
                    "inboxId": "82433",
                    "limit": 20,
                    "senderContains": ["全国健康保険協会"],
                    "apply": False,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        _chmod_private(config_file)
        created_config = True
    if not env_sample_file.exists():
        env_sample_file.write_text(
            "MAILMATE_EMAIL=\nMAILMATE_PASSWORD=\n# MAILMATE_OP_ITEM=\n",
            encoding="utf-8",
        )
        _chmod_private(env_sample_file)
        created_env_sample = True

    return {
        "ok": True,
        "config": str(config_file),
        "envSample": str(env_sample_file),
        "stateDir": str(state_directory),
        "createdConfig": created_config,
        "createdEnvSample": created_env_sample,
    }


def _decision_counts(rows: list[Any]) -> dict[str, int]:
    counts = {"discarded": 0, "dry_run": 0, "skipped": 0}
    for row in rows:
        if not isinstance(row, dict):
            continue
        decision = str(row.get("decision") or "")
        if decision in counts:
            counts[decision] += 1
    return counts


def _chmod_private(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass


class FileLock:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path).expanduser()
        self._fd: int | None = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise RuntimeError(f"Another MailMate CLI run is already active: {self.path}") from exc
        with os.fdopen(self._fd, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        self._fd = None
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
