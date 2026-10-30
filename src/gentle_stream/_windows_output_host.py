"""Standard-library-only Windows supervisor; stdin is already mixed stereo PCM.

Executed by native Windows Python, never by the speech renderer. The native
Popen handle owns FFplay: Linux interop signals are not used to kill it.
"""
import queue
import subprocess
import sys
import threading


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or not argv[1].isdigit() or not 100 <= int(argv[1]) <= 192000:
        print('Windows audio: expected FFplay path and sample rate', file=sys.stderr)
        return 1
    process = subprocess.Popen(
        [argv[0], '-hide_banner', '-loglevel', 'warning', '-nostats', '-nodisp', '-autoexit',
         '-window_title', 'gentle-stream-windows-audio', '-f', 'f32le', '-ar', argv[1],
         '-ch_layout', 'stereo', '-probesize', '32', '-analyzeduration', '1', '-i', 'pipe:0'],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=sys.stderr, bufsize=0)
    pending = queue.Queue(maxsize=4)
    errors = []

    def write_pcm():
        try:
            while (chunk := pending.get()) is not None:
                data = memoryview(chunk)
                while data:
                    count = process.stdin.write(data)
                    if not count:
                        raise BrokenPipeError('native output closed')
                    data = data[count:]
        except (OSError, ValueError) as error:
            errors.append(error)
        finally:
            process.stdin.close()

    writer = threading.Thread(target=write_pcm, daemon=True, name='native-audio-write')
    writer.start()
    try:
        while chunk := sys.stdin.buffer.read1(8192):
            if process.poll() is not None:
                raise BrokenPipeError('FFplay exited before input ended')
            pending.put(chunk, timeout=2)
        pending.put(None, timeout=2)
        writer.join(timeout=1)
        if writer.is_alive() or errors:
            raise OSError('native audio writer stalled or failed')
        return process.wait(timeout=1)
    except (OSError, queue.Full, subprocess.TimeoutExpired) as error:
        print(f'Windows audio: {error}', file=sys.stderr)
        return 1
    finally:
        if process.poll() is None:
            process.terminate()  # Native Windows handle, not a Linux PID or a global taskkill.
            process.wait(timeout=1)
        writer.join(timeout=1)


if __name__ == '__main__':
    sys.exit(main())
