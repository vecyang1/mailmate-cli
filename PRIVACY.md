# Privacy Policy

**MailMate CLI** (`mailmate-cli`) is an open-source, local-first command-line tool for inspecting and managing your own MailMate mail (such as safe paper-original discard).

It runs entirely on your own computer.

## Who Operates This Tool

MailMate CLI is **not** a hosted software-as-a-service (SaaS). There is no remote backend, no telemetry server, no centralized database, and no operator who can access or view your data.

Each user runs their own copy locally, using their own credentials and connecting directly to their own MailMate account.

## What Data The App Touches

- **Authentication Credentials**: Your MailMate login email and password, or 1Password reference ID, read strictly from your local environment or local configuration file (`~/.config/mailmate-cli/env`).
- **Session State**: Session cookies saved to your local machine (`~/.local/state/mailmate-cli/cookies.txt`) with restricted file permissions (`chmod 600`).
- **Mail Metadata & Scans**: Mail detail records, statuses, and downloaded files accessed directly from `mailmate.jp`.

## Network Communication

MailMate CLI makes HTTPS network requests **only** to the official MailMate platform:

- `mailmate.jp`

It sends **no telemetry, no analytics, no crash logs, and no diagnostics** to any third-party service or third-party server.

## Local File Isolation

All state, audit logs, and configuration remain on your local disk:
- Config: `~/.config/mailmate-cli/`
- State: `~/.local/state/mailmate-cli/`
