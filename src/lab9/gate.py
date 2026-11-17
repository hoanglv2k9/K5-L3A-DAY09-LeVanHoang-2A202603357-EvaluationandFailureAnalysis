"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def _is_missing_or_nonfinite(val: object) -> bool:
    if val is None:
        return True
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return not math.isfinite(float(val))
    return False


def _check_metrics_finite(pr: dict, base: dict, spec: dict, problems: list[str]) -> None:
    metrics_map = pr.get("metrics") or {}
    base_metrics = base.get("metrics") or {}
    for k, v in metrics_map.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and not math.isfinite(float(v)):
            problems.append(f"non-finite metric {k}={v}")
    for m in spec.get("metrics") or []:
        mid = m["id"]
        missing_key = mid in base_metrics and mid not in metrics_map
        is_none = mid in metrics_map and metrics_map[mid] is None
        if missing_key or is_none:
            if not (mid == "cost_per_success" and metrics_map.get("pass_rate") == 0):
                problems.append(f"missing/None metric {mid}")


def _check_rows_and_slices(pr: dict, base: dict, spec: dict, problems: list[str]) -> None:
    failures = pr.get("evaluator_failures") or []
    if failures:
        problems.append(f"evaluator_failures non-empty ({len(failures)})")
    pr_rows = pr.get("rows") or []
    base_rows = base.get("rows") or []
    if not pr_rows:
        problems.append("PR rows empty")
    man = pr.get("manifest") or {}
    items_n, seeds = man.get("items"), man.get("seeds")
    if isinstance(items_n, bool) or not isinstance(items_n, int) or items_n <= 0 or not isinstance(seeds, list) or not seeds:
        problems.append("invalid manifest items/seeds")
    elif len(pr_rows) != items_n * len(seeds):
        problems.append(f"row count {len(pr_rows)} != {items_n}*{len(seeds)}")
    pr_pairs = [(r.get("item_id"), r.get("seed")) for r in pr_rows]
    base_pairs = [(r.get("item_id"), r.get("seed")) for r in base_rows]
    if len(pr_pairs) != len(set(pr_pairs)):
        problems.append("duplicate (item_id, seed) rows in PR")
    if base_rows and set(pr_pairs) != set(base_pairs):
        problems.append("PR (item_id, seed) set differs from baseline")
    row_graded = {
        m["id"]
        for m in (spec.get("metrics") or [])
        if any(m["id"] in r for r in base_rows) or any(m["id"] in r for r in pr_rows)
    }
    for mid in sorted(row_graded):
        if any(mid not in r or _is_missing_or_nonfinite(r[mid]) for r in pr_rows):
            problems.append(f"row missing/None value for graded metric {mid}")
    base_slices = {r.get("item_id"): frozenset(r.get("slices") or []) for r in base_rows}
    relabelled = sorted(
        {
            str(r.get("item_id"))
            for r in pr_rows
            if r.get("item_id") in base_slices and frozenset(r.get("slices") or []) != base_slices[r.get("item_id")]
        }
    )
    if relabelled:
        problems.append(f"slice tags changed for {', '.join(relabelled[:5])}")


def _check_ratchet(spec: dict, base_spec: dict | None, problems: list[str]) -> None:
    if base_spec is None or spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        return
    pr_metrics = {m["id"]: m for m in (spec.get("metrics") or [])}
    for bm in base_spec.get("metrics") or []:
        mid = bm["id"]
        pm = pr_metrics.get(mid)
        if pm is None:
            problems.append(f"ratchet: metric {mid} removed")
            continue
        if bm.get("blocking") and not pm.get("blocking"):
            problems.append(f"ratchet: metric {mid} became non-blocking")
        th_b, th_p = bm.get("threshold") or {}, pm.get("threshold") or {}
        if "max" in th_b and ("max" not in th_p or float(th_p["max"]) > float(th_b["max"]) + 1e-12):
            problems.append(f"ratchet: {mid} max raised")
        if "min" in th_b and ("min" not in th_p or float(th_p["min"]) + 1e-12 < float(th_b["min"])):
            problems.append(f"ratchet: {mid} min lowered")
        if "max_increase" in th_b and (
            "max_increase" not in th_p or float(th_p["max_increase"]) > float(th_b["max_increase"]) + 1e-12
        ):
            problems.append(f"ratchet: {mid} max_increase raised")
        if th_b.get("no_significant_drop") and not th_p.get("no_significant_drop"):
            problems.append(f"ratchet: {mid} dropped no_significant_drop")
    pr_slices = {(s["name"], s["metric"]): s for s in (spec.get("slices") or [])}
    for bs in base_spec.get("slices") or []:
        key = (bs["name"], bs["metric"])
        label = f"{bs['name']}/{bs['metric']}"
        ps = pr_slices.get(key)
        if ps is None:
            problems.append(f"ratchet: slice {label} removed")
            continue
        if bs.get("blocking") and not ps.get("blocking"):
            problems.append(f"ratchet: slice {label} became non-blocking")
        if "min" in bs and ("min" not in ps or float(ps["min"]) + 1e-12 < float(bs["min"])):
            problems.append(f"ratchet: slice {label} min lowered")
        if "max" in bs and ("max" not in ps or float(ps["max"]) > float(bs["max"]) + 1e-12):
            problems.append(f"ratchet: slice {label} max raised")
        if bs.get("no_significant_drop") and not ps.get("no_significant_drop"):
            problems.append(f"ratchet: slice {label} dropped no_significant_drop")


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    _check_metrics_finite(pr, base, spec, problems)
    _check_rows_and_slices(pr, base, spec, problems)
    _check_ratchet(spec, base_spec, problems)
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name = s["name"]
        metric = s["metric"]
        sid = f"slice:{name}/{metric}"
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        verdict, note = "ok", ""
        if not a:
            val: float | None = None
            verdict = "missing"
        else:
            raw_val = sum(a.values()) / len(a)
            val = round(raw_val, 4)
            if "min" in s and raw_val + 1e-12 < float(s["min"]):
                verdict = "fail"
            if "max" in s and raw_val - 1e-12 > float(s["max"]):
                verdict = "fail"
            if s.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap(
                        [a[k] for k in keys],
                        [b[k] for k in keys],
                        n_resamples=bs.get("n_resamples", 1000),
                        rng=bs.get("rng", 2027),
                        confidence=bs.get("confidence", 0.95),
                    )
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        is_blocking = bool(s.get("blocking", False))
        if verdict != "ok" and is_blocking:
            blocked.append(sid)
        th = {k: s[k] for k in ("min", "max", "no_significant_drop") if k in s}
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if is_blocking else "warn")
        lines.append(f"  {sid:<26} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
