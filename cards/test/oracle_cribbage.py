"""
A deliberately naive, independent reference implementation of cribbage scoring.

Nothing here is shared with cards.cribbage; cards are plain (rank, suit) tuples
where rank is 1-13 and suit is any hashable. It exists to cross-check the engine.
"""

import itertools
from typing import List, Sequence, Tuple

RawCard = Tuple[int, str]


def value(rank: int) -> int:
    """Point value of a rank when counting."""
    return min(rank, 10)


def hand_score(hand: Sequence[RawCard], starter: RawCard, is_crib: bool = False) -> int:
    """Score a four-card hand with its starter."""
    cards = list(hand) + [starter]
    total = 0
    # fifteens
    for size in range(2, 6):
        for combo in itertools.combinations(cards, size):
            if sum(value(r) for r, _ in combo) == 15:
                total += 2
    # pairs
    for a, b in itertools.combinations(cards, 2):
        if a[0] == b[0]:
            total += 2
    # runs: find the longest run length, then count every distinct combination of that length
    for length in (5, 4, 3):
        runs = [
            combo
            for combo in itertools.combinations(cards, length)
            if sorted(r for r, _ in combo) == list(range(min(r for r, _ in combo),
                                                         min(r for r, _ in combo) + length))
        ]
        if runs:
            total += length * len(runs)
            break
    # flush
    suits = [s for _, s in hand]
    if len(set(suits)) == 1:
        if starter[1] == suits[0]:
            total += 5
        elif not is_crib:
            total += 4
    # nobs
    if any(r == 11 and s == starter[1] for r, s in hand):
        total += 1
    return total


def peg_play_score(sequence: List[RawCard], new: RawCard) -> int:
    """Points for playing `new` onto the current sequence (no go / last card points)."""
    seq = list(sequence) + [new]
    total = 0
    count = sum(value(r) for r, _ in seq)
    if count == 15:
        total += 2
    if count == 31:
        total += 2
    # pairs, pair royal, double pair royal: trailing run of equal ranks
    same = 1
    while same < len(seq) and seq[-1 - same][0] == new[0]:
        same += 1
    total += {1: 0, 2: 2, 3: 6, 4: 12}[same]
    # runs: longest trailing window of >= 3 cards that is a set of consecutive ranks, any order
    for length in range(len(seq), 2, -1):
        window = sorted(r for r, _ in seq[-length:])
        if window == list(range(window[0], window[0] + length)):
            total += length
            break
    return total
