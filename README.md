# MailMate CLI

Quiet local CLI for MailMate mail inspection and safe paper-original discard.

The main safety rule is intentionally conservative:

- A grey dot / cover image is treated as cover-only mail, not as a verified inside scan.
- A red dot is treated as `scanRequested`, not as proof that the scan is complete.
- Mail with `未開封` or the banner `郵便物がまだ開封スキャンされていません。` is skipped.
- Paper-original discard is eligible only when the detail page explicitly proves opened/scanned inside content exists and MailMate exposes a real discard form/link.
- `--apply` always requires `--yes`. Without `--apply`, commands are dry-run only.

## Setup

Use environment variables for the quietest future runs:

```bash
export MAILMATE_EMAIL="you@example.com"
export MAILMATE_PASSWORD="..."
```

Or use a local env file that stays outside the repo:

```bash
mkdir -p ~/.config/mailmate-cli
chmod 700 ~/.config/mailmate-cli
$EDITOR ~/.config/mailmate-cli/env
chmod 600 ~/.config/mailmate-cli/env
```

Expected keys:

```bash
MAILMATE_EMAIL=you@example.com
MAILMATE_PASSWORD=...
```

For silent 1Password-backed refresh without storing the MailMate password:

```bash
MAILMATE_OP_ITEM=<item-name-or-id>
```

Or use 1Password only when you explicitly want it:

```bash
./bin/mailmate --op-item "MailMate" login
```

The CLI stores only MailMate session cookies in:

```bash
~/.local/state/mailmate-cli/cookies.txt
```

It does not open Chrome, does not ask for Chrome developer access, and does not read Chrome cookies/profile stores.

## Commands

Login or refresh the cookie jar:

```bash
./bin/mailmate login
```

Check local readiness without printing secrets:

```bash
./bin/mailmate --json doctor
```

Create local config scaffolding without writing credentials:

```bash
./bin/mailmate init
```

Run the unattended config-driven sweep:

```bash
./bin/mailmate --quiet run
```

Default config path:

```bash
~/.config/mailmate-cli/config.json
```

Safe dry-run config example:

```json
{
  "inboxId": "12345",
  "limit": 20,
  "senderContains": ["Example Sender"]
}
```

Apply mode requires both config confirmation and CLI confirmation:

```json
{
  "inboxId": "12345",
  "limit": 20,
  "senderContains": ["Example Sender"],
  "apply": true,
  "confirmedPaperDiscard": true
}
```

```bash
./bin/mailmate --quiet run --yes
```

Unattended runs use:

```bash
~/.local/state/mailmate-cli/audit.jsonl
~/.local/state/mailmate-cli/run.lock
```

Check the last unattended run:

```bash
./bin/mailmate --json status
```

Preview a macOS LaunchAgent for silent scheduled runs:

```bash
./bin/mailmate launch-agent --print
```

Write the plist without loading it:

```bash
./bin/mailmate --json launch-agent --install
```

For scheduled apply mode after the config has `apply=true` and `confirmedPaperDiscard=true`:

```bash
./bin/mailmate --json launch-agent --run-yes --install
```

The default generated LaunchAgent runs:

```bash
./bin/mailmate --quiet run
```

Inspect the mail from the notification:

```bash
./bin/mailmate --json inspect 198843
```

Dry-run a safe discard decision:

```bash
./bin/mailmate --json abandon 198843
```

Actually discard the paper original only if the scanned copy is verified:

```bash
./bin/mailmate --quiet abandon 198843 --apply --yes
```

Dry-run the inbox sweep:

```bash
./bin/mailmate --json sweep --inbox-id 12345 --sender-contains "Example Sender" --limit 20
```

Apply the inbox sweep:

```bash
./bin/mailmate --quiet sweep --inbox-id 12345 --sender-contains "Example Sender" --limit 20 --apply --yes
```

## Exit Codes

- `0`: command completed
- `2`: invalid arguments or `--apply` without `--yes`
- `77`: authentication required
- `1`: MailMate/network/runtime error

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m mailmate_cli --no-login --json inspect 198843
./scripts/verify.sh
```

The no-login smoke should return exit code `77` with `auth_required`; that proves it fails quietly without browser prompts.

See [docs/01_operational_runbook.md](docs/01_operational_runbook.md) for the live E2E checklist and current auth/browser diagnostic notes.

## License

GNU Affero General Public License v3.0 (AGPL-3.0-or-later). See [LICENSE](LICENSE) for details.
