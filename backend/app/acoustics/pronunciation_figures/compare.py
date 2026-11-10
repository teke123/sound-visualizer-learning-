"""基于共享测量结果进行逐音节配对与差值计算。"""
from __future__ import annotations

import numpy as np

from .measure import Analysis, _rnd


def paired(left, right, usable=True):
    return {"learner": left, "reference": right,
            "difference": _rnd(left - right, 3) if usable and left is not None and right is not None else None,
            "can_use": bool(usable and left is not None and right is not None)}


def compare(learner: Analysis, reference: Analysis | None) -> dict:
    if reference is None:
        return {"available": False, "reason": "reference_missing", "syllables": []}
    if len(learner.syllables) != len(reference.syllables):
        return {"available": False, "reason": "syllable_count_mismatch", "syllables": []}
    same_sex = learner.sex == reference.sex and learner.sex != "unknown"
    same_band = learner.bandwidth_hz == reference.bandwidth_hz
    rows = []
    for ls, rs in zip(learner.syllables, reference.syllables):
        lr, rr = ls["reliability"], rs["reliability"]
        matched = (ls["symbol"] == rs["symbol"] and ls["final"]["label"] == rs["final"]["label"]
                   and (ls["initial"] or {}).get("label") == (rs["initial"] or {}).get("label"))
        usable = lambda key: matched and lr[key] and rr[key]
        pairs = [(x, y) for x, y in zip(ls["tone"]["contour_degree"], rs["tone"]["contour_degree"])
                 if x is not None and y is not None]
        tone_ok = usable("absolute_pitch") and len(pairs) >= 10
        row = {"learner_symbol": ls["symbol"], "reference_symbol": rs["symbol"],
               "matched_target": matched,
               "tone": {"chao": [ls["tone"]["chao"], rs["tone"]["chao"]],
                        "can_compare_shape": usable("tone_shape"), "can_compare_height": tone_ok,
                        "mean_abs_degree_diff": _rnd(np.mean([abs(x-y) for x, y in pairs]), 3) if tone_ok else None,
                        "mean_degree_diff": _rnd(np.mean([x-y for x, y in pairs]), 3) if tone_ok else None,
                        "start": paired(ls["tone"]["start_degree"], rs["tone"]["start_degree"], tone_ok),
                        "end": paired(ls["tone"]["end_degree"], rs["tone"]["end_degree"], tone_ok)},
               "duration_ms": paired(ls["duration_ms"], rs["duration_ms"], matched),
               "duration_share": paired(ls["duration_share"], rs["duration_share"], matched),
               "vowel_mid_hz": [paired(x, y, usable("vowel") and same_sex) for x, y in zip(ls["vowel"]["mid_hz"], rs["vowel"]["mid_hz"])],
               "vowel_mid_z": [paired(x, y, usable("vowel")) for x, y in zip(ls["vowel"].get("mid_z", []), rs["vowel"].get("mid_z", []))] or None}
        cons = {}
        lc, rc = ls["consonant"] or {}, rs["consonant"] or {}
        for key, flag in (("vot_ms", "vot"), ("closure_ms", "vot"),
                          ("frication_ms", "noise_spectrum"), ("aspiration_ms", "vot"),
                          ("noise_ms", "noise_spectrum"), ("noise_rise_ms", "noise_rise"),
                          ("murmur_ms", "sonorant_midpoint"), ("hnr_db", "sonorant_midpoint"), ("voiced_fraction", "sonorant_midpoint")):
            if key in lc or key in rc:
                cons[key] = paired(lc.get(key), rc.get(key), usable(flag))
        if "prevoiced" in lc or "prevoiced" in rc:
            cons["prevoiced"] = {"learner": lc.get("prevoiced"), "reference": rc.get("prevoiced"), "can_use": usable("vot")}
        for key in ("peak_hz", "cog_hz", "sd_hz", "skewness", "kurtosis", "level_rel_vowel_db"):
            lp, rp = lc.get("spectrum", {}), rc.get("spectrum", {})
            if lp or rp:
                ok = usable("noise_spectrum") and same_band
                if key != "level_rel_vowel_db":
                    ok = ok and same_sex and lp.get("place_cue_available", False) and rp.get("place_cue_available", False)
                cons[key] = paired(lp.get(key), rp.get(key), ok)
        for key in ("F3_min_hz", "F2_vowel_onset_hz"):
            if key in lc or key in rc:
                cons[key] = paired(lc.get(key), rc.get(key), usable("sonorant_midpoint") and same_sex)
        for key in ("formants_consonant_mid_hz", "formants_vowel_mid_hz"):
            if key in lc and key in rc:
                cons[key] = [paired(x, y, usable("sonorant_midpoint") and same_sex) for x, y in zip(lc[key], rc[key])]
        row["consonant"] = cons
        ln, rn = ls["nasal_coda"] or {}, rs["nasal_coda"] or {}
        row["nasal_coda"] = {key: paired(ln.get(key), rn.get(key), usable("nasal_coda"))
                             for key in ("murmur_ms", "murmur_share", "F1_change_hz", "F2_change_hz",
                                         "F3_change_hz", "F2_slope_hz_per_ms")} if ln or rn else None
        if row["nasal_coda"] is not None:
            row["nasal_coda"]["detected"] = {"learner": ln.get("detected"), "reference": rn.get("detected"), "can_use": False}
        rows.append(row)
    return {"available": True, "same_estimated_sex": same_sex, "same_spectral_band": same_band,
            "syllables": rows}
