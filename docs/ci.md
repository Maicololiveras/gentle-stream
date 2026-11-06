# Device-free CI on Linux, macOS and WSL

[Tests](../.github/workflows/tests.yml) runs the locked Python 3.13 test suite on
pull requests and pushes to `main`. It covers Linux, macOS and **Ubuntu running
inside Windows Subsystem for Linux**, not native Windows Python. This is delivery
configuration (risk item 5), not evidence that the hosted jobs have passed.

## What each job installs

| Job | Hosted runner | Setup |
| :--- | :--- | :--- |
| Linux | `ubuntu-24.04` | APT `libportaudio2`; native uv 0.11.14 |
| macOS | `macos-14` | Homebrew `portaudio`; native uv 0.11.14 |
| WSL | `windows-latest` | `setup-wsl` installs `Ubuntu-24.04`, WSL 2; APT `libportaudio2`, `python3-venv`, `ca-certificates`; Linux uv 0.11.14 in a bootstrap venv |

All three install managed Python from `.python-version` (currently `3.13`) with
`uv python install`, then run `uv sync --locked`. The default `dev` group supplies
pytest, pytest-asyncio and pyfluidsynth. `uv run --locked` refuses lockfile drift;
CI never regenerates `uv.lock`. Python patch releases and OS package revisions
can change: this is not a fully hermetic image.

PortAudio is required even with fake streams: importing `sounddevice` can load
its shared library before any fake output stream is constructed. CI checks the
Python version and imports sounddevice/reports its PortAudio version before tests.
No audio device, audio server, Gentle Shell, provider account or credentials are
required by these tests.

## Test command and exact exclusions

The README's development command remains `uv run pytest`. CI uses:

```bash
uv run --locked pytest -k 'not test_genre_renders_cleanly_deterministically_and_fast'
```

- **One function is deselected on all three platforms:**
  `tests/test_genres_contract.py::test_genre_renders_cleanly_deterministically_and_fast`,
  including all its genre/backend parametrizations. Its literal `>10×` rendering
  assertion depends on host speed; [upstream #3](https://github.com/Gentleman-Programming/gentle-stream/issues/3)
  records 4.6–6.8× on constrained WSL and a passing Docker baseline. The exact
  function-name filter avoids excluding unrelated tests with names like `fast`.
  This also loses that function's finite/bounded audio, seam and determinism
  assertions; other rendering tests still run, but are not an equivalent replacement.
  Restore the gate once upstream provides a portable performance policy. Run it
  separately on suitable hardware with:
  `uv run --locked pytest tests/test_genres_contract.py::test_genre_renders_cleanly_deterministically_and_fast`.
- **No platform-specific exclusions.** POSIX fake Windows-adapter/transport tests
  still run on Linux, macOS and WSL. They do not require the hard-coded local
  Windows installations because their dependencies are mocked or relocated.
  Unknown failures must be investigated, not silently added to a skip list.
- **Existing sampled-backend skips remain in the tests.** No FluidSynth shared
  library, FluidR3_GM soundfont, `setup-samples`, or sample download is provisioned.
  The Python pyfluidsynth binding alone does not enable sampled coverage. Tests
  that already check those prerequisites may skip; no fixed skip count is promised.
- No `continue-on-error`, blanket test-file ignore, threshold override or retries.
  Every other collection/test/setup failure fails its job, including unrelated
  regressions and other timing assertions.

This selection is the explicit difference from the full-suite request in
[upstream #2](https://github.com/Gentleman-Programming/gentle-stream/issues/2).
It does not establish a full-suite green result.

## WSL paths and isolation

The pinned setup-wsl action supplies the documented `wsl-bash {0}` shell and makes
Ubuntu 24.04 the default distribution. The test step verifies Linux, a Microsoft
kernel and Ubuntu 24.04 before proceeding. Windows-native `setup-uv` is deliberately
not used in this job: it would install a Windows binary, not Linux uv.
Ubuntu's Python creates a bootstrap venv; pip installs the official binary
`uv==0.11.14` distribution from PyPI without a downloaded shell installer.
The application itself always uses managed Python 3.13 and `uv.lock`.

The wrapper translates the Windows checkout working path. CI copies that checkout
to a fresh `/tmp/gs-ci-XXXXXX/repo` inside WSL's Linux filesystem before installing
or testing. This avoids DrvFS executable-bit, Unix-socket and permission differences.
The selected matrix platform is embedded as a fixed workflow value; Linux process
environment exports happen **inside** the script, not through Windows PATH or an
assumption that arbitrary Windows environment variables cross into WSL.

Each job creates its own system `/tmp/gs-ci-XXXXXX` scratch directory. Config,
cache, runtime socket root, managed Python and the project venv go there;
`PYTEST_ADDOPTS` puts pytest's cache there too. The existing daemon tests use their
own short `/tmp/gs-*` roots and fake audio streams with fixture cleanup. This keeps
AF_UNIX paths short on macOS as well. Runner disposal reclaims CI scratch after
the job; the workflow performs no temp deletion and uploads no artifacts.
Do not run this provisioning script on a personal machine: it is designed for
fresh, disposable hosted runners. Local runtime verification belongs to an
isolated test runner, never a live music session.

## Permissions and execution bounds

- Repository token permissions are only `contents: read`; checkout disables
  credential persistence. No secrets, custom tokens, publishing or write-back.
- Only `pull_request` and `push` to `main`; no privileged `pull_request_target`,
  self-hosted runner, environment approvals or ad-hoc downloaded scripts.
- Exactly three matrix jobs, maximum parallelism three, 30 minutes per job.
  `fail-fast: false` retains evidence from each platform; it does not forgive errors.
- Workflow concurrency cancels obsolete runs for the same PR/ref. There is no
  cross-run persistent dependency/distribution cache.
- APT/Homebrew/bootstrap installation occurs only in disposable runners. APT uses
  runner sudo (or setup-wsl's distribution administration), not an elevated
  GitHub token; application tests receive no extra repository privileges.

## Action pins and upstream documentation

Full 40-character commit references were resolved read-only through GitHub's
`repos/{owner}/{repo}/commits/{ref}` API. The major names below identify the source
ref at resolution time, not floating references used by the workflow.

| Action | Source ref | Commit |
| :--- | :--- | :--- |
| `actions/checkout` | `v4` | `11d5960a326750d5838078e36cf38b85af677262` |
| `astral-sh/setup-uv` | `v6` | `d0cc045d04ccac9d8b7881df0226f9e82c39688e` |
| `Vampire/setup-wsl` | `v6` | `887f39deb6c0976365e546926fe66f41b77d65ff` |

Sources inspected for the configuration:

- [checkout at its pin](https://github.com/actions/checkout/tree/11d5960a326750d5838078e36cf38b85af677262): read-only permissions and `persist-credentials`.
- [setup-uv at its pin](https://github.com/astral-sh/setup-uv/tree/d0cc045d04ccac9d8b7881df0226f9e82c39688e): explicit uv version, managed Python, cache disabling.
- [setup-wsl at its pin](https://github.com/Vampire/setup-wsl/tree/887f39deb6c0976365e546926fe66f41b77d65ff): Ubuntu-24.04 support, WSL version, package inputs, working directory and `wsl-bash` shell.
- [uv 0.11.14 release](https://github.com/astral-sh/uv/releases/tag/0.11.14),
  [official installation guidance](https://docs.astral.sh/uv/getting-started/installation/),
  [locked project execution](https://docs.astral.sh/uv/concepts/projects/sync/).
- [GitHub workflow syntax](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions).

Review action updates against upstream source before replacing a pin. Top-level
pins do not pin every transitive action dependency, OS package or Python download.

## What a green run would not prove

Local YAML/structure checks cannot launch or validate hosted GitHub runners.
**The initial Linux, macOS and Windows-hosted WSL runs remain unverified.** Verify
all three on the actual PR, including runner availability, WSL distribution/kernel
installation, translated working directory and locked wheel availability. An
unavailable hosted WSL environment must fail visibly, not fall back to Linux-only
or Windows-native Python under a WSL label.

Device-free tests do not prove audible output, device underflows, acoustic pause
latency, TUI rendering in every real terminal, provider access, sampled instruments,
or voice synthesis. In particular, optional Windows output requires installed
**Windows Python and Windows FFplay**, WSL interop and configured executable paths;
none is provisioned here. Linux/mock transport tests cannot establish that this
bridge works against real Windows audio. See [Windows/WSL setup](windows-wsl.md)
and [integrated voice](integrated-voice.md) for separate manual prerequisites.

### Review checklist

- Confirm all three hosted jobs appear and actually execute on their named OS.
- Read setup output and pytest's deselected/skipped counts, not only the green badge.
- Investigate every failure other than the explicitly deselected issue #3 function.
- Keep manual audio/provider/Windows interop evidence separate from CI status.
