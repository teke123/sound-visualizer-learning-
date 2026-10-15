"""f0 contour plotting with matplotlib.

Port of the shinytone (citationtone_hub) Visualise tab's plot logic
(``inst/app/ui/visualise_ui.R``, the ``current_plot`` reactive) from ggplot2
to matplotlib: tone-coloured scatter of long-format f0 data, optional
landmark-based time alignment (parts laid side by side or overlaid), and
by-tone / by-speaker-by-tone faceting. Companion to the R package behind
Xu & Zhang (2024, JASA 156(4), 2538-2565).

Also provides :func:`plot_comparison`, an addition for user-vs-reference
comparison (not part of the R original).
"""

from __future__ import annotations

import re
import warnings
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from .utils import require_columns

# Tone colour palette: the 12-colour qualitative set from visualise_ui.R.
# It leads with the brand pine-green (#3B8A6E) and coral accent (#E07A5F)
# so a typical small tone inventory reads as on-brand, then fans across the
# hue wheel. 12 colours match the "colour by tone only when <= 12 distinct
# values" cap, so every coloured tone level gets a distinct colour.
TONE_PALETTE = ['#3B8A6E', '#E07A5F', '#4F86B3', '#E0A458',
                '#8E6CA8', '#2FA89B', '#CB5E84', '#B5654A',
                '#7E9B3E', '#5566A0', '#A88B2D', '#6E7177']

ONE_COLOR = "#3b8a6e"   # single-colour fallback (low-cardinality / no tone)
NA_COLOR = "#999999"    # grey50, ggplot's default colour for NA levels
BOUNDARY_COLOR = "#bfbfbf"  # R "grey75" for the dashed part boundaries

# First column matching a token-like pattern (global.R var_patterns$token),
# used to connect points into per-token contour lines when aligning.
_TOKEN_PATTERNS = (r"^token$", r"^token", r"^filename", r"^basename",
                   r"^item$", r"^segment", r"^id$")


def _vis_token_col(cols) -> Optional[str]:
    """First column name matching a token-like pattern, or None (vis_token_col)."""
    for pat in _TOKEN_PATTERNS:
        for c in cols:
            if re.search(pat, str(c), flags=re.IGNORECASE):
                return c
    return None


def _f0_axis_label(col: str) -> str:
    """Pretty y-axis label for an f0 column (approximating f0_axis_label()).

    Maps the column name to a units label: a name containing "st"/"semitone"
    reads as semitones, one containing "zscore" reads as z-scores, anything
    else as Hz. Unlike the R helper (which typesets a literal f subscript 0
    and returns custom names unchanged), this keeps the column name visible
    so plots stay self-describing for arbitrary y columns.
    """
    c = col.lower()
    if "semitone" in c or "st" in c:
        return f"{col} (semitones)"
    if "zscore" in c or "z-score" in c or "z_score" in c:
        return f"{col} (z-score)"
    return f"{col} (Hz)"


def _prepare_alignment(data: pd.DataFrame, x_var: str, align_by: str,
                       align_layout: str):
    """Renormalise the X (time) variable within each part of a landmark set.

    Port of the alignment block of ``current_plot()``: ``p_in`` is the time
    frame's position within its ``<align_by>_start`` / ``<align_by>_end``
    interval, clipped to [0, 1]. "sequential" lays parts side by side
    (part index i -> x in [i-1, i]) so multi-syllable words align part by
    part; "overlay" maps every part onto a single 0-1 axis.

    Returns ``(df, x_values, x_label, seq_layout, max_i, groups)`` where rows
    with a non-finite aligned x are dropped (as R's
    ``plot_data[is.finite(plot_data$.aligned_x), ]``), and ``groups`` is the
    per-row contour-line grouping key (token when side by side, token + part
    when overlaid, so a line does not wrap from a part's end back to 0), or
    None when no token-like column exists.
    """
    sc = f"{align_by}_start"
    ec = f"{align_by}_end"
    ic = f"{align_by}_i"
    tv = pd.to_numeric(data[x_var], errors="coerce").to_numpy(dtype=float)
    st = pd.to_numeric(data[sc], errors="coerce").to_numpy(dtype=float)
    en = pd.to_numeric(data[ec], errors="coerce").to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p_in = (tv - st) / (en - st)
    p_in[~np.isfinite(p_in)] = np.nan
    p_in = np.clip(p_in, 0.0, 1.0)

    seq_layout = False
    max_i = None
    if align_layout == "sequential" and ic in data.columns:
        seg_i = np.rint(pd.to_numeric(data[ic], errors="coerce")
                        .to_numpy(dtype=float))
        aligned = (seg_i - 1.0) + p_in
        seq_layout = True
        if np.isfinite(seg_i).any():
            max_i = int(np.nanmax(seg_i))
    else:
        aligned = p_in

    keep = np.isfinite(aligned)
    df = data.loc[keep]
    x_values = aligned[keep]
    x_label = (f"{align_by} (part by part)" if seq_layout
               else f"normalised time within {align_by} (0-1)")

    groups = None
    tok_col = _vis_token_col(data.columns)
    if tok_col is not None:
        if not seq_layout and ic in data.columns:
            seg = pd.to_numeric(data.loc[keep, ic], errors="coerce")
            groups = (df[tok_col].astype(str) + "##" + seg.astype(str)).to_numpy()
        else:
            groups = df[tok_col].astype(str).to_numpy()
    return df, x_values, x_label, seq_layout, max_i, groups


def _default_figsize(facet: str, n_tones: int = 0, n_speakers: int = 0
                     ) -> Tuple[float, float]:
    """Default panel size in inches, from the app's pixel heuristics / 100 dpi.

    Port of ``plot_height()`` / ``plot_width()``: 800x600 px normally,
    width ``max(400 + 100 * n_tones, 600)`` px when faceting by tone, and
    height ``300 + 100 * n_speakers`` px for the speaker x tone grid.
    """
    if facet == "speaker_tone":
        width = max(400 + 100 * max(n_tones, 1), 600) / 100.0
        height = (300 + 100 * max(n_speakers, 1)) / 100.0
    elif facet == "tone":
        width = max(400 + 100 * max(n_tones, 1), 600) / 100.0
        height = 600 / 100.0
    else:
        width, height = 800 / 100.0, 600 / 100.0
    return width, height


def _draw_panel(ax: Axes, x: np.ndarray, y: np.ndarray,
                tone_vals: Optional[np.ndarray], tone_colors: dict,
                colour_by_tone: bool, aligned: bool,
                groups: Optional[np.ndarray], seq_layout: bool,
                max_i: Optional[int]) -> None:
    """Draw one panel: contour lines (aligned), boundary vlines, scatter."""
    # Connect each token's frames into a contour line, but only when aligned
    # (the R plot likewise draws geom_line only on the aligned axis).
    if aligned and groups is not None:
        for g in pd.unique(groups):
            m = groups == g
            if colour_by_tone:
                tv = tone_vals[m]
                tv = tv[~pd.isna(tv)]
                line_color = tone_colors.get(tv[0], NA_COLOR) if len(tv) else NA_COLOR
                alpha = 0.45
            else:
                line_color = ONE_COLOR
                alpha = 0.4
            ax.plot(x[m], y[m], color=line_color, alpha=alpha, lw=0.8,
                    zorder=1, solid_capstyle="round")
    # Dashed part boundaries when laying parts side by side.
    if seq_layout and max_i is not None and max_i > 1:
        for b in range(1, max_i):
            ax.axvline(b, linestyle="--", color=BOUNDARY_COLOR, lw=0.4,
                       zorder=0)
    # Points on top.
    if colour_by_tone:
        colors = [tone_colors.get(v, NA_COLOR) for v in tone_vals]
        ax.scatter(x, y, c=colors, alpha=0.75, s=12, zorder=2,
                   edgecolors="none")
    else:
        ax.scatter(x, y, c=ONE_COLOR, alpha=0.6, s=12, zorder=2,
                   edgecolors="none")
    # Tick at each part's centre, labelled by part number.
    if seq_layout and max_i is not None:
        ax.set_xticks([i + 0.5 for i in range(max_i)])
        ax.set_xticklabels([str(i + 1) for i in range(max_i)])


def plot_contours(data: pd.DataFrame, x_var: str, y_var: str,
                  tone_var: Optional[str] = None,
                  speaker_var: Optional[str] = None,
                  facet: str = "none", align_by: Optional[str] = None,
                  align_layout: str = "sequential",
                  ax: Optional[Axes] = None,
                  figsize: Optional[Tuple[float, float]] = None,
                  title: Optional[str] = None) -> Figure:
    """Scatter plot of f0 contours, optionally aligned by landmark and faceted.

    Port of shinytone ``current_plot()`` (``inst/app/ui/visualise_ui.R``).
    Part of the visualisation pipeline of the R package behind Xu & Zhang
    (2024, JASA 156(4), 2538-2565).

    Parameters
    ----------
    data : Long-format data frame (one row per f0 sample); not modified.
    x_var, y_var : Column names for the time (x) and f0 (y) axes.
    tone_var : Optional tone-category column. With at most 12 distinct
        values contours are coloured per tone level from :data:`TONE_PALETTE`
        (cycled) with a legend; with more, or when no column is given, all
        points use one colour and a warning is raised (the R app's warning
        bar).
    speaker_var : Optional speaker column, used by ``facet="speaker_tone"``.
    facet : "none", "tone" (one panel per tone level in a row) or
        "speaker_tone" (rows = speakers, columns = tones).
    align_by : Optional landmark-set base name (e.g. "syllable"). When the
        data carries ``<align_by>_start`` / ``<align_by>_end`` columns, x is
        renormalised within each part: ``align_layout="sequential"`` lays
        parts side by side (part i occupies [i-1, i], dashed boundaries,
        ticks at part centres; needs ``<align_by>_i``), "overlay" stacks all
        parts on one 0-1 axis. Rows whose aligned x is not finite are
        dropped. When aligned, frames are connected into per-token contour
        lines. When the landmark columns are missing the raw x axis is used
        silently, as in the R app (whose UI only offers valid sets).
    ax : Axes to draw on (only with ``facet="none"``); returns its figure.
    figsize : Figure size in inches; defaults follow the R app's
        pixel heuristics / 100 dpi.
    title : Optional panel title (axes title, or figure title when faceted).

    Returns
    -------
    The matplotlib Figure holding the plot.
    """
    require_columns(data, [x_var, y_var])
    if facet not in ("none", "tone", "speaker_tone"):
        raise ValueError("facet must be one of 'none', 'tone', 'speaker_tone'")
    if align_layout not in ("sequential", "overlay"):
        raise ValueError('align_layout must be "sequential" or "overlay"')
    if tone_var is not None:
        require_columns(data, [tone_var])
    if speaker_var is not None:
        require_columns(data, [speaker_var])
    if facet in ("tone", "speaker_tone") and tone_var is None:
        raise ValueError(f"facet={facet!r} needs a tone_var")
    if facet == "speaker_tone" and speaker_var is None:
        raise ValueError('facet="speaker_tone" needs a speaker_var')

    # Colour by Tone only when it has a manageable number of distinct values;
    # compute on the raw column, as in R (a continuous column mis-selected as
    # Tone would explode the discrete legend).
    colour_by_tone = False
    if tone_var is not None:
        n_lv = int(data[tone_var].nunique(dropna=False))
        colour_by_tone = n_lv <= len(TONE_PALETTE)
        if not colour_by_tone:
            warnings.warn(
                f"The tone variable '{tone_var}' has {n_lv} distinct values, "
                "which looks like a continuous column rather than tone "
                "categories. Contours are shown in a single colour; pick a "
                "categorical tone column to colour by tone.", stacklevel=2)
    else:
        warnings.warn(
            "No tone variable given; contours are shown in a single colour.",
            stacklevel=2)

    tone_colors = {}   # level -> hex, order of appearance
    if colour_by_tone:
        levels = list(pd.unique(data[tone_var].dropna()))
        tone_colors = {lv: TONE_PALETTE[i % len(TONE_PALETTE)]
                       for i, lv in enumerate(levels)}

    # ---- Optional landmark alignment --------------------------------------
    df = data
    x_values = None
    x_label = x_var
    seq_layout = False
    max_i = None
    groups = None
    aligned = False
    if align_by and (f"{align_by}_start" in data.columns
                     and f"{align_by}_end" in data.columns):
        df, x_values, x_label, seq_layout, max_i, groups = _prepare_alignment(
            data, x_var, align_by, align_layout)
        aligned = True
    if x_values is None:
        x_values = pd.to_numeric(df[x_var], errors="coerce").to_numpy(dtype=float)
    y_values = pd.to_numeric(df[y_var], errors="coerce").to_numpy(dtype=float)
    tone_vals = (df[tone_var].to_numpy() if tone_var is not None
                 else np.full(len(df), np.nan, dtype=object))
    y_label = _f0_axis_label(y_var)

    created = False
    if facet == "none":
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize or _default_figsize("none"))
            created = True
        else:
            fig = ax.figure
        _draw_panel(ax, x_values, y_values, tone_vals, tone_colors,
                    colour_by_tone, aligned, groups, seq_layout, max_i)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        if colour_by_tone:
            _add_tone_legend(ax, tone_colors, tone_var)
        if title:
            ax.set_title(title)
        if created:
            fig.tight_layout()
        return fig

    if ax is not None:
        raise ValueError("ax is only supported with facet='none'; faceting "
                         "creates its own figure grid")

    tone_levels = list(pd.unique(df[tone_var].dropna()))
    if not tone_levels:
        raise ValueError(f"No non-missing values in tone column '{tone_var}' "
                         "to facet by")
    tone_row_vals = df[tone_var].to_numpy()
    if facet == "tone":
        width, height = figsize or _default_figsize("tone", len(tone_levels))
        fig, axs = plt.subplots(1, len(tone_levels), figsize=(width, height),
                                sharex=True, sharey=True, squeeze=False)
        panels = [axs[0][i] for i in range(len(tone_levels))]
        masks = [tone_row_vals == lev for lev in tone_levels]
    else:
        speakers = list(pd.unique(df[speaker_var].dropna()))
        width, height = figsize or _default_figsize(
            "speaker_tone", len(tone_levels), len(speakers))
        fig, axs = plt.subplots(len(speakers), len(tone_levels),
                                figsize=(width, height), sharex=True,
                                sharey=True, squeeze=False)
        speaker_row_vals = df[speaker_var].to_numpy()
        panels, masks = [], []
        for sp in speakers:
            for lev in tone_levels:
                panels.append(axs[len(panels) // len(tone_levels)]
                              [len(panels) % len(tone_levels)])
                masks.append((tone_row_vals == lev) &
                             (speaker_row_vals == sp))

    for i, (mask, panel) in enumerate(zip(masks, panels)):
        _draw_panel(panel, x_values[mask], y_values[mask],
                    tone_vals[mask], tone_colors, colour_by_tone, aligned,
                    groups[mask] if groups is not None else None,
                    seq_layout, max_i)
        panel.set_xlabel(x_label)
        if i % len(tone_levels) == 0:
            panel.set_ylabel(y_label)
    if colour_by_tone:
        _add_tone_legend(axs[0][0], tone_colors, tone_var)
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    return fig


def _add_tone_legend(ax: Axes, tone_colors: dict, tone_var: str) -> None:
    handles = [Line2D([0], [0], marker="o", color="none",
                      markerfacecolor=color, markersize=5, label=str(level))
               for level, color in tone_colors.items()]
    ax.legend(handles=handles, title=tone_var, frameon=False)


def save_plot(fig: Figure, path, dpi: int = 300):
    """Save a figure as PNG.

    Port of the Visualise tab's download handler (``ggsave`` with a white
    background at 300 dpi). Returns the path written.
    """
    fig.savefig(path, dpi=dpi, facecolor="white")
    return str(path)


def plot_comparison(user_contour: pd.DataFrame, ref_contour: pd.DataFrame,
                    x_col: str = "time", y_col: str = "f0",
                    label_user: str = "You", label_ref: str = "Reference",
                    ax: Optional[Axes] = None) -> Figure:
    """Overlay a user's contour on a reference contour.

    Addition for user-vs-reference comparison (not in the R original): both
    curves are drawn on one shared axis, the user's as a solid line and the
    reference's as a dashed line. Each contour's ``x_col`` is min-max
    normalised to [0, 1] first, so a recorded contour in raw seconds and a
    reference template on normalised time line up (a single-frame or
    zero-range contour lands at 0.5).

    Returns the matplotlib Figure.
    """
    require_columns(user_contour, [x_col, y_col], where="user_contour")
    require_columns(ref_contour, [x_col, y_col], where="ref_contour")

    def _norm_xy(d):
        xv = pd.to_numeric(d[x_col], errors="coerce").to_numpy(dtype=float)
        yv = pd.to_numeric(d[y_col], errors="coerce").to_numpy(dtype=float)
        xn = np.full(len(xv), np.nan)
        fin = np.isfinite(xv)
        if fin.any():
            lo, hi = xv[fin].min(), xv[fin].max()
            xn[fin] = 0.5 if hi == lo else (xv[fin] - lo) / (hi - lo)
        return xn, yv

    xu, yu = _norm_xy(user_contour)
    xr, yr = _norm_xy(ref_contour)
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 4))
    else:
        fig = ax.figure
    ax.plot(xu, yu, color=ONE_COLOR, lw=2.0, label=label_user)
    ax.plot(xr, yr, color=TONE_PALETTE[1], lw=2.0, ls="--", label=label_ref)
    ax.set_xlabel("time (normalised 0-1)")
    ax.set_ylabel(_f0_axis_label(y_col))
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig
