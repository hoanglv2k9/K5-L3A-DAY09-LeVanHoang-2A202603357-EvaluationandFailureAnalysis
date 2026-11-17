"""Extra unit tests for M5-M7 (collected under `-k advanced`, skipped cleanly by Core `-k 'not advanced'` and Lab 8 `ci.yml`)."""

from __future__ import annotations

import copy

import pytest

pytestmark = pytest.mark.student


def test_slice_check_ci_drop_blocks_even_above_min_floor():
    from lab9 import gate

    # 5 items x 5 seeds in slice "money_movement": drop 1 seed on every item -> mean=0.80 >= min 0.70, CI=[-0.2, -0.2] < 0.
    base_rows = [
        {"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["money_movement"]}
        for i in range(5)
        for s in (11, 22, 33, 44, 55)
    ]
    pr_rows = copy.deepcopy(base_rows)
    for r in pr_rows:
        if r["seed"] == 11:
            r["pass_rate"] = False
    base = {
        "manifest": {"eval_set_sha": "x", "items": 5, "seeds": [11, 22, 33, 44, 55]},
        "rows": base_rows,
        "metrics": {"pass_rate": 1.0},
        "evaluator_failures": [],
    }
    pr = {
        "manifest": {"eval_set_sha": "x", "items": 5, "seeds": [11, 22, 33, 44, 55]},
        "rows": pr_rows,
        "metrics": {"pass_rate": 0.8},
        "evaluator_failures": [],
    }
    spec = {
        "eval_set_version": "v2",
        "bootstrap": {"n_resamples": 1000, "rng": 2027, "confidence": 0.95},
        "metrics": [],
        "slices": [
            {"name": "money_movement", "metric": "pass_rate", "min": 0.70, "no_significant_drop": True, "blocking": True}
        ],
    }
    blocked, lines = gate.slice_check(pr, base, spec)
    assert blocked == ["slice:money_movement/pass_rate"]
    assert "BLOCK" in lines[0]


def test_slice_check_missing_blocking_and_nonblocking_warn():
    from lab9 import gate

    rows = [{"item_id": "E-001", "seed": 11, "pass_rate": False, "slices": ["denial"]}]
    base = {
        "manifest": {"eval_set_sha": "x", "items": 1, "seeds": [11]},
        "rows": rows,
        "metrics": {"pass_rate": 0.0},
        "evaluator_failures": [],
    }
    spec = {
        "eval_set_version": "v2",
        "slices": [
            {"name": "escalation", "metric": "pass_rate", "min": 0.9, "blocking": True},
            {"name": "denial", "metric": "pass_rate", "min": 0.9, "blocking": False},
        ],
    }
    blocked, lines = gate.slice_check(base, base, spec)
    assert blocked == ["slice:escalation/pass_rate"]
    assert "MISSING" in lines[0]
    assert "warn" in lines[1]


@pytest.mark.parametrize("bad", [(5, 6, 1), (5, 2, 0), (3, 1, 4), (0, 0, 1), (5, -1, 1), (True, 1, 1)])
def test_pass_hat_k_rejects_bad_args_and_handles_large_n(bad):
    from lab9 import stats

    with pytest.raises(ValueError):
        stats.pass_hat_k(*bad)
    with pytest.raises(ValueError):
        stats.pass_at_k(*bad)
    assert stats.pass_hat_k(2000, 1999, 5) == pytest.approx(1995 / 2000, abs=1e-9)


def test_integrity_catches_hidden_traps_and_ratchet():
    from lab9 import gate

    rows = [
        {"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["money_movement"] if i == 0 else []}
        for i in range(4)
        for s in (1, 2)
    ]
    base = {
        "manifest": {"eval_set_sha": "x", "items": 4, "seeds": [1, 2]},
        "rows": copy.deepcopy(rows),
        "metrics": {"pass_rate": 1.0},
        "evaluator_failures": [],
    }
    spec = {
        "eval_set_version": "v2",
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True, "threshold": {"min": 0.9, "no_significant_drop": True}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.9, "no_significant_drop": True, "blocking": True}],
    }
    assert gate.integrity_check(base, base, spec, spec) == []

    # Hidden trap 1: evaluator_failures non-empty on an otherwise green run.
    with_fail = copy.deepcopy(base)
    with_fail["evaluator_failures"] = ["E-000@1:ReplyMatchesLedger:boom"]
    assert gate.integrity_check(with_fail, base, spec)

    # Hidden trap 2: duplicate rows keeping len == items * len(seeds).
    dup = copy.deepcopy(base)
    dup["rows"][-1] = copy.deepcopy(dup["rows"][0])
    assert gate.integrity_check(dup, base, spec)

    # Hidden trap 3: slice relabelling.
    relabeled = copy.deepcopy(base)
    for r in relabeled["rows"]:
        if r["item_id"] == "E-000":
            r["slices"] = []
    assert gate.integrity_check(relabeled, base, spec)

    # Hidden trap 4: cherry-picked seeds even if manifest was forged to match.
    cherry = copy.deepcopy(base)
    cherry["rows"] = [r for r in cherry["rows"] if r["seed"] == 1]
    cherry["manifest"]["seeds"] = [1]
    assert gate.integrity_check(cherry, base, spec)

    # Ratchet: tightening passes; dropping no_significant_drop or making non-blocking fails.
    tighter = copy.deepcopy(spec)
    tighter["metrics"][0]["threshold"]["min"] = 0.95
    assert gate.integrity_check(base, base, tighter, spec) == []
    no_ci = copy.deepcopy(spec)
    no_ci["slices"][0].pop("no_significant_drop")
    assert gate.integrity_check(base, base, no_ci, spec)
    non_block = copy.deepcopy(spec)
    non_block["metrics"][0]["blocking"] = False
    assert gate.integrity_check(base, base, non_block, spec)

    # Hidden trap 5: NaN inside a row's metric value and deleted metric from PR summary.
    row_nan = copy.deepcopy(base)
    row_nan["rows"][0]["pass_rate"] = float("nan")
    assert gate.integrity_check(row_nan, base, spec)
    del_metric = copy.deepcopy(base)
    del del_metric["metrics"]["pass_rate"]
    assert gate.integrity_check(del_metric, base, spec)
