from __future__ import annotations

from .models import DiscardDecision, MailDetail, OpenScanDecision

# Predictable debt collection, routine rent guarantee, or generic junk mail
# where the envelope already states the sender and purpose, and opening
# adds zero new information while incurring unnecessary scan fees and burning quota.
SKIP_OPEN_PATTERNS = [
    "神田お玉ヶ池",
    "神田お玉ケ池",
    "お玉ヶ池法律事務所",
    "casa",
    "株式会社casa",
]


def is_skip_open_sender(sender: str | None, notes: str | None = None) -> bool:
    """Return True if the sender/envelope is a known predictable notice that should not be opened."""
    text = f"{sender or ''} {notes or ''}".lower()
    return any(pat.lower() in text for pat in SKIP_OPEN_PATTERNS)


def decide_open_scan(detail: MailDetail, *, force: bool = False) -> OpenScanDecision:
    """Return whether requesting an open and scan is valid and safe."""
    if detail.already_discarded:
        return OpenScanDecision(False, "already_discarded", message="Original paper is already discarded.")

    if detail.has_digital_copy or detail.status in {"開封済み", "スキャン済み"}:
        return OpenScanDecision(False, "already_opened", message="Mail is already opened and scanned.")

    if detail.scan_requested or detail.status in {"開封待ち", "開封待ち/依頼中", "依頼中"}:
        return OpenScanDecision(False, "scan_pending", message="Open/scan is already requested and pending.")

    if detail.status != "未開封" and not detail.open_scan_action:
        return OpenScanDecision(
            False,
            "not_unopened",
            message=f"Mail status is '{detail.status or 'unknown'}', not unopened.",
        )

    if not force and is_skip_open_sender(detail.sender, detail.notes):
        return OpenScanDecision(
            False,
            "skip_open_known_sender",
            message=(
                f"Known sender '{detail.sender}' already clear without opening (debt collection / routine notice). "
                "Opening incurs unnecessary scan fees. Pass --force to override."
            ),
        )

    if not detail.open_scan_action:
        return OpenScanDecision(False, "no_open_action", message="No open/scan action form was found.")

    return OpenScanDecision(
        True,
        "eligible",
        action=detail.open_scan_action,
        message="Safe open and scan request candidate.",
    )


def decide_discard(detail: MailDetail, *, force: bool = False) -> DiscardDecision:
    """Return whether discarding the paper original is safe enough to automate."""
    if detail.already_discarded:
        return DiscardDecision(False, "already_discarded", message="Original paper is already discarded.")

    if not force:
        if detail.scan_missing or detail.status in {"未開封", "開封待ち", "開封待ち/依頼中"}:
            reason = "scan_pending" if detail.scan_requested else "not_scanned"
            return DiscardDecision(
                False,
                reason,
                message="Digital copy is not verified yet; red-dot scan requests are treated as pending. Pass --force to override.",
            )

        if not detail.has_digital_copy:
            return DiscardDecision(
                False,
                "digital_copy_not_verified",
                message="The page does not prove that a scanned/digital copy exists. Pass --force to override.",
            )

    if not detail.discard_actions:
        return DiscardDecision(False, "no_discard_action", message="No discard form/link was found.")

    return DiscardDecision(True, "eligible", action=detail.discard_actions[0], message="Safe discard candidate.")
