import unittest

from mailmate_cli.models import DiscardAction, MailDetail, OpenScanAction
from mailmate_cli.safety import decide_discard, decide_open_scan


class SafetyTests(unittest.TestCase):
    def test_unopened_scan_missing_is_never_eligible(self):
        detail = MailDetail(
            mail_id="199671",
            sender="株式会社Casa",
            status="未開封",
            received_date="2026年06月01日(月)",
            scan_missing=True,
            scan_requested=True,
            has_digital_copy=False,
            already_discarded=False,
            discard_actions=[
                DiscardAction(method="POST", url="https://mailmate.jp/app/mails/199671/discard")
            ],
        )

        decision = decide_discard(detail)

        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "scan_pending")

    def test_already_discarded_is_skipped(self):
        detail = MailDetail(
            mail_id="199671",
            sender="株式会社Casa",
            status="破棄済み",
            received_date="2026年06月01日(月)",
            scan_missing=False,
            scan_requested=False,
            has_digital_copy=True,
            already_discarded=True,
            discard_actions=[],
        )

        decision = decide_discard(detail)

        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "already_discarded")

    def test_scanned_mail_with_discard_action_is_eligible(self):
        action = DiscardAction(method="PATCH", url="https://mailmate.jp/app/mails/198843/discard")
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

        decision = decide_discard(detail)

        self.assertTrue(decision.eligible)
        self.assertEqual(decision.reason, "eligible")
        self.assertEqual(decision.action, action)

    def test_scanned_mail_without_action_is_not_eligible(self):
        detail = MailDetail(
            mail_id="198843",
            sender="全国健康保険協会 東京支部",
            status="開封済み",
            received_date="2026年05月28日(木)",
            scan_missing=False,
            scan_requested=False,
            has_digital_copy=True,
            already_discarded=False,
            discard_actions=[],
        )

        decision = decide_discard(detail)

        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "no_discard_action")

    def test_decide_open_scan_eligible_when_unopened(self):
        open_action = OpenScanAction(method="POST", url="https://mailmate.jp/app/mails/216221/open_mail")
        detail = MailDetail(
            mail_id="216221",
            sender="全国健康保険協会",
            status="未開封",
            received_date="2026年08月10日(月)",
            scan_missing=True,
            scan_requested=False,
            has_digital_copy=False,
            already_discarded=False,
            open_scan_action=open_action,
        )

        decision = decide_open_scan(detail)

        self.assertTrue(decision.eligible)
        self.assertEqual(decision.reason, "eligible")
        self.assertEqual(decision.action, open_action)

    def test_decide_open_scan_skips_already_opened(self):
        detail = MailDetail(
            mail_id="216635",
            sender="法律事務所",
            status="開封済み",
            received_date="2026年08月12日(水)",
            scan_missing=False,
            scan_requested=False,
            has_digital_copy=True,
            already_discarded=False,
        )

        decision = decide_open_scan(detail)

        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "already_opened")

    def test_decide_open_scan_skips_scan_pending(self):
        detail = MailDetail(
            mail_id="220249",
            sender="茅ヶ崎市",
            status="開封待ち",
            received_date="2026年09月03日(木)",
            scan_missing=True,
            scan_requested=True,
            has_digital_copy=False,
            already_discarded=False,
        )

        decision = decide_open_scan(detail)

        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "scan_pending")

    def test_decide_open_scan_skips_already_discarded(self):
        detail = MailDetail(
            mail_id="198843",
            sender="協会",
            status="破棄済み",
            received_date="2026年05月28日(木)",
            scan_missing=False,
            scan_requested=False,
            has_digital_copy=False,
            already_discarded=True,
        )

        decision = decide_open_scan(detail)

        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "already_discarded")


if __name__ == "__main__":
    unittest.main()
