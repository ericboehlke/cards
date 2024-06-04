"""
A version of solitaire caled Yukon.
"""

from typing import Union, List
from collections import namedtuple

from cards.cards.card import Suit, Card, KING, ACE, shuffled, DECK
from cards.cards.card_shortcuts import card_shortcut_dict


class Foundation:
    """The foundation where the cards a built in accending order according to suit."""

    def __init__(self):
        self.foundations = {e: None for e in Suit}

    def __repr__(self) -> str:
        return "\n".join(
            [
                f"{'' if Card.SUIT_WIDTH == 2 else ' '}{suit.nickname}: {Card.display(card)}"
                for suit, card in self.foundations.items()
            ]
        )

    def can_build(self, card) -> bool:
        """Returns true if the card can be build on the foundation."""
        return Card.lower_card(card) in self.foundations.values() or card.number() == ACE

    def build(self, card) -> None:
        """Build the foundation by adding the card."""
        if not self.can_build(card):
            raise ValueError
        if card.number() == ACE:
            assert self.foundations[card.suit()] is None
            self.foundations[card.suit()] = card
        else:
            assert self.foundations[card.suit()] == Card.lower_card(card)
            self.foundations[card.suit()] = card


class Pile:
    """A pile of cards with some visible and some not."""

    def __init__(self, cards, visible=5):
        """cards is [bottom, ..., top]"""
        self.cards = cards
        self.visible = visible
        if self.visible > len(cards):
            raise ValueError

    def find(self, card):
        """
        returns index, is_visible
        """
        if card in self.cards:
            index = self.cards.index(card)
            if index < (len(self.cards) - self.visible):
                return index, False
            return index, True
        return None, False

    def __checkrep(self):
        assert self.visible <= len(
            self.cards
        ), f"visible cards: {self.visible}, total cards: {len(self.cards)}"

    def __repr__(self):
        self.__checkrep()
        cardstrs = [Card.FACEDOWN] * (len(self.cards) - self.visible) + [
            card.__repr__() for card in self.visible_cards()
        ]
        return " ".join(cardstrs)

    def is_empty(self) -> bool:
        """Returns True if the Pile is empty."""
        self.__checkrep()
        return len(self.cards) == 0

    def display_card(self, index, highlight_function=lambda _: False) -> str:
        """Return a string representation of the Pile."""
        self.__checkrep()
        if index >= len(self.cards):
            return "   "
        if index < (len(self.cards) - self.visible):
            return Card.FACEDOWN
        return Card.display(self.cards[index], highlight_function)

    def visible_cards(self) -> List[Card]:
        """Return a list of the visible cards in the Pile."""
        self.__checkrep()
        return self.cards[-self.visible :]

    def pop_cards(self, count: int) -> List[Card]:
        """Pop the specified number of cards off the Pile and return them."""
        self.__checkrep()
        if count > len(self.cards) or count > self.visible:
            raise ValueError
        popped = self.cards[len(self.cards) - count :]
        self.cards = self.cards[: len(self.cards) - count]
        self.visible = self.visible - count
        self.visible = max(self.visible, 1)
        if len(self.cards) == 0:
            self.visible = 0
        return popped

    def test_pop_cards(self, count) -> List[Card]:
        """Return the specified number of cards from the top of the Pile without removing them."""
        self.__checkrep()
        if count > len(self.cards) or count > self.visible:
            raise ValueError
        popped = self.cards[len(self.cards) - count :]
        return popped

    def can_add_cards(self, cards) -> bool:
        """Returns True if the cards can be added to the Pile."""
        self.__checkrep()
        if len(cards) == 0:
            return False
        bottom_card = cards[0]
        if len(self.cards) > 0:
            top_card = self.cards[-1]
            numbers_good = bottom_card.number() + 1 == top_card.number()
            colors_good = bottom_card.opposite_color(top_card)
            return numbers_good and colors_good
        return bottom_card.number() == KING

    def add_cards(self, cards):
        """Add the cards to the Pile."""
        self.__checkrep()
        if not self.can_add_cards(cards):
            raise ValueError
        self.cards = self.cards + cards
        self.visible += len(cards)


class Tableau:
    """
    The tableau, a collection of 7 piles of cards
    """

    def __init__(self, deck):
        # pile_sizes = [1, 5, 7, 8, 9, 10, 11]
        self.piles = [
            Pile(deck[:1], 1),
            Pile(deck[1:7], 5),
            Pile(deck[7:14], 5),
            Pile(deck[14:22], 5),
            Pile(deck[22:31], 5),
            Pile(deck[31:41], 5),
            Pile(deck[41:52], 5),
        ]

    def find(self, card):
        """
        assumes no duplicates
        returns pile, index, is_visible
        """
        res = list(
            filter(
                lambda x: (x[1] is not None),
                ((i, *pile.find(card)) for i, pile in enumerate(self.piles)),
            )
        )
        if len(res) == 1:
            return res[0]
        if len(res) == 0:
            return (None, None, False)
        raise ValueError


class Board:
    """
    The board to play Yukon.
    """

    Location = namedtuple("Location", "pile_index row_index")

    def __init__(self, deck):
        self.tableau = Tableau(deck)
        self.foundation = Foundation()

    def __repr__(self):
        return self.display()

    def show(self, *highlight_cards):
        """Print the board."""
        print(self.display(highlight_cards))

    def display(self, highlight_cards: List[Card] = []):
        """Return a string representation of the Board."""

        def highlight_function(card):
            return card in highlight_cards

        board = "          0    1    2    3    4    5    6\n"
        row = 0
        foundation = list(self.foundation.foundations.items())
        space = "" if Card.SUIT_WIDTH == 2 else " "
        for row in range(max(4, max(len(pile.cards) for pile in self.tableau.piles))):
            if row < 4:
                board += f"{space}{foundation[row][0].nickname}: {Card.display(foundation[row][1])}"
            else:
                board += "       "
            board += "  {}  {}  {}  {}  {}  {}  {}".format(
                *[pile.display_card(row, highlight_function) for pile in self.tableau.piles]
            )
            board += f" {str(row).rjust(3)}\n"
        return board

    def t(self, from_pile: Pile, to_pile: Pile, num_cards: Union[int, None] = None):
        """Move the specified number of cards from a pile to another pile."""
        if num_cards is None:
            num_cards = self.tableau.piles[from_pile].visible
        test_hand = self.tableau.piles[from_pile].test_pop_cards(num_cards)
        if self.tableau.piles[to_pile].can_add_cards(test_hand):
            hand = self.tableau.piles[from_pile].pop_cards(num_cards)
            self.tableau.piles[to_pile].add_cards(hand)
            return True
        return False

    def tableau_move(self, from_location: Location, to_location: Location):
        """Move one or more visible cards from one pile to another."""
        if isinstance(to_location, Board.Location):
            assert (
                to_location.row_index == len(self.tableau.piles[to_location.pile_index].cards) - 1
            )
            to_pile_index = to_location.pile_index
        else:
            to_pile_index = to_location
        from_pile = self.tableau.piles[from_location.pile_index]
        num_cards = len(from_pile.cards) - from_location.row_index
        return self.t(from_location.pile_index, to_pile_index, num_cards)

    def foundation_move(self, from_location: Location) -> bool:
        """Build a card from the location on the foundation."""
        assert (
            from_location.row_index == len(self.tableau.piles[from_location.pile_index].cards) - 1
        )
        return self.f(from_location.pile_index)

    def f(self, from_pile: Pile) -> bool:
        """Build a card from the pile specified on the foundation."""
        test_hand = self.tableau.piles[from_pile].test_pop_cards(1)
        if self.foundation.can_build(test_hand[0]):
            hand = self.tableau.piles[from_pile].pop_cards(1)
            self.foundation.build(hand[0])
            return True
        return False

    def build_foundations(self):
        """Build the foundations automatically as much as possible."""
        while any((self.f(i) for i, pile in enumerate(self.tableau.piles) if not pile.is_empty())):
            pass

    def find(self, card):
        """Find the card on the board."""
        pile_index, index, is_visible = self.tableau.find(card)
        if pile_index is not None and index is not None:
            if is_visible:
                print(f"{card} is in Pile {pile_index}, row {index}.")
            else:
                print(f"{card} is not visible")
        else:
            print(f"{card} is in the foundations")

    def locate(self, card):
        """Given a card, return the it's location on the board."""
        pile_index, index, is_visible = self.tableau.find(card)
        if pile_index is not None and index is not None and is_visible:
            return Board.Location(pile_index, index)
        return None

    def parse_command(self, command):
        """
        <from_card|from_pile> <to_card|to_pile|f(oundation)>
        or
        build
        """
        if command == "build":
            return self.build_foundations()

        if command == "exit":
            raise InterruptedError

        split_command = command.split()
        if len(split_command) == 2 and split_command[0] == "show":
            card_str = split_command[1]
            if card_str in card_shortcut_dict:
                card = card_shortcut_dict[card_str]
                self.show(card)
            else:
                print(f"{card_str} is not a card")
            return "No Show"

        from_str, to_str = split_command
        from_pile = None
        from_location = None
        if from_str.isnumeric():
            from_pile = int(from_str)
        elif from_str in card_shortcut_dict:
            from_card = card_shortcut_dict[from_str]
            from_location = self.locate(from_card)
            if from_location is None:
                print(f"Could not find card {from_card}")
                return False
        else:
            print(f"idk what you mean by {from_str}")

        to_pile = None
        to_location = None
        to_foundation = False
        if to_str.isnumeric():
            to_pile = int(to_str)
        elif to_str[0].lower() == "f":
            to_foundation = True
        elif to_str in card_shortcut_dict:
            to_card = card_shortcut_dict[to_str]
            to_location = self.locate(to_card)
            if to_location is None:
                print(f"Could not find card {to_card}")
                return False
        else:
            print(f"idk what you mean by {to_str}")

        if from_pile is not None and to_pile is not None:
            return self.t(from_pile, to_pile)
        if from_pile is not None and to_location is not None:
            print("Not yet implemented. Specify a 'to pile' instead.")
            raise NotImplementedError()
        if from_location is not None and to_location is not None:
            return self.tableau_move(from_location, to_location)
        if from_location is not None and to_pile is not None:
            return self.tableau_move(from_location, to_pile)
        if from_location is not None and to_foundation:
            return self.foundation_move(from_location)
        if from_pile is not None and to_foundation:
            return self.f(from_pile)
        print("Something did not work in the parsing.")
        raise ValueError()


def play():
    """Play a game of Yukon."""
    b = Board(shuffled(DECK))
    feedback = None
    while True:
        if feedback == "No Show":
            feedback = None
        else:
            b.show()
        command = input()
        try:
            feedback = b.parse_command(command)
        except InterruptedError:
            break
        except (ValueError, NotImplementedError):
            pass


if __name__ == "__main__":
    play()
