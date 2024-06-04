"""
Tests for the Card class.
"""

import unittest
from cards.cards.card import Card, Suit, JACK


class TestCard(unittest.TestCase):
    """Tests for the Card class."""

    def test_opposite_color(self):
        """Test the opposite color function with opposite colors."""
        jack_of_clubs = Card(Suit.CLUBS, JACK)
        ten_of_hearts = Card(Suit.HEARTS, 10)
        self.assertTrue(jack_of_clubs.opposite_color(ten_of_hearts))
        self.assertTrue(ten_of_hearts.opposite_color(jack_of_clubs))


if __name__ == "__main__":
    unittest.main()
