"""Integrated PCM contract: no devices, network, models or actual TTS."""
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import io
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import numpy as np

from gentle_stream import voice
from gentle_stream.composer import FIRST_FORM, FORM
from gentle_stream.engine import Engine
from gentle_stream.style import Style

LINES = ("Sigue tu camino", "Respira con calma", "Tu luz permanece")
PLAIN = Style(bpm=140, genre="rock", vinyl=0)
SPOKEN = replace(PLAIN, mood="energia, agrega frases", voice_lines=LINES)
ERROR = "Cannot apply voice: prepared cache missing or corrupt; submit the mood with 'agrega frases' again to prepare it."


def expected_mix(music, clip, offset=0):
    indices = np.arange(offset, offset + len(music))
    fade = int(.05 * 22050)
    weight = np.clip(np.minimum(indices, len(clip) - 1 - indices) / fade, 0, 1)[:, None]
    return music.astype(float) * (1 - .88 * weight) + clip[offset:offset + len(music)] * .80 * weight


class LegacyEngine(Engine):
    """Original unvoiced rendering path, kept independent of the voice mix."""
    def render_bar(self):
        self._schedule_bar()
        n = int(round(self.bar_seconds * self.sr))
        out = self._acc[:n].copy()
        self._acc[:-n] = self._acc[n:]
        self._acc[-n:] = 0
        out = self._master(out)
        self.bar += 1
        self.samples_out += n
        return out.astype(np.float32)


class VoiceMixTests(unittest.TestCase):
    def setUp(self):
        # Nonconstant stereo clips, each longer than a bar, with distinct values.
        self.clips = tuple(np.column_stack((np.linspace(.25, .75, n),
                                           np.linspace(-.75, -.25, n))).astype(np.float32)
                           for n in (42001, 44003, 46005))
        for clip in self.clips:
            clip.flags.writeable = False
        self.before = tuple(c.tobytes() for c in self.clips)
        self.load = patch.object(voice, "load", return_value=self.clips).start()
        self.render = patch.object(voice, "_render", side_effect=AssertionError("TTS at audio time")).start()
        self.addCleanup(patch.stopall)

    def engine(self, style=PLAIN, cls=Engine):
        return cls(style, seed=123, sr=22050, samples=False)

    def test_foreground_balance_and_50ms_ramps_use_absolute_cross_bar_offsets(self):
        sr = 22050
        n = round(240 / SPOKEN.bpm * sr)
        fade = int(.05 * sr)
        # Fade-out straddles a bar boundary: neither ramp may restart there.
        length = n + fade // 2
        total = sum(bars for _, bars in FIRST_FORM) * n
        starts = (0, total // 2, total - length)
        for bed, speech in ((.5, .1), (1., 1.), (-1., -1.)):
            with self.subTest(bed=bed, speech=speech):
                clips = tuple(np.tile([0., speech], (length, 1)).astype(np.float32)
                              for _ in range(3))
                self.load.return_value = clips
                with patch.object(Engine, "_schedule_bar"), patch.object(
                        Engine, "_master", side_effect=lambda x: np.tile([bed, 0.], (len(x), 1))):
                    engine = self.engine(SPOKEN)
                    actual = np.concatenate([engine.render_bar() for _ in range(total // n + 1)])
                baseline = np.tile(np.array([bed, 0.], dtype=np.float32), (len(actual), 1))
                outside = np.ones(len(actual), dtype=bool)
                for start, clip in zip(starts, clips):
                    region = actual[start:start + length]
                    outside[start:start + length] = False
                    # Channel separation measures voice and bed gains independently.
                    np.testing.assert_allclose(region[fade:-fade],
                                               np.tile([bed * .12, speech * .80],
                                                       (length - 2 * fade, 1)), atol=6e-8, rtol=0)
                    if speech == .1:
                        ratio_db = 20 * np.log10(abs(region[fade, 1] / region[fade, 0]))
                        self.assertGreater(float(ratio_db), 2.)
                    np.testing.assert_array_equal(region[[0, -1]], baseline[[0, 0]])
                    np.testing.assert_allclose(region, expected_mix(baseline[:length], clip),
                                               atol=6e-8, rtol=0)
                    self.assertLessEqual(float(np.abs(np.diff(region, axis=0)).max()),
                                         max(abs(bed) * .88, abs(speech) * .80) / fade + 1e-7)
                np.testing.assert_array_equal(actual[outside], baseline[outside])
                self.assertTrue(np.isfinite(actual).all())
                self.assertLessEqual(float(np.abs(actual).max()), 1.)
        self.render.assert_not_called()

    def test_full_first_and_next_form_exactly_three_integrated_regions(self):
        mixed, old = self.engine(SPOKEN), self.engine(cls=LegacyEngine)
        bars = sum(n for _, n in FIRST_FORM)
        self.assertEqual(bars, 44)
        n = round(mixed.bar_seconds * mixed.sr)
        total = bars * n
        starts = (0, total // 2, total - len(self.clips[2]))
        # Rendering must use only resident PCM, even if cache disappears now.
        self.load.side_effect = AssertionError("cache read during rendering")
        count = bars + sum(n for _, n in FORM)
        actual = np.concatenate([mixed.render_bar() for _ in range(count)])
        baseline = np.concatenate([old.render_bar() for _ in range(count)])
        expected = baseline.copy()
        mask = np.zeros(len(actual), dtype=bool)
        for start, clip in zip(starts, self.clips):
            end = start + len(clip)
            expected[start:end] = expected_mix(baseline[start:end], clip).astype(np.float32)
            mask[start + 1:end - 1] = True
        np.testing.assert_allclose(actual, expected, rtol=0, atol=6e-8)
        np.testing.assert_array_equal(actual[~mask], baseline[~mask])
        changed = np.any(actual != baseline, axis=1)
        np.testing.assert_array_equal(changed, mask)
        edges = np.diff(np.r_[False, changed, False].astype(int))
        np.testing.assert_array_equal(np.flatnonzero(edges == 1), [s + 1 for s in starts])
        np.testing.assert_array_equal(np.flatnonzero(edges == -1),
                                      [s + len(c) - 1 for s, c in zip(starts, self.clips)])
        self.assertTrue(np.isfinite(actual).all())
        self.assertLessEqual(float(np.abs(actual).max()), 1)
        self.load.assert_called_once_with(LINES, sr=22050)
        self.render.assert_not_called()
        self.assertEqual(tuple(c.tobytes() for c in self.clips), self.before)

    def test_default_off_is_original_audio_without_cache_or_renderer(self):
        current, old = self.engine(), self.engine(cls=LegacyEngine)
        for _ in range(3):
            np.testing.assert_array_equal(current.render_bar(), old.render_bar())
        self.load.assert_not_called()
        self.render.assert_not_called()

    def test_next_restarts_cues_from_resident_clips_and_plain_style_clears_them(self):
        spoken, plain = self.engine(SPOKEN), self.engine()
        for _ in range(2):
            spoken.render_bar()
            plain.render_bar()
        self.load.side_effect = AssertionError("next must reuse validated resident clips")
        spoken.queue_next()
        plain.queue_next()
        a, b = spoken.render_bar(), plain.render_bar()
        self.assertEqual(spoken.piece, 2)
        np.testing.assert_allclose(a, expected_mix(b, self.clips[0]), rtol=0, atol=6e-8)
        spoken.queue_style(PLAIN)
        plain.queue_style(PLAIN)
        for _ in range(3):
            np.testing.assert_array_equal(spoken.render_bar(), plain.render_bar())
        self.render.assert_not_called()

    def test_reapplying_style_loads_once_before_queue_and_resets_cues(self):
        spoken, plain = self.engine(), self.engine()
        spoken.queue_style(SPOKEN)
        plain.queue_style(PLAIN)
        self.load.assert_called_once_with(LINES, sr=22050)
        self.load.side_effect = AssertionError("late cache access")
        a, b = spoken.render_bar(), plain.render_bar()
        np.testing.assert_allclose(a, expected_mix(b, self.clips[0]), rtol=0, atol=6e-8)

    def test_cli_help_describes_opt_in_and_preserves_existing_controls(self):
        from gentle_stream import main

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with self.assertRaises(SystemExit) as exit:
                main(["--help"])
        self.assertEqual(exit.exception.code, 0)
        self.assertEqual(err.getvalue(), "")
        for text in ("'agrega frases'", "first form", "beginning, middle, end",
                     "space    play / pause", "--model", "--mood", "ctl"):
            self.assertIn(text, out.getvalue())

    def test_daemon_returns_actionable_rejection_and_keeps_rendering(self):
        from gentle_stream.daemon import handle

        engine, old = self.engine(), self.engine()
        player = SimpleNamespace(set_style=engine.queue_style)
        with patch.object(voice, "load", side_effect=voice.VoiceError("missing")):
            reply = handle(player, {"cmd": "set_style", "style": SPOKEN.to_dict()})
        self.assertEqual(reply, {"ok": False, "error": "bad request: " + ERROR})
        np.testing.assert_array_equal(engine.render_bar(), old.render_bar())

    def test_preset_apply_reports_cache_failure_without_preparing_speech(self):
        from gentle_stream.app import StreamApp
        from gentle_stream.client import PlayerError

        for error in (ValueError(ERROR), PlayerError("bad request: " + ERROR)):
            with self.subTest(error=type(error).__name__):
                app = StreamApp(Mock(), Mock(), presets=Mock())
                app.player.set_style.side_effect = error
                app._status = Mock()
                app.push_screen = lambda picker, chosen: chosen(SimpleNamespace(style=SPOKEN, name="Voice"))
                with patch.object(voice, "prepare", side_effect=AssertionError("UI synthesis")):
                    app.action_pick_preset()
                app.player.set_style.assert_called_once_with(SPOKEN)
                message = app._status.call_args.args[0]
                self.assertIn("Could not apply style:", message)
                self.assertIn("agrega frases", message)
                self.assertNotIn("Up next", message)

    def test_missing_or_corrupt_cache_rejects_before_queue_without_changing_music(self):
        for reason in ("prepared voice cache is unavailable", "voice PCM must be finite"):
            with self.subTest(reason=reason):
                current, old = self.engine(), self.engine()
                current.queue_style(PLAIN)  # rejection must preserve a pending request too
                old.queue_style(PLAIN)
                with patch.object(voice, "load", side_effect=voice.VoiceError(reason)):
                    with self.assertRaisesRegex(ValueError, "^" + ERROR.replace(".", r"\.") + "$"):
                        current.queue_style(SPOKEN)
                    with self.assertRaises(ValueError) as error:
                        self.engine(SPOKEN)
                    self.assertEqual(str(error.exception), ERROR)
                for _ in range(2):
                    np.testing.assert_array_equal(current.render_bar(), old.render_bar())
        self.render.assert_not_called()


if __name__ == "__main__":
    unittest.main()
