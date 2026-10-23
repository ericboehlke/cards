"""
Drives a cribbage JSON-lines server process and checks it against the Python CribbageEnv.

For each game it picks shuffled decks, plays the Python env with a mix of legal and junk actions
(reusing scripts/diff_python_go.py), then sends the same decks and actions to the server through the
protocol (`{"command": "reset", "decks": ..., "first_dealer": ...}` then one `{"action": ...}` per
line), reading one reply line per line sent, and compares every reply with the Python result
(only the human oriented error `message` is stripped). Junk protocol lines (bad JSON, non objects,
unknown commands) are mixed in and must produce the documented error codes and change nothing.

The server command defaults to the Go binary built from ./cmd/cribbage (`cribbage serve --json`).
Override it with --cmd or the CRIBBAGE_SERVE_CMD environment variable, e.g.

    CRIBBAGE_SERVE_CMD="/path/to/cribbage serve --json" uv run python scripts/check_protocol.py

    uv run python scripts/check_protocol.py --games 3000 --seed 0
"""

import argparse
import json
import os
import random
import select
import shlex
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import diff_python_go as dpg  # noqa: E402

JUNK_LINES = [
    ("not json", "bad_json"),
    ("{", "bad_json"),
    ('{"action": ', "bad_json"),
    ("[1, 2]", "bad_request"),
    ("5", "bad_request"),
    ('"action"', "bad_request"),
    ("null", "bad_request"),
    ("{}", "bad_request"),
    ('{"command": "bogus"}', "bad_request"),
    ('{"command": 5}', "bad_request"),
    ('{"action": 5}', "bad_action"),
    ('{"action": null}', "bad_action"),
    ('{"action": "play"}', "bad_action"),
    ('{"action": []}', "bad_action"),
    ('{"action": {"type": 5}}', "bad_action"),
    ('{"action": {"type": "play", "card": null}}', "bad_action"),
    ('{"action": {"type": "play", "card": 5}}', "bad_action"),
    ('{"action": {"type": "discard", "cards": "5H"}}', "bad_action"),
]


# Blank lines are ignored by the Python server: they must produce no reply at all.
BLANK_LINES = ["", "   ", "\r", " \t "]


class ProtocolError(Exception):
    """The server broke the protocol (timeout, closed stdout, unparsable or unterminated reply)."""


class Server:
    """A server subprocess speaking the protocol, one line out and one line back."""

    def __init__(self, argv, timeout=20.0):
        self.timeout = timeout
        self.buf = b""
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.opening = self.read()

    def read(self):
        """Read one reply line, failing cleanly (and killing the server) on timeout or garbage."""
        deadline = time.monotonic() + self.timeout
        fd = self.proc.stdout.fileno()
        while b"\n" not in self.buf:
            left = deadline - time.monotonic()
            if left <= 0 or not select.select([fd], [], [], left)[0]:
                self.kill()
                raise ProtocolError(f"timed out after {self.timeout}s waiting for a reply")
            chunk = os.read(fd, 65536)
            if not chunk:
                err = self.kill()
                raise ProtocolError(f"server closed stdout; stderr: {err}")
            self.buf += chunk
        line, _, self.buf = self.buf.partition(b"\n")
        try:
            return json.loads(line.decode("utf-8"))
        except ValueError as e:
            self.kill()
            raise ProtocolError(f"reply is not valid JSON ({e}): {line[:200]!r}") from e

    def write(self, message):
        text = message if isinstance(message, str) else json.dumps(message)
        try:
            self.proc.stdin.write((text + "\n").encode())
            self.proc.stdin.flush()
        except OSError as e:
            err = self.kill()
            raise ProtocolError(f"cannot write to server ({e}); stderr: {err}") from e

    def send(self, message):
        self.write(message)
        return self.read()

    def kill(self):
        self.proc.kill()
        self.proc.wait()
        err = self.proc.stderr.read().decode("utf-8", "replace")
        for f in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                f.close()
            except OSError:
                pass
        return err

    def close(self):
        """Close stdin and wait for a clean exit; returns (exit code, stderr). Extra output is a problem."""
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            self.kill()
            raise ProtocolError("server did not exit after stdin was closed")
        rest = self.buf + self.proc.stdout.read()
        err = self.proc.stderr.read().decode("utf-8", "replace")
        self.proc.stdout.close()
        self.proc.stderr.close()
        if rest.strip():
            raise ProtocolError(f"unexpected extra output: {rest[:200]!r}")
        return self.proc.returncode, err


def default_command(tmp):
    env = os.environ.get("CRIBBAGE_SERVE_CMD")
    if env:
        return shlex.split(env)
    go = dpg.find_go()
    binary = os.path.join(tmp, "cribbage")
    subprocess.run([go, "build", "-o", binary, "./cmd/cribbage"], cwd=ROOT, check=True)
    return [binary, "serve", "--json"]


def check_game(server, seed, junk, max_decks, junk_lines):
    """Replay one Python game on the server. Returns (actions, error message or None)."""
    game, py_results = dpg.play_python(seed, junk, max_decks)
    rng = random.Random(seed ^ 0x5EED)
    reply = server.send({"command": "reset", "decks": game["decks"], "first_dealer": game["first_dealer"]})
    steps = [("<reset>", reply)]
    for action in game["actions"]:
        if rng.random() < junk_lines:
            current = py_results[len(steps) - 1]
            want = {"ok": True, "error": None, "events": [], "observation": current["observation"], "done": current["done"]}
            before = server.send({"command": "observe"})
            d = dpg.first_diff(want, before)
            if d:
                return 0, f"observe: {d}"
            if rng.random() < 0.3:
                # Blank lines get no reply: the next reply read must be the observe reply.
                blank = rng.choice(BLANK_LINES)
                server.write(blank)
                r = server.send({"command": "observe"})
                d = dpg.first_diff(want, r)
                if d:
                    return 0, f"after blank line {blank!r}, expected no reply but the next reply differs: {d}"
            else:
                line, code = rng.choice(JUNK_LINES)
                r = server.send(line)
                if r["ok"] or r["error"]["code"] != code:
                    return 0, f"{line!r}: expected error {code}, got {r['error']}"
                if r["observation"] != before["observation"] or r["events"] != [] or r["done"] != before["done"]:
                    return 0, f"{line!r}: error reply changed or lost the observation"
        steps.append((action, server.send({"action": action})))
    if len(steps) != len(py_results):
        return 0, "internal: result count mismatch"
    # An observe after the last action must report the final state (including done: true).
    final = py_results[-1]
    want = {"ok": True, "error": None, "events": [], "observation": final["observation"], "done": final["done"]}
    d = dpg.first_diff(want, server.send({"command": "observe"}))
    if d:
        return 0, f"final observe: {d}"
    for i, ((action, got), want) in enumerate(zip(steps, py_results)):
        d = dpg.first_diff(dpg.strip(want), dpg.strip(got))
        if d:
            return len(game["actions"]), f"step {i} action {action!r}: {d}"
    return len(game["actions"]), None


def run(argv, seed, games, junk, max_decks, junk_lines, report=print):
    """Check `games` games on one server process; returns the number of differing games."""
    bad = actions = 0
    try:
        server = Server(argv)
    except ProtocolError as e:
        report(f"cannot start server: {e}")
        report("0 games, 1 problems")
        return 1
    try:
        for i in range(games):
            n, err = check_game(server, seed + i, junk, max_decks, junk_lines)
            actions += n
            if err:
                bad += 1
                if bad <= 10:
                    report(f"seed {seed + i}: {err}")
        code, err = server.close()
        if code != 0:
            report(f"server exited {code}: {err}")
            bad += 1
    except ProtocolError as e:
        report(f"seed {seed + i}: protocol error: {e}")
        bad += 1
    except (KeyError, TypeError) as e:
        server.kill()
        report(f"seed {seed + i}: malformed reply ({type(e).__name__}: {e})")
        bad += 1
    report(f"{games} games (seeds {seed}..{seed + games - 1}), {actions} actions, {bad} problems")
    return bad


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--junk", type=float, default=0.25, help="probability an action is junk")
    parser.add_argument("--junk-lines", type=float, default=0.1, help="probability of a junk protocol line")
    parser.add_argument("--max-decks", type=int, default=40)
    parser.add_argument("--cmd", help="server command (default: build ./cmd/cribbage, or $CRIBBAGE_SERVE_CMD)")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        argv = shlex.split(args.cmd) if args.cmd else default_command(tmp)
        bad = run(argv, args.seed, args.games, args.junk, args.max_decks, args.junk_lines)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
