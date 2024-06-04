"""
A single tool for playing the cribbage games
"""

import argparse

from cards.cribbage import cribbage
from cards.cribbage import discards
from cards.cribbage import pegging
from cards.cribbage import scoring


def main():
    """Main"""

    print("Cribbage")
    print("Eric Boehlke, 2024")
    print()

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="game")
    subparsers.add_parser("discard")
    subparsers.add_parser("pegging")
    subparsers.add_parser("score")
    args = parser.parse_args()

    if args.game == "discard":
        return discards.main()
    if args.game == "pegging":
        return pegging.main()
    if args.game == "score":
        return scoring.main()
    return cribbage.main()


if __name__ == "__main__":
    main()
