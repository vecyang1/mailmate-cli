from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from .models import DiscardAction, InboxItem, MailDetail, OpenScanAction


DISCARD_TERMS = ("破棄", "廃棄", "discard", "dispose", "abandon", "shred")
SCAN_PENDING_TERMS = (
    "郵便物がまだ開封スキャンされていません",
    "開封スキャン",
    "scan has not been completed",
    "開封待ち",
    "開封スキャン依頼",
)
DISCARDED_TERMS = ("破棄済み", "廃棄済み", "discarded", "disposed")
SCANNED_TERMS = ("開封済み", "スキャン済み", "opened", "scanned")


def normalize_space(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", unescape(value)).strip()


def _attrs_to_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {name.lower(): value or "" for name, value in attrs}


class _MailMateHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.headings: list[str] = []
        self.links: list[dict[str, object]] = []
        self.forms: list[dict[str, object]] = []
        self._current_link: dict[str, object] | None = None
        self._current_form: dict[str, object] | None = None
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._button_parts: list[str] | None = None
        self._button_attrs: dict[str, str] | None = None
        self._ignore_data_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._ignore_data_depth += 1
            return
        if self._ignore_data_depth > 0:
            return

        attrs_dict = _attrs_to_dict(attrs)
        if self._current_link is not None:
            if "class" in attrs_dict:
                self._current_link["inner_classes"].append(attrs_dict["class"])  # type: ignore[index]
            if "tooltip-title" in attrs_dict:
                self._current_link["tooltips"].append(attrs_dict["tooltip-title"])  # type: ignore[index]

        if tag == "form":
            self._current_form = {
                "action": attrs_dict.get("action", ""),
                "method": attrs_dict.get("method", "get"),
                "attrs": attrs_dict,
                "fields": {},
                "text_parts": [],
                "buttons": [],
            }
        elif tag == "input" and self._current_form is not None:
            name = attrs_dict.get("name")
            if name:
                self._current_form["fields"][name] = attrs_dict.get("value", "")  # type: ignore[index]
            input_type = attrs_dict.get("type", "").lower()
            if input_type in {"submit", "button", "image"}:
                self._current_form["buttons"].append(attrs_dict.get("value", ""))  # type: ignore[index]
        elif tag == "button" and self._current_form is not None:
            self._button_parts = []
            self._button_attrs = attrs_dict
        elif tag == "a":
            self._current_link = {
                "attrs": attrs_dict,
                "text_parts": [],
                "inner_classes": [attrs_dict.get("class", "")],
                "tooltips": [attrs_dict.get("tooltip-title", "")] if "tooltip-title" in attrs_dict else [],
            }
        elif tag in {"h1", "h2", "h3"}:
            self._heading_tag = tag
            self._heading_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            if self._ignore_data_depth > 0:
                self._ignore_data_depth -= 1
            return
        if self._ignore_data_depth > 0:
            return

        if tag == "a" and self._current_link is not None:
            text = normalize_space(" ".join(self._current_link["text_parts"]))  # type: ignore[index]
            self._current_link["text"] = text
            self.links.append(self._current_link)
            self._current_link = None
        elif tag == "form" and self._current_form is not None:
            self._current_form["text"] = normalize_space(" ".join(self._current_form["text_parts"]))  # type: ignore[index]
            self.forms.append(self._current_form)
            self._current_form = None
        elif tag == "button" and self._current_form is not None and self._button_parts is not None:
            text = normalize_space(" ".join(self._button_parts))
            title = self._button_attrs.get("title", "") if self._button_attrs else ""
            aria = self._button_attrs.get("aria-label", "") if self._button_attrs else ""
            self._current_form["buttons"].append(normalize_space(" ".join([text, title, aria])))  # type: ignore[index]
            self._button_parts = None
            self._button_attrs = None
        elif tag == self._heading_tag:
            heading = normalize_space(" ".join(self._heading_parts))
            if heading:
                self.headings.append(heading)
            self._heading_tag = None
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._ignore_data_depth > 0:
            return
        if not data.strip():
            return
        self.text_parts.append(data)
        if self._current_link is not None:
            self._current_link["text_parts"].append(data)  # type: ignore[index]
        if self._current_form is not None:
            self._current_form["text_parts"].append(data)  # type: ignore[index]
        if self._heading_tag is not None:
            self._heading_parts.append(data)
        if self._button_parts is not None:
            self._button_parts.append(data)


def parse_html(html: str) -> _MailMateHTMLParser:
    parser = _MailMateHTMLParser()
    parser.feed(html)
    return parser


def discover_discard_actions(html: str, page_url: str) -> list[DiscardAction]:
    parser = parse_html(html)
    actions: list[DiscardAction] = []
    csrf = _extract_meta_csrf(html)

    for form in parser.forms:
        action = str(form.get("action") or "")
        attrs = form.get("attrs", {})
        fields = dict(form.get("fields", {}))
        buttons = " ".join(str(part) for part in form.get("buttons", []))
        haystack = " ".join(
            [
                action,
                str(form.get("text") or ""),
                buttons,
                " ".join(str(v) for v in attrs.values()) if isinstance(attrs, dict) else "",
            ]
        ).lower()
        if "shred_form" in action:
            shred_url = urljoin(page_url, re.sub(r"/shred_form$", "/shred", action))
            f_data = {"authenticity_token": csrf} if csrf else {}
            actions.append(
                DiscardAction(
                    method="PATCH",
                    url=shred_url,
                    fields=f_data,
                    label="破棄",
                    needs_confirm=True,
                )
            )
            continue
        if not _contains_any(haystack, DISCARD_TERMS):
            continue
        method = str(form.get("method") or "get").upper()
        method_override = fields.get("_method")
        if method_override:
            method = method_override.upper()
        actions.append(
            DiscardAction(
                method=method,
                url=urljoin(page_url, action),
                fields=fields,
                label=normalize_space(" ".join([str(form.get("text") or ""), buttons])),
                needs_confirm=_contains_any(haystack, ("confirm", "確認")),
            )
        )

    for link in parser.links:
        attrs = link.get("attrs", {})
        if not isinstance(attrs, dict):
            continue
        href = attrs.get("href", "")
        haystack = " ".join([href, str(link.get("text") or ""), " ".join(attrs.values())]).lower()
        if "shred_form" in href:
            shred_url = urljoin(page_url, re.sub(r"/shred_form$", "/shred", href))
            f_data = {"authenticity_token": csrf} if csrf else {}
            actions.append(
                DiscardAction(
                    method="PATCH",
                    url=shred_url,
                    fields=f_data,
                    label="破棄",
                    needs_confirm=True,
                )
            )
            continue
        if not href or not _contains_any(haystack, DISCARD_TERMS):
            continue
        method = (
            attrs.get("data-turbo-method")
            or attrs.get("data-method")
            or attrs.get("data-method-type")
            or "GET"
        ).upper()
        fields = {}
        if csrf and method != "GET":
            fields["authenticity_token"] = csrf
        actions.append(
            DiscardAction(
                method=method,
                url=urljoin(page_url, href),
                fields=fields,
                label=normalize_space(str(link.get("text") or attrs.get("title") or attrs.get("aria-label") or "")),
                needs_confirm=bool(attrs.get("data-confirm") or attrs.get("data-turbo-confirm")),
            )
        )

    return _dedupe_actions(actions)


def parse_mail_detail(html: str, page_url: str, scan_requested: bool = False) -> MailDetail:
    parser = parse_html(html)
    text = normalize_space(" ".join(parser.text_parts))
    mail_id = _mail_id_from_url(page_url) or _match_first(text, r"#\s*(\d{3,})") or ""
    status = _extract_status(text)
    sender = parser.headings[0] if parser.headings else None
    received_date = _match_first(text, r"(\d{4}年\d{1,2}月\d{1,2}日(?:\([^)]+\))?)")
    location = _match_first(text, r"場所\s*([^\s#]+)")
    notes = _match_first(text, r"メモ\s*(?:メモを編集\s*)?([^\s].*?)(?:郵便物情報|受領日|ステータス|$)")
    scan_missing = _contains_any(text, SCAN_PENDING_TERMS) or status in {"未開封", "開封待ち", "開封待ち/依頼中"}
    already_discarded = _contains_any(text, DISCARDED_TERMS) or bool(status and "破棄" in status)
    scanned_status = bool(status and _contains_any(status, SCANNED_TERMS))
    scanned_page = _contains_any(text, SCANNED_TERMS) and not scan_missing and not already_discarded
    has_digital_copy = scanned_status or scanned_page
    actions = discover_discard_actions(html, page_url)

    # Detect scan requested from page text or status
    scan_requested = (
        scan_requested
        or bool(status and ("開封待ち" in status or "依頼中" in status))
        or "開封スキャン依頼" in text
        or "開封待ち" in text
    )

    # Discover open scan action
    open_scan_action: OpenScanAction | None = None
    csrf = _extract_meta_csrf(html)
    for form in parser.forms:
        action = str(form.get("action") or "")
        if "open_mail" in action:
            form_csrf = form.get("fields", {}).get("authenticity_token") or csrf
            fields = {"_method": "patch"}
            if form_csrf:
                fields["authenticity_token"] = form_csrf
            open_scan_action = OpenScanAction(
                method="POST",
                url=urljoin(page_url, action),
                fields=fields,
                label="開封スキャン",
            )
            break
    if not open_scan_action and mail_id and (status == "未開封" or "開封スキャン" in text):
        fields = {"_method": "patch"}
        if csrf:
            fields["authenticity_token"] = csrf
        open_scan_action = OpenScanAction(
            method="POST",
            url=urljoin(page_url, f"/app/mails/{mail_id}/open_mail"),
            fields=fields,
            label="開封スキャン",
        )

    # Discover archive url
    archive_url: str | None = None
    for form in parser.forms:
        action = str(form.get("action") or "")
        if "archive_mail" in action:
            archive_url = urljoin(page_url, action)
            break
    if not archive_url and mail_id:
        archive_url = urljoin(page_url, f"/app/mails/{mail_id}/archive_mail")

    pdf_urls: list[str] = []
    pdf_download_url: str | None = None
    if mail_id and (f"/app/mails/{mail_id}/generate_pdf" in html or "generate_pdf" in html):
        pdf_download_url = urljoin(page_url, f"/app/mails/{mail_id}/generate_pdf")

    for link in parser.links:
        l_attrs = link.get("attrs", {})
        if not isinstance(l_attrs, dict):
            continue
        l_href = l_attrs.get("href", "")
        d_title = str(l_attrs.get("data-title", ""))
        if "/rails/active_storage/" in l_href or l_href.lower().endswith(".pdf"):
            pdf_urls.append(urljoin(page_url, l_href))
        if d_title:
            for match_link in re.findall(r"href=['\"]([^'\"]+)['\"]", d_title):
                if "/rails/active_storage/" in match_link or match_link.lower().endswith(".pdf"):
                    pdf_urls.append(urljoin(page_url, match_link))
                elif "generate_pdf" in match_link:
                    pdf_download_url = urljoin(page_url, match_link)

    pdf_urls = list(dict.fromkeys(pdf_urls))
    if not pdf_download_url and mail_id and (has_digital_copy or pdf_urls):
        pdf_download_url = urljoin(page_url, f"/app/mails/{mail_id}/generate_pdf")

    return MailDetail(
        mail_id=mail_id,
        sender=sender,
        status=status,
        received_date=received_date,
        scan_missing=scan_missing,
        scan_requested=scan_requested,
        has_digital_copy=has_digital_copy,
        already_discarded=already_discarded,
        discard_actions=actions,
        pdf_urls=pdf_urls,
        pdf_download_url=pdf_download_url,
        location=location,
        notes=notes,
        open_scan_action=open_scan_action,
        archive_url=archive_url,
    )


def parse_inbox(html: str, page_url: str) -> list[InboxItem]:
    parser = parse_html(html)
    items: list[InboxItem] = []
    seen: set[str] = set()
    for link in parser.links:
        attrs = link.get("attrs", {})
        if not isinstance(attrs, dict):
            continue
        href = attrs.get("href", "")
        mail_id = _mail_id_from_url(href)
        if not mail_id or mail_id in seen:
            continue
        seen.add(mail_id)
        text = normalize_space(str(link.get("text") or ""))
        sender = _sender_from_link_text(text)
        received_date = _match_first(text, r"(\d{4}年\d{1,2}月\d{1,2}日(?:\([^)]+\))?)")
        inner_classes = [str(c) for c in link.get("inner_classes", []) if c]
        tooltips = [str(t) for t in link.get("tooltips", []) if t]
        class_text = " ".join(
            [attrs.get("class", ""), attrs.get("data-status", ""), attrs.get("aria-label", ""), text]
            + inner_classes
            + tooltips
        )

        is_opening = any("--opening" in c for c in inner_classes) or any("開封スキャン依頼" in t for t in tooltips)
        is_opened = any("--opened" in c for c in inner_classes) or any("開封済み" in t for t in tooltips)
        is_unopened = any("--unopened" in c for c in inner_classes) or any("未開封" in t for t in tooltips)

        scan_requested = is_opening or _looks_scan_requested(class_text)
        is_read = not any("--unread" in c for c in inner_classes)
        is_bill = any("--bill" in c for c in inner_classes)

        status = None
        if is_opened and not is_unopened:
            status = "開封済み"
        elif is_opening:
            status = "開封待ち/依頼中"
        elif is_unopened:
            status = "未開封"
        elif tooltips:
            status = tooltips[0]
        else:
            status = _extract_status(class_text)

        items.append(
            InboxItem(
                mail_id=mail_id,
                sender=sender,
                received_date=received_date,
                url=urljoin(page_url, href),
                scan_requested=scan_requested,
                status=status,
                is_read=is_read,
                is_bill=is_bill,
            )
        )
    return items


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    value_lower = value.lower()
    return any(term.lower() in value_lower for term in terms)


def _dedupe_actions(actions: list[DiscardAction]) -> list[DiscardAction]:
    seen: set[tuple[str, str]] = set()
    deduped: list[DiscardAction] = []
    for action in actions:
        key = (action.method, action.url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped


def _extract_meta_csrf(html: str) -> str | None:
    match = re.search(r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if match:
        return unescape(match.group(1))
    return None


def _extract_status(text: str) -> str | None:
    status_words = "未開封|開封待ち/依頼中|開封待ち|依頼中|開封済み|スキャン済み|破棄済み|廃棄済み|転送済み|保管中|メール室|オフサイト保管"
    match = re.search(rf"ステータス\s*({status_words})", text)
    if match:
        return match.group(1)
    match = re.search(rf"\b({status_words})\b", text)
    return match.group(1) if match else None


def _mail_id_from_url(url: str) -> str | None:
    match = re.search(r"/app/mails/(\d+)(?:/|$)", urlparse(url).path)
    return match.group(1) if match else None


def _match_first(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def _sender_from_link_text(text: str) -> str:
    without_date = re.sub(r"\d{4}年\d{1,2}月\d{1,2}日(?:\([^)]+\))?", "", text)
    without_hash = re.sub(r"#\s*\d+", "", without_date)
    return normalize_space(without_hash)


def _looks_scan_requested(value: str) -> bool:
    value_lower = value.lower()
    return any(
        marker in value_lower
        for marker in (
            "scan-requested",
            "scan_requested",
            "dot-danger",
            "text-danger",
            "bg-danger",
            "is-scan-requested",
            "red",
            "danger",
        )
    )
