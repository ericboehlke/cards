"""
A JSON-lines interface to the cribbage environment for LLM agents and test harnesses.

Reads one JSON object per line on stdin and writes one JSON object per line on stdout; it prints
the opening observation first. Input lines:

    {"action": {"type": "discard", "cards": ["5H", "KS"]}}
    {"action": {"type": "play", "card": "7D"}}
    {"command": "observe"}
    {"command": "reset", "seed": 3}
"""

import json
import sys
from typing import Optional, TextIO

from cards.cribbage.api import CribbageEnv


def serve(
    seed: Optional[int] = None,
    opponent: str = "greedy",
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
) -> None:
    """Serve the environment over JSON lines until end of input."""
    env = CribbageEnv(seed=seed, opponent=opponent)

    def send(result: dict) -> None:
        stdout.write(json.dumps(result) + "\n")
        stdout.flush()

    def error(code: str, message: str) -> dict:
        return {
            "ok": False,
            "error": {"code": code, "message": message},
            "events": [],
            "observation": env.observation(),
            "done": env.done,
        }

    send(env.reset())
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as e:
            send(error("bad_json", f"Not valid JSON: {e}"))
            continue
        if not isinstance(message, dict):
            send(error("bad_request", 'Send a JSON object like {"action": {...}}'))
        elif "action" in message:
            send(env.step(message["action"]))
        elif message.get("command") == "observe":
            send({"ok": True, "error": None, "events": [], "observation": env.observation(), "done": env.done})
        elif message.get("command") == "reset":
            send(env.reset(message.get("seed")))
        else:
            send(error("bad_request", 'Send {"action": {...}}, {"command": "observe"} or {"command": "reset"}'))
