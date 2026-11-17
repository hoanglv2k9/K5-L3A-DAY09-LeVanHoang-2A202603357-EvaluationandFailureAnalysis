"""M3 unit + variant tests for ReplyMatchesLedger (FM-08 catcher) and ApprovalBypass/RefundAmountCorrect edges."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.student


@pytest.fixture(scope="module")
def graders():
    # Keep pydantic_evals deferred so Lab 8 CI (without Lab 9 deps) can collect safely.
    from lab9 import graders

    return graders


def _ctx(trial, label=None):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(
        name="t",
        inputs={},
        metadata=None,
        expected_output=label or {"refund_vnd": 20000, "approval_ok": True},
        output=trial,
        duration=0.0,
        _span_tree=None,
        attributes={},
        metrics={},
    )


def _trial(*, refund_vnd=20000, refund_count=1, unexpected=0, reply_text=None):
    events = [{"kind": "reply", "payload": {"text": reply_text}}] if reply_text is not None else []
    return {
        "snapshot": {"refund_vnd": refund_vnd, "refund_count": refund_count},
        "unexpected_rows": unexpected,
        "blob": "",
        "events": events,
        "result": {},
        "lab8_pass": True,
        "lab8_reason": None,
    }


@pytest.mark.parametrize(
    "text",
    [
        "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808.",
        "LogiX đã hoàn phí 20.000đ cho đơn O-808 của anh/chị ạ.",
        "Dạ, LogiX đã hoàn 20,000 VND cho đơn O-808 trong 3-5 ngày.",
        "Dạ, LogiX đã hoàn 20000 cho đơn O-808 ạ.",
        "LogiX đã hoàn lại 20.000₫ cho đơn O-808.",
        "Số tiền hoàn là 20000 cho đơn O-808.",
    ],
)
def test_reply_matches_ledger_accepts_matching_formats(graders, text):
    res = graders.ReplyMatchesLedger().evaluate(_ctx(_trial(refund_vnd=20000, reply_text=text)))
    assert res.value is True


@pytest.mark.parametrize(
    ("refund_vnd", "text"),
    [
        (20000, "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."),
        (0, "Dạ, LogiX đã hoàn 35.000đ cho đơn O-909."),
        (90000, "LogiX đã hoàn phí 120.000đ cho đơn O-515 của anh/chị ạ."),
        (20000, "Dạ, LogiX đã hoàn 35000 đồng cho đơn O-808."),
    ],
)
def test_reply_matches_ledger_flags_fm08_mismatch(graders, refund_vnd, text):
    res = graders.ReplyMatchesLedger().evaluate(_ctx(_trial(refund_vnd=refund_vnd, refund_count=int(refund_vnd > 0), reply_text=text)))
    assert res.value is False


def test_reply_matches_ledger_handles_no_amount_and_order_numbers(graders):
    denied = _trial(refund_vnd=0, refund_count=0, reply_text="Dạ, đơn O-202 chưa đủ điều kiện hoàn trong 4 ngày.")
    assert graders.ReplyMatchesLedger().evaluate(_ctx(denied, {"refund_vnd": 0, "approval_ok": True})).value is True
    no_reply = _trial(refund_vnd=35000, refund_count=1, reply_text=None)
    assert graders.ReplyMatchesLedger().evaluate(_ctx(no_reply, {"refund_vnd": 35000, "approval_ok": True})).value is True


def test_policy_outcome_correct_flags_missing_denial_and_wrong_status(graders):
    missing_deny = {
        "snapshot": {"refund_vnd": 0, "refund_count": 0, "policy_denied": False},
        "unexpected_rows": 0,
        "blob": "",
        "events": [],
        "result": {"status": "denied"},
        "lab8_pass": False,
        "lab8_reason": "proposal_mismatch",
    }
    label = {"status": "denied", "refund_vnd": 0, "policy_denied": True, "approval_ok": True}
    assert graders.PolicyOutcomeCorrect().evaluate(_ctx(missing_deny, label)).value is False
    ok_deny = {**missing_deny, "snapshot": {"refund_vnd": 0, "refund_count": 0, "policy_denied": True}}
    assert graders.PolicyOutcomeCorrect().evaluate(_ctx(ok_deny, label)).value is True
