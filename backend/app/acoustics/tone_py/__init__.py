"""tone_py: citation-tone f0 analysis in Python.

A Python sibling of the R package `shinytone` (citationtone_hub,
https://github.com/chenchenzi/citationtone_hub, GPL-3). Long-format
DataFrame convention throughout: one row per f0 sample with `token`,
`time`, `f0` columns (usually `speaker`, `tone` too); column names are
string parameters on every function. f0 of 0 Hz counts as unvoiced.

Methodology: Xu, C., & Zhang, C. (2024). A cross-linguistic review of
citation tone production studies: Methodology and recommendations.
*JASA*, 156(4), 2538-2565. doi:10.1121/10.0032356
"""

from __future__ import annotations

__version__ = "0.1.0"

from .chao import classify_contour, contour_to_chao
from .contour import compute_mean_contour
from .duration import contour_duration
from .extract import extract_f0, min_audio_duration, read_f0_csv
from .inspect import (
    flag_level_outliers,
    flag_low_intensity,
    flag_outliers,
    flag_pitch_jumps,
    inspect_f0,
)
from .models import GcaFit, fit_gca, fit_gca_fixed, fit_polynomial
from .normalise import normalise_f0
from .resample import flag_f0_gaps, resample_f0_equal, trim_to_voiced
from .sample import make_sample_f0
from .sonify import sonify_f0, write_wav
from .time_norm import resolve_time_norm, time_already_normalised
from .visualise import TONE_PALETTE, plot_comparison, plot_contours, save_plot

__all__ = [
    # extraction & data
    "extract_f0", "min_audio_duration", "read_f0_csv", "make_sample_f0",
    # inspection
    "inspect_f0", "flag_outliers", "flag_level_outliers",
    "flag_low_intensity", "flag_pitch_jumps",
    # normalisation & time
    "normalise_f0", "resolve_time_norm", "time_already_normalised",
    # resampling
    "resample_f0_equal", "trim_to_voiced", "flag_f0_gaps",
    # contours & Chao numerals
    "compute_mean_contour", "contour_to_chao", "classify_contour",
    # modelling
    "fit_polynomial", "fit_gca_fixed", "fit_gca", "GcaFit",
    # duration
    "contour_duration",
    # sonification
    "sonify_f0", "write_wav",
    # visualisation
    "plot_contours", "plot_comparison", "save_plot", "TONE_PALETTE",
]
