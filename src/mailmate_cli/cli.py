from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from .client import (
    DEFAULT_BASE_URL,
    DEFAULT_COOKIE_JAR,
    DEFAULT_ENV_FILE,
    AuthRequiredError,
    Credentials,
    MailMateClient,
    MailMateError,
    extract_text_from_pdf,
    load_env_file,
    resolve_credentials,
)
from .config import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
    DEFAULT_STATE_DIR,
    ProfilePaths,
    RunConfig,
    load_run_config,
    resolve_profile_paths,
)
from .launchd import (
    DEFAULT_LAUNCH_AGENT_LABEL,
    DEFAULT_LAUNCH_AGENT_PATH,
    build_launch_agent_plist,
    install_launch_agent,
    launch_agent_plist_xml,
)
from .models import DiscardDecision, InboxItem, MailDetail
from .runtime import (
    DEFAULT_AUDIT_LOG,
    DEFAULT_LOCK_FILE,
    FileLock,
    append_audit_log,
    build_status_report,
    scaffold_local_setup,
)
from .safety import decide_discard, decide_open_scan


def require_apply_confirmation(*, apply: bool, yes: bool) -> None:
    if apply and not yes:
        raise SystemExit(2)


def format_decision_row(detail: MailDetail, decision: DiscardDecision, *, applied: bool) -> dict[str, object]:
    open_scan_dec = decide_open_scan(detail)
    return {
        "mailId": detail.mail_id,
        "sender": detail.sender,
        "receivedDate": detail.received_date,
        "status": detail.status,
        "scanRequested": detail.scan_requested,
        "scanMissing": detail.scan_missing,
        "hasDigitalCopy": detail.has_digital_copy,
        "decision": "discarded" if applied else ("dry_run" if decision.eligible else "skipped"),
        "reason": decision.reason,
        "message": decision.message,
        "actionMethod": decision.action.method if decision.action else None,
        "actionUrl": decision.action.url if decision.action else None,
        "openScanEligible": open_scan_dec.eligible,
        "openScanReason": open_scan_dec.reason,
        "archiveAvailable": bool(detail.archive_url),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mailmate",
        description="Quietly inspect MailMate mail and safely discard paper originals only after scan verification.",
    )
    parser.add_argument("--profile", default=os.environ.get("MAILMATE_PROFILE", "default"), help="Profile name (e.g. default, profile2).")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--cookie-jar", default=str(DEFAULT_COOKIE_JAR))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Optional local env file for MailMate credentials.")
    parser.add_argument("--email", default=None, help="MailMate email. Defaults to MAILMATE_EMAIL.")
    parser.add_argument("--password-env", default="MAILMATE_PASSWORD", help="Env var containing the MailMate password.")
    parser.add_argument("--op-item", default=None, help="Optional 1Password item name/id for username/password lookup.")
    parser.add_argument("--audit-log", default=str(DEFAULT_AUDIT_LOG), help="JSONL audit log for unattended runs.")
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK_FILE), help="Lock file that prevents overlapping runs.")
    parser.add_argument("--no-login", action="store_true", help="Use existing cookie jar only; never fetch credentials.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument("--quiet", action="store_true", help="Only print actionable lines unless --json is set.")

    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="List mail items from MailMate inbox.")
    list_cmd.add_argument("--inbox-id", default=None, help="Optional inbox ID filter.")
    list_cmd.add_argument("--limit", type=int, default=30, help="Maximum number of items to return.")
    list_cmd.add_argument("--sender", default=None, help="Filter by sender name substring.")
    list_cmd.add_argument("--search", default=None, help="Server-side search query across sender/notes/mail.")
    list_cmd.add_argument("--filter", dest="filter_name", default=None, help="Filter by folder/status (e.g. archived, shredded).")
    list_cmd.add_argument("--tag", default=None, help="Filter by tag (e.g. bill).")
    list_cmd.add_argument("--status", default=None, help="Filter by status (opened, unopened, mailroom, etc.).")
    list_cmd.add_argument("--unread-only", action="store_true", help="Only show unread mail.")
    list_cmd.set_defaults(func=cmd_list)

    read_cmd = sub.add_parser("read", help="Read a specific mail's content, metadata, and attached PDF scans.")
    read_cmd.add_argument("mail_id", help="MailMate mail ID to read.")
    read_cmd.add_argument("--text", action="store_true", default=True, help="Extract and display scanned PDF document text.")
    read_cmd.add_argument("--no-text", dest="text", action="store_false", help="Do not extract PDF text.")
    read_cmd.add_argument("--download-dir", default=None, help="Directory to save downloaded scanned PDF.")
    read_cmd.set_defaults(func=cmd_read)

    open_cmd = sub.add_parser("open", aliases=["request-scan"], help="Request MailMate staff to open and scan an unopened mail.")
    open_cmd.add_argument("mail_id", help="MailMate mail ID to open/scan.")
    open_cmd.add_argument("--apply", action="store_true", help="Actually submit the open scan request.")
    open_cmd.add_argument("--yes", action="store_true", help="Required with --apply.")
    open_cmd.set_defaults(func=cmd_open)

    download_cmd = sub.add_parser("download", help="Download the scanned PDF for a mail item.")
    download_cmd.add_argument("mail_id", help="MailMate mail ID.")
    download_cmd.add_argument("--output", "-o", default=None, help="Destination file path for PDF.")
    download_cmd.set_defaults(func=cmd_download)

    archive_cmd = sub.add_parser("archive", help="Archive a mail item in MailMate.")
    archive_cmd.add_argument("mail_id", help="MailMate mail ID to archive.")
    archive_cmd.add_argument("--apply", action="store_true", help="Actually submit the archive action.")
    archive_cmd.add_argument("--yes", action="store_true", help="Required with --apply.")
    archive_cmd.set_defaults(func=cmd_archive)

    unread_cmd = sub.add_parser("mark-unread", help="Mark a mail item as unread.")
    unread_cmd.add_argument("mail_id", help="MailMate mail ID.")
    unread_cmd.add_argument("--apply", action="store_true", help="Actually submit the mark unread action.")
    unread_cmd.add_argument("--yes", action="store_true", help="Required with --apply.")
    unread_cmd.set_defaults(func=cmd_mark_unread)

    bill_cmd = sub.add_parser("mark-bill", help="Mark a mail item as bill (請求書).")
    bill_cmd.add_argument("mail_id", help="MailMate mail ID.")
    bill_cmd.add_argument("--apply", action="store_true", help="Actually submit the mark bill action.")
    bill_cmd.add_argument("--yes", action="store_true", help="Required with --apply.")
    bill_cmd.set_defaults(func=cmd_mark_bill)

    receipt_cmd = sub.add_parser("mark-receipt", help="Mark a mail item as receipt (領収書).")
    receipt_cmd.add_argument("mail_id", help="MailMate mail ID.")
    receipt_cmd.add_argument("--apply", action="store_true", help="Actually submit the mark receipt action.")
    receipt_cmd.add_argument("--yes", action="store_true", help="Required with --apply.")
    receipt_cmd.set_defaults(func=cmd_mark_receipt)

    address_cmd = sub.add_parser("address", help="Show MailMate mailing address and forwarding email accounts.")
    address_cmd.add_argument("--inbox-id", default=None, help="Inbox ID.")
    address_cmd.set_defaults(func=cmd_address)

    note_cmd = sub.add_parser("note", help="Read or update a mail item's memo/note.")
    note_cmd.add_argument("mail_id", help="MailMate mail ID.")
    note_cmd.add_argument("text", nargs="?", default=None, help="New note text. If omitted, prints current note.")
    note_cmd.add_argument("--apply", action="store_true", help="Actually update the note.")
    note_cmd.add_argument("--yes", action="store_true", help="Required with --apply.")
    note_cmd.set_defaults(func=cmd_note)

    timeline_cmd = sub.add_parser("timeline", aliases=["activities"], help="Show audit timeline activity history for a mail item.")
    timeline_cmd.add_argument("mail_id", help="MailMate mail ID.")
    timeline_cmd.set_defaults(func=cmd_timeline)

    bills_cmd = sub.add_parser("bills", help="List extracted bills and payment deadlines.")
    bills_cmd.add_argument("--export", default=None, help="Path to export raw CSV ledger.")
    bills_cmd.add_argument("--unpaid-only", action="store_true", default=False, help="Only show unpaid bills.")
    bills_cmd.set_defaults(func=cmd_bills)

    init = sub.add_parser("init", help="Create safe local config scaffolding without credentials.")
    init.add_argument("--config", default=str(DEFAULT_CONFIG_FILE))
    init.add_argument("--env-sample", default=str(DEFAULT_ENV_FILE.with_name("env.sample")))
    init.add_argument("--state-dir", default=str(DEFAULT_AUDIT_LOG.parent))
    init.set_defaults(func=cmd_init)

    doctor = sub.add_parser("doctor", help="Check local readiness without printing secrets.")
    doctor.set_defaults(func=cmd_doctor)

    status = sub.add_parser("status", help="Summarize the latest unattended run audit log.")
    status.set_defaults(func=cmd_status)

    launch_agent = sub.add_parser("launch-agent", help="Print or install a macOS LaunchAgent plist for silent runs.")
    launch_agent.add_argument("--label", default=DEFAULT_LAUNCH_AGENT_LABEL)
    launch_agent.add_argument("--program", default=_default_program_path())
    launch_agent.add_argument("--interval-minutes", type=int, default=360)
    launch_agent.add_argument("--plist-path", default=str(DEFAULT_LAUNCH_AGENT_PATH))
    launch_agent.add_argument("--stdout-log", default=str(DEFAULT_AUDIT_LOG.with_name("launchd.out.log")))
    launch_agent.add_argument("--stderr-log", default=str(DEFAULT_AUDIT_LOG.with_name("launchd.err.log")))
    launch_agent.add_argument("--run-yes", action="store_true", help="Include run --yes for explicitly confirmed apply configs.")
    launch_agent.add_argument("--print", dest="print_plist", action="store_true")
    launch_agent.add_argument("--install", action="store_true")
    launch_agent.set_defaults(func=cmd_launch_agent)

    login = sub.add_parser("login", help="Create or refresh the private cookie jar.")
    login.set_defaults(func=cmd_login)

    inspect = sub.add_parser("inspect", help="Inspect one MailMate mail id.")
    inspect.add_argument("mail_id")
    inspect.set_defaults(func=cmd_inspect)

    abandon = sub.add_parser("abandon", help="Safely discard one paper original if already scanned.")
    abandon.add_argument("mail_id")
    abandon.add_argument("--apply", action="store_true", help="Actually submit the discard action.")
    abandon.add_argument("--yes", action="store_true", help="Required with --apply.")
    abandon.set_defaults(func=cmd_abandon)

    sweep = sub.add_parser("sweep", help="Inspect inbox mail and discard eligible scanned originals.")
    sweep.add_argument("--inbox-id", default="82433")
    sweep.add_argument("--limit", type=int, default=20)
    sweep.add_argument("--sender-contains", default=None)
    sweep.add_argument("--mail-id", action="append", default=[])
    sweep.add_argument("--apply", action="store_true")
    sweep.add_argument("--yes", action="store_true")
    sweep.set_defaults(func=cmd_sweep)

    run = sub.add_parser("run", help="Run the unattended config-driven sweep with audit logging.")
    run.add_argument("--config", default=str(DEFAULT_CONFIG_FILE))
    run.add_argument("--yes", action="store_true", help="Required when config has apply=true.")
    run.set_defaults(func=cmd_run)

    return parser


def _resolve_profile_defaults(args: argparse.Namespace) -> None:
    profile = getattr(args, "profile", "default") or "default"
    paths = resolve_profile_paths(profile)
    if getattr(args, "cookie_jar", None) is None or args.cookie_jar == str(DEFAULT_COOKIE_JAR):
        args.cookie_jar = str(paths.cookie_jar)
    if getattr(args, "env_file", None) is None or args.env_file == str(DEFAULT_ENV_FILE):
        args.env_file = str(paths.env_file)
    if getattr(args, "audit_log", None) is None or args.audit_log == str(DEFAULT_AUDIT_LOG):
        args.audit_log = str(paths.audit_log)
    if getattr(args, "lock_file", None) is None or args.lock_file == str(DEFAULT_LOCK_FILE):
        args.lock_file = str(paths.lock_file)
    if hasattr(args, "config") and (args.config is None or args.config == str(DEFAULT_CONFIG_FILE)):
        args.config = str(paths.config_file)
    if hasattr(args, "env_sample") and (args.env_sample is None or args.env_sample == str(DEFAULT_ENV_FILE.with_name("env.sample"))):
        args.env_sample = str(paths.env_file.with_name("env.sample"))
    if hasattr(args, "state_dir") and (args.state_dir is None or args.state_dir == str(DEFAULT_AUDIT_LOG.parent)):
        args.state_dir = str(paths.state_dir)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _resolve_profile_defaults(args)
    try:
        return args.func(args)
    except SystemExit:
        raise
    except AuthRequiredError as exc:
        _emit_error(args, "auth_required", str(exc))
        return 77
    except MailMateError as exc:
        _emit_error(args, "mailmate_error", str(exc))
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    client = _client(args)
    _ensure_auth(args, client)
    items = client.inbox(
        getattr(args, "inbox_id", None),
        limit=args.limit,
        search=getattr(args, "search", None),
        filter_name=getattr(args, "filter_name", None),
        tag=getattr(args, "tag", None),
    )
    if getattr(args, "sender", None):
        items = [it for it in items if args.sender.lower() in it.sender.lower()]
    if getattr(args, "unread_only", False):
        items = [it for it in items if not it.is_read]
    if getattr(args, "status", None):
        s = args.status.lower()
        if s in {"opened", "open", "開封済み"}:
            items = [it for it in items if it.status == "開封済み"]
        elif s in {"unopened", "未開封"}:
            items = [it for it in items if it.status == "未開封"]
        elif s in {"opening", "pending", "開封待ち", "開封待ち/依頼中", "依頼中"}:
            items = [it for it in items if it.status in {"開封待ち", "開封待ち/依頼中", "依頼中"} or it.scan_requested]
        elif s in {"mailroom", "メール室"}:
            items = [it for it in items if it.status == "メール室"]
        else:
            items = [it for it in items if it.status and s in it.status.lower()]

    rows = [
        {
            "mailId": it.mail_id,
            "sender": it.sender,
            "receivedDate": it.received_date,
            "status": it.status,
            "isRead": it.is_read,
            "isBill": it.is_bill,
            "scanRequested": it.scan_requested,
            "url": it.url,
        }
        for it in items
    ]
    human = _human_list(rows)
    _emit(args, rows, human)
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    client = _client(args)
    _ensure_auth(args, client)
    detail = client.detail(args.mail_id)

    pdf_text = ""
    downloaded_path = None
    target_url = detail.pdf_download_url or (detail.pdf_urls[0] if detail.pdf_urls else None)

    if target_url and (getattr(args, "download_dir", None) or getattr(args, "text", True)):
        try:
            pdf_bytes = client.download_pdf_bytes(
                target_url, referer=f"{args.base_url.rstrip('/')}/app/mails/{detail.mail_id}/view_mail"
            )
            if getattr(args, "download_dir", None):
                dest_dir = Path(args.download_dir).expanduser()
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_file = dest_dir / f"mail_{detail.mail_id}.pdf"
                dest_file.write_bytes(pdf_bytes)
                downloaded_path = str(dest_file)
            if getattr(args, "text", True):
                pdf_text = extract_text_from_pdf(pdf_bytes)
        except Exception as exc:
            pdf_text = f"[Could not download/extract PDF: {exc}]"

    row = {
        "mailId": detail.mail_id,
        "sender": detail.sender,
        "receivedDate": detail.received_date,
        "status": detail.status,
        "location": detail.location,
        "notes": detail.notes,
        "scanRequested": detail.scan_requested,
        "scanMissing": detail.scan_missing,
        "hasDigitalCopy": detail.has_digital_copy,
        "pdfDownloadUrl": detail.pdf_download_url,
        "pdfPageUrls": detail.pdf_urls,
        "downloadedPath": downloaded_path,
        "extractedText": pdf_text,
    }
    human = _human_read(row)
    _emit(args, row, human)
    return 0


def cmd_open(args: argparse.Namespace) -> int:
    require_apply_confirmation(apply=args.apply, yes=args.yes)
    client = _client(args)
    _ensure_auth(args, client)
    detail = client.detail(args.mail_id)
    decision = decide_open_scan(detail)
    applied = False
    if args.apply and decision.eligible:
        client.request_scan(args.mail_id, f"{args.base_url.rstrip('/')}/app/mails/{detail.mail_id}/view_mail")
        applied = True
    row = {
        "mailId": detail.mail_id,
        "sender": detail.sender,
        "receivedDate": detail.received_date,
        "status": "開封待ち/依頼中" if applied else detail.status,
        "decision": "requested" if applied else ("dry_run" if decision.eligible else "skipped"),
        "reason": decision.reason,
        "message": "Open and scan requested." if applied else decision.message,
        "actionUrl": decision.action.url if decision.action else None,
    }
    human = (
        f"{row['decision']}: mail #{row['mailId']} {row.get('sender') or ''} "
        f"status={row.get('status') or '?'} reason={row['reason']}"
    )
    _emit(args, row, human)
    return 0 if decision.eligible or not args.apply else 66


def cmd_download(args: argparse.Namespace) -> int:
    client = _client(args)
    _ensure_auth(args, client)
    detail = client.detail(args.mail_id)
    target_url = detail.pdf_download_url or (detail.pdf_urls[0] if detail.pdf_urls else None)
    if not target_url:
        _emit_error(args, "no_pdf_available", f"Mail #{detail.mail_id} has no scanned PDF copy.")
        return 1
    pdf_bytes = client.download_pdf_bytes(
        target_url, referer=f"{args.base_url.rstrip('/')}/app/mails/{detail.mail_id}/view_mail"
    )
    if getattr(args, "output", None):
        output_path = Path(args.output).expanduser()
    else:
        output_path = Path.cwd() / "downloads" / f"mail_{detail.mail_id}.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf_bytes)
    result = {
        "mailId": detail.mail_id,
        "sender": detail.sender,
        "path": str(output_path.resolve()),
        "sizeBytes": len(pdf_bytes),
    }
    human = f"Downloaded PDF for mail #{detail.mail_id} to {result['path']} ({result['sizeBytes']} bytes)"
    _emit(args, result, human)
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    require_apply_confirmation(apply=args.apply, yes=args.yes)
    client = _client(args)
    _ensure_auth(args, client)
    detail = client.detail(args.mail_id)
    applied = False
    if args.apply:
        client.archive_mail(args.mail_id, f"{args.base_url.rstrip('/')}/app/mails/{detail.mail_id}/view_mail")
        applied = True
    result = {
        "mailId": detail.mail_id,
        "sender": detail.sender,
        "status": detail.status,
        "decision": "archived" if applied else "dry_run",
        "actionUrl": detail.archive_url,
    }
    human = f"{result['decision']}: archive mail #{detail.mail_id} ({detail.sender or ''})"
    _emit(args, result, human)
    return 0


def cmd_mark_unread(args: argparse.Namespace) -> int:
    require_apply_confirmation(apply=args.apply, yes=args.yes)
    client = _client(args)
    _ensure_auth(args, client)
    detail = client.detail(args.mail_id)
    applied = False
    if args.apply:
        client.mark_unread(args.mail_id, f"{args.base_url.rstrip('/')}/app/mails/{detail.mail_id}/view_mail")
        applied = True
    result = {
        "mailId": detail.mail_id,
        "sender": detail.sender,
        "decision": "marked_unread" if applied else "dry_run",
    }
    human = f"{result['decision']}: mail #{detail.mail_id} unread"
    _emit(args, result, human)
    return 0


def cmd_mark_bill(args: argparse.Namespace) -> int:
    require_apply_confirmation(apply=args.apply, yes=args.yes)
    client = _client(args)
    _ensure_auth(args, client)
    detail = client.detail(args.mail_id)
    applied = False
    if args.apply:
        client.mark_bill(args.mail_id, f"{args.base_url.rstrip('/')}/app/mails/{detail.mail_id}/view_mail")
        applied = True
    result = {
        "mailId": detail.mail_id,
        "sender": detail.sender,
        "decision": "marked_bill" if applied else "dry_run",
    }
    human = f"{result['decision']}: mail #{detail.mail_id} bill"
    _emit(args, result, human)
    return 0


def cmd_mark_receipt(args: argparse.Namespace) -> int:
    require_apply_confirmation(apply=args.apply, yes=args.yes)
    client = _client(args)
    _ensure_auth(args, client)
    detail = client.detail(args.mail_id)
    applied = False
    if args.apply:
        client.mark_receipt(args.mail_id, f"{args.base_url.rstrip('/')}/app/mails/{detail.mail_id}/view_mail")
        applied = True
    result = {
        "mailId": detail.mail_id,
        "sender": detail.sender,
        "decision": "marked_receipt" if applied else "dry_run",
    }
    human = f"{result['decision']}: mail #{detail.mail_id} receipt"
    _emit(args, result, human)
    return 0


def cmd_address(args: argparse.Namespace) -> int:
    client = _client(args)
    _ensure_auth(args, client)
    addr = client.mailing_address(getattr(args, "inbox_id", None))
    row = {
        "inboxId": addr.inbox_id,
        "mailInAddress": addr.mail_in_address,
        "invoiceAddress": addr.invoice_address,
        "receiptAddress": addr.receipt_address,
        "japaneseAddress": addr.japanese_address,
        "englishAddress": addr.english_address,
        "postalCode": addr.postal_code,
        "managementId": addr.management_id,
    }
    human = (
        f"MailMate Mailing Address (Inbox #{row['inboxId']}):\n"
        f"  Japanese : {row['japaneseAddress']}\n"
        f"  English  : {row['englishAddress']}\n"
        f"  Inbound  : {row['mailInAddress']}\n"
        f"  Invoice  : {row['invoiceAddress']}\n"
        f"  Receipt  : {row['receiptAddress']}"
    )
    _emit(args, row, human)
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    client = _client(args)
    _ensure_auth(args, client)
    current_note = client.get_note(args.mail_id)
    if args.text is None:
        row = {
            "mailId": args.mail_id,
            "note": current_note,
        }
        human = f"mail #{args.mail_id} note: {current_note or '(empty)'}"
        _emit(args, row, human)
        return 0

    require_apply_confirmation(apply=args.apply, yes=args.yes)
    applied = False
    if args.apply:
        client.set_note(args.mail_id, args.text)
        applied = True

    row = {
        "mailId": args.mail_id,
        "previousNote": current_note,
        "note": args.text if applied else current_note,
        "proposedNote": args.text,
        "decision": "updated" if applied else "dry_run",
    }
    human = f"{row['decision']}: mail #{args.mail_id} note -> {args.text}"
    _emit(args, row, human)
    return 0


def cmd_timeline(args: argparse.Namespace) -> int:
    client = _client(args)
    _ensure_auth(args, client)
    acts = client.activities(args.mail_id)
    rows = [
        {
            "timestamp": a.timestamp,
            "actor": a.actor,
            "description": a.description,
        }
        for a in acts
    ]
    lines = [f"Timeline for mail #{args.mail_id} ({len(rows)} events):"]
    for r in rows:
        lines.append(f"  {r['timestamp']} | {r['actor']} | {r['description']}")
    human = "\n".join(lines)
    _emit(args, rows, human)
    return 0


def cmd_bills(args: argparse.Namespace) -> int:
    client = _client(args)
    _ensure_auth(args, client)
    if getattr(args, "export", None):
        csv_text = client.export_bills_csv()
        dest = Path(args.export).expanduser()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(csv_text, encoding="utf-8")
        row = {"exportedPath": str(dest.resolve()), "sizeBytes": len(csv_text.encode("utf-8"))}
        _emit(args, row, f"Exported bills ledger to {row['exportedPath']}")
        return 0

    bill_items = client.bills()
    if getattr(args, "unpaid_only", False):
        bill_items = [b for b in bill_items if b.status == "unpaid"]

    rows = [
        {
            "vendor": b.vendor,
            "dueDate": b.due_date,
            "amount": b.amount,
            "linkedMailId": b.linked_mail_id,
            "status": b.status,
            "category": b.category,
        }
        for b in bill_items
    ]
    lines = [f"DUE DATE    AMOUNT       MAIL#    STATUS  VENDOR"]
    lines.append("-" * 72)
    for r in rows:
        due = r["dueDate"] or "—"
        amt = r["amount"].ljust(12)
        mid = (r["linkedMailId"] or "—").ljust(7)
        st = r["status"].ljust(7)
        lines.append(f"{due:<11} {amt} {mid} {st} {r['vendor']}")
    human = "\n".join(lines)
    _emit(args, rows, human)
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    credentials = _credentials(args)
    if credentials is None:
        raise AuthRequiredError("Provide MAILMATE_EMAIL/MAILMATE_PASSWORD or --op-item to login.")
    client = _client(args)
    client.login(credentials)
    _emit(args, {"ok": True, "cookieJar": str(Path(args.cookie_jar).expanduser())}, "Login refreshed.")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    result = scaffold_local_setup(args.config, args.env_sample, args.state_dir)
    _emit(args, result, _human_init(result))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    report = build_doctor_report(args)
    _emit(args, report, _human_doctor(report))
    return 0 if report["ok"] else 77


def cmd_status(args: argparse.Namespace) -> int:
    report = build_status_report(args.audit_log)
    _emit(args, report, _human_status(report))
    return 0 if report["ok"] else 77


def cmd_launch_agent(args: argparse.Namespace) -> int:
    plist = build_launch_agent_plist(
        label=args.label,
        program=args.program,
        interval_minutes=args.interval_minutes,
        stdout_log=args.stdout_log,
        stderr_log=args.stderr_log,
        run_yes=args.run_yes,
    )
    if args.print_plist:
        print(launch_agent_plist_xml(plist), end="")
        return 0
    if args.install:
        result = install_launch_agent(args.plist_path, plist)
    else:
        result = {
            "installed": False,
            "plistPath": str(Path(args.plist_path).expanduser()),
            "label": args.label,
            "programArguments": plist["ProgramArguments"],
            "startInterval": plist["StartInterval"],
            "nextAction": "Pass --install to write the plist, then load it manually with launchctl when ready.",
        }
    _emit(args, result, _human_launch_agent(result))
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    client = _client(args)
    _ensure_auth(args, client)
    detail = client.detail(args.mail_id)
    decision = decide_discard(detail)
    _emit(args, format_decision_row(detail, decision, applied=False), _human_row(format_decision_row(detail, decision, applied=False)))
    return 0


def cmd_abandon(args: argparse.Namespace) -> int:
    require_apply_confirmation(apply=args.apply, yes=args.yes)
    client = _client(args)
    _ensure_auth(args, client)
    detail = client.detail(args.mail_id)
    decision = decide_discard(detail)
    applied = False
    if args.apply and decision.eligible and decision.action:
        client.submit_discard(decision.action, f"{args.base_url.rstrip('/')}/app/mails/{detail.mail_id}/view_mail")
        applied = True
    row = format_decision_row(detail, decision, applied=applied)
    _emit(args, row, _human_row(row))
    return 0 if decision.eligible or not args.apply else 66


def cmd_sweep(args: argparse.Namespace) -> int:
    require_apply_confirmation(apply=args.apply, yes=args.yes)
    if args.limit <= 0:
        raise SystemExit(2)
    client = _client(args)
    _ensure_auth(args, client)
    rows = _sweep_rows(client, args)
    _emit(args, rows, "\n".join(_human_row(row) for row in rows if not args.quiet or row["decision"] != "skipped"))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = load_run_config(args.config)
    require_apply_confirmation(apply=config.apply, yes=args.yes)
    with FileLock(args.lock_file):
        client = _client(args)
        _ensure_auth(args, client)
        rows = _sweep_rows(client, _run_config_to_args(config, args))
        append_audit_log(
            args.audit_log,
            {
                "command": "run",
                "config": {
                    "inboxId": config.inbox_id,
                    "limit": config.limit,
                    "senderContains": config.sender_contains,
                    "mailIds": config.mail_ids,
                    "apply": config.apply,
                },
                "rows": rows,
            },
        )
    _emit(args, rows, "\n".join(_human_row(row) for row in rows if not args.quiet or row["decision"] != "skipped"))
    return 0


def _sweep_rows(client: MailMateClient, args: argparse.Namespace) -> list[dict[str, object]]:
    items = _target_items(client.inbox(args.inbox_id, limit=args.limit), args)
    rows: list[dict[str, object]] = []
    for item in items:
        detail = client.detail(item.mail_id, scan_requested=item.scan_requested)
        decision = decide_discard(detail)
        applied = False
        if args.apply and decision.eligible and decision.action:
            client.submit_discard(decision.action, f"{args.base_url.rstrip('/')}/app/mails/{detail.mail_id}/view_mail")
            applied = True
        rows.append(format_decision_row(detail, decision, applied=applied))
    return rows


def _run_config_to_args(config: RunConfig, args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        inbox_id=config.inbox_id,
        limit=config.limit,
        sender_contains=config.sender_contains,
        mail_id=config.mail_ids,
        apply=config.apply,
        base_url=args.base_url,
    )


def _target_items(items: Iterable[InboxItem], args: argparse.Namespace) -> list[InboxItem]:
    wanted_ids = set(args.mail_id or [])
    output = []
    for item in items:
        if wanted_ids and item.mail_id not in wanted_ids:
            continue
        if args.sender_contains and not _matches_any_sender(item.sender, args.sender_contains):
            continue
        output.append(item)
    return output


def _matches_any_sender(sender: str, filters: str | list[str]) -> bool:
    if isinstance(filters, str):
        filters = [filters]
    return any(part in sender for part in filters)


def _client(args: argparse.Namespace) -> MailMateClient:
    return MailMateClient(base_url=args.base_url, cookie_jar=Path(args.cookie_jar))


def _credentials(args: argparse.Namespace) -> Credentials | None:
    if args.no_login:
        return None
    return resolve_credentials(
        email=args.email,
        password_env=args.password_env,
        op_item=args.op_item,
        env_file=Path(args.env_file) if args.env_file else None,
    )


def _ensure_auth(args: argparse.Namespace, client: MailMateClient) -> None:
    client.ensure_authenticated(None if args.no_login else lambda: _credentials(args))


def _emit(args: argparse.Namespace, payload: object, human: str) -> None:
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif human:
        print(human)


def _emit_error(args: argparse.Namespace, code: str, message: str) -> None:
    if getattr(args, "json", False):
        print(json.dumps({"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False), file=sys.stderr)
    else:
        print(f"{code}: {message}", file=sys.stderr)


def _human_row(row: dict[str, object]) -> str:
    return (
        f"{row['decision']}: mail #{row['mailId']} {row.get('sender') or ''} "
        f"status={row.get('status') or '?'} reason={row['reason']}"
    ).strip()


def _human_list(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "No mail found matching criteria."
    lines = [
        f"{'ID':<8} {'DATE':<16} {'STATUS':<12} {'READ':<6} {'BILL':<5} {'SENDER'}",
        "-" * 72,
    ]
    for r in rows:
        m_id = str(r["mailId"])
        date = str(r.get("receivedDate") or "-")
        st = str(r.get("status") or "-")
        read = "read" if r.get("isRead") else "UNREAD"
        bill = "bill" if r.get("isBill") else ""
        sender = str(r.get("sender") or "")
        lines.append(f"{m_id:<8} {date:<16} {st:<12} {read:<6} {bill:<5} {sender}")
    return "\n".join(lines)


def _human_read(row: dict[str, object]) -> str:
    parts = [
        "=" * 64,
        f"Mail #{row['mailId']}: {row.get('sender') or 'Unknown Sender'}",
        "=" * 64,
        f"Received Date:  {row.get('receivedDate') or '-'}",
        f"Status:         {row.get('status') or '-'}",
        f"Location:       {row.get('location') or '-'}",
    ]
    if row.get("notes"):
        parts.append(f"Notes:          {row['notes']}")
    if row.get("pdfDownloadUrl"):
        parts.append(f"Download URL:   {row['pdfDownloadUrl']}")
    if row.get("downloadedPath"):
        parts.append(f"Saved to:       {row['downloadedPath']}")
    if row.get("extractedText"):
        parts.append("\n--- Scanned Document Text ---")
        parts.append(str(row["extractedText"]))
    elif row.get("scanMissing"):
        parts.append("\n[Notice: Mail is unopened/scan is pending; no digital copy available yet.]")
    parts.append("=" * 64)
    return "\n".join(parts)


def build_doctor_report(args: argparse.Namespace) -> dict[str, object]:
    cookie_path = Path(args.cookie_jar).expanduser()
    env_path = Path(args.env_file).expanduser() if getattr(args, "env_file", None) else None
    env_values = load_env_file(env_path) if env_path else {}
    password_env = getattr(args, "password_env", "MAILMATE_PASSWORD")
    email_present = bool(getattr(args, "email", None) or os.environ.get("MAILMATE_EMAIL") or env_values.get("MAILMATE_EMAIL"))
    password_present = bool(os.environ.get(password_env) or env_values.get(password_env))
    op_item_present = bool(getattr(args, "op_item", None) or os.environ.get("MAILMATE_OP_ITEM") or env_values.get("MAILMATE_OP_ITEM"))
    cookie_present = cookie_path.exists() and cookie_path.stat().st_size > 0
    credential_status = "present" if email_present and password_present else ("op_configured" if op_item_present else "missing")

    checks: dict[str, dict[str, object]] = {
        "cookieJar": {
            "status": "present" if cookie_present else "missing",
            "path": str(cookie_path),
            "mode": _file_mode(cookie_path) if cookie_path.exists() else None,
        },
        "envFile": {
            "status": "present" if env_path and env_path.exists() else "missing",
            "path": str(env_path) if env_path else None,
        },
        "credentials": {
            "status": credential_status,
            "email": "present" if email_present else "missing",
            "password": "present" if password_present else "missing",
            "opItem": "configured" if op_item_present else "not_configured",
        },
        "onePasswordCli": _one_password_cli_check(),
    }
    ok = cookie_present or (email_present and password_present) or op_item_present
    next_action = (
        "Run list/read/sweep dry-run."
        if ok
        else f"Set MAILMATE_EMAIL and {password_env}, create {env_path or DEFAULT_ENV_FILE}, or pass --op-item."
    )
    return {"ok": ok, "checks": checks, "nextAction": next_action}


def _file_mode(path: Path) -> str:
    return oct(path.stat().st_mode & 0o777)


def _one_password_cli_check() -> dict[str, object]:
    op_path = shutil.which("op")
    if not op_path:
        return {"status": "missing"}
    try:
        proc = subprocess.run(["op", "--version"], check=True, capture_output=True, text=True, timeout=5)
    except Exception:
        return {"status": "present", "version": "unknown"}
    return {"status": "present", "version": proc.stdout.strip()}


def _human_doctor(report: dict[str, object]) -> str:
    status = "ready" if report["ok"] else "needs_auth"
    return f"{status}: {report['nextAction']}"


def _human_init(result: dict[str, object]) -> str:
    return f"initialized: config={result['config']} envSample={result['envSample']}"


def _human_status(report: dict[str, object]) -> str:
    if not report["ok"]:
        return f"no_audit_log: {report['auditLog']}"
    latest = report["latest"]
    if not isinstance(latest, dict):
        return f"no_audit_log: {report['auditLog']}"
    counts = latest.get("counts", {})
    return (
        f"last_run: runs={report['runs']} discarded={counts.get('discarded', 0)} "
        f"dry_run={counts.get('dry_run', 0)} skipped={counts.get('skipped', 0)}"
    )


def _human_launch_agent(result: dict[str, object]) -> str:
    status = "installed" if result.get("installed") else "preview"
    return f"{status}: {result['plistPath']}"


def _default_program_path() -> str:
    project_bin = Path(__file__).resolve().parents[2] / "bin" / "mailmate"
    if project_bin.exists():
        return str(project_bin)
    found = shutil.which("mailmate")
    return found or "mailmate"
