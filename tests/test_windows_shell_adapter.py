"""Local WSL adapter checks; fake Node never invokes Windows or a model."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ADAPTER = Path(__file__).resolve().parents[1] / "scripts" / "gentle-shell-windows"
WINDOWS_BUNDLE = r"C:\Users\maicolj\.gentle-shell-bundle"


class WindowsShellAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gentle-stream-adapter-")
        self.addCleanup(self.temp.cleanup)
        self.bundle = Path(self.temp.name) / "bundle with spaces"
        self.bundle.mkdir()
        (self.bundle / "current").write_text("4.4.0-1.2.0\n")
        self.node = self.bundle / "runtime" / "node-24.21.0" / "node.exe"
        self.node.parent.mkdir(parents=True)
        self.node.write_text(
            f"#!{sys.executable}\n"
            "import json, sys\n"
            "print(json.dumps(sys.argv[1:], ensure_ascii=False))\n"
            "sys.stderr.write('fake node stderr\\n')\n"
            "sys.exit(23)\n"
        )
        self.node.chmod(0o755)
        self.install_entrypoint("4.4.0-1.2.0")

    def install_entrypoint(self, version):
        entrypoint = self.bundle / "versions" / version / "node_modules/gentle-pi/bin/gentle-shell.mjs"
        entrypoint.parent.mkdir(parents=True)
        entrypoint.write_text("// Fake entrypoint; not executed.\n")

    def run_adapter(self, *args):
        # Relocate only the bundle for isolation. Exercise main and a real fake
        # executable in a child process, including exec's streams and exit code.
        harness = (
            "import pathlib, runpy, sys; "
            "ns = runpy.run_path(sys.argv[1]); "
            "main = ns['main']; "
            "main.__globals__['BUNDLE'] = pathlib.Path(sys.argv[2]); "
            "sys.exit(main(sys.argv[3:]))"
        )
        return subprocess.run(
            [sys.executable, "-B", "-c", harness, str(ADAPTER), str(self.bundle), *args],
            capture_output=True, text=True, timeout=10,
        )

    def assert_forwarded(self, result, version, args):
        script = WINDOWS_BUNDLE + "\\versions\\" + version + r"\node_modules\gentle-pi\bin\gentle-shell.mjs"
        self.assertEqual(result.returncode, 23)
        self.assertEqual(result.stdout, json.dumps([script, *args], ensure_ascii=False) + "\n")
        self.assertEqual(result.stderr, "fake node stderr\n")

    def test_preserves_arguments_streams_and_exit_code(self):
        args = ["--", "-p", "--mode", "json", "--model", "provider/model", "",
                'lluvia ☔\n"quotes" \\ trailing\\', "$(echo unsafe); & | %PATH% `whoami`"]
        self.assert_forwarded(self.run_adapter(*args), "4.4.0-1.2.0", args)

    def test_reads_current_on_each_invocation_and_preserves_discovery(self):
        self.install_entrypoint("next-version")
        (self.bundle / "current").write_text("next-version\r\n")
        args = ["--", "--no-mcp", "--no-skill-registry", "--list-models"]
        self.assert_forwarded(self.run_adapter(*args), "next-version", args)

    def test_rejects_invalid_version_without_executing_node(self):
        (self.bundle / "current").write_text("../escape")
        result = self.run_adapter("--version")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "gentle-shell-windows: invalid bundle version in current\n")
        self.assertEqual((self.bundle / "current").read_text(), "../escape")


if __name__ == "__main__":
    unittest.main()
