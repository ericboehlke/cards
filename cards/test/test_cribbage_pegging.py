"""
Test the scoring of the pegging phase of cribbage.
"""

import unittest
from cards.cribbage.pegging import CardsInPlay, PeggingScore
from cards.cribbage.players import Player
from cards.cards.card_shortcuts import *  # pylint: disable=wildcard-import, unused-wildcard-import


class TestPegging(unittest.TestCase):
    """Test the pegging phase of cribbage."""

    def assertZeroScore(self, score):  # pylint: disable=invalid-name
        """Assert that the score is all zeros."""
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 0, 0),
                Player.PLAYER2: PeggingScore(0, 0, 0, 0, 0, 0),
            },
        )

    def test_pegging_score_constructor(self):
        """Test that the PeggingScore constructor is in the correct order for these tests."""
        score = PeggingScore(1, 2, 3, 4, 5, 6)
        self.assertEqual(score.fifteen, 1)
        self.assertEqual(score.thirtyone, 2)
        self.assertEqual(score.go, 3)
        self.assertEqual(score.pair, 4)
        self.assertEqual(score.run, 5)
        self.assertEqual(score.total, 6)

    def test_fifteen(self):
        """Test a 15."""
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER1, KING_OF_HEARTS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, FIVE_OF_HEARTS)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 0, 0),
                Player.PLAYER2: PeggingScore(2, 0, 0, 0, 0, 2),
            },
        )

    def test_pair(self):
        """Test a pair."""
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER1, KING_OF_HEARTS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, KING_OF_DIAMONDS)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 0, 0),
                Player.PLAYER2: PeggingScore(0, 0, 0, 2, 0, 2),
            },
        )

    def test_double_pair_royal(self):
        """Test a double pair royal."""
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER1, SIX_OF_HEARTS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, SIX_OF_DIAMONDS)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 0, 0),
                Player.PLAYER2: PeggingScore(0, 0, 0, 2, 0, 2),
            },
        )
        score = cards_in_play.play(Player.PLAYER1, SIX_OF_HEARTS)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 6, 0, 6),
                Player.PLAYER2: PeggingScore(0, 0, 0, 0, 0, 0),
            },
        )
        score = cards_in_play.play(Player.PLAYER2, SIX_OF_DIAMONDS)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 0, 0),
                Player.PLAYER2: PeggingScore(0, 0, 0, 12, 0, 12),
            },
        )

    def test_thirtyone(self):
        """Test a 31."""
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER1, KING_OF_HEARTS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, TEN_OF_DIAMONDS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER1, KING_OF_SPADES)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, ACE_OF_DIAMONDS)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 0, 0),
                Player.PLAYER2: PeggingScore(0, 2, 0, 0, 0, 2),
            },
        )

    def test_run(self):
        """Test runs"""
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER1, THREE_OF_HEARTS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, FOUR_OF_DIAMONDS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER1, FIVE_OF_SPADES)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 3, 3),
                Player.PLAYER2: PeggingScore(0, 0, 0, 0, 0, 0),
            },
        )
        score = cards_in_play.play(Player.PLAYER2, TWO_OF_SPADES)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 0, 0),
                Player.PLAYER2: PeggingScore(0, 0, 0, 0, 4, 4),
            },
        )

    def test_out_of_order_run(self):
        """Test run that is out of order but still valid."""
        self.maxDiff = None
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER1, THREE_OF_HEARTS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, FIVE_OF_SPADES)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER1, FOUR_OF_DIAMONDS)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 3, 3),
                Player.PLAYER2: PeggingScore(0, 0, 0, 0, 0, 0),
            },
        )
        score = cards_in_play.play(Player.PLAYER2, TWO_OF_SPADES)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 0, 0),
                Player.PLAYER2: PeggingScore(0, 0, 0, 0, 4, 4),
            },
        )

    def test_no_run_not_consecutive(self):
        """Test runs must be consecutive."""
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER1, THREE_OF_HEARTS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, FIVE_OF_SPADES)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER1, TWO_OF_SPADES)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, FOUR_OF_DIAMONDS)
        self.assertZeroScore(score)

    def test_triple_king_thirtyone(self):
        """Test a triple king then an ace for 31."""
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER1, KING_OF_HEARTS)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 0, 0),
                Player.PLAYER2: PeggingScore(0, 0, 0, 0, 0, 0),
            },
        )
        score = cards_in_play.play(Player.PLAYER2, KING_OF_DIAMONDS)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 0, 0),
                Player.PLAYER2: PeggingScore(0, 0, 0, 2, 0, 2),
            },
        )
        score = cards_in_play.play(Player.PLAYER1, KING_OF_SPADES)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 6, 0, 6),
                Player.PLAYER2: PeggingScore(0, 0, 0, 0, 0, 0),
            },
        )
        score = cards_in_play.play(Player.PLAYER2, ACE_OF_HEARTS)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 0, 0),
                Player.PLAYER2: PeggingScore(0, 2, 0, 0, 0, 2),
            },
        )

    def test_go(self):
        """Test a go."""
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER1, KING_OF_HEARTS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, TEN_OF_DIAMONDS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER1, KING_OF_SPADES)
        self.assertZeroScore(score)
        score = cards_in_play.go(Player.PLAYER2)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 1, 0, 0, 1),
                Player.PLAYER2: PeggingScore(0, 0, 0, 0, 0, 0),
            },
        )
        score = cards_in_play.go(Player.PLAYER1)
        self.assertZeroScore(score)

    def test_thirtyone_run(self):
        """Test a 31 that is also a run."""
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER2, TWO_OF_HEARTS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER1, NINE_OF_DIAMONDS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, JACK_OF_SPADES)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER1, TEN_OF_CLUBS)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 2, 0, 0, 3, 5),
                Player.PLAYER2: PeggingScore(0, 0, 0, 0, 0, 0),
            },
        )

    def test_thirtyone_pair(self):
        """Test a pair of tens for 31."""
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER2, TWO_OF_HEARTS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER1, NINE_OF_DIAMONDS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, TEN_OF_SPADES)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER1, TEN_OF_CLUBS)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 2, 0, 2, 0, 4),
                Player.PLAYER2: PeggingScore(0, 0, 0, 0, 0, 0),
            },
        )

    def test_value_error_over_31(self):
        """Test not able to play cards over 31."""
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER2, TWO_OF_HEARTS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER1, JACK_OF_DIAMONDS)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, TEN_OF_SPADES)
        self.assertZeroScore(score)
        with self.assertRaises(ValueError):
            score = cards_in_play.play(Player.PLAYER1, TEN_OF_CLUBS)

    def test_automatic_go_if_31(self):
        """Test that if a 31 is played, the count resets."""
        cards_in_play = CardsInPlay()
        score = cards_in_play.play(Player.PLAYER1, H8)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, S6)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER1, H9)
        self.assertZeroScore(score)
        score = cards_in_play.play(Player.PLAYER2, D8)
        self.assertEqual(
            score,
            {  #                             15 31 go p  r  t
                Player.PLAYER1: PeggingScore(0, 0, 0, 0, 0, 0),
                Player.PLAYER2: PeggingScore(0, 2, 0, 0, 0, 2),
            },
        )
        self.assertEqual(cards_in_play.count(), 0)
        score = cards_in_play.play(Player.PLAYER1, D10)
        self.assertZeroScore(score)
        self.assertEqual(cards_in_play.count(), 10)


if __name__ == "__main__":
    unittest.main()
