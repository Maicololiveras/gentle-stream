"""One mood model call, explicit voice permission, preparation before return."""
import json
import unittest
from unittest.mock import patch

from gentle_stream.bridge import (GentleShell, InterpretError, PROMPT, Usage, genre_lines,
                                  GENRE_NAMES, KEYS, MODES, CHORD_INSTRUMENTS,
                                  LEAD_INSTRUMENTS, DRUMS)
from gentle_stream.style import Style
from gentle_stream import voice

LINES = ("Sigue tu camino", "Respira con calma", "Tu luz permanece")


class VoiceBridgeTests(unittest.TestCase):
    def test_off_is_original_prompt_and_style_even_with_unsolicited_lines(self):
        current = Style(key="A", space=0.8)
        cur = current.to_dict()
        cur.pop("mood")
        expected = PROMPT.format(mood="calm", current=json.dumps(cur), keys=", ".join(KEYS),
                                 modes=", ".join(MODES), chords=", ".join(CHORD_INSTRUMENTS),
                                 leads=", ".join(LEAD_INSTRUMENTS), drums=", ".join(DRUMS),
                                 genre_names=", ".join(GENRE_NAMES), genres=genre_lines())
        with patch.object(GentleShell, "_run", return_value=json.dumps({"name": "Calm", "voice_lines": LINES})) as run, \
                patch.object(voice, "prepare") as prepare:
            style, usage = GentleShell().interpret_with_usage("calm", current)
        self.assertEqual(style, Style.from_dict({"name": "Calm", "mood": "calm"}, current))
        self.assertIsNone(usage)
        run.assert_called_once_with(GentleShell().command(expected))
        prepare.assert_not_called()

    def test_only_exact_case_insensitive_words_enable_voice(self):
        for mood, enabled in [("AGREGA FRASES de esperanza", True), ("calma, agrega frases!", True),
                              ("agregafrases", False), ("desagrega frases", False),
                              ("agrega frasesitas", False), ("sin voces", False)]:
            with self.subTest(mood=mood), \
                    patch.object(GentleShell, "_run", return_value=json.dumps({"voice_lines": LINES})) as run, \
                    patch.object(voice, "prepare") as prepare:
                style = GentleShell().interpret(mood, Style())
                run.assert_called_once()
                self.assertEqual(style.voice_lines, LINES if enabled else ())
                self.assertEqual(prepare.call_count, int(enabled))
                if enabled:
                    prompt = run.call_args.args[0][-1]
                    self.assertIn('"voice_lines"', prompt)
                    self.assertIn("exactly three", prompt)
                    self.assertIn("Spanish", prompt)
                    self.assertIn("at most 12 words", prompt)
                    self.assertIn("one concise sentence", prompt)
                    self.assertIn("reflective motivational idea", prompt)
                    self.assertIn("concrete action", prompt)
                    self.assertIn("calm", prompt)
                    prepare.assert_called_once_with(LINES)

    def test_new_plain_mood_clears_previous_voice_and_prompt_context(self):
        old = Style(mood="agrega frases", voice_lines=LINES)
        with patch.object(GentleShell, "_run", return_value="{}") as run, patch.object(voice, "prepare") as prepare:
            style = GentleShell().interpret("solo música", old)
        self.assertEqual(style.voice_lines, ())
        self.assertNotIn("voice_lines", run.call_args.args[0][-1])
        prepare.assert_not_called()

    def test_opted_in_requires_three_valid_lines_and_no_stale_fallback(self):
        old = Style(mood="agrega frases", voice_lines=LINES)
        for response in [{}, {"voice_lines": ["una sola"]}, {"voice_lines": ["una"] * 3}]:
            with self.subTest(response=response), \
                    patch.object(GentleShell, "_run", return_value=json.dumps(response)) as run, \
                    patch.object(voice, "prepare") as prepare:
                with self.assertRaises(InterpretError):
                    GentleShell().interpret("agrega frases nuevas", old)
                run.assert_called_once()
                prepare.assert_not_called()

    def test_preparation_failure_is_interpret_error(self):
        with patch.object(GentleShell, "_run", return_value=json.dumps({"voice_lines": LINES})), \
                patch.object(voice, "prepare", side_effect=voice.VoiceError("voice unavailable")):
            with self.assertRaisesRegex(InterpretError, "voice unavailable"):
                GentleShell().interpret("agrega frases", Style())

    def test_existing_models_command_and_jsonl_usage_preserved(self):
        with patch.object(GentleShell, "_run", return_value="provider model\nopenai example\n") as run:
            self.assertEqual(GentleShell().list_models(), ["openai/example"])
            run.assert_called_once_with(["--no-mcp", "--no-skill-registry", "--list-models"])
        event = {"type": "message_end", "message": {"role": "assistant", "content": [
            {"type": "text", "text": '{"genre":"Jazz", "bpm":90}'}],
            "usage": {"totalTokens": 42}}}
        with patch.object(GentleShell, "_run", return_value=json.dumps(event)):
            style, usage = GentleShell(model="provider/model").interpret_with_usage("club", Style(space=0.8))
        self.assertEqual((style.genre, style.bpm, style.space), ("jazz", 90, 0.8))
        self.assertEqual(usage, Usage(total=42))


if __name__ == "__main__":
    unittest.main()
