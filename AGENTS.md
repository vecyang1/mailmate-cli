# Working on mailmate-cli

## What this project is

Quiet local CLI for MailMate postal mail operations: list inbox, read/OCR scans, request open and scan, download PDFs, archive, mark status, and safely discard paper originals.
Runs locally against MailMate session cookies, with no external server or telemetry.

## Available Surfaces

- `mailmate list [--search Q] [--filter F] [--tag T] [--status S] [--unread-only]`: list inbox postal items.
- `mailmate audit [--limit N]`: audit mailbox for unopened items, physical storage fee aging (>30d ¥8/day fee penalty), proactive 20-30d buffer warnings, and current burn rate.
- `mailmate read <id> [--download-dir D] [--text]`: read metadata, attached scans, and OCR text.
- `mailmate open <id> [--force] [--apply --yes]`: request staff to open and scan unopened mail (dry-run by default; blocks predictable debt-collection notices unless --force).
- `mailmate download <id> [--output PATH]`: download scanned multi-page PDF.
- `mailmate archive <id> [--apply --yes]`: archive processed mail.
- `mailmate mark-bill / mark-receipt / mark-unread <id> [--apply --yes]`: fast triage tags.
- `mailmate address`: retrieve registered physical Japanese/English postal address and inbound digital forwarding emails.
- `mailmate note <id> [TEXT] [--apply --yes]`: read or update mail memo note.
- `mailmate timeline <id>` (alias `activities`): retrieve full audit timeline events with timestamps and actors.
- `mailmate bills [--unpaid-only] [--export PATH]`: inspect and export extracted financial invoices and vouchers.
- `mailmate inspect <id>`: check safe discard and open scan eligibility.
- `mailmate abandon <id> [--force] [--apply --yes]`: discard paper original (only if scanned and eligible, or forced by operator instruction).
- `mailmate sweep [--inbox-id ID] [--sender-contains S] [--filter F] [--min-days N] [--force] [--apply --yes]`: batch discard eligible mail (supports --filter in_paid_storage, or --min-days 23 to discard 7 days before fee penalty).

## Safety Rules

- **Cover image is not inside scan**: A grey dot / cover image is treated as cover-only, not as verified inside scan.
- **Red dot is pending**: Treated as scan requested (`開封待ち`), but pending until detail status proves opened/scanned content.
- **Discard criteria**: Paper-original discard is eligible ONLY when the detail page explicitly proves opened/scanned inside content exists and MailMate exposes a real discard action (`/shred`).
- **Confirmation requirement**: `--apply` always requires `--yes`. Without `--apply`, commands are dry-run only.
- **Proactive Storage Defense Invariant**: Fukuoka physical mail has 30 days free storage; from day 31 it incurs ¥8/day fee penalty. `CAD-20261031-mailmate-storage-defense-cadence` runs bi-weekly (Mondays and Thursdays 09:00, `0 9 * * 1,4`) to enforce proactive defense: scanned mail stored >= 23 days is discarded 7 days before penalty (`--min-days 23`), and unopened administrative mail approaching 20 days is proactively expedited for scanning.

## Verification

```bash
./scripts/verify.sh
```
