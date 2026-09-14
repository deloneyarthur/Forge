"""A campaign lane must reach Crucible as `selection_arm="ranked"` (their 09-13 §3): the
1.37.0 Literal admits nothing else we could honestly claim, and an unadmitted value would be
rejected at their inbox (the D342 class). The internal `selection_mode` keeps the trigger."""

from __future__ import annotations

from forge.submission.submitter import _SELECTION_ARM_BY_MODE, _selection_arm_for


def test_campaign_modes_stamp_ranked() -> None:
    for trigger in ("leg_health", "refutation_retraction", "exploration_floor"):
        assert _selection_arm_for(f"campaign:{trigger}") == "ranked"


def test_legacy_modes_are_unchanged() -> None:
    for mode, arm in _SELECTION_ARM_BY_MODE.items():
        assert _selection_arm_for(mode) == arm
    assert _selection_arm_for("tail_lane") is None
