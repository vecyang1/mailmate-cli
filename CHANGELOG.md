# Changelog

## 0.6.0 - 2026-06-23

- Added `launch-agent --run-yes` for explicitly confirmed scheduled apply mode.
- Kept the default LaunchAgent dry-run safe; actual paper-original discard still requires config `apply=true`, `confirmedPaperDiscard=true`, and generated `run --yes`.

## 0.5.1 - 2026-06-23

- Updated `doctor` to report `op_configured` when a 1Password item is configured without storing a MailMate password.
- Recorded live read-only MailMate E2E proof for login, inspect, sweep, and unattended dry-run behavior.

## 0.5.0 - 2026-06-23

- Added `launch-agent` command to print or install a macOS LaunchAgent plist for silent scheduled runs.
- Added LaunchAgent plist generation tests and verifier smoke coverage.
- Kept scheduler installation opt-in; the CLI writes a plist only with `--install` and does not load it with `launchctl`.

## 0.4.0 - 2026-06-23

- Added `init` command to scaffold local config, env sample, and state directory without writing fake credentials.
- Added `status` command to summarize the latest unattended-run audit log.
- Added tests and verification smokes for setup/status behavior.

## 0.3.0 - 2026-06-22

- Added config-driven `run` command for unattended sweeps with a single-process lock.
- Added private JSONL audit logging for unattended runs.
- Added JSON config parser with explicit `confirmedPaperDiscard` requirement for config-driven apply mode.
- Added runtime/config tests for lock contention, audit log permissions, config normalization, and dry-run audit output.

## 0.2.0 - 2026-06-22

- Added optional env-file credential loading for unattended runs without browser automation.
- Added `doctor` command for local readiness checks that do not print secrets or fetch 1Password item values.
- Added `scripts/verify.sh` for repeatable unit, compile, no-login, apply-guard, and doctor verification.
- Updated the MailMate HTTP user agent to use the package version.

## 0.1.1 - 2026-06-22

- Tightened scan detection so cover-image/blob assets from grey-dot mail never count as a verified inside-content scan.
- Documented MailMate dot semantics: grey dot means cover-only/unrequested; red dot means scan requested, still pending until detail status proves opened/scanned content.

## 0.1.0 - 2026-06-22

- Added quiet MailMate CLI with cookie-jar login, single-mail inspect, single-mail abandon, and inbox sweep commands.
- Added conservative discard classifier: red-dot scan requests are pending until the detail page proves a digital copy exists.
- Added tests for parser, safety classifier, CLI guardrails, and TLS context setup.
