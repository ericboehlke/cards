from dataclasses import dataclass
from types import MappingProxyType
from collections import namedtuple
import random
import copy
from termcolor import colored
from aenum import Enum

class Suit(Enum):
    _init_ = "value suitname symbol"
    HEARTS = 1, "hearts", colored("♥️", "red")
    DIAMONDS = 2, "diamonds", colored("♦️", "red")
    CLUBS = 3, "clubs", colored("♣️", "black")
    SPADES = 4, "spades", colored("♠️", "black")

ImmutableCard = namedtuple('ImmutableCard', 'suit number visible')

def is_red(card):
    return card.suit in [Suit.DIAMONDS, Suit.HEARTS]

def display_card(card):
    if card is None:
        return "   "
    card_str = (str(card.number).rjust(2) + card.suit.symbol)
    if card.visible:
        if is_red(card):
            return colored(card_str, "red")
        else:
            return colored(card_str, "black")
    else:
        return colored("xXx", "blue")

def flip_card_faceup(card):
    return ImmutableCard(card.suit, card.number, True)

def flip_card_facedown(card):
    return ImmutableCard(card.suit, card.number, False)

def get_card(cards, index):
    return cards[index] if index < len(cards) else None

deck = tuple(ImmutableCard(suit, number, visible=True) for suit in Suit for number in range(1, 14))

def shuffled(cards):
    shuffled_cards = list(copy.deepcopy(cards))
    random.shuffle(shuffled_cards)
    return tuple(shuffled_cards)

def make_tableau_pile(cards, number_hidden):
     return tuple(map(flip_card_facedown, cards[:number_hidden])) + cards[number_hidden:]

Board = namedtuple("Board", "foundation tableau")
def make_board(deck):
    return Board(
        foundation = MappingProxyType({
            Suit.CLUBS: None,
            Suit.SPADES: None,
            Suit.HEARTS: None,
            Suit.DIAMONDS: None,
        }),
        tableau = (
            make_tableau_pile(deck[:1], 0),
            make_tableau_pile(deck[1:7], 5),
            make_tableau_pile(deck[7:14], 5),
            make_tableau_pile(deck[14:22], 5),
            make_tableau_pile(deck[22:31], 5),
            make_tableau_pile(deck[31:41], 5),
            make_tableau_pile(deck[41:52], 5),
        )
    )

def make_display_foundation(foundation):
    def display_foundation(suit):
        card = foundation[suit]
        if card is not None:
            return f"{suit.symbol}: {display_card(card)}"
        else:
            return f"{suit.symbol}: ---"
    return display_foundation

mdf_lambda = lambda f: lambda s: f"{s.symbol}: {display_card(f[s])}" if f[s] is not None else f"{s.symbol}: ---"

def concat_foundation_tableau_strs(foundation_strs, tableau_strs):
    def get_foundation_str(index):
        return foundation_strs[index] if index < len(foundation_strs) else " "*6
    def get_tableau_str(index):
        return tableau_strs[index] if index < len(tableau_strs) else ""
    return map(lambda i: get_foundation_str(i) + "  " + get_tableau_str(i), range(max(map(len, (foundation_strs, tableau_strs)))))

cfts = lambda fs, ts: map(lambda i: (fs[i] if i < len(fs) else " "*6) + "  " + (ts[i] if i < len(ts) else ""), range(max(map(len, (fs, ts)))))

def display_board_lambda(board):
    return \
    "         0    1    2    3    4    5    6\n" + \
    "\n".join((
        fs := tuple(map(
            lambda s: f"{s.symbol}: {display_card(board.foundation[s])}" 
                      if board.foundation[s] is not None else 
                      f"{s.symbol}: ---", Suit)),
        ts := tuple(map(
            lambda i: "  ".join(map(
                lambda p: display_card(get_card(p, i)), 
                board.tableau)), 
            range(max(map(len, board.tableau)))
        )),
        map(lambda i: 
            (fs[i] if i < len(fs) else " "*6) + "  " + 
            (ts[i] if i < len(ts) else ""), 
            range(max(map(len, (fs, ts)))))
    )[2])

def display_board_lambda_oneline(board):
    return "         0    1    2    3    4    5    6\n" + "\n".join((fs := tuple(map(lambda s: f"{s.symbol}: {display_card(board.foundation[s])}" if board.foundation[s] is not None else f"{s.symbol}: ---", Suit)), ts := tuple(map(lambda i: "  ".join(map(lambda p: display_card(get_card(p, i)), board.tableau)), range(max(map(len, board.tableau))))), map(lambda i: (fs[i] if i < len(fs) else " "*6) + "  " + (ts[i] if i < len(ts) else ""), range(max(map(len, (fs, ts))))))[2])

def display_board(board):
    return \
    "         0    1    2    3    4    5    6\n" + \
    "\n".join(concat_foundation_tableau_strs(
        tuple(map(make_display_foundation(board.foundation), Suit)),
        tuple(map(
            lambda i: "  ".join(map(
                lambda p: display_card(get_card(p, i)), 
                board.tableau)), 
            range(max(map(len, board.tableau)))
        ))
    ))

def tableau_move(board, from_pile, to_pile, num_cards):
    return Board(
        foundation = board.foundation,
        tableau = (
            make_tableau_pile(deck[:1], 0),
            make_tableau_pile(deck[1:7], 5),
            make_tableau_pile(deck[7:14], 5),
            make_tableau_pile(deck[14:22], 5),
            make_tableau_pile(deck[22:31], 5),
            make_tableau_pile(deck[31:41], 5),
            make_tableau_pile(deck[41:52], 5),
        )
    )

print(display_board_lambda_oneline(make_board(shuffled(deck))))
board = make_board(deck)