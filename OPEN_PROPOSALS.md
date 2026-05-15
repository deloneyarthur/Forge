

<!-- 2026-05-14 cleanup: 480 duplicate loosen proposals bulk-rejected (proposer dedup now active; commit 8422cab). Operator audit: decided_by='aj-bulk-2026-05-14'. -->

---
- proposal_id: 646a865f-1379-4535-b470-e1df4b91d0f2
- STATUS: APPROVED at 2026-05-14T08:43:57.394115
- proposed_at: 2026-05-14T08:05:51.852643+00:00
- proposal_type: loosen
- target: prefilter_calibration
- rationale: Rolling 2-batch promotion rate is below 0.0050; propose loosening pre-filter thresholds by 10%.
- evidence_json: {"trigger": "auto_tune_loosen"}
- proposal_yaml: |
    # Proposed pre-filter loosening — rolling promotion rate below min threshold
    # step_pct: 0.1000
---
- proposal_id: c6a8eba9-3578-4530-bf95-42f07f8e1f94
- STATUS: PENDING
- proposed_at: 2026-05-14T16:38:04.630964+00:00
- proposal_type: tighten
- target: prefilter_calibration
- rationale: 110 of all rejected candidates failed `ablation_arm` (100%); propose tightening the pre-filter that catches this earlier.
- evidence_json: {"failure_count": 110, "failure_rate": 1.0, "target": "ablation_arm", "trigger": "gate_failure_concentration"}
- proposal_yaml: |
    # Proposed tightening — pre-filter for ablation_arm
    # Triggered by failure_rate=1.00
---
- proposal_id: facc310b-5d82-45d0-a87b-4b574304a88d
- STATUS: PENDING
- proposed_at: 2026-05-14T16:38:04.630964+00:00
- proposal_type: tighten
- target: prefilter_calibration
- rationale: 110 of all rejected candidates failed `cpcv_sharpe_p25` (100%); propose tightening the pre-filter that catches this earlier.
- evidence_json: {"failure_count": 110, "failure_rate": 1.0, "target": "cpcv_sharpe_p25", "trigger": "gate_failure_concentration"}
- proposal_yaml: |
    # Proposed tightening — pre-filter for cpcv_sharpe_p25
    # Triggered by failure_rate=1.00
---
- proposal_id: bb8b3a0d-7315-4fe8-b5b6-ddf0abcdf4ba
- STATUS: PENDING
- proposed_at: 2026-05-14T16:38:04.630964+00:00
- proposal_type: tighten
- target: prefilter_calibration
- rationale: 110 of all rejected candidates failed `deflated_sharpe` (100%); propose tightening the pre-filter that catches this earlier.
- evidence_json: {"failure_count": 110, "failure_rate": 1.0, "target": "deflated_sharpe", "trigger": "gate_failure_concentration"}
- proposal_yaml: |
    # Proposed tightening — pre-filter for deflated_sharpe
    # Triggered by failure_rate=1.00
---
- proposal_id: 00a2afd1-be78-45ee-9fbf-28dfd86485ba
- STATUS: PENDING
- proposed_at: 2026-05-14T16:38:04.630964+00:00
- proposal_type: tighten
- target: prefilter_calibration
- rationale: 110 of all rejected candidates failed `min_oos_trade_count` (100%); propose tightening the pre-filter that catches this earlier.
- evidence_json: {"failure_count": 110, "failure_rate": 1.0, "target": "min_oos_trade_count", "trigger": "gate_failure_concentration"}
- proposal_yaml: |
    # Proposed tightening — pre-filter for min_oos_trade_count
    # Triggered by failure_rate=1.00
---
- proposal_id: 40e8eb39-2468-4b55-b896-f7b137b37c2b
- STATUS: PENDING
- proposed_at: 2026-05-14T16:38:04.630964+00:00
- proposal_type: tighten
- target: prefilter_calibration
- rationale: 110 of all rejected candidates failed `pbo` (100%); propose tightening the pre-filter that catches this earlier.
- evidence_json: {"failure_count": 110, "failure_rate": 1.0, "target": "pbo", "trigger": "gate_failure_concentration"}
- proposal_yaml: |
    # Proposed tightening — pre-filter for pbo
    # Triggered by failure_rate=1.00
---
- proposal_id: b0946a31-4a47-42a1-946e-b4d812c7cd3d
- STATUS: PENDING
- proposed_at: 2026-05-14T16:38:04.630964+00:00
- proposal_type: tighten
- target: prefilter_calibration
- rationale: 110 of all rejected candidates failed `profit_factor` (100%); propose tightening the pre-filter that catches this earlier.
- evidence_json: {"failure_count": 110, "failure_rate": 1.0, "target": "profit_factor", "trigger": "gate_failure_concentration"}
- proposal_yaml: |
    # Proposed tightening — pre-filter for profit_factor
    # Triggered by failure_rate=1.00
---
- proposal_id: 4fac1dbe-1d3f-450f-86d7-5350bbfdfc09
- STATUS: PENDING
- proposed_at: 2026-05-14T16:38:04.630964+00:00
- proposal_type: tighten
- target: prefilter_calibration
- rationale: 110 of all rejected candidates failed `regime_stress_p25_return` (100%); propose tightening the pre-filter that catches this earlier.
- evidence_json: {"failure_count": 110, "failure_rate": 1.0, "target": "regime_stress_p25_return", "trigger": "gate_failure_concentration"}
- proposal_yaml: |
    # Proposed tightening — pre-filter for regime_stress_p25_return
    # Triggered by failure_rate=1.00
---
- proposal_id: 3d7dd548-1931-4136-ab47-ef3e2aa2fa16
- STATUS: PENDING
- proposed_at: 2026-05-14T16:38:04.630964+00:00
- proposal_type: tighten
- target: prefilter_calibration
- rationale: 110 of all rejected candidates failed `sharpe_baseline` (100%); propose tightening the pre-filter that catches this earlier.
- evidence_json: {"failure_count": 110, "failure_rate": 1.0, "target": "sharpe_baseline", "trigger": "gate_failure_concentration"}
- proposal_yaml: |
    # Proposed tightening — pre-filter for sharpe_baseline
    # Triggered by failure_rate=1.00
---
- proposal_id: dba68e07-233b-4c4f-89da-3bc1cf22c639
- STATUS: PENDING
- proposed_at: 2026-05-14T16:38:04.630964+00:00
- proposal_type: tighten
- target: prefilter_calibration
- rationale: 110 of all rejected candidates failed `walk_forward_sharpe_median` (100%); propose tightening the pre-filter that catches this earlier.
- evidence_json: {"failure_count": 110, "failure_rate": 1.0, "target": "walk_forward_sharpe_median", "trigger": "gate_failure_concentration"}
- proposal_yaml: |
    # Proposed tightening — pre-filter for walk_forward_sharpe_median
    # Triggered by failure_rate=1.00
