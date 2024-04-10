from yukon import *
import unittest

class TestCard(unittest.TestCase):
    def test_opposite_color(self):
        jack_of_clubs = Card(Suit.CLUBS, JACK)
        ten_of_hearts = Card(Suit.HEARTS, 10)
        self.assertTrue(jack_of_clubs.opposite_color(ten_of_hearts))
        self.assertTrue(ten_of_hearts.opposite_color(jack_of_clubs))

class TestPile(unittest.TestCase):
    def test_invalid_pile(self):
        with self.assertRaises(ValueError):
            Pile([], 5)

    def test_valid_pile_10(self):
        pile = Pile(deck[:10], 5)
        self.assertEqual(pile.cards, deck[:10])
        self.assertEqual(pile.visible, 5)

    def test_valid_pile_0(self):
        pile = Pile([], 0)
        self.assertEqual(pile.cards, [])
        self.assertEqual(pile.visible, 0)

    def test_pop_1(self):
        pile = Pile(deck[:10], 5)
        popped_cards = pile.pop_cards(1)
        self.assertEqual(len(popped_cards), 1)
        self.assertEqual(popped_cards[0], deck[9])
        self.assertEqual(pile.cards, deck[:9])
        self.assertEqual(pile.visible, 4)

    def test_pop_2(self):
        pile = Pile(deck[:10], 5)
        popped_cards = pile.pop_cards(2)
        self.assertEqual(len(popped_cards), 2)
        self.assertEqual(popped_cards[0], deck[8])
        self.assertEqual(popped_cards[1], deck[9])
        self.assertEqual(pile.cards, deck[:8])
        self.assertEqual(pile.visible, 3)

    def test_pop_5(self):
        pile = Pile(deck[:10], 5)
        popped_cards = pile.pop_cards(5)
        self.assertEqual(len(popped_cards), 5)
        self.assertEqual(popped_cards, deck[5:10])
        self.assertEqual(pile.cards, deck[:5])
        self.assertEqual(pile.visible, 1)

    def test_pop_6(self):
        pile = Pile(deck[:10], 5)
        with self.assertRaises(ValueError):
            pile.pop_cards(6)

    def test_pop_11(self):
        pile = Pile(deck[:10], 5)
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
        pile = Pile(deck[:10], 5)
        can_add = pile.can_add_cards([Card(Suit.CLUBS, 9)])
        self.assertTrue(can_add)

    def test_can_add_cards_2_happy(self):
        pile = Pile(deck[:10], 5)
        can_add = pile.can_add_cards([Card(Suit.CLUBS, 9), Card(Suit.HEARTS, JACK)])
        self.assertTrue(can_add)

    def test_can_add_cards_1_sad(self):
        pile = Pile(deck[:10], 5)
        can_add = pile.can_add_cards(deck[11:12])
        self.assertFalse(can_add)

    def test_can_add_cards_3_sad(self):
        pile = Pile(deck[:10], 5)
        can_add = pile.can_add_cards(deck[12:9:-1])
        self.assertFalse(can_add)

    def test_can_add_cards_to_empty_happy(self):
        pile = Pile([], 0)
        can_add = pile.can_add_cards(deck[12:14])
        self.assertTrue(can_add)

    def test_can_add_cards_to_empty_sad(self):
        pile = Pile([], 0)
        can_add = pile.can_add_cards(deck[:3])
        self.assertFalse(can_add)

    def test_add_cards_1_happy(self):
        pile = Pile(deck[:10], 5)
        hand = [Card(Suit.CLUBS, 9)]
        pile.add_cards(hand)
        self.assertEqual(pile.cards, deck[:10] + hand)
        self.assertEqual(pile.visible, 6)

    def test_add_cards_2_happy(self):
        pile = Pile(deck[:10], 5)
        hand = [Card(Suit.CLUBS, 9), Card(Suit.HEARTS, JACK)]
        pile.add_cards(hand) # Jack and Queen of clubs
        self.assertEqual(pile.cards, deck[:10] + hand)
        self.assertEqual(pile.visible, 7)

    def test_add_cards_1_sad(self):
        pile = Pile(deck[:10], 5)
        with self.assertRaises(ValueError):
            pile.add_cards(deck[50:51])

    def test_add_cards_1_sad_same_color(self):
        pile = Pile(deck[:10], 5)
        with self.assertRaises(ValueError):
            pile.add_cards(deck[10:11])

    def test_add_cards_3_sad(self):
        pile = Pile(deck[:10], 5)
        with self.assertRaises(ValueError):
            pile.add_cards(deck[12:9:-1])

    def test_add_cards_to_empty_happy(self):
        pile = Pile([], 0)
        pile.add_cards(deck[12:14])
        self.assertEqual(pile.cards, deck[12:14])
        self.assertEqual(pile.visible, 2)

    def test_add_cards_to_empty_sad(self):
        pile = Pile([], 0)
        with self.assertRaises(ValueError):
            can_add = pile.add_cards(deck[:3])

class TestBoard(unittest.TestCase):
    def test_stuff(self):
        pile = Pile([], 0)
        hand = [Card(Suit.HEARTS, KING), Card(Suit.HEARTS, 8)]
        can_add = pile.can_add_cards(hand)
        self.assertTrue(can_add)
        pile.add_cards(hand)