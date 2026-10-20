"""Regression cases for the F0 review; no network or application database."""
import io
import unittest
import wave
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.acoustics import f0_pipeline as fp
from app.content.usecases import _split_voiced_equal
from app.scoring.rules import curve_phenomena
from app import config
from app.acoustics import usecases as acoustics_uc
from app.acoustics.models import AudioRow, FeatureCacheRow
from app.content.models import LevelRow, MediaAssetRow
from app.detection.models import RecordingRow, AssessmentResultRow
from app.db import JSONText, now
from app.platform.envelope import ApiError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def track(values):
    hz = np.asarray(values, dtype=float)
    n = len(hz)
    return fp.PitchTrack(
        times=0.03 + np.arange(n) * 0.01, f0=hz.copy(),
        strength=np.where(np.isfinite(hz), .9, 0.0),
        rescue_f0=hz.copy(), rescue_strength=np.where(np.isfinite(hz), .9, 0.0),
        intensity_db=np.full(n, 70.0), background_db=30.0,
        duration=n * .01 + .06)


class F0Regressions(unittest.TestCase):
    def test_internal_octave_spike_is_corrected_without_exception(self):
        raw = np.full(11, 200.0)
        raw[5] = 400.0
        t = track(raw)
        side = fp.process_syllables(t, [(0, t.duration)], 100, 400)[0]
        self.assertTrue(all(abs(f["hz"] - 200) < 5 for f in side["frames"] if f["hz"]))

    def test_reference_path_uses_seconds_not_frame_indices(self):
        t = track([200, 200, 200, 200, 200, 200, 400, 400, 400, 200, 200])
        hz, strength = t.f0.copy(), t.strength.copy()
        sources, removed = np.ones(11, dtype=int), np.zeros(11, dtype=bool)
        fp._correct_interval(t.times, hz, strength, sources, removed, t, 0, 6, 8,
                             (5, fp._st(200)), (9, fp._st(200)))
        np.testing.assert_allclose(hz[6:9], 200, atol=1)

    def test_single_anchor_reference_uses_anchor_time(self):
        t = track([200, 198, 196, 194, 192, 190, 380, 380, 380])
        hz, strength = t.f0.copy(), t.strength.copy()
        sources, removed = np.ones(9, dtype=int), np.zeros(9, dtype=bool)
        fp._correct_interval(t.times, hz, strength, sources, removed, t, 0, 6, 8,
                             (5, fp._st(190)), None)
        np.testing.assert_allclose(hz[6:], 190, atol=1)

    def test_complete_short_rise_is_diagnosed_after_resampling(self):
        t = track(np.linspace(150, 160, 60))
        side = fp.process_syllables(t, [(0, t.duration)], 100, 400)[0]
        self.assertTrue(side["quality"]["canDiagnose"])
        tags = curve_phenomena({"status": "ok", "segments": [
            {"toneValue": 2, "syllable": "ma", "user": side}]})
        self.assertIn("tone_rise_insufficient", [p["tag"] for p in tags])

    def test_diagnosis_does_not_interpolate_across_a_missing_feature(self):
        t = track(np.linspace(150, 260, 60))
        t.f0[10:16] = np.nan
        t.rescue_f0[10:16] = np.nan
        side = fp.process_syllables(t, [(0, t.duration)], 100, 400)[0]
        tags = curve_phenomena({"status": "ok", "segments": [
            {"toneValue": 2, "syllable": "ma", "user": side}]})
        self.assertFalse(any(p["tag"] in ("tone_start_high", "tone_start_low",
                                         "tone_rise_insufficient") for p in tags))

    def test_voiced_fallback_consumes_entire_recording(self):
        bounds = _split_voiced_equal([[0, .1], [.2, .5]], 2)
        self.assertEqual(len(bounds), 2)
        self.assertAlmostEqual(bounds[0][0], 0)
        self.assertAlmostEqual(bounds[-1][1], .5)
        self.assertAlmostEqual(bounds[0][1], .3)

    def test_hum_keeps_one_frame_gap_silent_and_original_duration(self):
        frames = [{"t": i * .01, "hz": 200 if i != 2 else None,
                   "degree": 3 if i != 2 else None, "intensityDb": 70}
                  for i in range(10)]
        data = fp.sonify_frames(frames, duration=.5)
        with wave.open(io.BytesIO(data)) as wav:
            fs = wav.getframerate()
            signal = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
        self.assertEqual(len(signal), int(.5 * fs))
        self.assertTrue(np.all(signal[int(.02 * fs):int(.03 * fs)] == 0))
        self.assertTrue(np.any(signal[:int(.02 * fs)] != 0))

    def test_two_frame_voiced_run_can_be_synthesized(self):
        frames = [{"t": .1, "hz": 200, "degree": 3, "intensityDb": 70},
                  {"t": .11, "hz": 200, "degree": 3, "intensityDb": 70}]
        self.assertGreater(len(fp.sonify_frames(frames, duration=.3)), 1000)


class HumSnapshotRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_patch = patch.object(config, "DATA_DIR", Path(self.tmp.name))
        self.data_patch.start()
        self.engine = create_engine("sqlite://")
        for model in (AudioRow, FeatureCacheRow, LevelRow, MediaAssetRow, RecordingRow, AssessmentResultRow):
            model.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.audio = AudioRow(id="au_test", user_id="u1", purpose="recording",
                              storage_path="unused.wav", duration_sec=.7, pcm_sha256="test", created_at=now())
        self.asset = MediaAssetRow(id="med_test", kind="audio", filename="ref.wav",
                                  storage_path="unused-ref.wav", mime="audio/wav", duration_sec=.8, created_at=now())
        self.frames = [{"t": .1 + i * .01, "hz": 200.0, "degree": 3.0, "intensityDb": 70}
                       for i in range(10)]
        self.curve = {"sampleMediaId": self.asset.id,
                      "referenceRange": {"fLo": 100, "fHi": 400},
                      "segments": [{"user": {"frames": self.frames},
                                    "reference": {"frames": self.frames}}]}
        self.db.add_all([self.audio, self.asset, RecordingRow(
            id="rec_test", user_id="u1", audio_id=self.audio.id, level_id="L01", submission_id="s1",
            submission_payload_hash="h1", status="completed", deadline_at=now(), created_at=now()),
            AssessmentResultRow(id="res_test", recording_id="rec_test",
                                payload=JSONText.dump({"curve": self.curve}), created_at=now())])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.data_patch.stop()
        self.tmp.cleanup()

    def test_private_hum_reuses_exact_chart_frames_and_duration(self):
        with patch.object(fp, "extract_track", side_effect=AssertionError("must reuse chart")), \
                patch.object(fp, "sonify_frames", return_value=b"wav") as synth:
            result = acoustics_uc.get_f0_hum(self.db, self.audio, recording_id="rec_test")
        self.assertEqual(result.read_bytes(), b"wav")
        self.assertEqual(synth.call_args.args[0], self.frames)
        self.assertEqual(synth.call_args.kwargs["duration"], .7)

    def test_reference_remap_uses_stored_degree_and_reference_duration(self):
        with patch.object(fp, "extract_track", side_effect=AssertionError("must reuse chart")), \
                patch.object(fp, "sonify_f0", return_value=np.zeros(1600)) as synth:
            acoustics_uc.get_f0_hum(self.db, self.audio, (100, 400),
                                    recording_id="rec_test", side="reference")
        np.testing.assert_allclose(synth.call_args.args[0], 200, atol=.01)
        with wave.open(str(next((Path(self.tmp.name) / "hum").glob("*.wav")))) as wav:
            self.assertAlmostEqual(wav.getnframes() / wav.getframerate(), .8)

    def test_public_hum_reuses_standard_curve_and_rebuilds_missing_file(self):
        standard = {"sampleMediaId": self.asset.id, "segments": [{"frames": self.frames}]}
        self.db.add(LevelRow(id="L01", order=1, layer="vowel", published=True,
                             content=JSONText.dump({"detection": {"sampleMediaId": self.asset.id},
                                                    "standardCurve": standard}),
                             created_at=now(), updated_at=now()))
        self.db.commit()
        with patch.object(fp, "extract_track", side_effect=AssertionError("must reuse chart")), \
                patch.object(fp, "sonify_frames", return_value=b"wav") as synth:
            result = acoustics_uc.get_media_f0_hum(self.db, self.asset.id, (100, 400))
            result.unlink()
            rebuilt = acoustics_uc.get_media_f0_hum(self.db, self.asset.id, (100, 400))
        self.assertTrue(rebuilt.is_file())
        self.assertEqual(synth.call_count, 2)
        self.assertEqual(synth.call_args.args[0], self.frames)
        self.assertEqual(synth.call_args.kwargs["duration"], .8)
        self.assertEqual(self.db.query(FeatureCacheRow).count(), 1)

    def test_explicit_recording_must_belong_to_the_audio(self):
        with self.assertRaises(ApiError):
            acoustics_uc.get_f0_hum(self.db, self.audio, recording_id="other_recording")


if __name__ == "__main__":
    unittest.main()

