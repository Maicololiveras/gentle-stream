"""Prepare bounded voice PCM off the audio thread. No playback, tools or model calls.

prepare() may synthesize; load() only reads validated cache files. Both return a
trio of read-only float32 (frames, 2) arrays in phrase order, or () for no voice.
The engine must load before its callback and keep those arrays in memory.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

from .style import validate_voice_lines

VOICE = "es-CO-GonzaloNeural"
RATE = "-10%"
MAX_SECONDS = 8
# Beginning and midpoint are start-aligned; the final cue is end-aligned.
# T2 maps these fractions onto the first musical form, once, not endless repeats.
CUE_POSITIONS = (0.0, 0.5, 1.0)
ADAPTER = Path(__file__).resolve().parents[2] / "scripts" / "forge-voice-windows"


class VoiceError(RuntimeError):
    """Preparation failed, or an already-prepared clip is absent/corrupt."""


def _request(lines, sr):
    if type(sr) is not int or not 8000 <= sr <= 96000:
        raise VoiceError("voice sample rate must be an integer from 8000 to 96000")
    if isinstance(lines, (tuple, list)) and not lines:
        return ()
    valid = validate_voice_lines(lines)
    if not valid:
        raise VoiceError("voice requires exactly three single-sentence phrases of 2-12 words")
    return valid


def _path(text, sr):
    key = json.dumps([1, text, VOICE, RATE, sr], ensure_ascii=False).encode("utf-8")
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "gentle-stream" / "voice" / (hashlib.sha256(key).hexdigest() + ".f32")


def _pcm(raw, sr):
    if not raw or len(raw) % 8 or len(raw) > MAX_SECONDS * sr * 8:
        raise VoiceError("voice PCM must be nonempty stereo float32, at most 8 seconds")
    clip = np.frombuffer(raw, dtype="<f4").reshape(-1, 2)
    if not np.isfinite(clip).all() or np.any(np.abs(clip) > 1):
        raise VoiceError("voice PCM must be finite and bounded to [-1, 1]")
    clip.flags.writeable = False
    return clip


def _read(path, sr):
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_SECONDS * sr * 8 + 1)
    except OSError as e:
        raise VoiceError("prepared voice cache is unavailable") from e
    return _pcm(raw, sr)


def _render(text, sr):
    try:
        result = subprocess.run([sys.executable, "-B", str(ADAPTER), text, str(sr)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise VoiceError("Windows voice preparation failed or timed out") from e
    if result.returncode:
        raise VoiceError("Windows voice preparation failed")
    return result.stdout


def _write(path, raw):
    """Only validated complete PCM becomes authoritative; concurrent writers replace atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".voice-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def prepare(lines, sr=44100) -> tuple[np.ndarray, ...]:
    """Blocking preparation/cache reuse; call only on a non-audio worker before style delivery.

    Cache identity includes normalized text, voice, speech rate and sample rate.
    Missing or corrupt entries are re-rendered. Failure raises VoiceError, never
    authorizes a partial clip, and never starts an external player.
    """
    clips = []
    for text in _request(lines, sr):
        path = _path(text, sr)
        try:
            clip = _read(path, sr)
        except VoiceError:
            raw = _render(text, sr)
            clip = _pcm(raw, sr)
            try:
                _write(path, raw)
            except OSError as e:
                raise VoiceError("cannot save prepared voice cache") from e
        clips.append(clip)
    return tuple(clips)


def load(lines, sr=44100) -> tuple[np.ndarray, ...]:
    """Read prepared PCM only; missing/corrupt entries raise VoiceError. Never synthesizes.

    Disk I/O is still blocking: call before the audio callback, not inside it.
    """
    return tuple(_read(_path(text, sr), sr) for text in _request(lines, sr))
