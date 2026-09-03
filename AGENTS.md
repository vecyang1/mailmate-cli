# Working on mailmate-cli

## What this project is

Quiet local CLI for MailMate mail inspection and safe paper-original discard.
Runs locally against MailMate session cookies, with no external server or telemetry.

## Safety Rules

- **Cover image is not inside scan**: A grey dot / cover image is treated as cover-only, not as verified inside scan.
- **Red dot is pending**: Treated as scan requested, but pending until detail status proves opened/scanned content.
- **Discard criteria**: Paper-original discard is eligible ONLY when the detail page explicitly proves opened/scanned inside content exists and MailMate exposes a real discard action.
- **Confirmation requirement**: `--apply` always requires `--yes`. Without `--apply`, commands are dry-run only.

## Verification

```bash
./scripts/verify.sh
```
