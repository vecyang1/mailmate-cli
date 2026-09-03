import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mailmate_cli.client import _ssl_context, load_env_file, resolve_credentials


class ClientTests(unittest.TestCase):
    def test_ssl_context_is_available(self):
        context = _ssl_context()

        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode.name, "CERT_REQUIRED")

    def test_load_env_file_parses_quotes_exports_and_comments(self):
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "mailmate.env"
            env_path.write_text(
                """
                # local MailMate runtime config
                export MAILMATE_EMAIL="user@example.com"
                MAILMATE_PASSWORD='dummy value'
                IGNORED_LINE
                """,
                encoding="utf-8",
            )

            values = load_env_file(env_path)

        self.assertEqual(values["MAILMATE_EMAIL"], "user@example.com")
        self.assertEqual(values["MAILMATE_PASSWORD"], "dummy value")
        self.assertNotIn("IGNORED_LINE", values)

    def test_resolve_credentials_prefers_environment_over_env_file(self):
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "mailmate.env"
            env_path.write_text(
                "MAILMATE_EMAIL=file@example.com\nMAILMATE_PASSWORD=file-password\n",
                encoding="utf-8",
            )

            with patch.dict(
                "os.environ",
                {"MAILMATE_EMAIL": "env@example.com", "MAILMATE_PASSWORD": "env-password"},
                clear=False,
            ):
                credentials = resolve_credentials(env_file=env_path)

        self.assertIsNotNone(credentials)
        self.assertEqual(credentials.email, "env@example.com")
        self.assertEqual(credentials.password, "env-password")

    def test_resolve_credentials_uses_env_file_when_process_env_missing(self):
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "mailmate.env"
            env_path.write_text(
                "MAILMATE_EMAIL=file@example.com\nMAILMATE_PASSWORD=file-password\n",
                encoding="utf-8",
            )

            with patch.dict("os.environ", {}, clear=True):
                credentials = resolve_credentials(env_file=env_path)

        self.assertIsNotNone(credentials)
        self.assertEqual(credentials.email, "file@example.com")
        self.assertEqual(credentials.password, "file-password")

    def test_inbox_path_without_inbox_id(self):
        from mailmate_cli.client import MailMateClient

        client = MailMateClient()
        with patch.object(client, "request", return_value=("<html></html>", "https://mailmate.jp/app/mails")) as mock_req:
            client.inbox(inbox_id=None, limit=10)
            mock_req.assert_called_once_with("/app/mails")

    def test_inbox_path_with_inbox_id(self):
        from mailmate_cli.client import MailMateClient

        client = MailMateClient()
        with patch.object(client, "request", return_value=("<html></html>", "https://mailmate.jp/app/mails?inbox_id=999")) as mock_req:
            client.inbox(inbox_id="999", limit=10)
            mock_req.assert_called_once_with("/app/mails?inbox_id=999")

    def test_inbox_path_with_search_filter_and_tag(self):
        from mailmate_cli.client import MailMateClient

        client = MailMateClient()
        with patch.object(client, "request", return_value=("<html></html>", "https://mailmate.jp/app/mails")) as mock_req:
            client.inbox(search="神田", filter_name="shredded", tag="bill", limit=10)
            args = mock_req.call_args[0][0]
            self.assertIn("search=%E7%A5%9E%E7%94%B0", args)
            self.assertIn("filter=shredded", args)
            self.assertIn("tag=bill", args)

    def test_request_encodes_non_ascii_url(self):
        from mailmate_cli.client import MailMateClient

        client = MailMateClient()
        # Mock opener.open
        with patch.object(client.opener, "open") as mock_open:
            mock_resp = unittest.mock.MagicMock()
            mock_resp.read.return_value = b"<html>ok</html>"
            mock_resp.headers.get_content_charset.return_value = "utf-8"
            mock_resp.geturl.return_value = "https://mailmate.jp/app/mails?search=%E7%A5%9E%E7%94%B0"
            mock_open.return_value = mock_resp

            content, url = client.request("/app/mails?search=神田")
            self.assertEqual(content, "<html>ok</html>")
            # Verify the Request object received a properly quoted ASCII URL
            req = mock_open.call_args[0][0]
            self.assertIn("%E7%A5%9E%E7%94%B0", req.full_url)

    def test_extract_text_from_pdf_empty(self):
        from mailmate_cli.client import extract_text_from_pdf

        self.assertEqual(extract_text_from_pdf(b""), "")


if __name__ == "__main__":
    unittest.main()
