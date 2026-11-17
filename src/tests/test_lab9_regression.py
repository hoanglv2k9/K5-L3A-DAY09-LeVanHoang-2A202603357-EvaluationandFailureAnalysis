"""Regression test from M1 trace case (docs/trace_case.md): seeded_regression & swarm vs fixed on C-002."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.student


@pytest.mark.parametrize(
    ("shape", "seed"),
    [("seeded_regression", 11), ("swarm", 55)],
    ids=["seeded_regression_11", "ref_override_55"],
)
def test_fm03_c002_trace_regression(shape: str, seed: int):
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9.graders import DbFactKept
    from lab9.trace_case import investigate

    bad = investigate(shape, "C-002", seed)
    good = investigate("fixed", "C-002", seed)

    bad_trial = bad["trial"]
    good_trial = good["trial"]

    assert bad_trial["lab8_pass"] is False
    assert bad_trial["snapshot"]["refund_vnd"] == 20000
    assert any(e.get("kind") == "model_override" for e in bad_trial["events"])

    bad_ctx = EvaluatorContext(
        name=f"{shape}-C-002@{seed}",
        inputs={"claim_id": "C-002", "seed": seed},
        metadata=None,
        expected_output=bad["label"],
        output=bad_trial,
        duration=0.0,
        _span_tree=None,
        attributes={},
        metrics={},
    )
    good_ctx = EvaluatorContext(
        name=f"fixed-C-002@{seed}",
        inputs={"claim_id": "C-002", "seed": seed},
        metadata=None,
        expected_output=good["label"],
        output=good_trial,
        duration=0.0,
        _span_tree=None,
        attributes={},
        metrics={},
    )

    assert DbFactKept().evaluate(bad_ctx).value is False
    assert good_trial["lab8_pass"] is True
    assert good_trial["snapshot"]["refund_vnd"] == 0
    assert DbFactKept().evaluate(good_ctx).value is True
