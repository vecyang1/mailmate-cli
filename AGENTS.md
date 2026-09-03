# Working on mailmate-cli

## What this project is

Quiet local CLI for MailMate postal mail operations: list inbox, read/OCR scans, request open and scan, download PDFs, archive, mark status, and safely discard paper originals.
Runs locally against MailMate session cookies, with no external server or telemetry.

## Available Surfaces

- `mailmate list [--search Q] [--filter F] [--tag T] [--status S] [--unread-only]`: list inbox postal items.
- `mailmate read <id> [--download-dir D] [--text]`: read metadata, attached scans, and OCR text.
- `mailmate open <id> [--apply --yes]`: request staff to open and scan unopened mail (dry-run by default).
- `mailmate download <id> [--output PATH]`: download scanned multi-page PDF.
- `mailmate archive <id> [--apply --yes]`: archive processed mail.
- `mailmate mark-bill / mark-receipt / mark-unread <id> [--apply --yes]`: fast triage tags.
- `mailmate inspect <id>`: check safe discard and open scan eligibility.
- `mailmate abandon <id> [--apply --yes]`: discard paper original (only if scanned and eligible).
- `mailmate sweep [--inbox-id ID] [--sender-contains S] [--apply --yes]`: batch discard eligible mail.

## Safety Rules

- **Cover image is not inside scan**: A grey dot / cover image is treated as cover-only, not as verified inside scan.
- **Red dot is pending**: Treated as scan requested (`開封待ち`), but pending until detail status proves opened/scanned content.
- **Discard criteria**: Paper-original discard is eligible ONLY when the detail page explicitly proves opened/scanned inside content exists and MailMate exposes a real discard action (`/shred`).
- **Confirmation requirement**: `--apply` always requires `--yes`. Without `--apply`, commands are dry-run only.

## Verification

```bash
./scripts/verify.sh
```
