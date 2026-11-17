"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
import math
from numbers import Integral

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")
    tp = fp = fn = tn = 0
    for h_raw, j_raw in zip(human, judge):
        h_pos = str(h_raw).strip().upper() == POS
        j_pos = str(j_raw).strip().upper() == POS
        if h_pos and j_pos:
            tp += 1
        elif not h_pos and j_pos:
            fp += 1
        elif h_pos and not j_pos:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    tp, fp, fn = cm["tp"], cm["fp"], cm["fn"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    total = cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"]
    if total == 0:
        raise ValueError("cohen_kappa is undefined for empty sequences")
    p_o = (cm["tp"] + cm["tn"]) / total
    p_e = (
        (cm["tp"] + cm["fn"]) * (cm["tp"] + cm["fp"])
        + (cm["fp"] + cm["tn"]) * (cm["fn"] + cm["tn"])
    ) / (total * total)
    if abs(1.0 - p_e) <= 1e-12:
        raise ValueError("cohen_kappa is undefined when p_e == 1")
    return (p_o - p_e) / (1.0 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denom = float(sensitivity) + float(specificity) - 1.0
    if abs(denom) <= 1e-12:
        return max(0.0, min(1.0, float(observed_rate)))
    raw = (float(observed_rate) + float(specificity) - 1.0) / denom
    return max(0.0, min(1.0, raw))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    if len(a) != len(b):
        raise ValueError("a and b must have the same length")
    if len(a) == 0:
        raise ValueError("a and b must be non-empty")
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    if np.all(arr_a == arr_b):
        return (0.0, 0.0, 0.0)
    delta = float(np.mean(arr_a - arr_b))
    if len(arr_a) == 1:
        return (delta, delta, delta)
    res = bootstrap(
        (arr_a, arr_b),
        lambda x, y, axis=-1: np.mean(x - y, axis=axis),
        paired=True,
        method="percentile",
        n_resamples=n_resamples,
        confidence_level=confidence,
        rng=np.random.default_rng(rng),
    )
    return (delta, float(res.confidence_interval.low), float(res.confidence_interval.high))


def _validate_nck(n: int, c: int, k: int) -> tuple[int, int, int]:
    if any(isinstance(v, bool) or not isinstance(v, Integral) for v in (n, c, k)):
        raise ValueError(f"n, c, k must be integers, got {(n, c, k)!r}")
    ni, ci, ki = int(n), int(c), int(k)
    if ni <= 0 or ki <= 0 or ki > ni or ci < 0 or ci > ni:
        raise ValueError(f"invalid (n, c, k)={(ni, ci, ki)}: require 0 <= c <= n and 1 <= k <= n")
    return ni, ci, ki


def _comb_ratio(m: int, n: int, k: int) -> float:
    """Compute C(m, k) / C(n, k) for 0 <= m <= n and 1 <= k <= n."""
    if m < k:
        return 0.0
    try:
        ratio = math.comb(m, k) / math.comb(n, k)
    except OverflowError:
        ratio = 1.0
        for i in range(k):
            ratio *= (m - i) / (n - i)
    return max(0.0, min(1.0, ratio))


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    ni, ci, ki = _validate_nck(n, c, k)
    return max(0.0, min(1.0, 1.0 - _comb_ratio(ni - ci, ni, ki)))


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    ni, ci, ki = _validate_nck(n, c, k)
    return _comb_ratio(ci, ni, ki)
