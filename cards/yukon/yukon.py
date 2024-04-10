import random
import copy
from termcolor import colored
from collections import namedtuple
from cards.cards.card import Suit, Card, KING, QUEEN, JACK, ACE


class Foundation:
    def __init__(self):
        self.foundations = {e: None for e in Suit}

    def __repr__(self) -> str:
        return "\n".join(
            [
                f"{'' if Card.SUIT_WIDTH == 2 else ' '}{suit.nickname}: {Card.display(card)}"
                for suit, card in self.foundations.items()
            ]
        )

    def can_build(self, card):
        return Card.lower_card(card) in self.foundations.values() or card.number() == ACE

    def build(self, card):
        if not self.can_build(card):
            raise ValueError
        else:
            if card.number() == ACE:
                assert self.foundations[card.suit()] is None
                self.foundations[card.suit()] = card
            else:
                assert self.foundations[card.suit()] == Card.lower_card(card)
                self.foundations[card.suit()] = card


class Pile:
    def __init__(self, cards, visible=5):
        # cards is [bottom, ..., top]
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
            else:
                return index, True
        else:
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

    def is_empty(self):
        self.__checkrep()
        return len(self.cards) == 0

    def display_card(self, index, highlight_function=lambda _: False):
        self.__checkrep()
        if index >= len(self.cards):
            return "   "
        elif index < (len(self.cards) - self.visible):
            return colored(Card.FACEDOWN, "blue")
        else:
            return Card.display(self.cards[index], highlight_function)

    def visible_cards(self):
        self.__checkrep()
        return self.cards[-self.visible :]

    def pop_cards(self, count):
        self.__checkrep()
        if count > len(self.cards) or count > self.visible:
            raise ValueError
        popped = self.cards[len(self.cards) - count :]
        self.cards = self.cards[: len(self.cards) - count]
        self.visible = self.visible - count
        if self.visible < 1:
            self.visible = 1
        if len(self.cards) == 0:
            self.visible = 0
        return popped

    def test_pop_cards(self, count):
        self.__checkrep()
        if count > len(self.cards) or count > self.visible:
            raise ValueError
        popped = self.cards[len(self.cards) - count :]
        return popped

    def can_add_cards(self, cards):
        self.__checkrep()
        if len(cards) == 0:
            return False
        bottom_card = cards[0]
        if len(self.cards) > 0:
            top_card = self.cards[-1]
            numbers_good = bottom_card.number() + 1 == top_card.number()
            colors_good = bottom_card.opposite_color(top_card)
            return numbers_good and colors_good
        else:
            return bottom_card.number() == KING

    def add_cards(self, cards):
        self.__checkrep()
        if not self.can_add_cards(cards):
            raise ValueError
        else:
            self.cards = self.cards + cards
            self.visible += len(cards)


deck = [Card(suit, number) for suit in Suit for number in range(1, 14)]

CA = ACE_OF_CLUBS = Card(Suit.CLUBS, ACE)
C2 = TWO_OF_CLUBS = Card(Suit.CLUBS, 2)
C3 = THREE_OF_CLUBS = Card(Suit.CLUBS, 3)
C4 = FOUR_OF_CLUBS = Card(Suit.CLUBS, 4)
C5 = FIVE_OF_CLUBS = Card(Suit.CLUBS, 5)
C6 = SIX_OF_CLUBS = Card(Suit.CLUBS, 6)
C7 = SEVEN_OF_CLUBS = Card(Suit.CLUBS, 7)
C8 = EIGHT_OF_CLUBS = Card(Suit.CLUBS, 8)
C9 = NINE_OF_CLUBS = Card(Suit.CLUBS, 9)
CT = C10 = TEN_OF_CLUBS = Card(Suit.CLUBS, 10)
CJ = JACK_OF_CLUBS = Card(Suit.CLUBS, JACK)
CQ = QUEEN_OF_CLUBS = Card(Suit.CLUBS, QUEEN)
CK = KING_OF_CLUBS = Card(Suit.CLUBS, KING)

DA = ACE_OF_DIAMONDS = Card(Suit.DIAMONDS, ACE)
D2 = TWO_OF_DIAMONDS = Card(Suit.DIAMONDS, 2)
D3 = THREE_OF_DIAMONDS = Card(Suit.DIAMONDS, 3)
D4 = FOUR_OF_DIAMONDS = Card(Suit.DIAMONDS, 4)
D5 = FIVE_OF_DIAMONDS = Card(Suit.DIAMONDS, 5)
D6 = SIX_OF_DIAMONDS = Card(Suit.DIAMONDS, 6)
D7 = SEVEN_OF_DIAMONDS = Card(Suit.DIAMONDS, 7)
D8 = EIGHT_OF_DIAMONDS = Card(Suit.DIAMONDS, 8)
D9 = NINE_OF_DIAMONDS = Card(Suit.DIAMONDS, 9)
DT = D10 = TEN_OF_DIAMONDS = Card(Suit.DIAMONDS, 10)
DJ = JACK_OF_DIAMONDS = Card(Suit.DIAMONDS, JACK)
DQ = QUEEN_OF_DIAMONDS = Card(Suit.DIAMONDS, QUEEN)
DK = KING_OF_DIAMONDS = Card(Suit.DIAMONDS, KING)

SA = ACE_OF_SPADES = Card(Suit.SPADES, ACE)
S2 = TWO_OF_SPADES = Card(Suit.SPADES, 2)
S3 = THREE_OF_SPADES = Card(Suit.SPADES, 3)
S4 = FOUR_OF_SPADES = Card(Suit.SPADES, 4)
S5 = FIVE_OF_SPADES = Card(Suit.SPADES, 5)
S6 = SIX_OF_SPADES = Card(Suit.SPADES, 6)
S7 = SEVEN_OF_SPADES = Card(Suit.SPADES, 7)
S8 = EIGHT_OF_SPADES = Card(Suit.SPADES, 8)
S9 = NINE_OF_SPADES = Card(Suit.SPADES, 9)
ST = S10 = TEN_OF_SPADES = Card(Suit.SPADES, 10)
SJ = JACK_OF_SPADES = Card(Suit.SPADES, JACK)
SQ = QUEEN_OF_SPADES = Card(Suit.SPADES, QUEEN)
SK = KING_OF_SPADES = Card(Suit.SPADES, KING)

HA = ACE_OF_HEARTS = Card(Suit.HEARTS, ACE)
H2 = TWO_OF_HEARTS = Card(Suit.HEARTS, 2)
H3 = THREE_OF_HEARTS = Card(Suit.HEARTS, 3)
H4 = FOUR_OF_HEARTS = Card(Suit.HEARTS, 4)
H5 = FIVE_OF_HEARTS = Card(Suit.HEARTS, 5)
H6 = SIX_OF_HEARTS = Card(Suit.HEARTS, 6)
H7 = SEVEN_OF_HEARTS = Card(Suit.HEARTS, 7)
H8 = EIGHT_OF_HEARTS = Card(Suit.HEARTS, 8)
H9 = NINE_OF_HEARTS = Card(Suit.HEARTS, 9)
HT = H10 = TEN_OF_HEARTS = Card(Suit.HEARTS, 10)
HJ = JACK_OF_HEARTS = Card(Suit.HEARTS, JACK)
HQ = QUEEN_OF_HEARTS = Card(Suit.HEARTS, QUEEN)
HK = KING_OF_HEARTS = Card(Suit.HEARTS, KING)

card_shortcut_dict = {
    "10C": C10,
    "10D": D10,
    "10S": S10,
    "10H": H10,
    "AC": CA,
    "2C": C2,
    "3C": C3,
    "4C": C4,
    "5C": C5,
    "6C": C6,
    "7C": C7,
    "8C": C8,
    "9C": C9,
    "TC": CT,
    "JC": CJ,
    "QC": CQ,
    "KC": CK,
    "AD": DA,
    "2D": D2,
    "3D": D3,
    "4D": D4,
    "5D": D5,
    "6D": D6,
    "7D": D7,
    "8D": D8,
    "9D": D9,
    "TD": DT,
    "JD": DJ,
    "QD": DQ,
    "KD": DK,
    "AS": SA,
    "2S": S2,
    "3S": S3,
    "4S": S4,
    "5S": S5,
    "6S": S6,
    "7S": S7,
    "8S": S8,
    "9S": S9,
    "TS": ST,
    "JS": SJ,
    "QS": SQ,
    "KS": SK,
    "AH": HA,
    "2H": H2,
    "3H": H3,
    "4H": H4,
    "5H": H5,
    "6H": H6,
    "7H": H7,
    "8H": H8,
    "9H": H9,
    "TH": HT,
    "JH": HJ,
    "QH": HQ,
    "KH": HK,
}


def shuffled(cards):
    shuffled_cards = copy.deepcopy(cards)
    random.shuffle(shuffled_cards)
    return list(shuffled_cards)


class Tableau:
    def __init__(self, deck):
        pile_sizes = [1, 5, 7, 8, 9, 10, 11]
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
        elif len(res) == 0:
            return (None, None, False)
        else:
            raise ValueError


class Board:
    Location = namedtuple("Location", "pile_index row_index")

    def __init__(self, deck):
        self.tableau = Tableau(deck)
        self.foundation = Foundation()

    def __repr__(self):
        return self.display()

    def show(self, *highlight_cards):
        print(self.display(highlight_cards))

    def display(self, highlight_cards=[]):
        def highlight_function(card):
            return card in highlight_cards

        board = "          0    1    2    3    4    5    6\n"
        row = 0
        foundation = list(self.foundation.foundations.items())
        space = "" if Card.SUIT_WIDTH == 2 else " "
        for row in range(max(4, max([len(pile.cards) for pile in self.tableau.piles]))):
            if row < 4:
                board += f"{space}{foundation[row][0].nickname}: {Card.display(foundation[row][1])}"
            else:
                board += "       "
            board += "  {}  {}  {}  {}  {}  {}  {}".format(
                *[pile.display_card(row, highlight_function) for pile in self.tableau.piles]
            )
            board += f" {str(row).rjust(3)}\n"
        return board

    def t(self, from_pile, to_pile, num_cards=None):
        if num_cards is None:
            num_cards = self.tableau.piles[from_pile].visible
        test_hand = self.tableau.piles[from_pile].test_pop_cards(num_cards)
        if self.tableau.piles[to_pile].can_add_cards(test_hand):
            hand = self.tableau.piles[from_pile].pop_cards(num_cards)
            self.tableau.piles[to_pile].add_cards(hand)
            return True
        else:
            return False

    def tableau_move(self, from_location, to_location):
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

    def foundation_move(self, from_location):
        assert (
            from_location.row_index == len(self.tableau.piles[from_location.pile_index].cards) - 1
        )
        return self.f(from_location.pile_index)

    def f(self, from_pile):
        test_hand = self.tableau.piles[from_pile].test_pop_cards(1)
        if self.foundation.can_build(test_hand[0]):
            hand = self.tableau.piles[from_pile].pop_cards(1)
            self.foundation.build(hand[0])
            return True
        else:
            return False

    def build_foundations(self):
        while any((self.f(i) for i, pile in enumerate(self.tableau.piles) if not pile.is_empty())):
            pass

    def find(self, card):
        pile_index, index, is_visible = self.tableau.find(card)
        if pile_index is not None and index is not None:
            if is_visible:
                print(f"{card} is in Pile {pile_index}, row {index}.")
            else:
                print(f"{card} is not visible")
        else:
            print(f"{card} is in the foundations")

    def locate(self, card):
        pile_index, index, is_visible = self.tableau.find(card)
        if pile_index is not None and index is not None and is_visible:
            return Board.Location(pile_index, index)
        else:
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
        elif from_pile is not None and to_location is not None:
            print(f"Not yet implemented. Specify a 'to pile' instead.")
            raise NotImplemented
        elif from_location is not None and to_location is not None:
            return self.tableau_move(from_location, to_location)
        elif from_location is not None and to_pile is not None:
            return self.tableau_move(from_location, to_pile)
        elif from_location is not None and to_foundation:
            return self.foundation_move(from_location)
        elif from_pile is not None and to_foundation:
            return self.f(from_pile)
        else:
            print("Something did not work in the parsing.")
            raise ValueError


b = board = Board(shuffled(deck))


def play():
    b = Board(shuffled(deck))
    feedback = None
    while True:
        if feedback == "No Show":
            feedback == None
        else:
            b.show()
        command = input()
        try:
            feedback = b.parse_command(command)
        except InterruptedError:
            break
        except:
            pass


if __name__ == "__main__":
    play()
