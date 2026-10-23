"""
Differential test: the Python CribbageEnv against the Go Env (cmd/diffdriver).

For each game this script picks shuffled decks (seeded), plays the Python env with a mix of legal
and junk actions, and records every action and result. The same decks and actions are replayed on
the Go env and every result is compared field by field, with only the human oriented error
`message` field stripped (error `code`s are compared).

    uv run python scripts/diff_python_go.py --seed 0 --games 2000
    uv run python scripts/diff_python_go.py --seed 0 --games 200 --junk 0.4 --keep out.json

Needs the Go toolchain (PATH or ~/sdk/go/bin). Exits 1 if any game differs.
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cards.cribbage.api import CribbageEnv  # noqa: E402

RANKS = "A23456789TJQK"
ALL_IDS = [r + s for s in "HDCS" for r in RANKS]
# Spellings that stress card id parsing. Python accepts case and whitespace variations and "10H".
ODD_IDS = ["ah", " AH ", "10H", "10h", "1H", "0H", "TS", "tS", "A", "", "ZZ", "AHH", "5X", "H5", "5", "KS "]


def make_decks(rng, n):
    decks = []
    for _ in range(n):
        d = list(ALL_IDS)
        rng.shuffle(d)
        decks.append(d)
    return decks


def junk_action(rng, obs):
    """A mostly invalid action, as a JSON object (only shapes both sides can represent)."""
    def pick():
        return rng.choice(ODD_IDS if rng.random() < 0.4 else ALL_IDS)

    choices = [
        lambda: {"type": "bogus"},
        lambda: {},
        lambda: {"type": "play"},
        lambda: {"type": "discard"},
        lambda: {"type": "play", "card": pick()},
        lambda: {"type": "play", "cards": [pick(), pick()]},
        lambda: {"type": "play", "cards": []},
        lambda: {"type": "play", "card": pick(), "cards": [pick()]},
        lambda: {"type": "discard", "cards": [pick()]},
        lambda: {"type": "discard", "cards": [pick(), pick()]},
        lambda: {"type": "discard", "cards": [pick(), pick(), pick()]},
        lambda: {"type": "discard", "cards": []},
        lambda: {"type": "PLAY", "card": pick()},
        lambda: {"type": "play", "card": ""},
    ]
    hand = obs["your_hand"]
    if hand:  # cards actually held: wrong phase, over 31, wrong card count
        choices += [
            lambda: {"type": "play", "card": rng.choice(hand)},
            lambda: {"type": "discard", "cards": rng.sample(hand, min(2, len(hand)))},
            lambda: {"type": "play", "card": rng.choice(hand)},
        ]
    legal = obs["legal_actions"]
    if legal:
        a = rng.choice(legal)
        ids = a.get("cards") or [a["card"]]
        choices += [
            lambda: {"type": "discard" if a["type"] == "play" else "play", "cards": ids * 2},
            lambda: {"type": a["type"], "cards": list(reversed(ids))},
            lambda: {"type": a["type"], "cards": [i.lower() for i in ids]},
            lambda: {"type": "play", "cards": ids[:1]},
        ]
    return rng.choice(choices)()


def strip(v):
    if isinstance(v, dict):
        return {k: strip(x) for k, x in v.items() if k not in ("message",)}
    if isinstance(v, list):
        return [strip(x) for x in v]
    return v


def play_python(seed, junk, max_decks):
    rng = random.Random(seed)
    n_decks = rng.choice([1, 2, 3] + [max_decks] * 7)  # few decks exercise decks_exhausted
    decks = make_decks(rng, n_decks)
    first = rng.choice(["you", "opponent"])
    env = CribbageEnv(decks=decks, first_dealer=first)
    result = env.reset()
    results = [result]
    actions = []
    while not result["done"] and len(actions) < 2000:
        legal = result["observation"]["legal_actions"]
        if rng.random() < junk:
            action = junk_action(rng, result["observation"])
        else:
            action = rng.choice(legal)
        result = env.step(action)
        actions.append(action)
        results.append(result)
    return {"seed": seed, "first_dealer": first, "decks": decks, "actions": actions}, results


def worker(args):
    seed, junk, max_decks = args
    return play_python(seed, junk, max_decks)


def find_go():
    go = shutil.which("go") or os.path.expanduser("~/sdk/go/bin/go")
    if not os.path.exists(go):
        sys.exit("go toolchain not found")
    return go


def first_diff(a, b, path=""):
    if type(a) != type(b):
        return f"{path}: {a!r} != {b!r}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}.{k}: missing on one side ({a.get(k, '<absent>')!r} vs {b.get(k, '<absent>')!r})"
            d = first_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
    elif isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
    elif a != b:
        return f"{path}: {a!r} != {b!r}"
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0, help="first game seed")
    parser.add_argument("--games", type=int, default=2000)
    parser.add_argument("--junk", type=float, default=0.25, help="probability that an action is junk")
    parser.add_argument("--max-decks", type=int, default=40)
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--keep", help="write the games (decks, actions, Python results) to this JSON file")
    args = parser.parse_args()

    go = find_go()
    with tempfile.TemporaryDirectory() as tmp:
        binary = os.path.join(tmp, "diffdriver")
        subprocess.run([go, "build", "-o", binary, "./cmd/diffdriver"], cwd=ROOT, check=True)
        with Pool(args.jobs) as pool:
            played = pool.map(
                worker, [(args.seed + i, args.junk, args.max_decks) for i in range(args.games)], chunksize=8
            )
        games = [g for g, _ in played]
        proc = subprocess.run(
            [binary], input=json.dumps({"games": games}), capture_output=True, text=True
        )
    if proc.returncode != 0:
        sys.exit(f"go driver failed: {proc.stderr}")
    go_games = json.loads(proc.stdout)["games"]
    if not isinstance(go_games, list) or len(go_games) != len(played):
        sys.exit(f"go driver returned {go_games and len(go_games)} games, expected {len(played)}")
    if args.keep:
        with open(args.keep, "w") as f:
            json.dump([{**g, "python_results": r} for (g, r) in played], f)

    bad = 0
    steps = ok_steps = rejected = exhausted = wins = 0
    for (game, py_results), go_game in zip(played, go_games):
        steps += len(game["actions"])
        rejected += sum(1 for r in py_results if not r["ok"])
        exhausted += any(e["type"] == "decks_exhausted" for r in py_results for e in r["events"])
        wins += py_results[-1]["observation"]["winner"] is not None
        go_results = go_game["results"]
        diff = None
        if len(go_results) != len(py_results):
            diff = f"result count {len(go_results)} != {len(py_results)}"
        else:
            for i, (p, g) in enumerate(zip(py_results, go_results)):
                d = first_diff(strip(p), strip(g))
                if d:
                    action = game["actions"][i - 1] if i else "<reset>"
                    diff = f"step {i} action {action!r}: {d}"
                    break
        if diff:
            bad += 1
            if bad <= 10:
                print(f"seed {game['seed']}: {diff}")
    print(
        f"{args.games} games (seeds {args.seed}..{args.seed + args.games - 1}), {steps} actions, "
        f"{rejected} rejected, {wins} won, {exhausted} ended by decks_exhausted, {bad} differing games"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
