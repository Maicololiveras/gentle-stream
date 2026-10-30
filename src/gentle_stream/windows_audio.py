"""Opt-in WSL -> native Windows output. No synthesis, devices or downloads here."""
from __future__ import annotations

import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import threading
import time

import numpy as np


def _executable(variable: str, candidates) -> Path:
    explicit = os.environ.get(variable)
    for candidate in ([explicit] if explicit else candidates):
        if not candidate:
            continue
        path = Path(candidate).absolute()
        if not explicit and 'WindowsApps' in path.parts:
            continue  # Never launch the Microsoft Store Python alias.
        try:
            with path.open('rb') as file:
                if path.suffix.lower() == '.exe' and file.read(2) == b'MZ':
                    return path
        except OSError:
            pass
    raise OSError(f'Set {variable} to the WSL path of the installed Windows executable')


def _executables():
    if sys.platform != 'linux' or not os.environ.get('WSL_DISTRO_NAME'):
        raise OSError('Windows audio output requires WSL with Windows interop enabled')
    local = Path(__file__).resolve().parents[2] / '.voice-venv' / 'Scripts' / 'python.exe'
    python = _executable('GENTLE_STREAM_WINDOWS_PYTHON', [local, shutil.which('python.exe')])
    ffplay = _executable('GENTLE_STREAM_WINDOWS_FFPLAY', [shutil.which('ffplay.exe')])
    converted = subprocess.run(['wslpath', '-w', str(ffplay)], check=True,
                               capture_output=True, text=True, timeout=5)
    return str(python), converted.stdout.strip()


class WindowsPCMStream:
    """The Player's stream interface, paced at wall time with bounded pipe writes.

    Native Windows Python supervises FFplay and cleans it up on input EOF/failure.
    Hardware underflows cannot be observed through this transport.
    """
    audio_output = 'windows'
    reports_output_underflows = False

    def __init__(self, *, samplerate, channels, dtype, blocksize, callback, latency=None):
        if channels != 2 or dtype != 'float32' or not 100 <= samplerate <= 192000 or blocksize <= 0:
            raise ValueError('Windows output requires float32 stereo PCM and a positive block size')
        self._python, self._ffplay = _executables()
        self._rate, self._frames, self._callback = samplerate, blocksize, callback
        self._stop = threading.Event()
        self._process = None
        self._thread = None
        self.error = None

    def start(self):
        if self._thread is not None:
            return
        host = Path(__file__).with_name('_windows_output_host.py').read_text(encoding='utf-8')
        self._process = subprocess.Popen(
            [self._python, '-I', '-B', '-u', '-c', host, self._ffplay, str(self._rate)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, bufsize=0)
        try:
            os.set_blocking(self._process.stdin.fileno(), False)
            self._thread = threading.Thread(target=self._run, daemon=True, name='gentle-stream-windows')
            self._thread.start()
        except Exception:
            self._thread = None
            self._process.stdin.close()
            self._process.wait(timeout=6)
            raise

    def _write(self, data):
        fd = self._process.stdin.fileno()
        view = memoryview(data)
        while view and not self._stop.is_set():
            if self._process.poll() is not None:
                raise BrokenPipeError('Windows audio supervisor exited; see player.log')
            if not select.select([], [fd], [], .05)[1]:
                continue
            try:
                count = os.write(fd, view[:select.PIPE_BUF])
            except BlockingIOError:
                continue
            view = view[count:]

    def _run(self):
        audio = np.empty((self._frames, 2), dtype=np.float32)
        period, deadline = self._frames / self._rate, time.monotonic()
        try:
            while not self._stop.wait(max(0., deadline - time.monotonic())):
                self._callback(audio, self._frames, None, None)
                self._write(audio.astype('<f4', copy=False).tobytes())
                deadline = max(deadline + period, time.monotonic())  # Never burst to catch up.
        except Exception as error:
            self.error = str(error)
        finally:
            self._process.stdin.close()  # EOF lets the Windows supervisor clean up its native child.
            try:
                code = self._process.wait(timeout=6)
                if code:
                    self.error = self.error or f'Windows audio supervisor exited with status {code}; see player.log'
            except subprocess.TimeoutExpired:
                self.error = 'Windows audio supervisor did not exit after EOF; inspect player.log'

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=7)
            if self._thread.is_alive() or self._process.poll() is None:
                raise RuntimeError('Windows audio supervisor did not stop; inspect player.log')

    def close(self):
        self.stop()
