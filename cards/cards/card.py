"""
Classes for representing and using cards.
"""

import copy
import random
from aenum import Enum
from termcolor import colored

KING = 13
QUEEN = 12
JACK = 11
ACE = 1

SUIT_WIDTH = 2


class Suit(Enum):
    """The suit of a playing card."""

    _init_ = "value suitname nickname"
    HEARTS = 1, "hearts", colored("♥️", "red")
    DIAMONDS = 2, "diamonds", colored("♦️", "red")
    CLUBS = 3, "clubs", colored("♣️", "black")
    SPADES = 4, "spades", colored("♠️", "black")


class Card:
    """
    Class for representing a playing card.
    """

    SUIT_WIDTH = SUIT_WIDTH
    FACEDOWN = colored("xXx", "blue")

    def __init__(self, suit, number):
        self.__suit = suit
        self.__number = number
        self.__checkrep()

    def __checkrep(self):
        assert 1 <= self.__number <= 13, f"number is {self.__number}"

    def is_red(self):
        """Returns True if the card is red, False if black."""
        self.__checkrep()
        return self.__suit in [Suit.HEARTS, Suit.DIAMONDS]

    def suit(self):
        """Returns the suit of the card."""
        self.__checkrep()
        return self.__suit

    def number(self):
        """Returns the number of the card."""
        self.__checkrep()
        return self.__number

    # https://stackoverflow.com/questions/390250/elegant-ways-to-support-equivalence-equality-in-python-classes
    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, Card):
            return self.number() == other.number() and self.suit() == other.suit()
        return NotImplemented

    def __ne__(self, other):
        """Overrides the default implementation (unnecessary in Python 3)"""
        x = self.__eq__(other)
        if x is not NotImplemented:
            return not x
        return NotImplemented

    def __hash__(self):
        """Overrides the default implementation"""
        return hash(tuple(sorted(self.__dict__.items())))

    def __repr__(self) -> str:
        return Card.display(self)

    @staticmethod
    def number_to_string(number):
        """Converts a card number to a string for printing."""
        numberstr = str(number)
        if Card.SUIT_WIDTH == 2:
            if number == ACE:
                numberstr = "A"
            if number == 10:
                numberstr = "T"
            if number == JACK:
                numberstr = "J"
            if number == QUEEN:
                numberstr = "Q"
            if number == KING:
                numberstr = "K"
            return numberstr
        numberstr = str(number).rjust(2)
        if number == ACE:
            numberstr = " A"
        if number == JACK:
            numberstr = " J"
        if number == QUEEN:
            numberstr = " Q"
        if number == KING:
            numberstr = " K"
        return numberstr

    @staticmethod
    def display(card, highlight_function=lambda _: False):
        """Return a string representation of a card."""
        if card is None:
            return "---"
        if isinstance(card, Card):
            numberstr = Card.number_to_string(card.number())
            suitstr = card.suit().nickname
            cardstr = numberstr + suitstr
            if card.is_red():
                if highlight_function(card):
                    cardstr = colored(cardstr, "red", "on_light_yellow")
                else:
                    cardstr = colored(cardstr, "red")
            else:
                if highlight_function(card):
                    cardstr = colored(cardstr, "black", "on_light_yellow")
                else:
                    cardstr = colored(cardstr, "black")
            return cardstr
        raise NotImplementedError

    @staticmethod
    def lower_card(card):
        """Return the card with the same suit but with the number of the card reduced by 1."""
        if card.number() == 1:
            return None
        return Card(card.suit(), card.number() - 1)

    def opposite_color(self, other):
        """Return True if the cards are different colors."""
        if isinstance(other, Card):
            return self.is_red() != other.is_red()
        raise NotImplementedError


DECK = [Card(s, n) for s in Suit for n in range(1, 14)]


def rest_of_deck(cards):
    """Given a list of cards, return the rest of the deck."""
    return [c for c in DECK if c not in cards]


def shuffled(cards, rng=None):
    """Shuffle a list of cards, optionally with a seeded random.Random for reproducibility."""
    shuffled_cards = copy.deepcopy(cards)
    (rng or random).shuffle(shuffled_cards)
    return list(shuffled_cards)


_RANK_CHARS = "A23456789TJQK"
_SUIT_CHARS = {"HEARTS": "H", "DIAMONDS": "D", "CLUBS": "C", "SPADES": "S"}
_CHAR_SUITS = {char: name for name, char in _SUIT_CHARS.items()}


def card_id(card):
    """Return the stable plain-text id of a card, e.g. "5H", "TS", "AC"."""
    return _RANK_CHARS[card.number() - 1] + _SUIT_CHARS[card.suit().name]


def card_from_id(card_str):
    """Return the card for an id like "5H" ("10H" is also accepted). Raises ValueError if invalid."""
    text = str(card_str).strip().upper()
    if text.startswith("10"):
        text = "T" + text[2:]
    if len(text) != 2 or text[0] not in _RANK_CHARS or text[1] not in _CHAR_SUITS:
        raise ValueError(f"Not a card id: {card_str!r} (expected like '5H', 'TS', 'AC')")
    return Card(Suit[_CHAR_SUITS[text[1]]], _RANK_CHARS.index(text[0]) + 1)
