"""Census cell classification, re-based on HONEST evidence (D331 item 2).

WHY THE RE-BASE (joint finding with Crucible, 2026-07-22): the census classified
cells from Forge's `verdicts` ledger, which is ~94% Crucible **stage-one** rows.
Stage one is a cheap 5-year SCREEN that structurally cannot produce an
honest-coverage component; only the `fullhist_refit` validator can. So a cell
counted as "converting" on the strength of stage-one positives was counted on
unverified-admission artifacts, and freeze metric B — the number the whole freeze
criterion turns on — was a stage-one artifact.

WHY THE NEW `unevaluated` CLASS: re-basing alone would classify a cell with recent
flow but ZERO honest evaluations as `dead_unprotected`. Measured on the live
snapshot, 2 cells would flip out of `converting` and **both** had zero honest
evaluations — 100% of flips misclassified. Today that is small; the case it
protects is a NEW cell, which by construction has flow and no honest evidence yet.
Pruning those is the v17 cold-start mistake with a new label: absence of evidence
read as evidence of absence, on a lane that cannot supply the evidence.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from search_multiplicity_census import (
    _CONVERTING,
    _DEAD_UNPROTECTED,
    _PROTECTED,
    _THIN,
    _UNEVALUATED,
    Cell,
)


def _cell(**kw: object) -> Cell:
    base: dict[str, object] = {
        "hypothesis": "trend_continuation",
        "dte_bucket": "swing_mid",
        "axis": "xsect",
        "directional": "donchian",
        "regime": "adx",
    }
    base.update(kw)
    return Cell(**base)  # type: ignore[arg-type]


class TestConvertingRequiresHonestEvidence:
    def test_stage_one_positives_alone_do_not_make_a_cell_converting(self) -> None:
        """The defect this fixes: a cell 'converts' on unverified-admission rows."""
        c = _cell(submitted_recent=500, decided_recent=400, comp_recent=40, honest_decided_recent=0)
        assert c.classify() != _CONVERTING

    def test_one_honest_component_is_enough(self) -> None:
        c = _cell(
            submitted_recent=500,
            decided_recent=400,
            comp_recent=40,
            honest_decided_recent=10,
            honest_comp_recent=1,
        )
        assert c.classify() == _CONVERTING


class TestUnevaluatedIsNotDead:
    def test_flow_with_no_honest_evaluation_is_unevaluated_not_dead(self) -> None:
        """A new cell has flow and no honest evidence yet. Pruning it would be
        the v17 cold-start mistake: absence of evidence read as absence."""
        c = _cell(submitted_recent=500, decided_recent=400, comp_recent=0, honest_decided_recent=0)
        assert c.classify() == _UNEVALUATED

    def test_honestly_evaluated_and_failed_is_genuinely_dead(self) -> None:
        """The cell HAS been given a fair hearing and produced nothing."""
        c = _cell(
            submitted_recent=500,
            decided_recent=400,
            comp_recent=0,
            honest_decided_recent=50,
            honest_comp_recent=0,
        )
        assert c.classify() == _DEAD_UNPROTECTED

    def test_unevaluated_never_outranks_protection(self) -> None:
        c = _cell(submitted_recent=500, honest_decided_recent=0, promoted_book=True)
        assert c.classify() == _PROTECTED

    def test_thin_flow_stays_thin_even_when_honestly_evaluated(self) -> None:
        c = _cell(
            submitted_recent=5, decided_recent=5, honest_decided_recent=5, honest_comp_recent=0
        )
        assert c.classify() == _THIN


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
