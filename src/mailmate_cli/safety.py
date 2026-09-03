from __future__ import annotations

from .models import DiscardDecision, MailDetail, OpenScanDecision


def decide_open_scan(detail: MailDetail) -> OpenScanDecision:
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

    if not detail.open_scan_action:
        return OpenScanDecision(False, "no_open_action", message="No open/scan action form was found.")

    return OpenScanDecision(
        True,
        "eligible",
        action=detail.open_scan_action,
        message="Safe open and scan request candidate.",
    )


def decide_discard(detail: MailDetail) -> DiscardDecision:
    """Return whether discarding the paper original is safe enough to automate."""
    if detail.already_discarded:
        return DiscardDecision(False, "already_discarded", message="Original paper is already discarded.")

    if detail.scan_missing or detail.status in {"未開封", "開封待ち", "開封待ち/依頼中"}:
        reason = "scan_pending" if detail.scan_requested else "not_scanned"
        return DiscardDecision(
            False,
            reason,
            message="Digital copy is not verified yet; red-dot scan requests are treated as pending.",
        )

    if not detail.has_digital_copy:
        return DiscardDecision(
            False,
            "digital_copy_not_verified",
            message="The page does not prove that a scanned/digital copy exists.",
        )

    if not detail.discard_actions:
        return DiscardDecision(False, "no_discard_action", message="No discard form/link was found.")

    return DiscardDecision(True, "eligible", action=detail.discard_actions[0], message="Safe discard candidate.")
