"""Invariant: stamping ``search_n_trials`` never moves ``config_hash`` (D309).

`search_n_trials` is hash-excluded by contracts 1.19.0 (D175/D176). The
D309 stamp relies on that exclusion twice over:

- §13.4 idempotency — the stamped config must dedupe against its own
  unstamped hash (the unique index on ``submissions.config_hash``);
- hard rule #6 — enumeration stays deterministic because the stamp is a
  post-ranking, pre-submit decoration that cannot feed back into identity.

If a contracts upgrade ever folds the field into the hash, this test is
the tripwire: the stamp must then be renegotiated, not shipped silently.
"""

from __future__ import annotations

from forge.submission.search_multiplicity import stamp_search_n_trials
from tests.fixtures.strategy_configs import minimal_strategy_config
from tests.unit.test_submission.test_search_multiplicity import _candidate


def test_stamp_does_not_move_config_hash() -> None:
    config = minimal_strategy_config(name="hash_stability")
    original_hash = config.config_hash
    (stamped,) = stamp_search_n_trials([_candidate(config)], {})
    assert stamped.report.config.search_n_trials == 1
    assert stamped.report.config.config_hash == original_hash


def test_large_stamp_value_still_hash_stable() -> None:
    config = minimal_strategy_config(name="hash_stability_large")
    slot = ("mean_reversion", "swing_short", "named")
    (stamped,) = stamp_search_n_trials([_candidate(config)], {slot: 46_131})
    assert stamped.report.config.search_n_trials == 46_132
    assert stamped.report.config.config_hash == config.config_hash
