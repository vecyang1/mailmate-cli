import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mailmate_cli.cli import (
    build_doctor_report,
    cmd_init,
    cmd_launch_agent,
    cmd_run,
    cmd_status,
    format_decision_row,
    require_apply_confirmation,
)
from mailmate_cli.models import DiscardAction, DiscardDecision, InboxItem, MailDetail


class CliTests(unittest.TestCase):
    def test_apply_requires_yes(self):
        with self.assertRaises(SystemExit) as ctx:
            require_apply_confirmation(apply=True, yes=False)

        self.assertEqual(ctx.exception.code, 2)

    def test_format_decision_row_does_not_expose_secret_data(self):
        action = DiscardAction(
            method="PATCH",
            url="https://mailmate.jp/app/mails/198843/discard",
            fields={"authenticity_token": "dummy-token"},
        )
        detail = MailDetail(
            mail_id="198843",
            sender="全国健康保険協会 東京支部",
            status="開封済み",
            received_date="2026年05月28日(木)",
            scan_missing=False,
            scan_requested=True,
            has_digital_copy=True,
            already_discarded=False,
            discard_actions=[action],
        )
        decision = DiscardDecision(True, "eligible", action=action)

        row = format_decision_row(detail, decision, applied=False)

        self.assertEqual(row["mailId"], "198843")
        self.assertEqual(row["decision"], "dry_run")
        self.assertEqual(row["reason"], "eligible")
        self.assertEqual(row["actionMethod"], "PATCH")
        self.assertNotIn("dummy-token", str(row))

    def test_doctor_report_masks_credentials_and_reports_local_readiness(self):
        with TemporaryDirectory() as tmp:
            cookie_jar = Path(tmp) / "cookies.txt"
            cookie_jar.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
            cookie_jar.chmod(0o600)
            env_file = Path(tmp) / "mailmate.env"
            env_file.write_text(
                "MAILMATE_EMAIL=user@example.com\nMAILMATE_PASSWORD=dummy-password\n",
                encoding="utf-8",
            )
            args = Namespace(
                cookie_jar=str(cookie_jar),
                env_file=str(env_file),
                password_env="MAILMATE_PASSWORD",
                op_item=None,
                no_login=False,
            )

            with patch.dict("os.environ", {}, clear=True):
                report = build_doctor_report(args)

        self.assertTrue(report["ok"])
        self.assertIn("credentials", report["checks"])
        self.assertEqual(report["checks"]["credentials"]["status"], "present")
        self.assertEqual(report["checks"]["credentials"]["email"], "present")
        self.assertEqual(report["checks"]["credentials"]["password"], "present")
        self.assertNotIn("dummy-password", str(report))
        self.assertNotIn("user@example.com", str(report))

    def test_doctor_report_treats_1password_item_as_ready(self):
        with TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "mailmate.env"
            env_file.write_text("MAILMATE_OP_ITEM=mailmate-item\n", encoding="utf-8")
            args = Namespace(
                cookie_jar=str(Path(tmp) / "missing-cookies.txt"),
                env_file=str(env_file),
                password_env="MAILMATE_PASSWORD",
                op_item=None,
                no_login=False,
            )

            with patch.dict("os.environ", {}, clear=True):
                report = build_doctor_report(args)

        self.assertTrue(report["ok"])
        self.assertEqual(report["checks"]["credentials"]["status"], "op_configured")
        self.assertEqual(report["checks"]["credentials"]["opItem"], "configured")

    def test_run_command_uses_config_and_writes_audit_log(self):
        action = DiscardAction(method="PATCH", url="https://mailmate.jp/app/mails/198843/discard")

        class FakeClient:
            def __init__(self):
                self.submitted = False

            def inbox(self, inbox_id, limit=50):
                self.inbox_args = (inbox_id, limit)
                return [
                    InboxItem(
                        mail_id="198843",
                        sender="全国健康保険協会東京支部",
                        received_date="2026年05月28日(木)",
                        scan_requested=True,
                    )
                ]

            def detail(self, mail_id, *, scan_requested=False):
                return MailDetail(
                    mail_id=mail_id,
                    sender="全国健康保険協会東京支部",
                    status="開封済み",
                    received_date="2026年05月28日(木)",
                    scan_missing=False,
                    scan_requested=scan_requested,
                    has_digital_copy=True,
                    already_discarded=False,
                    discard_actions=[action],
                )

            def submit_discard(self, action, referer):
                self.submitted = True

        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            audit_path = Path(tmp) / "audit.jsonl"
            lock_path = Path(tmp) / "run.lock"
            config_path.write_text(
                json.dumps({"inboxId": "82433", "limit": 3, "senderContains": "全国健康保険協会"}),
                encoding="utf-8",
            )
            client = FakeClient()
            args = Namespace(
                config=str(config_path),
                audit_log=str(audit_path),
                lock_file=str(lock_path),
                base_url="https://mailmate.jp",
                yes=False,
                quiet=True,
                json=True,
                no_login=True,
            )

            with (
                patch("mailmate_cli.cli._client", return_value=client),
                patch("mailmate_cli.cli._ensure_auth", return_value=None),
                redirect_stdout(StringIO()),
            ):
                exit_code = cmd_run(args)

            records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(exit_code, 0)
        self.assertFalse(client.submitted)
        self.assertEqual(client.inbox_args, ("82433", 3))
        self.assertEqual(records[0]["command"], "run")
        self.assertEqual(records[0]["rows"][0]["decision"], "dry_run")
        self.assertEqual(records[0]["rows"][0]["mailId"], "198843")

    def test_status_command_reads_audit_log(self):
        with TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            audit_path.write_text(
                json.dumps({"timestamp": "2026-06-23T00:00:00+00:00", "command": "run", "rows": [{"decision": "skipped"}]})
                + "\n",
                encoding="utf-8",
            )
            args = Namespace(audit_log=str(audit_path), json=True)

            output = StringIO()
            with redirect_stdout(output):
                exit_code = cmd_status(args)

        self.assertEqual(exit_code, 0)
        self.assertIn('"runs": 1', output.getvalue())
        self.assertIn('"skipped": 1', output.getvalue())

    def test_init_command_scaffolds_local_files(self):
        with TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            env_sample_path = Path(tmp) / "env.sample"
            state_dir = Path(tmp) / "state"
            args = Namespace(
                config=str(config_path),
                env_sample=str(env_sample_path),
                state_dir=str(state_dir),
                json=True,
            )

            output = StringIO()
            with redirect_stdout(output):
                exit_code = cmd_init(args)
            config_exists = config_path.exists()
            env_sample_exists = env_sample_path.exists()
            state_dir_exists = state_dir.exists()

        self.assertEqual(exit_code, 0)
        self.assertIn('"createdConfig": true', output.getvalue())
        self.assertTrue(config_exists)
        self.assertTrue(env_sample_exists)
        self.assertTrue(state_dir_exists)

    def test_launch_agent_command_installs_plist_when_explicit(self):
        with TemporaryDirectory() as tmp:
            plist_path = Path(tmp) / "com.vec.mailmate-cli.run.plist"
            args = Namespace(
                label="com.vec.mailmate-cli.run",
                program="/opt/mailmate",
                interval_minutes=90,
                plist_path=str(plist_path),
                stdout_log=str(Path(tmp) / "out.log"),
                stderr_log=str(Path(tmp) / "err.log"),
                run_yes=False,
                install=True,
                print_plist=False,
                json=True,
            )

            output = StringIO()
            with redirect_stdout(output):
                exit_code = cmd_launch_agent(args)
            exists = plist_path.exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(exists)
        self.assertIn('"installed": true', output.getvalue())

    def test_cmd_list_filters_and_outputs(self):
        from mailmate_cli.cli import cmd_list

        mock_items = [
            InboxItem(mail_id="101", sender="茅ヶ崎市役所", received_date="2026年09月01日", status="開封済み", is_read=True, is_bill=False),
            InboxItem(mail_id="102", sender="法律事務所", received_date="2026年09月02日", status="未開封", is_read=False, is_bill=False),
        ]
        args = Namespace(
            base_url="https://mailmate.jp",
            cookie_jar="/tmp/mock_cookies.txt",
            no_login=True,
            inbox_id=None,
            limit=10,
            sender=None,
            status=None,
            unread_only=False,
            json=True,
            quiet=False,
        )

        with patch("mailmate_cli.cli._ensure_auth"), patch("mailmate_cli.cli._client") as mock_c:
            mock_c.return_value.inbox.return_value = mock_items
            buf = StringIO()
            with redirect_stdout(buf):
                exit_code = cmd_list(args)

        self.assertEqual(exit_code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["mailId"], "101")
        self.assertEqual(data[0]["status"], "開封済み")
        self.assertTrue(data[0]["isRead"])
        self.assertEqual(data[1]["mailId"], "102")
        self.assertFalse(data[1]["isRead"])

    def test_cmd_read_outputs_metadata_and_text(self):
        from mailmate_cli.cli import cmd_read

        mock_detail = MailDetail(
            mail_id="101",
            sender="茅ヶ崎市役所",
            status="開封済み",
            received_date="2026年09月01日",
            scan_missing=False,
            scan_requested=False,
            has_digital_copy=True,
            already_discarded=False,
            location="メール室",
            notes="重要通知",
            pdf_download_url="https://mailmate.jp/app/mails/101/generate_pdf",
        )
        args = Namespace(
            base_url="https://mailmate.jp",
            cookie_jar="/tmp/mock_cookies.txt",
            no_login=True,
            mail_id="101",
            text=True,
            download_dir=None,
            json=True,
            quiet=False,
        )

        with patch("mailmate_cli.cli._ensure_auth"), \
             patch("mailmate_cli.cli._client") as mock_c, \
             patch("mailmate_cli.cli.extract_text_from_pdf", return_value="Page 1 Content"):
            mock_c.return_value.detail.return_value = mock_detail
            mock_c.return_value.download_pdf_bytes.return_value = b"%PDF-dummy"
            buf = StringIO()
            with redirect_stdout(buf):
                exit_code = cmd_read(args)

        self.assertEqual(exit_code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["mailId"], "101")
        self.assertEqual(data["location"], "メール室")
        self.assertEqual(data["notes"], "重要通知")
        self.assertEqual(data["extractedText"], "Page 1 Content")

    def test_profile_resolves_custom_paths(self):
        from mailmate_cli.cli import build_parser, _resolve_profile_defaults

        parser = build_parser()
        args = parser.parse_args(["--profile", "profile2", "doctor"])
        _resolve_profile_defaults(args)

        self.assertIn("profiles/profile2", args.cookie_jar)
        self.assertIn("profiles/profile2", args.env_file)

    def test_cmd_open_dry_run_and_apply(self):
        from mailmate_cli.cli import cmd_open
        from mailmate_cli.models import OpenScanAction

        mock_detail = MailDetail(
            mail_id="216221",
            sender="全国健康保険協会",
            status="未開封",
            received_date="2026年08月10日(月)",
            scan_missing=True,
            scan_requested=False,
            has_digital_copy=False,
            already_discarded=False,
            open_scan_action=OpenScanAction(method="POST", url="https://mailmate.jp/app/mails/216221/open_mail"),
        )
        dry_args = Namespace(
            base_url="https://mailmate.jp",
            cookie_jar="/tmp/mock_cookies.txt",
            no_login=True,
            mail_id="216221",
            apply=False,
            yes=False,
            json=True,
            quiet=False,
        )

        with patch("mailmate_cli.cli._ensure_auth"), patch("mailmate_cli.cli._client") as mock_c:
            mock_c.return_value.detail.return_value = mock_detail
            buf = StringIO()
            with redirect_stdout(buf):
                exit_code = cmd_open(dry_args)
            self.assertEqual(exit_code, 0)
            data = json.loads(buf.getvalue())
            self.assertEqual(data["decision"], "dry_run")
            self.assertEqual(data["reason"], "eligible")

        apply_args = Namespace(
            base_url="https://mailmate.jp",
            cookie_jar="/tmp/mock_cookies.txt",
            no_login=True,
            mail_id="216221",
            apply=True,
            yes=True,
            json=True,
            quiet=False,
        )
        with patch("mailmate_cli.cli._ensure_auth"), patch("mailmate_cli.cli._client") as mock_c:
            mock_c.return_value.detail.return_value = mock_detail
            buf = StringIO()
            with redirect_stdout(buf):
                exit_code = cmd_open(apply_args)
            self.assertEqual(exit_code, 0)
            data = json.loads(buf.getvalue())
            self.assertEqual(data["decision"], "requested")
            mock_c.return_value.request_scan.assert_called_once()

    def test_cmd_download(self):
        from mailmate_cli.cli import cmd_download

        mock_detail = MailDetail(
            mail_id="216635",
            sender="法律事務所",
            status="開封済み",
            received_date="2026年08月12日(水)",
            scan_missing=False,
            scan_requested=False,
            has_digital_copy=True,
            already_discarded=False,
            pdf_download_url="https://mailmate.jp/app/mails/216635/generate_pdf",
        )
        with TemporaryDirectory() as tmp:
            dest_pdf = Path(tmp) / "downloaded.pdf"
            args = Namespace(
                base_url="https://mailmate.jp",
                cookie_jar="/tmp/mock_cookies.txt",
                no_login=True,
                mail_id="216635",
                output=str(dest_pdf),
                json=True,
                quiet=False,
            )
            with patch("mailmate_cli.cli._ensure_auth"), patch("mailmate_cli.cli._client") as mock_c:
                mock_c.return_value.detail.return_value = mock_detail
                mock_c.return_value.download_pdf_bytes.return_value = b"%PDF-1.4 test bytes"
                buf = StringIO()
                with redirect_stdout(buf):
                    exit_code = cmd_download(args)

            self.assertEqual(exit_code, 0)
            self.assertTrue(dest_pdf.exists())
            self.assertEqual(dest_pdf.read_bytes(), b"%PDF-1.4 test bytes")
            data = json.loads(buf.getvalue())
            self.assertEqual(data["sizeBytes"], len(b"%PDF-1.4 test bytes"))

    def test_cmd_archive_and_mark_commands(self):
        from mailmate_cli.cli import cmd_archive, cmd_mark_bill, cmd_mark_receipt, cmd_mark_unread

        mock_detail = MailDetail(
            mail_id="216635",
            sender="法律事務所",
            status="開封済み",
            received_date="2026年08月12日(水)",
            scan_missing=False,
            scan_requested=False,
            has_digital_copy=True,
            already_discarded=False,
            archive_url="https://mailmate.jp/app/mails/216635/archive_mail",
        )
        args = Namespace(
            base_url="https://mailmate.jp",
            cookie_jar="/tmp/mock_cookies.txt",
            no_login=True,
            mail_id="216635",
            apply=True,
            yes=True,
            json=True,
            quiet=False,
        )
        with patch("mailmate_cli.cli._ensure_auth"), patch("mailmate_cli.cli._client") as mock_c:
            mock_c.return_value.detail.return_value = mock_detail
            buf = StringIO()
            with redirect_stdout(buf):
                self.assertEqual(cmd_archive(args), 0)
                self.assertEqual(cmd_mark_bill(args), 0)
                self.assertEqual(cmd_mark_receipt(args), 0)
                self.assertEqual(cmd_mark_unread(args), 0)
            mock_c.return_value.archive_mail.assert_called_once()
            mock_c.return_value.mark_bill.assert_called_once()
            mock_c.return_value.mark_receipt.assert_called_once()
            mock_c.return_value.mark_unread.assert_called_once()

    def test_cmd_address(self):
        from mailmate_cli.cli import cmd_address
        from mailmate_cli.models import MailingAddress

        mock_addr = MailingAddress(
            inbox_id="82433",
            mail_in_address="test@pm.mailmate.jp",
            invoice_address="test@invoice.mailmate.jp",
            receipt_address="test@receipt.mailmate.jp",
            japanese_address="〒 810-0001 福岡市中央区天神3-16-17",
            english_address="(ID 48713), Tenjin, Japan",
            postal_code="810-0001",
            management_id="48713",
        )
        args = Namespace(
            base_url="https://mailmate.jp",
            cookie_jar="/tmp/mock_cookies.txt",
            no_login=True,
            inbox_id=None,
            json=True,
            quiet=False,
        )
        with patch("mailmate_cli.cli._ensure_auth"), patch("mailmate_cli.cli._client") as mock_c:
            mock_c.return_value.mailing_address.return_value = mock_addr
            buf = StringIO()
            with redirect_stdout(buf):
                self.assertEqual(cmd_address(args), 0)
            self.assertIn("test@pm.mailmate.jp", buf.getvalue())

    def test_cmd_note_read_and_update(self):
        from mailmate_cli.cli import cmd_note

        args_read = Namespace(
            base_url="https://mailmate.jp",
            cookie_jar="/tmp/mock_cookies.txt",
            no_login=True,
            mail_id="216635",
            text=None,
            apply=False,
            yes=False,
            json=True,
            quiet=False,
        )
        args_update = Namespace(
            base_url="https://mailmate.jp",
            cookie_jar="/tmp/mock_cookies.txt",
            no_login=True,
            mail_id="216635",
            text="new note text",
            apply=True,
            yes=True,
            json=True,
            quiet=False,
        )
        with patch("mailmate_cli.cli._ensure_auth"), patch("mailmate_cli.cli._client") as mock_c:
            mock_c.return_value.get_note.return_value = "current note"
            buf = StringIO()
            with redirect_stdout(buf):
                self.assertEqual(cmd_note(args_read), 0)
            self.assertIn("current note", buf.getvalue())

            buf2 = StringIO()
            with redirect_stdout(buf2):
                self.assertEqual(cmd_note(args_update), 0)
            mock_c.return_value.set_note.assert_called_once_with("216635", "new note text")
            self.assertIn("new note text", buf2.getvalue())

    def test_cmd_timeline(self):
        from mailmate_cli.cli import cmd_timeline
        from mailmate_cli.models import ActivityItem

        mock_acts = [
            ActivityItem(timestamp="2026/08/13 10:16", actor="MailMate", description="開封しました")
        ]
        args = Namespace(
            base_url="https://mailmate.jp",
            cookie_jar="/tmp/mock_cookies.txt",
            no_login=True,
            mail_id="216635",
            json=True,
            quiet=False,
        )
        with patch("mailmate_cli.cli._ensure_auth"), patch("mailmate_cli.cli._client") as mock_c:
            mock_c.return_value.activities.return_value = mock_acts
            buf = StringIO()
            with redirect_stdout(buf):
                self.assertEqual(cmd_timeline(args), 0)
            self.assertIn("開封しました", buf.getvalue())

    def test_cmd_bills(self):
        from mailmate_cli.cli import cmd_bills
        from mailmate_cli.models import BillItem

        mock_bills = [
            BillItem(vendor="水道局", due_date="2026-07-01", amount="1,000円", linked_mail_id="999", status="unpaid")
        ]
        args = Namespace(
            base_url="https://mailmate.jp",
            cookie_jar="/tmp/mock_cookies.txt",
            no_login=True,
            export=None,
            unpaid_only=False,
            json=True,
            quiet=False,
        )
        with patch("mailmate_cli.cli._ensure_auth"), patch("mailmate_cli.cli._client") as mock_c:
            mock_c.return_value.bills.return_value = mock_bills
            buf = StringIO()
            with redirect_stdout(buf):
                self.assertEqual(cmd_bills(args), 0)
            self.assertIn("水道局", buf.getvalue())
            self.assertIn("1,000円", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
