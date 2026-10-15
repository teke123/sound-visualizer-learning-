"""Per-tone mean f0 contours from long-format data.

Port of shinytone ``chao.R``'s ``compute_mean_contour()`` (citationtone_hub):
aggregates a long-format f0 dataset into a per-tone mean contour suitable
for plotting, comparison, or Chao numeral summarisation via
:func:`tone_py.chao.contour_to_chao`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .time_norm import resolve_time_norm
from .utils import require_columns


def compute_mean_contour(data: pd.DataFrame,
                         token: str = "token",
                         f0: str = "f0",
                         time: str = "time",
                         tone: str = "tone",
                         n_bins: int = 50,
                         time_normalised: str = "auto") -> pd.DataFrame:
    """Compute the per-tone mean f0 contour from long-format data.

    Aggregates a long-format f0 dataset into a per-tone mean contour
    suitable for plotting, comparison, or Chao numeral summarisation via
    :func:`tone_py.chao.contour_to_chao`.

    Internally:

    1. Within each token, the time axis is normalised to ``[0, 1]`` so
       tokens of different durations can be averaged on the same grid. A
       time column that is *already* normalised is detected and used
       as-is (override with ``time_normalised``); see
       :func:`tone_py.time_norm.resolve_time_norm`.
    2. Each sample's normalised time is rounded onto one of ``n_bins``
       equally-spaced bins: ``round(t * (n_bins - 1)) / (n_bins - 1)``.
    3. For each (tone, time-bin) cell, the mean of ``f0`` across all
       tokens of that tone with samples in the bin is computed (NaN f0
       values are skipped, matching R's ``mean(..., na.rm = TRUE)``).

    Parameters
    ----------
    data : Long-format data frame with one row per f0 sample.
    token, f0, time, tone : Column names.
    n_bins : Number of evenly-spaced time bins across ``[0, 1]``.
        Default 50. Larger values give a smoother contour at the cost of
        noisier per-bin estimates in sparsely populated bins.
    time_normalised : "auto" (default: detect an already-normalised
        [0, 1] time column and use it as-is), "no" (always rescale to
        [0, 1] within each token), or "yes" (declare the column already
        normalised).

    Returns
    -------
    A data frame with columns ``tone``, ``time`` (the bin value), and
    ``f0_predicted`` (the column name matches the convention used by the
    model-based contour functions so the same downstream tools can
    consume either), one row per (tone, time-bin), sorted by tone and
    time. The input data frame is not modified.

    Port of shinytone::compute_mean_contour().

    References
    ----------
    Xu, C., & Zhang, C. (2024). A cross-linguistic review of citation
    tone production studies: Methodology and recommendations. *The
    Journal of the Acoustical Society of America*, 156(4), 2538-2565.
    """
    require_columns(data, [token, f0, time, tone])

    t_norm, _ = resolve_time_norm(data, time, token, time_normalised)

    work = pd.DataFrame({
        "tone": data[tone].astype(str).to_numpy(),
        "time": np.round(np.asarray(t_norm, dtype=float) * (n_bins - 1))
                / (n_bins - 1),
        "f0": pd.to_numeric(data[f0], errors="coerce").to_numpy(dtype=float),
    })

    out = (work.groupby(["tone", "time"], as_index=False)["f0"]
               .mean()
               .rename(columns={"f0": "f0_predicted"})
               .sort_values(["tone", "time"], kind="stable")
               .reset_index(drop=True))
    return out
