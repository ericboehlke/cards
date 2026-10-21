"""
A single tool for playing the cribbage games
"""

import argparse

from cards.cribbage import cribbage
from cards.cribbage import discards
from cards.cribbage import pegging
from cards.cribbage import scoring
from cards.cribbage.api import OPPONENTS
from cards.cribbage.api_cli import serve


def main():
    """Main"""

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="game")
    subparsers.add_parser("discard")
    subparsers.add_parser("pegging")
    subparsers.add_parser("score")
    api = subparsers.add_parser("api", help="JSON-lines interface for LLM agents (see docs)")
    api.add_argument("--seed", type=int, default=None)
    api.add_argument("--opponent", choices=OPPONENTS, default="greedy")
    args = parser.parse_args()

    if args.game == "api":
        return serve(seed=args.seed, opponent=args.opponent)

    print("Cribbage")
    print("Eric Boehlke, 2024")
    print()

    if args.game == "discard":
        return discards.main()
    if args.game == "pegging":
        return pegging.main()
    if args.game == "score":
        return scoring.main()
    return cribbage.main()


if __name__ == "__main__":
    main()
