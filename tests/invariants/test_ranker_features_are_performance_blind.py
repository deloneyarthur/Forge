"""The ranker must never select on a config's OWN realised performance (D330).

WHY THIS IS LOAD-BEARING (joint finding with Crucible, 2026-07-22):

Classic Deflated-Sharpe multiplicity charges selection *on the reported statistic* —
observe N Sharpes, keep the best. Forge's two selection stages differ on exactly that
axis, and the whole DSR calibration agreed with Crucible rests on the difference:

  PREFILTER  `permutation_test` compares the config's OWN notional return against a
             permuted null. That IS selection on own-performance -> textbook multiple
             comparisons -> this stage carries the real DSR charge (unmeasured; the
             prefilter-holdout campaign is the instrument).

  RANKER     Orders by a model over STRUCTURAL features, fitted on OTHER configs'
             verdicts. Under the null it is independent of this config's noise draw,
             so ``E[R | top-k by S] = E[R]`` -> ZERO multiplicity. This is why the
             measured +0.220 ranked-vs-holdout shift is NOT deflated.

Crucible proposed the guarantee is architectural ("Forge does not run backtests, so the
draw does not exist"). **That is false and the distinction matters.** Forge DOES compute
own-performance at prefilter time: `permutation_test` puts `real_notional` and `p_value`
into its `FilterResult.details`, and `PreFilterReport.filter_results` carries them into
the ranking layer — the ranker holds the report. The information is one attribute access
away.

What actually holds the line is the SIGNATURE of ``extract_features``: it accepts a
``StrategyConfig`` and a ``RegistrySnapshot``, and never a ``PreFilterReport``. So the
model physically cannot read a performance statistic. That is a design choice, not an
impossibility — and adding `permutation_p_value` as a feature is a natural thing for
someone to try, because it is right there and looks predictive.

If that ever happens, the ranker starts selecting on own-performance, the independence
argument collapses, the +0.220 becomes a genuine multiple-comparison charge, and BOTH
repos' records would still say the architecture prevents it. This test is what makes the
claim survive that.
"""

from __future__ import annotations

import inspect

from forge.prefilters.types import PreFilterReport
from forge.ranking.features import extract_features

# Keys the prefilter battery puts into `FilterResult.details` that are derived from the
# config's own evaluated performance. A ranker feature named after any of these would
# mean the model is selecting on the statistic Crucible later reports.
_PERFORMANCE_DERIVED_DETAIL_KEYS = frozenset(
    {
        "real_notional",
        "p_value",
        "n_activations",
        "expected_trades",
        "predicted_activations",
    }
)


class TestExtractFeaturesCannotSeePerformance:
    def test_signature_takes_config_and_registry_only(self) -> None:
        """The structural guarantee: no performance-carrying object is even in scope.

        `PreFilterReport` is what holds `filter_results` (and therefore the permutation
        test's `real_notional`). If it ever becomes a parameter here, the independence
        argument the DSR agreement rests on is void.
        """
        params = list(inspect.signature(extract_features).parameters)
        assert params == ["config", "registry"], (
            f"extract_features signature changed to {params}. The ranker's independence "
            "from own-performance is enforced by this signature - see module docstring."
        )

    def test_no_prefilter_report_in_annotations(self) -> None:
        annotations = {
            str(p.annotation) for p in inspect.signature(extract_features).parameters.values()
        }
        assert not any("PreFilterReport" in a for a in annotations), (
            "extract_features accepts a PreFilterReport, which carries "
            "filter_results -> permutation_test's real_notional/p_value."
        )

    def test_report_still_carries_performance_so_the_risk_is_real(self) -> None:
        """Pins WHY the signature matters: the data really is one hop away.

        This is not a hypothetical. If this assertion ever fails, `filter_results` has
        stopped carrying prefilter detail and the docstring's threat model should be
        re-examined - but until then, the signature is the only thing holding the line.
        """
        assert "filter_results" in PreFilterReport.__dataclass_fields__


class TestFeatureNamesAreStructural:
    def test_no_feature_is_named_after_a_performance_detail(self) -> None:
        """Defence in depth: even via some future path, no feature may be a perf stat.

        Checked against the LIVE trained artifacts rather than a synthetic config, so it
        catches a feature that reached a shipped model without going through
        `extract_features`.
        """
        import json
        from pathlib import Path

        models_dir = Path.home() / "forge_data" / "models"
        artifacts = sorted(models_dir.glob("robustness_model_v1_*.json"))
        if not artifacts:  # no live models on this box (CI) - the signature tests still bind
            return
        model = json.loads(artifacts[-1].read_text())
        offenders = [
            name
            for name in model.get("feature_names", [])
            if any(key in name for key in _PERFORMANCE_DERIVED_DETAIL_KEYS)
        ]
        assert not offenders, (
            f"Live robustness model {artifacts[-1].name} carries performance-derived "
            f"features {offenders}. The ranker is now selecting on own-performance: the "
            "measured ranked-vs-holdout shift becomes a real DSR multiplicity charge and "
            "the Crucible agreement of 2026-07-22 must be re-opened."
        )
