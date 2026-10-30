# Integrated background voice

Add **agrega frases** to the listener's mood to request voice. Matching is
case-insensitive with word boundaries, not inferred from the model's answer.
Without those words, musical interpretation and its prompt stay unchanged;
unsolicited voice lines are discarded and no voice renderer runs.

The existing single mood request also asks for exactly three thematic Spanish
phrases: one concise sentence each, 2–12 words and at most 160 characters,
combining a reflective motivational idea with a concrete mood-related action.
For example: “No confundas velocidad con progreso: elegí tu próximo paso.”
The validator bounds sentence count and length; thematic quality is requested
from the model, not claimed to be mechanically verified. Invalid or missing
phrases fail interpretation without a second model call. Old styles/presets remain
readable; empty voice is omitted from serialized styles, with no format migration.

## Engine integration

The engine mixes cached speech directly into its stereo audio after music mastering,
so genre distortion does not distort the words. In each phrase's interior the mix is
12% mastered music + 80% bounded voice PCM, bringing speech forward over its music bed.
Entry and exit ramp over 50 ms using absolute clip offsets, without restarting at bar
boundaries. For clip index `i`, length `L` and `F = max(1, int(0.05 * sample_rate))`,
`w = clip(min(i, L - 1 - i) / F, 0, 1)` and
`output = music * (1 - 0.88 * w) + voice * 0.80 * w`.
The gains sum to at most one for bounded inputs. First/last clip samples and all
samples outside those spans are unchanged. The same prepared Gonzalo PCM is reused;
no external player, tool, network request or synthesis runs at cue time.

The first form is 44 bars (derived from `composer.FIRST_FORM`). The first clip starts
at sample zero, the second starts halfway through that form, and the last ends exactly
at its end. Clips can cross bar boundaries. Later endless forms have no voice repeats.
`n` starts a new piece and resets these cues using resident clips; applying a plain
style clears them. A newly applied voice style reads the cache once before queuing.

Missing/corrupt cache rejects an initial engine or style request with `ValueError`:

> Cannot apply voice: prepared cache missing or corrupt; submit the mood with 'agrega frases' again to prepare it.

The daemon transports that error and the TUI displays it without changing the current
music. Applying a saved prompt never synthesizes on the main UI thread: resubmit its
mood to prepare speech on the existing interpretation worker. Validated resident clips
survive cache removal during playback, including `n`.

## Preparation API

`gentle_stream.voice` exposes:

- `prepare(lines, sr=44100) -> tuple[np.ndarray, ...]`: blocking cache lookup and,
  when necessary, synthesis/decode. Called by mood interpretation **before**
  returning an opted-in style. Raises `VoiceError` on failure.
- `load(lines, sr=44100) -> tuple[np.ndarray, ...]`: disk reads only, never
  synthesis. Missing or corrupt PCM raises `VoiceError`. Use when restoring a
  prepared style. Call before starting audio, **never inside the callback**.
- Both accept an empty tuple/list and return `()`. Nonempty input must be exactly
  three valid phrases. Output is phrase-ordered, read-only little-endian float32
  stereo arrays with shape `(frames, 2)`, finite samples in `[-1, 1]`, duration
  greater than zero and at most 8 seconds. Integer sample rates: 8000–96000 Hz.
- `CUE_POSITIONS = (0.0, 0.5, 1.0)` describes beginning/middle/end of the **first
  musical form only**. Start-align the first two clips; end-align the last so it
  finishes at the end of that form. Keep all arrays in memory and mix them into
  the engine's audio. Do not synthesize, load files, or call a tool at cue time.

`Engine` loads clips at construction or `queue_style`, before a request becomes
pending. Piece initialization builds in-memory cue spans; `render_bar` only slices
those arrays. No audio callback changes or extra threads are needed.

## Local synthesis and cache

The synthesis-only adapter can be run with Python:

```text
python3 scripts/forge-voice-windows 'Sigue tu camino' 44100
```

Its stdout is raw float32 stereo PCM, not text or a playback command. It uses
Windows Python in this project's `.voice-venv` with `edge-tts==7.3.1` and the
existing Windows FFmpeg8.1 at the local paths in that script. The isolated
environment was explicitly authorized; shared Python and Forge remain unchanged.
From Windows, the local prerequisite can be prepared with Python 3.12:

```powershell
python -m venv .voice-venv
.\.voice-venv\Scripts\python.exe -m pip install edge-tts==7.3.1
```

Do not substitute the older shared Edge TTS environment: 7.3.1 includes upstream
protocol-v2 and server-date parsing corrections. It uses argv-safe subprocess calls and in-memory MP3/PCM pipes,
never a shell, Forge tool, `forge-speak.py`, player, or PowerShell. The voice is
`es-CO-GonzaloNeural`, speech rate `-10%` for a calmer reflective reading. This
is a rate adjustment, not a new voice or a claim of emotional synthesis.
Dependencies are not installed by it.
Synthesis and decode each have a 25-second timeout; the caller allows 60 seconds.

The Ubuntu cache is `$XDG_CACHE_HOME/gentle-stream/voice` (default
`~/.cache/gentle-stream/voice`). SHA-256 names include normalized text, voice,
speech rate and sample rate. Entries are bounded raw `.f32` PCM, not pickle.
Every read validates the PCM; preparation repairs corrupt entries. Only a
complete validated clip is atomically published. A later phrase failing can
leave earlier complete clips reusable, but never an authoritative partial clip.
No credentials or model session data are stored.

Tests use temporary cache directories and fake renderers/subprocesses; they do
not perform network synthesis, model requests, device playback or Forge calls.
Deterministic tests verify the entire first and following form against original
unvoiced rendering, including cross-bar clips, cue resets, cache rejection and bounded
output. Real Windows synthesis and audible mixing remain parent-owned verification.
