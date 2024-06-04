"""
A hand of cards in cribbage.
"""

from typing import List
from cards.cards.card import Card


class Hand:
    """A hand of cards in cribbage."""

    def __init__(self, cards: List[Card], is_crib: bool = False):
        self.__cards = cards
        self.__sort()
        self.is_crib = is_crib

    def __sort(self):
        self.__cards = sorted(self.__cards, key=lambda c: (c.number(), c.suit().value))

    def __repr__(self) -> str:
        return f"Hand({self.__cards}, is_crib={self.is_crib})"

    def cards(self) -> List[Card]:
        """Return a list of the cards in the hand."""
        return self.__cards

    def display(self, show=True) -> str:
        """Return a string representation of the hand for display."""
        if show:
            return " ".join([Card.display(c) for c in self.__cards])
        return " ".join([Card.FACEDOWN for c in self.__cards])

    def discard(self, card) -> Card:
        """Discard a card from the hand and return the card."""
        if card not in self.__cards:
            raise ValueError(f"Card {card} not in hand {self}")
        del self.__cards[self.__cards.index(card)]
        return card

    def add(self, card: Card) -> None:
        """Add a card to the hand."""
        self.__cards.append(card)
        self.__sort()
