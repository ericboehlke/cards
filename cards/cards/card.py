from aenum import Enum
from termcolor import colored

KING = 13
QUEEN = 12
JACK = 11
ACE = 1

SUIT_WIDTH = 2


class Suit(Enum):
    _init_ = "value suitname nickname"
    HEARTS = 1, "hearts", colored("♥️", "red")
    DIAMONDS = 2, "diamonds", colored("♦️", "red")
    CLUBS = 3, "clubs", colored("♣️", "black")
    SPADES = 4, "spades", colored("♠️", "black")


class Card:
    SUIT_WIDTH = SUIT_WIDTH
    FACEDOWN = "xXx"

    def __init__(self, suit, number):
        self.__suit = suit
        self.__number = number
        self.__checkrep()

    def __checkrep(self):
        assert 1 <= self.__number <= 13, f"number is {self.__number}"

    def is_red(self):
        self.__checkrep()
        return self.__suit in [Suit.HEARTS, Suit.DIAMONDS]

    def suit(self):
        self.__checkrep()
        return self.__suit

    def number(self):
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
    def display(card, highlight_function=lambda _: False):
        if card is None:
            return "---"
        elif isinstance(card, Card):
            numberstr = str(card.number())
            if Card.SUIT_WIDTH == 2:
                if card.__number == ACE:
                    numberstr = "A"
                if card.__number == 10:
                    numberstr = "T"
                if card.__number == JACK:
                    numberstr = "J"
                if card.__number == QUEEN:
                    numberstr = "Q"
                if card.__number == KING:
                    numberstr = "K"
            else:
                numberstr = str(card.number()).rjust(2)
                if card.__number == ACE:
                    numberstr = " A"
                if card.__number == JACK:
                    numberstr = " J"
                if card.__number == QUEEN:
                    numberstr = " Q"
                if card.__number == KING:
                    numberstr = " K"
            suitstr = card.suit().nickname
            cardstr = numberstr + suitstr
            if card.is_red():
                if highlight_function(card):
                    return colored(cardstr, "red", "on_light_yellow")
                else:
                    return colored(cardstr, "red")
            else:
                if highlight_function(card):
                    return colored(cardstr, "black", "on_light_yellow")
                else:
                    return colored(cardstr, "black")
        else:
            raise NotImplementedError

    @staticmethod
    def lower_card(card):
        if card.number() != 1:
            return Card(card.suit(), card.number() - 1)
        else:
            return None

    def opposite_color(self, other):
        if isinstance(other, Card):
            return self.is_red() != other.is_red()
