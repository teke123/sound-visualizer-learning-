"""Per-unit f0 contour duration.

Port of shinytone (citationtone_hub) ``R/duration.R`` ``contour_duration()``.
Adds the time from the first to the last frame with a measured f0 in each
unit: a whole token, or each labelled segment of a landmark set (e.g. each
syllable) within a token. This is the span the contour covers, not the
length of the unit's interval: unmeasured frames at either edge do not
count, and unmeasured frames inside the span (a gap) do not shorten it.
Part of the R package accompanying Xu & Zhang (2024, JASA 156(4), 2538-2565).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .utils import require_columns, run_lengths, token_group_key


def contour_duration(df: pd.DataFrame, token: str = "token",
                     time: str = "time", f0: str = "f0", set=None,
                     name=None, min_run: int = 2) -> pd.DataFrame:
    """Duration of each f0 contour, written on every row of its unit.

    Port of shinytone ``contour_duration()``.

    A frame counts as *measured* when its f0 is a finite number other than
    0; NaN and 0 (which pitch trackers write for unvoiced frames) do not
    count. Negative values do, so a normalised f0 column (semitones,
    z-scores) works as well as Hz. A unit with a single measured frame gets
    0, and a unit with none gets NaN.

    The first and last frames are anchored on a *run* of at least
    ``min_run`` consecutive measured frames (the rule ``trim_to_voiced()``
    uses for the voiced region), so a lone measured frame cut off from the
    contour (e.g. a tracking artefact in the silence) cannot stretch the
    duration at either end. If no run is that long, the first and last
    measured frames are used as they are.

    With ``set``, frames are grouped by token and by the segment's
    ``<set>_start`` / ``<set>_end`` boundaries, and only labelled segments
    are measured: frames in an empty-label interval (silence) or outside
    the tier get NaN. A ``<set>_i`` index column marks labelled segments
    (non-NaN); without one, the ``<set>`` label column is read and empty
    labels count as unlabelled.

    Parameters
    ----------
    df : Long-format f0 data frame. Not modified.
    token, time, f0 : Column names. Defaults ``"token"``, ``"time"``, ``"f0"``.
    set : Landmark-set base name (e.g. ``"syllable"``) to measure each
        segment of that set. None (default) measures whole tokens.
    name : Name of the new column. Default ``"token_f0_dur"``, or
        ``"<set>_f0_dur"`` with ``set``.
    min_run : Minimum number of consecutive measured frames the first and
        last frame must belong to. Default 2; 1 takes the first and last
        measured frames as they are.

    Returns
    -------
    Copy of ``df`` with the duration column appended, in the units of the
    ``time`` column. Row order is preserved; the value is repeated on every
    row of its unit.
    """
    need = [token, time, f0]
    if set is not None:
        need += [f"{set}_start", f"{set}_end"]
    require_columns(df, need)
    if name is None:
        name = "token_f0_dur" if set is None else f"{set}_f0_dur"

    tv = pd.to_numeric(df[time], errors="coerce").to_numpy(dtype=float)
    fv = pd.to_numeric(df[f0], errors="coerce").to_numpy(dtype=float)

    if set is None:
        # Whole tokens: value-matching group codes; rows with a missing
        # token id (R's NA_character_) are excluded from measurement.
        tok_ok = ~pd.isna(df[token]).to_numpy(dtype=bool)
        unit = np.full(len(df), np.nan)
        if tok_ok.any():
            unit[tok_ok] = token_group_key(df[token][tok_ok])
    else:
        st = pd.to_numeric(df[f"{set}_start"], errors="coerce").to_numpy(dtype=float)
        en = pd.to_numeric(df[f"{set}_end"], errors="coerce").to_numpy(dtype=float)
        inside = np.isfinite(st) & np.isfinite(en)
        # Labelled segments only. <set>_i is NaN in an empty-label interval;
        # without an index column, read the label itself.
        ic = f"{set}_i"
        if ic in df.columns:
            inside = inside & ~pd.isna(df[ic]).to_numpy(dtype=bool)
        elif set in df.columns:
            lab = df[set]
            labelled = lab.notna().to_numpy(dtype=bool) & \
                (lab.astype(str).str.strip() != "").to_numpy(dtype=bool)
            inside = inside & labelled
        tok_ok = ~pd.isna(df[token]).to_numpy(dtype=bool)
        seg = (pd.Series(st).round(12).astype(str) + "\r" +
               pd.Series(en).round(12).astype(str)).to_numpy()
        key = (df[token].astype(str) + "\r" + pd.Series(seg, index=df.index))
        unit = np.full(len(df), np.nan)
        valid = inside & tok_ok
        if valid.any():
            # Group only the valid rows; token_group_key would otherwise
            # give NaN keys a group of their own (dplyr semantics).
            unit[valid] = token_group_key(key[valid])

    use = np.isfinite(unit) & np.isfinite(tv)
    voiced = np.isfinite(fv) & (fv != 0)
    dur = np.full(len(df), np.nan)
    for g in np.unique(unit[use]):
        rows = np.flatnonzero(use & (unit == g))
        order = rows[np.argsort(tv[rows], kind="stable")]
        v = voiced[order]
        if not v.any():
            continue            # no measured f0: stays NaN
        values, starts, ends = run_lengths(v)
        lengths = ends - starts + 1
        long_runs = np.flatnonzero(values & (lengths >= min_run))
        if long_runs.size == 0:
            long_runs = np.flatnonzero(values)   # fall back to any run
        first = starts[long_runs[0]]
        last = ends[long_runs[-1]]
        dur[rows] = tv[order[last]] - tv[order[first]]

    out = df.copy()
    out[name] = dur
    return out
