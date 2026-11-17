"""Bonus (+5): parity checks between pydantic-evals graders and Inspect AI scorers.

Unmarked so `python -m pytest -q tests/test_bonus_inspect.py` runs directly without `-o addopts=`,
while `pytest.importorskip("inspect_ai")` ensures CI environments without inspect-ai skip cleanly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_inspect_ai_report_artifact_is_valid():
    pytest.importorskip("inspect_ai")
    report_path = Path("reports/bonus_inspect_comparison.json")
    assert report_path.is_file()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["framework"] == "inspect_ai"
    assert data["total_row_mismatches"] == 0
    by_shape = {r["shape"]: r for r in data["results"]}
    assert by_shape["leaky_demo"]["metrics"]["secret_leak"]["inspect_ai"] == 70
    assert by_shape["sibling_demo"]["metrics"]["approval_bypass"]["inspect_ai"] == 20
    for row in data["results"]:
        assert row["row_mismatches"] == 0
        for pair in row["metrics"].values():
            assert pair["pydantic_evals"] == pair["inspect_ai"]


def test_inspect_ai_port_matches_pydantic_evals_1to1():
    pytest.importorskip("inspect_ai")
    from lab9 import bonus_inspect, eval as lab9_eval

    spec = lab9_eval.load_spec(Path("config/metric_spec.yaml"))
    summary = bonus_inspect.compare_frameworks(
        ["fixed", "seeded_regression", "misreport_demo", "leaky_demo", "sibling_demo"],
        spec,
        seeds=[11, 55],
    )
    assert summary["total_row_mismatches"] == 0
    by_shape = {r["shape"]: r for r in summary["results"]}
    assert by_shape["leaky_demo"]["metrics"]["secret_leak"]["inspect_ai"] > 0
    assert by_shape["sibling_demo"]["metrics"]["approval_bypass"]["inspect_ai"] > 0
    for row in summary["results"]:
        assert row["row_mismatches"] == 0
        for pair in row["metrics"].values():
            assert pair["pydantic_evals"] == pair["inspect_ai"]
