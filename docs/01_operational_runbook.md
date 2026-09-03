# MailMate CLI Operational Runbook

## Purpose

This CLI quietly inspects MailMate mail and discards paper originals only when the detail page proves opened/scanned inside content exists.

## Safety Contract

- Grey dot / cover image: cover-only mail, not safe to discard.
- Red dot: scan requested, still not safe until detail status proves opened/scanned content.
- `未開封` or `郵便物がまだ開封スキャンされていません。`: never discard.
- `--apply` must always be paired with `--yes`.
- Browser cookies, local storage, profile databases, and saved passwords are out of scope for this CLI.

## Quiet Credential Sources

Preferred unattended setup:

```bash
mkdir -p ~/.config/mailmate-cli
chmod 700 ~/.config/mailmate-cli
$EDITOR ~/.config/mailmate-cli/env
chmod 600 ~/.config/mailmate-cli/env
```

`~/.config/mailmate-cli/env`:

```bash
MAILMATE_EMAIL=you@example.com
MAILMATE_PASSWORD=...
```

Alternative:

```bash
export MAILMATE_EMAIL="you@example.com"
export MAILMATE_PASSWORD="..."
```

1Password is supported only when an item name/id is known:

```bash
./bin/mailmate --op-item "<item-name-or-id>" login
```

## Current Live E2E State On 2026-06-23

Verified:

```bash
./scripts/verify.sh
```

Output included:

```text
Ran 32 tests ... OK
verification ok
```

Live authenticated MailMate E2E is completed for read-only and dry-run paths:

- `op item list` found a MailMate login item without printing secret fields.
- `./bin/mailmate --op-item <item-id> --json login` refreshed `~/.local/state/mailmate-cli/cookies.txt`.
- `./bin/mailmate --json inspect 198843` returned `status=未開封`, `scanMissing=true`, and `decision=skipped`.
- `./bin/mailmate --json abandon 198843` dry-run also skipped the paper-original discard.
- `./bin/mailmate --json sweep --inbox-id 12345 --sender-contains "Example Organization" --limit 20` returned three read-only rows; none were discarded.
- `./bin/mailmate --json --audit-log <temp>/audit.jsonl --lock-file <temp>/run.lock run --config examples/config.example.json` wrote one audit line and skipped all rows.
- `./bin/mailmate --quiet run` with the default local config exited `0` with no noisy output.
- `./bin/mailmate --json status` showed the latest default run had three `skipped` rows, zero `dry_run`, and zero `discarded`.

Local unattended auth is configured with a 1Password item pointer only:

```bash
~/.config/mailmate-cli/env
```

The file should contain `MAILMATE_OP_ITEM=<item-id>` rather than a MailMate password.

Check current readiness:

```bash
./bin/mailmate --json doctor
```

Create local scaffolding without fake credentials:

```bash
./bin/mailmate init
```

This creates:

```bash
~/.config/mailmate-cli/config.json
~/.config/mailmate-cli/env.sample
~/.local/state/mailmate-cli/
```

Copy `env.sample` to `env` only when real credentials are available:

```bash
cp ~/.config/mailmate-cli/env.sample ~/.config/mailmate-cli/env
chmod 600 ~/.config/mailmate-cli/env
```

## Unattended Run Mode

Default config:

```bash
~/.config/mailmate-cli/config.json
```

Dry-run config:

```json
{
  "inboxId": "12345",
  "limit": 20,
  "senderContains": ["Example Organization"]
}
```

Run:

```bash
./bin/mailmate --quiet run
```

Apply config requires an explicit persistent confirmation:

```json
{
  "inboxId": "12345",
  "limit": 20,
  "senderContains": ["Example Organization"],
  "apply": true,
  "confirmedPaperDiscard": true
}
```

Apply command still requires a runtime confirmation flag:

```bash
./bin/mailmate --quiet run --yes
```

Runtime files:

```bash
~/.local/state/mailmate-cli/audit.jsonl
~/.local/state/mailmate-cli/run.lock
```

The audit log is JSONL and chmod `600`. It stores decisions and MailMate IDs/senders/statuses, not credentials, CSRF tokens, or cookies.

Check the latest run:

```bash
./bin/mailmate --json status
```

## macOS Silent Schedule

Preview the LaunchAgent plist:

```bash
./bin/mailmate launch-agent --print
```

Write the plist:

```bash
./bin/mailmate --json launch-agent --install
```

Write an apply-capable plist only after the config has both `apply=true` and `confirmedPaperDiscard=true`:

```bash
./bin/mailmate --json launch-agent --run-yes --install
```

Default path:

```bash
~/Library/LaunchAgents/com.vec.mailmate-cli.run.plist
```

The command intentionally does not call `launchctl`. After `doctor` is ready and a dry-run `run` succeeds, load it manually:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.vec.mailmate-cli.run.plist
```

The plist includes a launchd-safe `PATH` with Homebrew and system binary directories so the wrapper can find `python3` outside an interactive shell.

Unload:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.vec.mailmate-cli.run.plist
```

Logs:

```bash
~/.local/state/mailmate-cli/launchd.out.log
~/.local/state/mailmate-cli/launchd.err.log
```

## Live E2E Checklist

After credentials are configured:

```bash
./bin/mailmate --json doctor
./bin/mailmate login
./bin/mailmate --json inspect 198843
./bin/mailmate --json abandon 198843
```

Only if the dry-run result is `eligible` and the user wants the paper original discarded:

```bash
./bin/mailmate --quiet abandon 198843 --apply --yes
```

Inbox sweep dry-run:

```bash
./bin/mailmate --json sweep --inbox-id 12345 --sender-contains "Example Organization" --limit 20
```

Inbox sweep apply:

```bash
./bin/mailmate --quiet sweep --inbox-id 12345 --sender-contains "Example Organization" --limit 20 --apply --yes
```
