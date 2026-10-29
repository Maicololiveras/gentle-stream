"""Device/network-free voice preparation contract."""
import io
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np

from gentle_stream import voice
from gentle_stream.style import Style

LINES = ("Sigue tu camino", "Respira con calma", "Tu luz permanece")
MOOD = "esperanza, agrega frases"


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gentle-stream-voice-")
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, XDG_CACHE_HOME=self.temp.name)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.pcm = np.full((64, 2), 0.125, dtype="<f4")

    def test_style_validates_and_round_trips_without_migration(self):
        old = Style(key="A", bpm=90).to_dict()
        self.assertNotIn("voice_lines", old)
        self.assertEqual(Style.from_dict(old), Style(key="A", bpm=90))
        style = Style.from_dict({"mood": MOOD, "voice_lines": list(LINES)})
        self.assertEqual(style.voice_lines, LINES)
        self.assertEqual(style.to_dict()["voice_lines"], list(LINES))
        self.assertEqual(Style.from_dict(style.to_dict()), style)
        for bad in [LINES[:2], (*LINES, "otra frase"), ("sola", *LINES[1:]),
                    ("uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece", *LINES[1:]),
                    ("Respira con calma. Da otro paso.", *LINES[1:]),
                    (123, *LINES[1:]), ("x" * 161 + " hola", *LINES[1:]),
                    ("hola\nmundo", *LINES[1:]), "hola mundo"]:
            with self.subTest(bad=bad):
                self.assertEqual(Style(mood=MOOD, voice_lines=bad).voice_lines, ())
        for line in ["Dos palabras", "Uno dos tres cuatro cinco seis siete ocho nueve diez once doce",
                     "No confundas velocidad con progreso: elegí tu próximo paso."]:
            self.assertEqual(Style(mood=MOOD, voice_lines=(line,) * 3).voice_lines, (line,) * 3)
        self.assertEqual(Style(voice_lines=LINES).voice_lines, ())

    def test_prepare_reuses_disk_cache_and_load_never_renders(self):
        with patch.object(voice, "_render", return_value=self.pcm.tobytes()) as render:
            clips = voice.prepare(LINES)
            self.assertEqual(render.call_count, 3)
            for clip in clips:
                np.testing.assert_array_equal(clip, self.pcm)
                self.assertFalse(clip.flags.writeable)
            render.reset_mock()
            for cached in [voice.prepare(LINES), voice.load(LINES)]:
                for clip in cached:
                    np.testing.assert_array_equal(clip, self.pcm)
            render.assert_not_called()
            voice.prepare(LINES, sr=22050)
            self.assertEqual(render.call_count, 3)
            for setting, value in [("VOICE", "other-voice"), ("RATE", "+0%")]:
                render.reset_mock()
                with patch.object(voice, setting, value):
                    voice.prepare(LINES)
                self.assertEqual(render.call_count, 3)
        self.assertTrue(list((Path(self.temp.name) / "gentle-stream" / "voice").glob("*.f32")))

    def test_rejects_bad_pcm_without_authoritative_cache(self):
        invalid = [b"", b"bad", np.array([[np.nan, 0]], dtype="<f4").tobytes(),
                   np.array([[0, np.inf]], dtype="<f4").tobytes(),
                   np.array([[1.01, 0]], dtype="<f4").tobytes(),
                   np.zeros((44100 * 8 + 1, 2), dtype="<f4").tobytes()]
        for raw in invalid:
            with self.subTest(size=len(raw)), patch.object(voice, "_render", return_value=raw):
                with self.assertRaises(voice.VoiceError):
                    voice.prepare(LINES)
                self.assertEqual(list(Path(self.temp.name).rglob("*.f32")), [])
        with patch.object(voice, "_render", side_effect=voice.VoiceError("failed")):
            with self.assertRaises(voice.VoiceError):
                voice.prepare(LINES)
        with patch.object(voice, "_render") as render:
            with self.assertRaises(voice.VoiceError):
                voice.load(LINES)
            render.assert_not_called()

    def test_corrupt_cache_rejected_by_load_and_repaired_by_prepare(self):
        with patch.object(voice, "_render", return_value=self.pcm.tobytes()) as render:
            voice.prepare(LINES)
            for path in Path(self.temp.name).rglob("*.f32"):
                path.write_bytes(b"broken")
            with self.assertRaises(voice.VoiceError):
                voice.load(LINES)
            render.reset_mock()
            voice.prepare(LINES)
            self.assertEqual(render.call_count, 3)

    def test_exact_duration_limit_and_atomic_write_failure(self):
        raw = np.zeros((8000 * 8, 2), dtype="<f4").tobytes()
        with patch.object(voice, "_render", return_value=raw):
            clips = voice.prepare(LINES, sr=8000)
        self.assertEqual([clip.shape for clip in clips], [(64000, 2)] * 3)
        with patch.object(voice, "_render", return_value=self.pcm.tobytes()), \
                patch("os.replace", side_effect=OSError("fake write failure")):
            with self.assertRaises(voice.VoiceError):
                voice.prepare(LINES, sr=22050)
        with patch.object(voice, "_render") as render:
            with self.assertRaises(voice.VoiceError):
                voice.load(LINES, sr=22050)
            render.assert_not_called()
        self.assertEqual(list(Path(self.temp.name).rglob("*.tmp")), [])

    def test_empty_and_invalid_requests_do_not_render(self):
        with patch.object(voice, "_render") as render:
            self.assertEqual(voice.prepare(()), ())
            self.assertEqual(voice.load(()), ())
            for lines, sr in [(LINES[:1], 44100), (LINES, 0), (LINES, 44100.0)]:
                with self.assertRaises(voice.VoiceError):
                    voice.prepare(lines, sr=sr)
            render.assert_not_called()
        self.assertEqual(voice.CUE_POSITIONS, (0.0, 0.5, 1.0))

    def test_preparation_adapter_call_is_argv_safe_and_failure_is_clean(self):
        result = subprocess.CompletedProcess([], 0, self.pcm.tobytes(), b"")
        with patch("subprocess.run", return_value=result) as run:
            voice.prepare(LINES)
        self.assertEqual(run.call_count, 3)
        for call, text in zip(run.call_args_list, LINES):
            self.assertEqual(call.args[0][-2:], [text, "44100"])
            self.assertTrue(call.args[0][-3].endswith("scripts/forge-voice-windows"))
            self.assertNotIn("shell", call.kwargs)
        # A distinct rate avoids the already-prepared entries.
        for outcome in [subprocess.CompletedProcess([], 1, b"", b"private failure"),
                        subprocess.TimeoutExpired("fake", 60)]:
            with self.subTest(outcome=type(outcome).__name__):
                kwargs = {"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome}
                with patch("subprocess.run", **kwargs):
                    with self.assertRaises(voice.VoiceError):
                        voice.prepare(LINES, sr=22050)
                with self.assertRaises(voice.VoiceError):
                    voice.load(LINES, sr=22050)

    def test_adapter_preserves_argv_and_only_pipes_audio(self):
        adapter = Path(__file__).resolve().parents[1] / "scripts" / "forge-voice-windows"
        ns = runpy.run_path(str(adapter))
        text = 'hola "mundo"; $(nada) & café'
        results = [subprocess.CompletedProcess([], 0, b"mp3", b""),
                   subprocess.CompletedProcess([], 0, self.pcm.tobytes(), b"")]
        with patch("subprocess.run", side_effect=results) as run:
            raw = ns["render"](text, 44100)
        self.assertEqual(raw, self.pcm.tobytes())
        synth, decode = run.call_args_list
        self.assertEqual(voice.VOICE, "es-CO-GonzaloNeural")
        self.assertEqual(voice.RATE, "-10%")
        self.assertEqual(synth.args[0][-3:], [text, voice.VOICE, voice.RATE])
        self.assertEqual(synth.args[0][0], str(adapter.parents[1] / ".voice-venv" / "Scripts" / "python.exe"))
        self.assertNotIn("shell", synth.kwargs)
        self.assertEqual(decode.kwargs["input"], b"mp3")
        self.assertIn("pipe:0", decode.args[0])
        self.assertIn("pipe:1", decode.args[0])
        self.assertIn("f32le", decode.args[0])
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("fake", 25)):
            with self.assertRaises(RuntimeError):
                ns["render"](text, 44100)
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "fake", stderr=b"private")):
            with self.assertRaises(RuntimeError):
                ns["render"](text, 44100)

    def test_adapter_main_emits_pcm_only_or_clean_error(self):
        adapter = Path(__file__).resolve().parents[1] / "scripts" / "forge-voice-windows"
        main = runpy.run_path(str(adapter))["main"]
        for fail in [False, True]:
            out, err = io.BytesIO(), io.StringIO()
            def fake_render(text, sr):
                self.assertEqual((text, sr), ("Sigue tu camino", 44100))
                if fail:
                    raise RuntimeError("voice unavailable")
                return self.pcm.tobytes()
            with patch.dict(main.__globals__, render=fake_render), \
                    patch("sys.stdout", SimpleNamespace(buffer=out)), patch("sys.stderr", err):
                code = main(["Sigue tu camino"])
            self.assertEqual(code, int(fail))
            self.assertEqual(out.getvalue(), b"" if fail else self.pcm.tobytes())
            self.assertEqual(err.getvalue(), "forge-voice-windows: voice unavailable\n" if fail else "")


if __name__ == "__main__":
    unittest.main()
