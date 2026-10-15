"""Shared helpers for the tone_py package.

Every module works on the same long-format DataFrame convention as the
upstream R package `shinytone` (citationtone_hub): one row per f0 sample,
with at least `token`, `time`, `f0` columns and usually `speaker` and
`tone`. Column names are always passed as string parameters so users can
rename freely.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd


def require_columns(data: pd.DataFrame, cols: Iterable[str], where: str = "data") -> None:
    """Raise ValueError listing any missing columns, mirroring shinytone's checks."""
    missing = [c for c in cols if c not in data.columns]
    if missing:
        raise ValueError(f"Column(s) not found in {where}: {', '.join(missing)}")


def require_numeric(data: pd.DataFrame, col: str, what: str = "numeric") -> None:
    """Raise ValueError when a column cannot be used as numbers."""
    values = data[col]
    if values.dtype.kind not in "bifu":
        converted = pd.to_numeric(values, errors="coerce")
        if len(values) > 0 and converted.isna().all() and not values.isna().all():
            raise ValueError(f"Column '{col}' must be {what}.")


def as_time_numeric(values: pd.Series) -> np.ndarray:
    """Coerce a time column to float, loudly failing when it is not numeric.

    String-like columns go through numeric coercion first so that "0.15"
    means 0.15; a column that converts to nothing but NaN is an error rather
    than a silent all-NaN axis.
    """
    converted = pd.to_numeric(values, errors="coerce")
    if len(values) > 0 and converted.isna().all() and not values.isna().all():
        raise ValueError("Time column is not numeric and could not be read as time.")
    return converted.to_numpy(dtype=float)


def f0_voiced(x) -> np.ndarray:
    """Boolean mask of voiced frames: finite f0 strictly above 0 Hz.

    Pitch trackers disagree on how they signal "no f0": some write NaN,
    others 0 Hz (RAPT/REAPER, some Praat scripts). 0 Hz is not a possible
    pitch, so both count as unvoiced here.
    """
    v = pd.to_numeric(pd.Series(list(x) if not hasattr(x, "dtype") else x),
                      errors="coerce").to_numpy(dtype=float)
    return np.isfinite(v) & (v > 0)


def f0_to_nan(x) -> np.ndarray:
    """Return f0 as float with unvoiced frames (NaN and 0 Hz) set to NaN.

    The result never aliases the caller's memory: ``to_numpy()`` on a
    float column returns a view, and writing NaN through it would silently
    overwrite the input DataFrame.
    """
    v = pd.to_numeric(pd.Series(list(x) if not hasattr(x, "dtype") else x),
                      errors="coerce").to_numpy(dtype=float, copy=True)
    v[~(np.isfinite(v) & (v > 0))] = np.nan
    return v


def token_group_key(tokens: Sequence) -> np.ndarray:
    """Integer group codes for token IDs, first-appearance order, NaN kept.

    Uses value matching (not string conversion) so two distinct IDs that
    print alike stay separate and NaN forms its own group, matching
    ``dplyr::group_by`` semantics.
    """
    s = tokens if isinstance(tokens, pd.Series) else pd.Series(tokens)
    seen: dict = {}
    codes: List[int] = []
    for v in s.tolist():
        if v is None or (isinstance(v, float) and np.isnan(v)):
            key = ("__nan__",)  # tuple sentinel: cannot collide with scalar IDs
        else:
            key = v
        if key not in seen:
            seen[key] = len(seen)
        codes.append(seen[key])
    return np.asarray(codes, dtype=np.int64)


def legendre_basis(t: np.ndarray, degree: int) -> np.ndarray:
    """Legendre polynomial basis on [-1, 1] up to `degree`, Bonnet recurrence."""
    t = np.asarray(t, dtype=float)
    n = t.shape[0]
    B = np.empty((n, degree + 1), dtype=float)
    B[:, 0] = 1.0  # P0
    if degree >= 1:
        B[:, 1] = t  # P1
    for k in range(2, degree + 1):
        # P_k = ((2k-1) t P_{k-1} - (k-1) P_{k-2}) / k
        B[:, k] = ((2 * k - 1) * t * B[:, k - 1] - (k - 1) * B[:, k - 2]) / k
    return B


def orthogonal_poly(x, degree: int, alpha=None, norm2=None) -> Tuple[np.ndarray, dict]:
    """Discrete orthogonal polynomial basis, R ``stats::poly()`` equivalent.

    Builds (or, given ``alpha``/``norm2`` from a previous call, re-applies)
    an orthonormal basis for ``1, x, x^2, ... x^degree`` under the inner
    product induced by the training points, via the three-term Stieltjes
    recurrence. The basis equals R's ``poly()`` up to a possible column
    sign flip, which is irrelevant as long as fit and prediction share one
    basis.

    With no stored coefficients (training path), ``x`` is the training
    vector. With them (prediction path), ``x`` may be any new vector on the
    same scale.

    Returns ``(Q, coefs)`` where ``Q`` has shape ``(len(x), degree)`` and
    ``coefs = {"alpha": [...], "norm2": [...]}`` can be passed back in to
    evaluate the same basis on new points. ``norm2[0]`` is the conventional
    leading 1; ``norm2[k]`` is ``||P_{k-1}||^2``.
    """
    x = np.asarray(x, dtype=float)

    if alpha is None or norm2 is None:
        alpha: List[float] = []
        norm2: List[float] = [1.0, float(len(x))]  # ||P_0||^2 = n
        p_km1 = np.ones_like(x)                    # P_0
        p_km2 = None
        cols = []
        for k in range(1, degree + 1):
            a = float(np.dot(x * p_km1, p_km1) / np.dot(p_km1, p_km1))
            if p_km2 is None:
                p_k = (x - a) * p_km1
            else:
                beta = norm2[k] / norm2[k - 1]     # ||P_{k-1}||^2 / ||P_{k-2}||^2
                p_k = (x - a) * p_km1 - beta * p_km2
            alpha.append(a)
            norm2.append(float(np.dot(p_k, p_k)))  # norm2[k+1] = ||P_k||^2
            cols.append(p_k / np.sqrt(norm2[k + 1]))
            p_km2, p_km1 = p_km1, p_k
        return np.column_stack(cols), {"alpha": alpha, "norm2": norm2}

    # Prediction path: identical recurrence with the stored coefficients.
    p_km1 = np.ones_like(x)                        # P_0
    p_km2 = None
    cols = []
    for k in range(1, degree + 1):
        a = alpha[k - 1]
        if p_km2 is None:
            p_k = (x - a) * p_km1
        else:
            beta = norm2[k] / norm2[k - 1]
            p_k = (x - a) * p_km1 - beta * p_km2
        cols.append(p_k / np.sqrt(norm2[k + 1]))
        p_km2, p_km1 = p_km1, p_k
    return np.column_stack(cols), {"alpha": alpha, "norm2": norm2}


def run_lengths(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Decompose a boolean mask into runs.

    Returns ``(values, starts, ends)`` with 0-based, end-inclusive indices.
    """
    if len(mask) == 0:
        return (np.array([], dtype=bool),
                np.array([], dtype=int),
                np.array([], dtype=int))
    change = np.flatnonzero(np.diff(mask.astype(np.int8))) + 1
    boundaries = np.concatenate(([0], change, [len(mask)]))
    starts = boundaries[:-1]
    ends = boundaries[1:] - 1
    return mask[starts], starts, ends
