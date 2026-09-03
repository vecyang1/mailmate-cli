from __future__ import annotations

import plistlib
from pathlib import Path
from typing import Any


DEFAULT_LAUNCH_AGENT_LABEL = "com.vec.mailmate-cli.run"
DEFAULT_LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{DEFAULT_LAUNCH_AGENT_LABEL}.plist"
DEFAULT_LAUNCH_AGENT_PATH_ENV = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def build_launch_agent_plist(
    *,
    label: str,
    program: str,
    interval_minutes: int,
    stdout_log: str,
    stderr_log: str,
    run_yes: bool = False,
) -> dict[str, Any]:
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be positive.")
    program_arguments = [program, "--quiet", "run"]
    if run_yes:
        program_arguments.append("--yes")
    return {
        "Label": label,
        "ProgramArguments": program_arguments,
        "RunAtLoad": False,
        "StartInterval": interval_minutes * 60,
        "StandardOutPath": stdout_log,
        "StandardErrorPath": stderr_log,
        "EnvironmentVariables": {"PATH": DEFAULT_LAUNCH_AGENT_PATH_ENV},
    }


def install_launch_agent(path: Path | str, plist: dict[str, Any]) -> dict[str, Any]:
    plist_path = Path(path).expanduser()
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_bytes(plistlib.dumps(plist, sort_keys=True))
    try:
        plist_path.chmod(0o644)
    except OSError:
        pass
    return {
        "installed": True,
        "plistPath": str(plist_path),
        "label": plist["Label"],
        "programArguments": plist["ProgramArguments"],
        "startInterval": plist["StartInterval"],
    }


def launch_agent_plist_xml(plist: dict[str, Any]) -> str:
    return plistlib.dumps(plist, sort_keys=True).decode("utf-8")
