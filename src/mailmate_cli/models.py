from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiscardAction:
    method: str
    url: str
    fields: dict[str, str] = field(default_factory=dict)
    label: str = ""
    needs_confirm: bool = False


@dataclass(frozen=True)
class InboxItem:
    mail_id: str
    sender: str
    received_date: str | None = None
    url: str | None = None
    scan_requested: bool = False
    status: str | None = None
    is_read: bool = True
    is_bill: bool = False


@dataclass(frozen=True)
class MailDetail:
    mail_id: str
    sender: str | None
    status: str | None
    received_date: str | None
    scan_missing: bool
    scan_requested: bool
    has_digital_copy: bool
    already_discarded: bool
    discard_actions: list[DiscardAction] = field(default_factory=list)
    pdf_urls: list[str] = field(default_factory=list)
    pdf_download_url: str | None = None
    location: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class DiscardDecision:
    eligible: bool
    reason: str
    action: DiscardAction | None = None
    message: str = ""
