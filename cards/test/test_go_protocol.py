"""
Runs the Python-side protocol checks against the Go binary (`cribbage serve --json`).
Skipped when the Go toolchain is absent. For a bigger run use scripts/check_protocol.py.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_protocol  # noqa: E402

GO = shutil.which("go") or os.path.expanduser("~/sdk/go/bin/go")


@unittest.skipUnless(os.path.exists(GO), "Go toolchain not installed")
class TestGoProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["PATH"] = os.path.dirname(GO) + os.pathsep + os.environ["PATH"]
        cls.argv = check_protocol.default_command(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_games_match_python_env(self):
        problems = []
        bad = check_protocol.run(self.argv, 0, 6, 0.25, 40, 0.1, report=problems.append)
        self.assertEqual(bad, 0, problems)

    def test_seed_is_reproducible(self):
        def opening(seed):
            server = check_protocol.Server(self.argv + ["--seed", str(seed)])
            first = server.opening
            again = server.send({"command": "reset"})  # replays the seeded game
            server.close()
            return first, again

        a, a_again = opening(7)
        b, _ = opening(7)
        self.assertEqual(a, b)
        self.assertEqual(a, a_again)
        self.assertTrue(a["ok"])

    def test_exit_on_eof_without_trailing_newline(self):
        server = check_protocol.Server(self.argv)
        server.proc.stdin.write(json.dumps({"command": "observe"}).encode())  # no newline
        server.proc.stdin.close()
        self.assertTrue(json.loads(server.proc.stdout.readline())["ok"])
        self.assertEqual(server.proc.wait(timeout=10), 0)
        server.proc.stdout.close()
        server.proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
