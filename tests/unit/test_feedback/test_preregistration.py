"""Tier-1a: pre-registration registry + post-cut confirmation (pure core).

The §8.4 auto-tightening triggers (and most manual prunes) observe a pattern in a
cohort and "confirm" it on the *same* cohort — guaranteed to look good
(post-selection bias). Pre-registration records the claim with a cohort cut, then
confirms it only on data that did NOT exist when the claim was made. These tests
pin the anti-bias guard (`confirm_promotion_claim` structurally ignores pre-cut
rows) and the registry round-trip; the CLI is tested separately.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.feedback.preregistration import (
    PreregEntry,
    append_preregistration,
    confirm_promotion_claim,
    load_preregistrations,
    resolve_preregistration,
)


def _entry(**overrides: object) -> PreregEntry:
    base: dict[str, object] = {
        "prereg_id": "abc123def456",
        "created_at": "2026-06-25T00:00:00",
        "claim": "configs with adx<10 never promote",
        "metric": "promotion_rate",
        "predicted": "<= 0.005",
        "cohort_cut": "2026-06-25T00:00:00",
        "action_if_confirmed": "tighten adx lower bound",
        "status": "registered",
        "resolved_at": None,
        "evidence": None,
    }
    base.update(overrides)
    return PreregEntry(**base)  # type: ignore[arg-type]


class TestConfirmPromotionClaim:
    def test_ignores_pre_cut_rows_the_anti_post_selection_guard(self) -> None:
        cut = "2026-06-20T00:00:00"
        rows = [
            # Pre-cut: matched AND promote heavily — would REFUTE "promotes <= 5%".
            *[("2026-06-19T00:00:00", True, True) for _ in range(50)],
            # Post-cut: matched, almost never promote — the honest confirming evidence.
            *[("2026-06-21T00:00:00", True, False) for _ in range(40)],
            ("2026-06-21T00:00:00", True, True),  # 1 of 41 post-cut ~ 2.4%
        ]
        res = confirm_promotion_claim(rows, cohort_cut=cut, predicted_max_rate=0.05, min_samples=30)
        assert res.outcome == "confirmed"  # pre-cut promotions are structurally ignored
        assert res.n_post_cut_matched == 41
        assert res.promotion_rate == pytest.approx(1 / 41, abs=1e-6)

    def test_refuted_when_post_cut_rate_exceeds_the_bound(self) -> None:
        cut = "2026-06-20T00:00:00"
        rows = [("2026-06-21T00:00:00", True, i < 10) for i in range(40)]  # 10/40 = 25%
        res = confirm_promotion_claim(rows, cohort_cut=cut, predicted_max_rate=0.05, min_samples=30)
        assert res.outcome == "refuted"
        assert res.promotion_rate == pytest.approx(0.25)

    def test_insufficient_when_too_few_post_cut_matched(self) -> None:
        cut = "2026-06-20T00:00:00"
        rows = [("2026-06-21T00:00:00", True, False) for _ in range(5)]
        res = confirm_promotion_claim(rows, cohort_cut=cut, predicted_max_rate=0.05, min_samples=30)
        assert res.outcome == "insufficient"
        assert res.n_post_cut_matched == 5

    def test_unmatched_rows_excluded(self) -> None:
        cut = "2026-06-20T00:00:00"
        rows = [("2026-06-21T00:00:00", False, True) for _ in range(100)]
        res = confirm_promotion_claim(rows, cohort_cut=cut, predicted_max_rate=0.05, min_samples=30)
        assert res.outcome == "insufficient"
        assert res.n_post_cut_matched == 0
        assert res.promotion_rate is None

    def test_rows_exactly_at_cut_are_not_post_cut(self) -> None:
        cut = "2026-06-20T00:00:00"
        rows = [("2026-06-20T00:00:00", True, False) for _ in range(40)]  # AT the cut
        res = confirm_promotion_claim(rows, cohort_cut=cut, predicted_max_rate=0.05, min_samples=30)
        assert res.outcome == "insufficient"
        assert res.n_post_cut_matched == 0


class TestRegistryRoundTrip:
    def test_append_then_load_roundtrips(self, tmp_path: Path) -> None:
        path = tmp_path / "preregistrations.jsonl"
        e1 = _entry(prereg_id="aaa")
        e2 = _entry(prereg_id="bbb", claim="family X is 96% zero-trade")
        append_preregistration(path, e1)
        append_preregistration(path, e2)
        assert load_preregistrations(path) == [e1, e2]

    def test_load_missing_file_is_empty(self, tmp_path: Path) -> None:
        assert load_preregistrations(tmp_path / "nope.jsonl") == []

    def test_resolve_updates_status_and_persists(self, tmp_path: Path) -> None:
        path = tmp_path / "preregistrations.jsonl"
        append_preregistration(path, _entry(prereg_id="aaa"))
        updated = resolve_preregistration(
            path,
            "aaa",
            outcome="confirmed",
            evidence="post-cut rate 0.002 (n=120)",
            resolved_at="2026-07-01T00:00:00",
        )
        assert updated.status == "confirmed"
        assert updated.resolved_at == "2026-07-01T00:00:00"
        reloaded = load_preregistrations(path)
        assert reloaded[0].status == "confirmed"
        assert reloaded[0].evidence == "post-cut rate 0.002 (n=120)"

    def test_resolve_unknown_id_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "preregistrations.jsonl"
        append_preregistration(path, _entry(prereg_id="aaa"))
        with pytest.raises(KeyError):
            resolve_preregistration(
                path, "zzz", outcome="confirmed", evidence="x", resolved_at="2026-07-01T00:00:00"
            )
