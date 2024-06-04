"""
Tests for the Yukon game.
"""

import unittest
from cards.cards.card import Card, Suit, JACK, KING, DECK
from cards.cards.card_shortcuts import ACE_OF_HEARTS
from cards.yukon.yukon import Pile


class TestPile(unittest.TestCase):
    """Test Piles"""

    def test_invalid_pile(self):
        with self.assertRaises(ValueError):
            Pile([], 5)

    def test_valid_pile_10(self):
        pile = Pile(DECK[:10], 5)
        self.assertEqual(pile.cards, DECK[:10])
        self.assertEqual(pile.visible, 5)

    def test_valid_pile_0(self):
        pile = Pile([], 0)
        self.assertEqual(pile.cards, [])
        self.assertEqual(pile.visible, 0)

    def test_pop_1(self):
        pile = Pile(DECK[:10], 5)
        popped_cards = pile.pop_cards(1)
        self.assertEqual(len(popped_cards), 1)
        self.assertEqual(popped_cards[0], DECK[9])
        self.assertEqual(pile.cards, DECK[:9])
        self.assertEqual(pile.visible, 4)

    def test_pop_2(self):
        pile = Pile(DECK[:10], 5)
        popped_cards = pile.pop_cards(2)
        self.assertEqual(len(popped_cards), 2)
        self.assertEqual(popped_cards[0], DECK[8])
        self.assertEqual(popped_cards[1], DECK[9])
        self.assertEqual(pile.cards, DECK[:8])
        self.assertEqual(pile.visible, 3)

    def test_pop_5(self):
        pile = Pile(DECK[:10], 5)
        popped_cards = pile.pop_cards(5)
        self.assertEqual(len(popped_cards), 5)
        self.assertEqual(popped_cards, DECK[5:10])
        self.assertEqual(pile.cards, DECK[:5])
        self.assertEqual(pile.visible, 1)

    def test_pop_6(self):
        pile = Pile(DECK[:10], 5)
        with self.assertRaises(ValueError):
            pile.pop_cards(6)

    def test_pop_11(self):
        pile = Pile(DECK[:10], 5)
        with self.assertRaises(ValueError):
            pile.pop_cards(11)

    def test_pop_from_empty(self):
        pile = Pile([], 0)
        with self.assertRaises(ValueError):
            pile.pop_cards(1)

    def test_pop_to_empty(self):
        pile = Pile([ACE_OF_HEARTS], 1)
        hand = pile.pop_cards(1)
        self.assertEqual(hand, [ACE_OF_HEARTS])
        self.assertEqual(pile.visible, 0)
        self.assertEqual(pile.cards, [])

    def test_can_add_cards_1_happy(self):
        pile = Pile(DECK[:10], 5)
        can_add = pile.can_add_cards([Card(Suit.CLUBS, 9)])
        self.assertTrue(can_add)

    def test_can_add_cards_2_happy(self):
        pile = Pile(DECK[:10], 5)
        can_add = pile.can_add_cards([Card(Suit.CLUBS, 9), Card(Suit.HEARTS, JACK)])
        self.assertTrue(can_add)

    def test_can_add_cards_1_sad(self):
        pile = Pile(DECK[:10], 5)
        can_add = pile.can_add_cards(DECK[11:12])
        self.assertFalse(can_add)

    def test_can_add_cards_3_sad(self):
        pile = Pile(DECK[:10], 5)
        can_add = pile.can_add_cards(DECK[12:9:-1])
        self.assertFalse(can_add)

    def test_can_add_cards_to_empty_happy(self):
        pile = Pile([], 0)
        can_add = pile.can_add_cards(DECK[12:14])
        self.assertTrue(can_add)

    def test_can_add_cards_to_empty_sad(self):
        pile = Pile([], 0)
        can_add = pile.can_add_cards(DECK[:3])
        self.assertFalse(can_add)

    def test_add_cards_1_happy(self):
        pile = Pile(DECK[:10], 5)
        hand = [Card(Suit.CLUBS, 9)]
        pile.add_cards(hand)
        self.assertEqual(pile.cards, DECK[:10] + hand)
        self.assertEqual(pile.visible, 6)

    def test_add_cards_2_happy(self):
        pile = Pile(DECK[:10], 5)
        hand = [Card(Suit.CLUBS, 9), Card(Suit.HEARTS, JACK)]
        pile.add_cards(hand)  # Jack and Queen of clubs
        self.assertEqual(pile.cards, DECK[:10] + hand)
        self.assertEqual(pile.visible, 7)

    def test_add_cards_1_sad(self):
        pile = Pile(DECK[:10], 5)
        with self.assertRaises(ValueError):
            pile.add_cards(DECK[50:51])

    def test_add_cards_1_sad_same_color(self):
        pile = Pile(DECK[:10], 5)
        with self.assertRaises(ValueError):
            pile.add_cards(DECK[10:11])

    def test_add_cards_3_sad(self):
        pile = Pile(DECK[:10], 5)
        with self.assertRaises(ValueError):
            pile.add_cards(DECK[12:9:-1])

    def test_add_cards_to_empty_happy(self):
        pile = Pile([], 0)
        pile.add_cards(DECK[12:14])
        self.assertEqual(pile.cards, DECK[12:14])
        self.assertEqual(pile.visible, 2)

    def test_add_cards_to_empty_sad(self):
        pile = Pile([], 0)
        with self.assertRaises(ValueError):
            pile.add_cards(DECK[:3])


class TestBoard(unittest.TestCase):
    """Tests for the Board."""

    def test_stuff(self):
        pile = Pile([], 0)
        hand = [Card(Suit.HEARTS, KING), Card(Suit.HEARTS, 8)]
        can_add = pile.can_add_cards(hand)
        self.assertTrue(can_add)
        pile.add_cards(hand)


if __name__ == "__main__":
    unittest.main()
