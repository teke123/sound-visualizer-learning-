"""Per-token time-axis normalisation to [0, 1].

Port of shinytone ``time_norm.R``: ``time_already_normalised()`` and
``resolve_time_norm()``. All modelling and summarising functions
(``fit_polynomial``, ``fit_gca_fixed``, ``compute_mean_contour``) rescale
time within each token before fitting; when the supplied column is already
proportional (e.g. ``time_prop`` from ``resample_f0_equal()``), re-applying
a per-token min-max rescale would stretch any token whose samples do not
span the full unit interval, so such a column is detected and used as-is.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from .utils import as_time_numeric, token_group_key


def time_already_normalised(time_values, tokens, eps: float = 1e-8) -> bool:
    """Does a time column look already normalised to [0, 1]?

    Heuristic used by :func:`resolve_time_norm` to decide whether a time
    column is already proportional (per-token normalised to the unit
    interval) and should be used as-is rather than min-max rescaled within
    each token again.

    Returns True only when all three hold:

    1. Every finite value lies in [0, 1] (within ``eps``).
    2. The pooled values actually use the unit scale: pooled minimum at or
       below 0.05 and pooled maximum at or above 0.95.
    3. Tokens individually cover the interval: the median per-token span
       (max - min) is at least 0.9.

    Condition 3 is the load-bearing one: raw time in seconds (durations of
    0.2-0.9 s) can satisfy the first two, but its per-token spans equal the
    variable durations, so it is correctly treated as unnormalised.

    Port of shinytone ``time_already_normalised()``.
    """
    try:
        tv = as_time_numeric(pd.Series(list(time_values) if not hasattr(time_values, "dtype")
                                       else time_values))
    except ValueError:
        return False
    fin = np.isfinite(tv)
    if not fin.any():
        return False
    t = tv[fin]
    if t.min() < -eps or t.max() > 1 + eps:
        return False
    if t.min() > 0.05 or t.max() < 0.95:
        return False
    tk = token_group_key(tokens)
    spans = np.array([t[(tk[fin] == g)].max() - t[(tk[fin] == g)].min()
                      for g in np.unique(tk[fin])])
    return bool(np.nanmedian(spans) >= 0.9)


def resolve_time_norm(data: pd.DataFrame, time: str, token: str,
                      time_normalised: str = "auto") -> Tuple[np.ndarray, bool]:
    """Per-token normalised time, honouring an already-normalised column.

    Builds the [0, 1] time axis the modelling functions fit on. With the
    default ``time_normalised="auto"`` the column is inspected with
    :func:`time_already_normalised`: a column that is already proportional
    is used as-is (clamped to [0, 1]), anything else is min-max rescaled to
    [0, 1] within each token.

    In the rescaling path, a token whose time has zero range (a single
    sample, or all-identical times) gets 0.5 for every row, and NaN times
    inside an otherwise valid token propagate as NaN.

    Parameters
    ----------
    data : Long-format data frame containing the time and token columns.
    time : Name of the time column.
    token : Name of the token-ID column.
    time_normalised : "auto" (detect and use an already-normalised column
        as-is), "no" (always rescale per token), or "yes" (declare the
        column already normalised to [0, 1]; values outside that interval
        are an error).

    Returns
    -------
    (time_norm, prenormalised) : numeric vector with one value per row of
        ``data`` and a flag telling whether the column was used as-is.

    Port of shinytone ``resolve_time_norm()``.
    """
    if time_normalised not in ("auto", "no", "yes"):
        raise ValueError("time_normalised must be one of 'auto', 'no', 'yes'")
    tv = as_time_numeric(data[time])
    tk = token_group_key(data[token])

    if time_normalised == "auto":
        pre = time_already_normalised(tv, data[token])
    else:
        pre = time_normalised == "yes"

    if pre:
        if time_normalised == "yes":
            fin = np.isfinite(tv)
            if (np.isinf(tv).any() or
                    (fin.any() and (tv[fin].min() < -1e-8 or tv[fin].max() > 1 + 1e-8))):
                raise ValueError(
                    f'time_normalised = "yes", but {time!r} has values outside '
                    '[0, 1]. Pass time_normalised="no" to rescale per token instead.')
        return np.clip(tv, 0.0, 1.0), True

    # Per-token min-max rescale. Tokens with no usable time yield NaN rows;
    # a zero-range token gets 0.5 everywhere.
    mn = np.full(tk.max() + 1, np.nan)
    mx = np.full(tk.max() + 1, np.nan)
    for g in np.unique(tk):
        vals = tv[tk == g]
        v = vals[np.isfinite(vals)]
        if v.size:
            mn[g] = v.min()
            mx[g] = v.max()
    mn_v = mn[tk]
    mx_v = mx[tk]
    degen = np.isnan(mn_v) | (np.isfinite(mn_v) & (mx_v == mn_v))
    with np.errstate(invalid="ignore"):
        tn = (tv - mn_v) / (mx_v - mn_v)
    tn[degen] = 0.5
    return tn, False
