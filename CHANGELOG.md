# Changelog

## 0.8.0 - 2026-09-03

- Added `open` (alias `request-scan`) command to request MailMate staff to open and scan unopened mail (`未開封`) with dry-run safety and `--apply --yes` guard.
- Added `download` command to download scanned PDFs directly with output destination controls and size reporting.
- Added `archive` command to archive processed mail items (`/app/mails/{id}/archive_mail`).
- Added `mark-unread`, `mark-bill`, and `mark-receipt` commands for fast postal mail triage.
- Enhanced `list` with server-side query options: `--search <query>`, `--filter <archived|shredded>`, and `--tag <tag>`.
- Fixed discard action discovery on detail pages: recognized `/app/mails/{id}/shred_form` modals and mapped them to `PATCH .../shred` actions with CSRF tokens.
- Fixed non-ASCII URL encoding bug in `client.request` preventing `UnicodeEncodeError` on Japanese search queries.
- Added automatic detection of `開封待ち` (scan requested / pending) on mail detail pages.
- Expanded test suite to 55 unit tests and added no-login/apply-guard smokes in `scripts/verify.sh`.

- Added `list` command to read and filter postal mail items directly from `https://mailmate.jp/app/mails` (`--limit`, `--sender`, `--status`, `--unread-only`, `--json`).
- Added `read` command to inspect mail metadata, download scanned PDFs, and extract document text/OCR directly in the terminal (`--text`, `--download-dir`, `--json`).
- Added PDF text extraction via PyMuPDF (`fitz`) and `pdftotext` fallback.
- Added multi-profile support via `--profile <name>` (e.g. `profile2`), isolating config, env, cookie jar, audit log, and run lock under `profiles/<name>/`.
- Added lazy credential resolution: existing valid cookies in `cookies.txt` are checked before attempting 1Password item resolution, avoiding unnecessary Touch ID prompts.
- Added project bridge card `PROJECT_LINKS.md` with cross-root governance compliance.
- Expanded test suite to 43 unit tests and verified live operations against real MailMate web endpoints.

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
