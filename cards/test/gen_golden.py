"""
Generate the language-neutral golden fixtures that pin down the Python cribbage behaviour.

    python -m cards.test.gen_golden --out testdata/golden

Writes scoring.json, pegging.json and games.json (see testdata/golden/README.md). The output is
deterministic (fixed seeds, sorted keys), so regenerating gives byte-identical files.
"""

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List

from cards.cards.card import DECK, card_from_id, card_id, rest_of_deck
from cards.cribbage.api import CribbageEnv
from cards.cribbage.hand import Hand
from cards.cribbage.discards import rank_discards
from cards.cribbage.pegging import CardsInPlay, play_ai
from cards.cribbage.players import Player
from cards.cribbage.scoring import card_value, score_hand

ALL_IDS = [card_id(c) for c in DECK]
P1, P2 = Player.PLAYER1, Player.PLAYER2
RANDOM_SCORING_CASES = 3000


def dump(data) -> str:
    """The canonical text of a fixture: sorted keys, one space indent, trailing newline."""
    return json.dumps(data, sort_keys=True, indent=1) + "\n"


def split(text: str) -> List[str]:
    return text.split()


# ---- scoring ----------------------------------------------------------------------------


def scoring_case(name: str, hand: List[str], starter: str, is_crib: bool) -> dict:
    cards = [card_from_id(c) for c in hand]
    total, parts = score_hand(Hand(cards, is_crib=is_crib), card_from_id(starter))
    return {
        "name": name,
        "hand": hand,
        "starter": starter,
        "is_crib": is_crib,
        "total": total,
        "breakdown": {
            "fifteens": parts.fifteens.total,
            "pairs": parts.pairs.total,
            "runs": parts.runs.total,
            "flush": parts.flush.total,
            "his_nobs": parts.his_nobs.total,
        },
    }


HANDCRAFTED_SCORING = [
    ("perfect 29", "5H 5S 5C JD", "5D", False),
    ("perfect 29 as crib", "5H 5S 5C JD", "5D", True),
    ("zero hand", "2H 4D 6C 8S", "KD", False),
    ("zero hand crib", "2H 4D 6C 8S", "KD", True),
    ("single run of 3", "AH 2D 3C 9S", "KD", False),
    ("single run of 5", "3H 4D 5C 6S", "7D", False),
    ("run of 4 plus fifteens", "4H 5D 6C 7S", "KD", False),
    ("double run", "3H 4D 4C 5S", "KD", False),
    ("double run of 4", "3H 4D 5C 5S", "6D", False),
    ("triple run", "3H 4D 4C 4S", "5D", False),
    ("double double run", "3H 3D 4C 4S", "5D", False),
    ("triple run on starter", "6H 7D 8C 8S", "8D", False),
    ("run not at the start", "AH KD QC JS", "TD", False),
    ("no wraparound run", "QH KD AC 2S", "9D", False),
    ("four of a kind", "7H 7D 7C 7S", "KD", False),
    ("three of a kind", "9H 9D 9C 2S", "KD", False),
    ("flush of 4 in hand", "2H 5H 9H KH", "3S", False),
    ("flush of 5 in hand", "2H 5H 9H KH", "3H", False),
    ("four suited in crib scores no flush", "2H 5H 9H KH", "3S", True),
    ("five suited in crib scores flush", "2H 5H 9H KH", "3H", True),
    ("nobs", "JH 2D 4C 8S", "KH", False),
    ("no nobs for other suit", "JH 2D 4C 8S", "KD", False),
    ("nobs with flush", "JH 2H 4H 8H", "KH", False),
    ("fifteens with face cards", "KH QD 5C 5S", "JD", False),
    ("fifteens with tens", "TH JD QC KS", "5D", False),
    ("many fifteens", "5H 5D 5C 5S", "TD", False),
    ("seven eight fifteen", "7H 8D 2C 9S", "KD", False),
    ("two three fours fives", "2H 3D 4C 5S", "AD", False),
    ("ace low fifteens", "AH AD AC AS", "KD", False),
    ("pair royal plus run", "AH AD AC 2S", "3D", False),
    ("jack pair nobs", "JH JD 4C 4S", "4H", False),
]


def scoring_fixture() -> dict:
    cases = [scoring_case(n, split(h), s, c) for n, h, s, c in HANDCRAFTED_SCORING]
    rng = random.Random(20240601)
    for i in range(RANDOM_SCORING_CASES):
        if i % 4 == 3:  # bias toward flushes
            suit = rng.choice("HDCS")
            pool = [c for c in ALL_IDS if c[1] == suit]
            hand = rng.sample(pool, 4)
            starter = rng.choice([c for c in ALL_IDS if c not in hand])
        else:
            cards = rng.sample(ALL_IDS, 5)
            hand, starter = cards[:4], cards[4]
        cases.append(scoring_case(f"random {i}", sorted(hand), starter, i % 2 == 0))
    return {"cases": cases}


# ---- pegging ----------------------------------------------------------------------------


def run_pegging(name: str, steps: List[tuple]) -> dict:
    """steps are (player, card id or "go"). Expected values come from the real CardsInPlay."""
    cip = CardsInPlay()
    out = []
    for player, what in steps:
        if what == "go":
            scores = cip.go(player)
        else:
            scores = cip.play(player, card_from_id(what))
        out.append(
            {
                "player": player.name,
                "play": what,
                "scores": {
                    p.name: {
                        "fifteen": s.fifteen,
                        "thirtyone": s.thirtyone,
                        "go": s.go,
                        "pair": s.pair,
                        "run": s.run,
                        "total": s.total,
                    }
                    for p, s in scores.items()
                },
                "count_after": cip.count(),
                "sequence_after": [card_id(p.card) for p in cip.sequence()],
            }
        )
    return {"name": name, "steps": out}


def alternate(text: str, first: Player = P1) -> List[tuple]:
    """Alternating plays from a string of card ids; "go" entries are said by the next player."""
    steps, player = [], first
    for token in split(text):
        steps.append((player, token))
        player = P2 if player == P1 else P1
    return steps


HANDCRAFTED_PEGGING = [
    ("fifteen", "KH 5D"),
    ("fifteen with ace and face", "5H TD"),
    ("thirty-one", "KH QD 5C 6S"),
    ("thirty-one then new count", "KH QD 5C 6S 4H"),
    ("pair", "7H 7D"),
    ("pair royal", "7H 7D 7C"),
    ("double pair royal", "7H 7D 7C 7S"),
    ("pair only counts trailing cards", "7H 7D 2C 7S"),
    ("pair by rank not value", "KH QD KC"),
    ("run of three", "4H 5D 6C"),
    ("run of three out of order", "5H 3D 4C"),
    ("run of four out of order", "6H 3D 5C 4S"),
    ("run of five out of order", "2H 5D 3C 6S 4H"),
    ("run needs trailing cards only", "9H AD 3C 2S 4H"),
    ("broken run is not a run", "4H 5D 7C"),
    ("run extends then pair breaks it", "4H 5D 6C 6S"),
    ("run with face cards", "JH QD KC"),
    ("no wraparound run", "QH KD AC"),
    ("fifteen and run together", "4H 5D 6C"),
    ("fifteen and pair together", "5H 5D 5C"),
    ("run of three making 15", "3H 4D 8C"),
]


def pegging_fixture() -> dict:
    cases = [run_pegging(name, alternate(text)) for name, text in HANDCRAFTED_PEGGING]
    # go scenarios: (player, card or go) written out so the go points are visible
    cases.append(
        run_pegging(
            "go: both stuck, last card scores 1",
            [(P1, "KH"), (P2, "QD"), (P1, "9C"), (P2, "go"), (P1, "go")],
        )
    )
    cases.append(
        run_pegging(
            "go: first go scores nothing, second go gives last card point",
            [(P1, "KH"), (P2, "QD"), (P1, "go"), (P2, "go")],
        )
    )
    cases.append(
        run_pegging(
            "go: both stuck at 30, no pair for 9H KD 9C",
            [(P1, "9H"), (P2, "KD"), (P1, "9C"), (P2, "go"), (P1, "go")],
        )
    )
    cases.append(
        run_pegging(
            "pair does not carry across a new count",
            [(P1, "KH"), (P2, "QD"), (P1, "QC"), (P2, "go"), (P1, "go"), (P2, "QS")],
        )
    )
    cases.append(
        run_pegging(
            "go on an empty sequence scores nothing",
            [(P1, "go")],
        )
    )
    rng = random.Random(777)
    for i in range(200):
        cases.append(run_pegging(f"random round {i}", random_round(rng)))
    return {"cases": cases}


def random_round(rng: random.Random) -> List[tuple]:
    """A legal pegging round: each player holds four random cards and plays randomly."""
    cards = rng.sample(ALL_IDS, 8)
    hands = {P1: cards[:4], P2: cards[4:]}
    cip = CardsInPlay()
    steps: List[tuple] = []
    turn = rng.choice([P1, P2])
    while hands[P1] or hands[P2]:
        playable = [c for c in hands[turn] if cip.can_play(card_from_id(c))]
        if playable:
            card = rng.choice(playable)
            hands[turn].remove(card)
            cip.play(turn, card_from_id(card))
            steps.append((turn, card))
        else:
            cip.go(turn)
            steps.append((turn, "go"))
        turn = P2 if turn == P1 else P1
    for player in (turn, P2 if turn == P1 else P1):  # the last card scores once both say go
        cip.go(player)
        steps.append((player, "go"))
    return steps


# ---- ai ---------------------------------------------------------------------------------


def ai_discard_case(name: str, hand: List[str], ai_is_dealer: bool) -> dict:
    cards = [card_from_id(c) for c in hand]
    hand_obj = Hand(cards)
    ranking = rank_discards(hand_obj, rest_of_deck(hand_obj.cards()), ai_is_dealer)
    return {
        "name": name,
        "hand": hand,
        "ai_is_dealer": ai_is_dealer,
        "chosen": [card_id(c) for c in ranking[0].discard],
        "ranking": [
            {
                "discard": [card_id(c) for c in r.discard],
                "hand_score": r.hand_score,
                "crib_score": r.crib_score,
            }
            for r in ranking
        ],
    }


def ai_play_case(name: str, hand: List[str], sequence: List[str]) -> dict:
    """`hand` is in hand order (sorted by rank, then H D C S); the sequence is the current count."""
    cip = CardsInPlay()
    player = P1
    for card in sequence:
        cip.play(player, card_from_id(card))
        player = P2 if player == P1 else P1
    chosen = play_ai(Hand([card_from_id(c) for c in hand]), cip)
    return {
        "name": name,
        "hand": hand,
        "sequence": sequence,
        "chosen": card_id(chosen) if chosen else None,
    }


def sort_ids(ids: List[str]) -> List[str]:
    return [card_id(c) for c in Hand([card_from_id(i) for i in ids]).cards()]


def ai_fixture() -> dict:
    discards = [
        ai_discard_case("tie: pairs of equal ranks", split("2H 2D 2C 2S 3H 3D"), False),
        ai_discard_case("five and tens as dealer", split("5H 5D TC JS QH KD"), True),
        ai_discard_case("five and tens as non-dealer", split("5H 5D TC JS QH KD"), False),
    ]
    rng = random.Random(4242)
    for i in range(150):
        discards.append(ai_discard_case(f"random {i}", sort_ids(rng.sample(ALL_IDS, 6)), i % 2 == 0))
    plays = [
        ai_play_case("empty table, tie goes to first card", split("2H 3D 4C 6S"), []),
        ai_play_case("makes fifteen", split("5H 7D 9C"), split("KH")),
        ai_play_case("cannot play", split("KH QD"), split("TH TD JC")),
        ai_play_case("makes a run", split("3H 6D 9C"), split("4H 5D")),
    ]
    for i in range(300):
        cards = rng.sample(ALL_IDS, 9)
        sequence = []
        total = 0
        for card in cards[:rng.randint(0, 5)]:
            value = card_value(card_from_id(card))
            if total + value > 31:
                break
            total += value
            sequence.append(card)
        hand = sort_ids(cards[5:5 + rng.randint(1, 4)])
        plays.append(ai_play_case(f"random {i}", hand, sequence))
    return {"discards": discards, "plays": plays}


# ---- games ------------------------------------------------------------------------------

MAX_STEPS = 500
MAX_DECKS = 30

ILLEGAL_PROBES = [
    {"type": "play", "card": "AH"},
    {"type": "discard", "cards": ["AH"]},
    {"type": "discard", "cards": ["ZZ", "AH"]},
    {"type": "bogus"},
]


def random_decks(seed: int) -> List[List[str]]:
    rng = random.Random(seed)
    decks = []
    for _ in range(MAX_DECKS):
        deck = list(ALL_IDS)
        rng.shuffle(deck)
        decks.append(deck)
    return decks


def play_game(name: str, seed: int, first_dealer: str, probe: bool) -> dict:
    """Play a whole game with the "first legal action" policy, recording every result."""
    decks = random_decks(seed)
    env = CribbageEnv(decks=decks, first_dealer=first_dealer, opponent="greedy")
    initial = env.reset()
    steps = []
    deals = sum(1 for e in initial["events"] if e["type"] == "deal")
    result = initial
    if probe:
        for action in ILLEGAL_PROBES:
            steps.append({"action": action, "result": env.step(action)})
    while not result["done"]:
        if len(steps) > MAX_STEPS:
            raise RuntimeError("game did not finish")
        action = result["observation"]["legal_actions"][0]
        result = env.step(action)
        deals += sum(1 for e in result["events"] if e["type"] == "deal")
        steps.append({"action": action, "result": result})
    return {
        "name": name,
        "opponent": "greedy",
        "first_dealer": first_dealer,
        "decks": decks[:deals],
        "initial": initial,
        "steps": steps,
    }


def games_fixture() -> dict:
    games = [
        play_game(f"game {i}", 1000 + i, "you" if i % 2 == 0 else "opponent", probe=(i == 0))
        for i in range(6)
    ]
    return {"games": games}


# ---- output -----------------------------------------------------------------------------


def build_all() -> Dict[str, str]:
    """Every fixture file name mapped to its exact text."""
    return {
        "scoring.json": dump(scoring_fixture()),
        "pegging.json": dump(pegging_fixture()),
        "games.json": dump(games_fixture()),
        "ai.json": dump(ai_fixture()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="testdata/golden", help="directory to write the fixtures to")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for filename, text in build_all().items():
        (out / filename).write_text(text)
        print(f"wrote {out / filename} ({len(text)} bytes)")


if __name__ == "__main__":
    main()
