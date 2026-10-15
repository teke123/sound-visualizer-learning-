"""Equal-N resampling of long-format f0 contours, and voiced-region helpers.

Port of shinytone ``resample.R``: ``resample_f0_equal()``,
``trim_to_voiced()``, and ``flag_f0_gaps()``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .utils import (as_time_numeric, f0_to_nan, require_columns,
                    run_lengths, token_group_key)

__all__ = ["resample_f0_equal", "trim_to_voiced", "flag_f0_gaps"]


def resample_f0_equal(df: pd.DataFrame,
                      n: int = 21,
                      token: str = "token",
                      time: str = "time",
                      f0: str = "f0",
                      intensity: str = "intensity",
                      method: str = "linear") -> pd.DataFrame:
    """Resample each token's f0 contour to ``n`` equidistant points.

    For each token, replaces the native pitch-frame grid with ``n``
    points equally spaced between the token's first and last frame time,
    so every token contributes the same number of samples at the same
    proportional positions (``n=21``: one point every 5% of the
    duration), the standard "measure f0 at every 5%/10% of the syllable"
    convention in citation-tone work (Xu & Zhang 2024).

    f0 at each new point follows Praat's rule for
    ``Pitch: Get value at time... Linear`` (``Sampled_getValueAtX()``).
    Of the two native frames bracketing the point, call the closer one
    *near* and the other *far*:

    * both voiced: linearly interpolated between them;
    * *far* unvoiced (NaN or 0 Hz): the *near* frame's value;
    * *near* unvoiced: NaN, since nothing was measured there.

    With ``method="nearest"`` a point always takes the nearer frame's
    measured value, or NaN when that frame is unvoiced; no value is ever
    computed. This rests on unvoiced frames being present as NaN/0 Hz
    rows; sparse input without such rows interpolates straight across
    gaps, exactly as Praat does on a PitchTier.

    Rows with missing time are dropped; rows sharing a frame time are
    collapsed to the first, so interpolation anchors are strictly
    increasing. A token left with fewer than two distinct times keeps
    its single remaining row with ``time_prop = 0.5`` and its raw f0
    value. Non-core columns are carried through only when constant
    within every token; columns that cannot be carried are named in the
    ``dropped_columns`` attribute of the result. Input columns named
    ``point`` or ``time_prop`` are always dropped (recomputed here).

    If an ``intensity`` column is present it is linearly interpolated
    across all frames with finite intensity, holding the end values
    constant outside the anchor range (R ``approx(..., rule = 2)``,
    matched by ``numpy.interp``); with ``method="nearest"`` it takes the
    near frame's raw value.

    Parameters
    ----------
    df : Long-format f0 data frame.
    n : Number of points per token (at least 2). Default ``21``.
    token, time, f0 : Column names. Defaults ``"token"``, ``"time"``,
        ``"f0"``.
    intensity : Name of the optional intensity column; used only when
        present in ``df``. Default ``"intensity"``.
    method : ``"linear"`` (default, Praat's own default) or
        ``"nearest"``.

    Returns
    -------
    A data frame with the ``token``, ``point`` (1..n), ``time`` (on the
    new grid), ``time_prop`` (0..1), and ``f0`` columns, plus
    ``intensity`` (when present) and any carried token-constant columns.
    Tokens keep their order of first appearance; rows are sorted by
    ``point`` within each token.

    Raises
    ------
    ValueError
        If ``method`` is invalid, ``n`` is smaller than 2, columns are
        missing, or the time/f0 columns are not numeric.

    References
    ----------
    Xu, C., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations. *The
    Journal of the Acoustical Society of America*, 156(4), 2538-2565.

    Port of shinytone::resample_f0_equal().
    """
    if method not in ("linear", "nearest"):
        raise ValueError("method must be one of 'linear', 'nearest'")
    try:
        n_pts = int(n)
    except (TypeError, ValueError):
        n_pts = 0
    if n_pts < 2:
        raise ValueError("`n` must be an integer of at least 2.")

    require_columns(df, [token, time, f0])
    # is.numeric() in R: integer/double only.
    for cl in (time, f0):
        if df[cl].dtype.kind not in "iuf":
            raise ValueError(f"Column '{cl}' must be numeric.")
    has_int = intensity in df.columns
    # An all-missing intensity column carries no measurements either way,
    # so accept it rather than refusing to resample f0 over it.
    if has_int and df[intensity].dtype.kind not in "iuf" \
            and not bool(df[intensity].isna().all()):
        raise ValueError(f"Column '{intensity}' must be numeric.")

    core = [token, time, f0] + ([intensity] if has_int else [])
    t_all = as_time_numeric(df[time])
    f_all = df[f0].to_numpy(dtype=float)
    i_all = (pd.to_numeric(df[intensity], errors="coerce").to_numpy(dtype=float)
             if has_int else None)

    tok_key = token_group_key(df[token])
    n_groups = int(tok_key.max()) + 1 if len(tok_key) else 0
    usable = ~np.isnan(t_all)

    extra = [c for c in df.columns
             if c not in core and c not in ("point", "time_prop")]
    if extra and usable.any():
        # Constancy is judged only over rows that survive the missing-time
        # drop: NaN-time rows must not make a token-constant column look
        # per-frame. NaN counts as a value ([1, NaN] has two unique values).
        sub = pd.DataFrame({c: df[c].to_numpy()[usable] for c in extra})
        nuniq = sub.groupby(tok_key[usable], sort=False).nunique(dropna=False)
        carried = [c for c in extra if bool((nuniq[c] <= 1).all())]
    else:
        # No usable rows anywhere: the empty split constrains nothing.
        carried = list(extra)
    dropped = [c for c in extra if c not in carried]

    out_cols = [token, "point", time, "time_prop", f0] \
        + ([intensity] if has_int else []) + carried
    acc = {c: [] for c in out_cols}  # type: dict
    token_vals = df[token].to_numpy()
    col_vals = {c: df[c].to_numpy() for c in carried}

    for g in range(n_groups):
        pos = np.flatnonzero(tok_key == g)
        tv = t_all[pos]
        ok = ~np.isnan(tv)
        pos, tv = pos[ok], tv[ok]
        if pos.size == 0:
            continue                      # token has no readable time at all
        order = np.argsort(tv, kind="stable")
        pos, tv = pos[order], tv[order]
        firsts = np.concatenate(([True], tv[1:] != tv[:-1]))
        pos, tv = pos[firsts], tv[firsts]
        tok_val = token_vals[pos[0]]

        if tv.size < 2:
            # Single remaining frame: no grid change is possible; the raw
            # f0/intensity values pass through untouched (0 Hz included).
            acc[token].append(tok_val)
            acc["point"].append(1)
            acc[time].append(float(tv[0]))
            acc["time_prop"].append(0.5)
            acc[f0].append(float(f_all[pos[0]]))
            if has_int:
                acc[intensity].append(float(i_all[pos[0]]))
            for c in carried:
                acc[c].append(col_vals[c][pos[0]])
            continue

        m = tv.size
        t_out = np.linspace(tv[0], tv[-1], n_pts)

        steps = np.diff(tv)
        dx = (tv[-1] - tv[0]) / (m - 1)
        scale = float(np.mean(np.abs(steps)))
        if scale <= 1e-9:
            is_uniform = bool(np.all(np.abs(steps - dx) <= 1e-9))
        else:
            # R all.equal(..., tolerance = 1e-9): mean relative difference.
            is_uniform = bool(np.mean(np.abs(steps - dx)) <= 1e-9 * scale)
        if is_uniform:
            # Praat derives frame index and phase from ONE index_real =
            # (x - x1) / dx; deriving them separately can disagree by an
            # ulp and pick the wrong neighbour.
            idx = (t_out - tv[0]) / dx
            left = np.floor(idx).astype(np.int64)
            phase = idx - np.floor(idx)
        else:
            left = np.searchsorted(tv, t_out, side="right") - 1
            np.clip(left, 0, m - 2, out=left)
            phase = (t_out - tv[left]) / (tv[left + 1] - tv[left])

        lo = phase < 0.5
        near = np.where(lo, left, left + 1)
        far = np.where(lo, left + 1, left)
        ph = np.where(lo, phase, 1.0 - phase)        # 0 .. 0.5

        ff = f0_to_nan(f_all[pos])                   # 0 Hz is unvoiced
        inside = (near >= 0) & (near <= m - 1)
        nv = np.full(n_pts, np.nan)
        nv[inside] = ff[near[inside]]
        if method == "nearest":
            f_out = nv
        else:
            fv = np.full(n_pts, np.nan)
            ins_f = (far >= 0) & (far <= m - 1)
            fv[ins_f] = ff[far[ins_f]]
            f_out = np.where(np.isnan(nv), np.nan,
                             np.where(np.isnan(fv), nv, nv + ph * (fv - nv)))

        acc[token].extend([tok_val] * n_pts)
        acc["point"].extend(range(1, n_pts + 1))
        acc[time].extend(t_out.tolist())
        acc["time_prop"].extend(np.linspace(0.0, 1.0, n_pts).tolist())
        acc[f0].extend(f_out.tolist())
        if has_int:
            iv = i_all[pos]
            if method == "nearest":
                out_int = np.full(n_pts, np.nan)
                out_int[inside] = iv[near[inside]]
            else:
                fin = np.isfinite(iv)
                k = int(fin.sum())
                if k >= 2:
                    # np.interp holds the end values, R approx rule = 2.
                    out_int = np.interp(t_out, tv[fin], iv[fin])
                elif k == 1:
                    out_int = np.full(n_pts, float(iv[fin][0]))
                else:
                    out_int = np.full(n_pts, np.nan)
            acc[intensity].extend(out_int.tolist())
        for c in carried:
            acc[c].extend([col_vals[c][pos[0]]] * n_pts)

    if len(acc["point"]) == 0:
        cols = {token: df[token].iloc[0:0],
                "point": pd.Series([], dtype="int64"),
                time: pd.Series([], dtype="float64"),
                "time_prop": pd.Series([], dtype="float64"),
                f0: pd.Series([], dtype="float64")}
        if has_int:
            cols[intensity] = pd.Series([], dtype="float64")
        for c in carried:
            cols[c] = df[c].iloc[0:0]
        out = pd.DataFrame(cols)
    else:
        out = pd.DataFrame({c: acc[c] for c in out_cols})
        out["point"] = out["point"].astype("int64")
        for c in [time, "time_prop", f0] + ([intensity] if has_int else []):
            out[c] = out[c].astype("float64")

    out.attrs["dropped_columns"] = list(dropped)
    return out


def trim_to_voiced(df: pd.DataFrame,
                   token: str = "token",
                   time: str = "time",
                   f0: str = "f0",
                   min_run: int = 2) -> pd.DataFrame:
    """Trim each token to its voiced region.

    Keeps only the rows between a token's first and last voiced frame,
    so a downstream measurement spans the syllable rather than the whole
    recording (frame trackers emit NA/0 Hz f0 across leading and
    trailing silence; Xu & Zhang 2024, sec. on f0 measurement regions).

    Edge anchors must belong to a run of at least ``min_run`` consecutive
    voiced frames, so one stray voiced frame in silence (a common
    octave-error artefact) cannot stretch the region; when no run is that
    long the first and last voiced frames are used. Frames inside the
    region are kept whether or not they are voiced, so an internal
    unvoiced stretch stays in place and still reads as NaN. Tokens with
    no voiced frame at all keep no rows.

    Parameters
    ----------
    df : Long-format f0 data frame.
    token, time, f0 : Column names. Defaults ``"token"``, ``"time"``,
        ``"f0"``.
    min_run : Minimum length of a consecutive voiced run an edge anchor
        must belong to. Default ``2``.

    Returns
    -------
    ``df`` with out-of-region rows removed, original row order and a
    fresh index; the input is not modified.

    References
    ----------
    Xu, C., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations. *The
    Journal of the Acoustical Society of America*, 156(4), 2538-2565.

    Port of shinytone::trim_to_voiced().
    """
    require_columns(df, [token, time, f0])
    tv = as_time_numeric(df[time])
    fv = f0_to_nan(df[f0])                            # 0 Hz is unvoiced
    key = token_group_key(df[token])

    keep = np.zeros(len(df), dtype=bool)
    for g in np.unique(key):
        idx = np.flatnonzero(key == g)
        # Region search walks time order (NaN times sort last); the rows
        # themselves keep their original order in the output.
        order = idx[np.argsort(tv[idx], kind="stable")]
        voiced = ~np.isnan(fv[order])
        if not voiced.any():
            continue                                  # no f0 at all
        values, starts, ends = run_lengths(voiced)
        long_runs = values & (ends - starts + 1 >= min_run)
        if not long_runs.any():
            long_runs = values                        # fall back to any voiced
        sel = np.flatnonzero(long_runs)
        keep[order[starts[sel[0]]:ends[sel[-1]] + 1]] = True

    return df[keep].reset_index(drop=True)


def flag_f0_gaps(df: pd.DataFrame,
                 token: str = "token",
                 f0: str = "f0",
                 time: str = "time") -> pd.DataFrame:
    """Flag tokens whose f0 has gaps inside the measured region.

    Adds two token-level columns so unvoiced stretches are visible
    rather than silently scattered NaNs:

    * ``n_missing``: the number of the token's rows with no f0
      (NaN or 0 Hz);
    * ``has_gap``: True when at least one such row sits *between* the
      token's first and last voiced rows. A missing value at the edge
      usually just means the region ran slightly past the voicing; only
      an interior one marks interrupted voicing (a medial voiceless
      stop, a creaky patch, or a tracking failure). A token with no f0
      at all gets ``has_gap = False``. Existing columns of either name
      are replaced.

    Rows are ordered by the ``time`` column when present, otherwise by
    row order, before "between" is judged. Run this on the native frames
    rather than on a resampled grid: resampling can fill a short dropout
    from its nearer frame, leaving no NaN behind for this to find.

    Parameters
    ----------
    df : Long-format f0 data frame.
    token, f0, time : Column names; ``time`` is used only when present
        in ``df``. Defaults ``"token"``, ``"f0"``, ``"time"``.

    Returns
    -------
    A copy of ``df`` with the ``n_missing`` and ``has_gap`` columns
    added (or replaced).

    Port of shinytone::flag_f0_gaps().
    """
    require_columns(df, [token, f0])
    out = df.copy()
    if len(df) == 0:
        out["n_missing"] = pd.Series([], dtype="int64")
        out["has_gap"] = pd.Series([], dtype=bool)
        return out

    fv = f0_to_nan(df[f0])                            # 0 Hz is unvoiced
    key = token_group_key(df[token])
    if time in df.columns:
        ord_within = as_time_numeric(df[time])
    else:
        ord_within = np.arange(len(df), dtype=float)

    n_miss = np.zeros(len(df), dtype=np.int64)
    gap = np.zeros(len(df), dtype=bool)
    for g in np.unique(key):
        idx = np.flatnonzero(key == g)
        order = idx[np.argsort(ord_within[idx], kind="stable")]
        present = ~np.isnan(fv[order])
        n_miss[idx] = int(np.count_nonzero(~present))
        if present.any():
            p = np.flatnonzero(present)
            inner = ~present[p[0]:p[-1] + 1]
            gap[idx] = bool(inner.any())

    out["n_missing"] = n_miss
    out["has_gap"] = gap
    return out
