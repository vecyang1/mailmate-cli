# Changelog

## [2026-11-07] - 2026-11-07

### Added
- Resilient retry loop in `MailMateClient.request`: exponential backoff (up to 3 attempts) handling transient SSL EOF (`UNEXPECTED_EOF_WHILE_READING`), URLError, and gateway errors (502/503/504) during unattended background sweeps.

### Maintenance
- Auto-sanitize privacy files and local paths (`7082230`)
- Record 2026-11-05 storage defense run receipt (`545c6ad`)

## [2026-11-04] - 2026-11-04

### Documentation
- Document audit, min-days filter, force discard, and proactive storage defense cadence (`062bb15`)

## 0.11.0 - 2026-10-31

### Added
- Added `--min-days <INT>` flag to `sweep` command and `_target_items`: enables proactive discarding of scanned mail items before threshold expiry (e.g. discard at 23 days to stay 7 days ahead of fee penalties).
- Enhanced `cmd_audit` and console reporting with 20-30 day proactive storage buffer warnings (`Storage 20-30d`) and specific mail IDs to prevent overdue penalties before 30-day threshold expiry.
- Added `--force` flag to `abandon` and `sweep` commands: allows discarding unopened or disputed mails when explicitly instructed.
- Added `--filter` flag to `sweep` command: supports targeted batch sweeping matching MailMate web filters (e.g. `in_paid_storage`).
- Recognized `破棄依頼済み` term in parser `DISCARDED_TERMS` to accurately track in-flight shredding status.
- Integrated MailMate server-side filters (`in_paid_storage`, `shredded`) into `cmd_audit` to reflect ground-truth billing state and burn rate accurately.
- Configured and live-verified weekly automated audit cadence `CAD-20261031-mailmate-storage-defense-cadence` (`0 9 * * 1`) under `scheduled-task-rescheduler`.

### Fixed
- Fixed `FakeClient.inbox` compatibility in test harness when passing optional `filter_name`.

## 0.10.0 - 2026-10-29

### Added
- `audit` command (`mailmate audit`): audits mailbox for unopened items with automated open/skip classification and physical storage aging analysis (>30-day ¥8/day fee penalty).
- `SKIP_OPEN_PATTERNS` & `is_skip_open_sender` safety policy: blocks automated/accidental `open` requests for predictable debt-collection, routine rent-guarantee notices (`弁護士法人神田お玉ヶ池法律事務所`, `株式会社Casa`) where the envelope already states the sender and purpose, preventing unnecessary scanning fees.
- `--force` flag on `open` command to override the `skip_open_known_sender` safety guard when explicitly requested.
- Symlink resolution in `bin/mailmate` allowing global PATH execution from `~/.local/bin/mailmate`.

## 0.9.1 - 2026-10-10

### Fixes
- Handle http.client.IncompleteRead on chunked responses in Python 3.14 (`f838134`)

## [2026-09-12] - 2026-09-12

### Fixes
- Untrack project links, virtualize test emails, fix license and path examples (`2300d85`)

## 0.9.0 - 2026-09-03

- Driven by live Chrome DevTools visual and DOM tree inspection:
  - Added `address` command: displays registered physical postal address (Japanese & English), postal code, management ID, and inbound forwarding email addresses (`@pm.mailmate.jp`, `@invoice.mailmate.jp`, `@receipt.mailmate.jp`).
  - Added `note` command: read or update mail memo notes (`mail_postal_mail[notes]`) with dry-run safety and `--apply --yes` guard. Live tested against MailMate Rails backend.
  - Added `timeline` (alias `activities`) command: retrieves full audit log history of mail items (creation, scan request, scan completion, memo updates) with timestamps and actors.
  - Added `bills` command: lists structured financial invoices and vouchers with vendor names, amounts, payment deadlines, and linked postal mail IDs. Supports direct ledger CSV export via `--export PATH`.
- Expanded test suite to 63 unit tests and extended verification smokes in `scripts/verify.sh`.

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
