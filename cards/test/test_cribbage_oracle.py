"""
Differential tests: compare the engine's cribbage scoring to a naive reference oracle.
"""

import random
import unittest

from cards.cards.card import DECK
from cards.cribbage.hand import Hand
from cards.cribbage.pegging import CardsInPlay
from cards.cribbage.players import Player
from cards.cribbage.scoring import score_hand, card_value
import oracle_cribbage as oracle


def raw(card):
    """Convert an engine card to the oracle's representation."""
    return (card.number(), card.suit().name)


class TestHandScoringAgainstOracle(unittest.TestCase):
    """Hand scoring must agree with the oracle."""

    def test_random_hands(self):
        """Random hands, crib and non-crib."""
        rng = random.Random(1)
        for i in range(20000):
            cards = rng.sample(DECK, 5)
            hand, starter = cards[:4], cards[4]
            is_crib = i % 2 == 0
            expected = oracle.hand_score([raw(c) for c in hand], raw(starter), is_crib)
            actual, _ = score_hand(Hand(list(hand), is_crib=is_crib), starter)
            self.assertEqual(actual, expected, f"{hand} + {starter} crib={is_crib}")

    def test_flushy_and_runny_hands(self):
        """Bias the sample toward suits and ranks that exercise flush and run edge cases."""
        rng = random.Random(2)
        for i in range(20000):
            suit = rng.choice(list({c.suit() for c in DECK}))
            suited = [c for c in DECK if c.suit() == suit]
            near = [c for c in DECK if c.number() in (3, 4, 5, 6)]
            pool = suited if i % 2 == 0 else near
            hand = rng.sample(pool, 4)
            starter = rng.choice([c for c in DECK if c not in hand])
            is_crib = i % 3 == 0
            expected = oracle.hand_score([raw(c) for c in hand], raw(starter), is_crib)
            actual, _ = score_hand(Hand(list(hand), is_crib=is_crib), starter)
            self.assertEqual(actual, expected, f"{hand} + {starter} crib={is_crib}")

    def test_perfect_hand(self):
        """The famous 29 hand."""
        cards = {(5, "HEARTS"), (5, "SPADES"), (5, "CLUBS"), (11, "DIAMONDS")}
        self.assertEqual(oracle.hand_score(list(cards), (5, "DIAMONDS")), 29)


class TestPeggingScoringAgainstOracle(unittest.TestCase):
    """Play scoring within one uninterrupted sequence must agree with the oracle."""

    def test_random_sequences(self):
        """Random legal sequences up to a count of 31."""
        rng = random.Random(3)
        for _ in range(5000):
            deck = rng.sample(DECK, 16)
            cip = CardsInPlay()
            sequence = []
            for card in deck:
                if sum(card_value(c) for c in [x for x in sequence] + [card]) > 31:
                    continue
                expected = oracle.peg_play_score([raw(c) for c in sequence], raw(card))
                player = Player.PLAYER1 if len(sequence) % 2 == 0 else Player.PLAYER2
                score = cip.play(player, card)[player]
                self.assertEqual(score.total, expected, f"{sequence} then {card}")
                sequence.append(card)
                if sum(card_value(c) for c in sequence) == 31:
                    break


if __name__ == "__main__":
    unittest.main()
