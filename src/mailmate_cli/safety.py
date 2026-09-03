from __future__ import annotations

from .models import DiscardDecision, MailDetail


def decide_discard(detail: MailDetail) -> DiscardDecision:
    """Return whether discarding the paper original is safe enough to automate."""
    if detail.already_discarded:
        return DiscardDecision(False, "already_discarded", message="Original paper is already discarded.")

    if detail.scan_missing or detail.status == "未開封":
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
