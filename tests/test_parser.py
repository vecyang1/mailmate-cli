import unittest

from mailmate_cli.parser import (
    discover_discard_actions,
    parse_activities,
    parse_bills_csv,
    parse_inbox,
    parse_mail_detail,
    parse_mailing_address,
    parse_note_from_edit,
)


UNOPENED_DETAIL = """
<html><body>
  <h1>株式会社Casa</h1>
  <div class="alert">郵便物がまだ開封スキャンされていません。</div>
  <button>開封スキャン</button>
  <img src="/rails/active_storage/blobs/cover-only.jpg" alt="郵便物の表面">
  <dl>
    <dt>受領日</dt><dd>2026年06月01日(月)</dd>
    <dt>ステータス</dt><dd>未開封</dd>
    <dt>郵便物 #</dt><dd>#199671</dd>
  </dl>
  <a title="破棄" href="/app/mails/199671/discard" data-method="post">破棄</a>
</body></html>
"""


SCANNED_DETAIL_WITH_FORM = """
<html><head>
  <meta name="csrf-token" content="meta-csrf-token">
</head><body>
  <h1>全国健康保険協会 東京支部</h1>
  <dl>
    <dt>受領日</dt><dd>2026年05月28日(木)</dd>
    <dt>ステータス</dt><dd>開封済み</dd>
    <dt>郵便物 #</dt><dd>#198843</dd>
  </dl>
  <a href="/rails/active_storage/blobs/letter.pdf">PDF</a>
  <form action="/app/mails/198843/discard" method="post">
    <input type="hidden" name="authenticity_token" value="form-token">
    <input type="hidden" name="_method" value="patch">
    <button title="破棄">原本を破棄</button>
  </form>
</body></html>
"""


INBOX_HTML = """
<html><body>
  <div class="mail-inbox__main__list">
    <a class="mail-row is-scan-requested" href="/app/mails/198843/view_mail">
      <span class="dot dot-danger"></span>
      <span>全国健康保険協会東京支部</span>
      <time>2026年05月28日(木)</time>
    </a>
    <a class="mail-row" href="/app/mails/199671/view_mail">
      <span class="dot dot-secondary"></span>
      <span>株式会社Casa</span>
      <time>2026年06月01日(月)</time>
    </a>
  </div>
</body></html>
"""


class ParserTests(unittest.TestCase):
    def test_parse_unopened_detail_detects_scan_missing(self):
        detail = parse_mail_detail(UNOPENED_DETAIL, "https://mailmate.jp/app/mails/199671/view_mail")

        self.assertEqual(detail.mail_id, "199671")
        self.assertEqual(detail.sender, "株式会社Casa")
        self.assertEqual(detail.status, "未開封")
        self.assertTrue(detail.scan_missing)
        self.assertFalse(detail.has_digital_copy)

    def test_discover_discard_form_prefers_form_method_override(self):
        actions = discover_discard_actions(
            SCANNED_DETAIL_WITH_FORM,
            "https://mailmate.jp/app/mails/198843/view_mail",
        )

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].method, "PATCH")
        self.assertEqual(actions[0].url, "https://mailmate.jp/app/mails/198843/discard")
        self.assertEqual(actions[0].fields["authenticity_token"], "form-token")

    def test_parse_scanned_detail_has_digital_copy(self):
        detail = parse_mail_detail(
            SCANNED_DETAIL_WITH_FORM,
            "https://mailmate.jp/app/mails/198843/view_mail",
        )

        self.assertEqual(detail.status, "開封済み")
        self.assertFalse(detail.scan_missing)
        self.assertTrue(detail.has_digital_copy)
        self.assertEqual(detail.discard_actions[0].method, "PATCH")

    def test_parse_inbox_marks_red_dot_as_scan_requested_not_opened(self):
        items = parse_inbox(INBOX_HTML, "https://mailmate.jp/app/mails?inbox_id=82433")

        self.assertEqual([item.mail_id for item in items], ["198843", "199671"])
        self.assertTrue(items[0].scan_requested)
        self.assertFalse(items[1].scan_requested)
        self.assertEqual(items[0].sender, "全国健康保険協会東京支部")

    def test_cover_image_alone_is_not_a_verified_inside_scan(self):
        detail = parse_mail_detail(
            """
            <html><body>
              <h1>茅ヶ崎市より</h1>
              <img src="/rails/active_storage/blobs/cover.jpg" alt="郵便物の表面">
              <dl>
                <dt>受領日</dt><dd>2026年06月15日(月)</dd>
                <dt>ステータス</dt><dd>保管中</dd>
                <dt>郵便物 #</dt><dd>#200001</dd>
              </dl>
              <a title="破棄" href="/app/mails/200001/discard" data-method="post">破棄</a>
            </body></html>
            """,
            "https://mailmate.jp/app/mails/200001/view_mail",
        )

        self.assertFalse(detail.scan_missing)
        self.assertFalse(detail.has_digital_copy)

    def test_parser_ignores_script_and_style_tags(self):
        html = """
        <html>
          <head>
            <style>.danger { color: red; }</style>
            <script>function evil() { return "doNotLeak"; }</script>
          </head>
          <body>
            <h1>Real Title</h1>
            <p>Real text</p>
            <script>console.log("more scripts");</script>
          </body>
        </html>
        """
        detail = parse_mail_detail(html, "https://mailmate.jp/app/mails/123/view_mail")
        self.assertEqual(detail.sender, "Real Title")
        # Ensure script/style text is not present anywhere in headings or sender
        self.assertNotIn("evil", detail.sender or "")
        self.assertNotIn("danger", detail.sender or "")

    def test_parse_inbox_extracts_status_and_read_state(self):
        html = """
        <html><body>
          <a href="/app/mails/210888/view_mail">
            <div class="mail-inbox__main__list__item mail-inbox__main__list__item--opened mail-inbox__main__list__item--bill mail-inbox__main__list__item--read">
              <span class="mail-inbox__main__list__item__notes">茅ヶ崎市</span>
              <span class="mail-inbox__main__list__item__received-on">2026年08月01日(土)</span>
              <div class="mail-inbox__main__list__item__marks">
                <div tooltip-title="開封済み"></div>
              </div>
            </div>
          </a>
          <a href="/app/mails/210080/view_mail">
            <div class="mail-inbox__main__list__item mail-inbox__main__list__item--unopened mail-inbox__main__list__item--unread">
              <span class="mail-inbox__main__list__item__notes">法律事務所</span>
              <span class="mail-inbox__main__list__item__received-on">2026年07月28日(火)</span>
            </div>
          </a>
          <a href="/app/mails/220249/view_mail">
            <div class="mail-inbox__main__list__item mail-inbox__main__list__item--opening mail-inbox__main__list__item--read">
              <span class="mail-inbox__main__list__item__notes">茅ヶ崎市</span>
              <div tooltip-title="開封スキャン依頼"></div>
            </div>
          </a>
        </body></html>
        """
        items = parse_inbox(html, "https://mailmate.jp/app/mails")
        self.assertEqual(len(items), 3)

        self.assertEqual(items[0].mail_id, "210888")
        self.assertEqual(items[0].sender, "茅ヶ崎市")
        self.assertEqual(items[0].status, "開封済み")
        self.assertTrue(items[0].is_read)
        self.assertTrue(items[0].is_bill)
        self.assertFalse(items[0].scan_requested)

        self.assertEqual(items[1].mail_id, "210080")
        self.assertEqual(items[1].status, "未開封")
        self.assertFalse(items[1].is_read)
        self.assertFalse(items[1].is_bill)

        self.assertEqual(items[2].mail_id, "220249")
        self.assertTrue(items[2].scan_requested)
        self.assertEqual(items[2].status, "開封待ち/依頼中")


    def test_parse_mail_detail_extracts_pdf_urls(self):
        html = """
        <html><body>
          <h1>テスト郵便物</h1>
          <dl>
            <dt>ステータス</dt><dd>開封済み</dd>
            <dt>場所</dt><dd>メール室</dd>
            <dt>メモ</dt><dd>重要書類です</dd>
          </dl>
          <a href="/rails/active_storage/representations/redirect/xxx/page1.pdf"
             data-title="page1.pdf <a href='/rails/active_storage/blobs/redirect/xxx/page1.pdf'>Download</a> <a href='/app/mails/198843/generate_pdf'>Download All</a>"></a>
        </body></html>
        """
        detail = parse_mail_detail(html, "https://mailmate.jp/app/mails/198843/view_mail")
        self.assertEqual(detail.status, "開封済み")
        self.assertEqual(detail.location, "メール室")
        self.assertIn("重要書類です", detail.notes or "")
        self.assertTrue(any("generate_pdf" in u for u in [detail.pdf_download_url or ""] + detail.pdf_urls))

    def test_discover_discard_from_shred_form(self):
        html = """
        <html><head><meta name="csrf-token" content="tok123"></head><body>
          <form action="/app/mails/216635/shred_form" method="get">
            <button>破棄</button>
          </form>
        </body></html>
        """
        actions = discover_discard_actions(html, "https://mailmate.jp/app/mails/216635/view_mail")
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].method, "PATCH")
        self.assertEqual(actions[0].url, "https://mailmate.jp/app/mails/216635/shred")
        self.assertEqual(actions[0].fields.get("authenticity_token"), "tok123")

    def test_parse_mail_detail_discovers_open_scan_and_archive(self):
        html = """
        <html><head><meta name="csrf-token" content="csrf_xyz"></head><body>
          <h1>未開封テスト</h1>
          <dl><dt>ステータス</dt><dd>未開封</dd></dl>
          <form action="/app/mails/216221/open_mail" method="post">
            <input type="hidden" name="_method" value="patch">
            <button type="submit">開封スキャン</button>
          </form>
          <form action="/app/mails/216221/archive_mail" method="post">
            <input type="hidden" name="_method" value="patch">
          </form>
        </body></html>
        """
        detail = parse_mail_detail(html, "https://mailmate.jp/app/mails/216221/view_mail")
        self.assertEqual(detail.status, "未開封")
        self.assertIsNotNone(detail.open_scan_action)
        self.assertEqual(detail.open_scan_action.url, "https://mailmate.jp/app/mails/216221/open_mail")
        self.assertEqual(detail.open_scan_action.fields.get("_method"), "patch")
        self.assertEqual(detail.open_scan_action.fields.get("authenticity_token"), "csrf_xyz")
        self.assertEqual(detail.archive_url, "https://mailmate.jp/app/mails/216221/archive_mail")

    def test_parse_mail_detail_detects_scan_pending_from_text(self):
        html = """
        <html><body>
          <h1>茅ヶ崎市</h1>
          <div>開封スキャン依頼を完了しました。近日中に更新します。</div>
          <dl><dt>ステータス</dt><dd>開封待ち</dd></dl>
        </body></html>
        """
        detail = parse_mail_detail(html, "https://mailmate.jp/app/mails/220249/view_mail")
        self.assertEqual(detail.status, "開封待ち")
        self.assertTrue(detail.scan_requested)
        self.assertTrue(detail.scan_missing)

    def test_parse_mailing_address(self):
        html = """
        <html><body>
          <input id="mail_in_address_input" value="user123.456" />
          <div data-clipboard-text="user123.456@pm.mailmate.jp"></div>
          <div>(ID 48713-82433), Yellow Base Tenjin 3F, 3-16-17 Tenjin, Chuo-ku, Fukuoka, Japan 810-0001</div>
          <div>〒 810-0001 福岡市中央区天神3-16-17 イエローベース天神3F (管理番号 : 48713-82433)</div>
        </body></html>
        """
        addr = parse_mailing_address(html, inbox_id="456")
        self.assertEqual(addr.inbox_id, "456")
        self.assertEqual(addr.mail_in_address, "user123.456@pm.mailmate.jp")
        self.assertEqual(addr.invoice_address, "user123.456@invoice.mailmate.jp")
        self.assertEqual(addr.receipt_address, "user123.456@receipt.mailmate.jp")
        self.assertEqual(addr.postal_code, "810-0001")
        self.assertEqual(addr.management_id, "48713-82433")

    def test_parse_activities(self):
        html = """
        <div class="activity">
          <div class="activity-description">
            <strong>MailMate</strong>が郵便物を開封しました
          </div>
          <div class="activity-timestamp">2026/08/13 10:16（日本時間）</div>
        </div>
        """
        acts = parse_activities(html)
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0].actor, "MailMate")
        self.assertIn("開封しました", acts[0].description)
        self.assertEqual(acts[0].timestamp, "2026/08/13 10:16（日本時間）")

    def test_parse_bills_csv(self):
        csv_text = "支払期日,支払日,品目名,請求金額,手数料,カテゴリ\n2026-06-15,,水道代 [郵便物 #12345],\"1,500円\",0円,水道光熱費\n"
        bills = parse_bills_csv(csv_text)
        self.assertEqual(len(bills), 1)
        self.assertEqual(bills[0].vendor, "水道代 [郵便物 #12345]")
        self.assertEqual(bills[0].linked_mail_id, "12345")
        self.assertEqual(bills[0].amount, "1,500円")
        self.assertEqual(bills[0].due_date, "2026-06-15")
        self.assertEqual(bills[0].status, "unpaid")

    def test_parse_note_from_edit(self):
        html = "<textarea name=\"mail_postal_mail[notes]\">hello memo</textarea>"
        self.assertEqual(parse_note_from_edit(html), "hello memo")


if __name__ == "__main__":
    unittest.main()
