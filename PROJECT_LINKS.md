# Project Links

> Scope: project-local — this file governs only this project root. Cross-project truth lives in the 2nd Brain vault: /Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain (contract: 00 - System/contracts/project-link-bridge.md).

This file is the project-local bridge card. It keeps roots findable without copying another root's source of truth.

## Control Card

| Field | Value |
|---|---|
| Project ID | a_coding-26-06-22-mailmate-cli-1b33adda |
| Project Name | 26.06.22-mailmate-cli |
| Canonical Hub | /Users/vecsatfoxmailcom/Documents/A-coding/26.06.22-mailmate-cli |
| Code Root | /Users/vecsatfoxmailcom/Documents/A-coding/26.06.22-mailmate-cli |
| 2nd Brain Router | /Users/vecsatfoxmailcom/Documents/Cowork/Antigravity Cowork/26.06.06 2nd Brain/00 - System/registries/project-capabilities.md |
| Live URL | https://mailmate.jp/app/mails |
| Deploy Owner | local CLI |
| Decision Owner | /Users/vecsatfoxmailcom/Documents/A-coding/26.06.22-mailmate-cli |
| Current Next Gate | `PYTHONPATH=src python3 -m unittest discover -s tests` |
| Init Gate | `./bin/mailmate init` |
| Operation Gate | `./bin/mailmate list` |
| QA Gate | `./scripts/verify.sh` |
| Do Not Edit Here | Direct 1Password vault secrets |
| Last Verified | 2026-09-03 |

## Ownership

Truth ownership is one-way. Navigation is two-way.

- Code root owns source code, tests, build/deploy, and technical runbooks.
- 2nd Brain owns stable memory and router context only.
- Keep project-level decisions in the declared decision owner. Other roots should point to that owner instead of maintaining a duplicate decision table.

## Safety

Do not store secrets, customer records, private health URLs, provider credentials, or raw API keys in this file.
