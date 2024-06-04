"""
Discarding in cribbage.
"""

import sys
import itertools
from collections import namedtuple
from typing import List, Tuple, Union
from termcolor import colored

from cards.cards.card import Card, Suit, shuffled
from cards.cards.card_shortcuts import card_shortcut_dict
from cards.cribbage.scoring import score_hand
from cards.cribbage.hand import Hand
from cards.cribbage.discard_table import opponent_crib_discard_table, player_crib_discard_table


Discard = namedtuple("Discard", "hand discard hand_score crib_score")


def which_cards_do_i_mean(cards_str: str, options: List[Card], suit_matters=True) -> List[Card]:
    """Given a string, return a list of cards that the string represents of the options provided."""
    output = []
    guess_strings = cards_str.split()
    for s in guess_strings:
        s_orig = s
        if s.upper() in card_shortcut_dict:
            output.append(card_shortcut_dict[s.upper()])
        else:
            face_card_shortcuts = {"A": "1", "T": "10", "J": "11", "Q": "12", "K": "13"}
            if s.upper() in face_card_shortcuts:
                s = face_card_shortcuts[s.upper()]
            option_numbers = [c.number() for c in options]
            unique_numbers = {
                n: options[i]
                for i, n in enumerate(option_numbers)
                if (option_numbers.count(n) == 1 or not suit_matters)
            }
            if s.isdigit() and (n := int(s)) in unique_numbers:
                output.append(unique_numbers[n])
            else:
                raise KeyError(f"I don't know what you mean by {s_orig}")
    return output


def display_discard(discard: Discard) -> str:
    """return a string representation of a discard"""
    total = discard.hand_score + discard.crib_score
    discard_cards = " ".join([str(c) for c in discard.discard])
    return (
        f"{discard.hand.display()} -> {discard_cards}  "
        f"({discard.hand_score:.2f} + {discard.crib_score:.2f} = {total:.2f})"
    )


def score_discard(
    discard: Union[List[Card], Tuple[Card, Card]], players_crib: bool = False
) -> float:
    """Return the expected value of the crib for a discard."""
    if players_crib:
        return player_crib_discard_table[discard[0].number()][discard[1].number()]
    return -1 * opponent_crib_discard_table[discard[0].number()][discard[1].number()]


def rank_discards(
    original_hand: Hand, remaining_deck: List[Card], players_crib: bool = False
) -> List[Discard]:
    """
    Rank the discards in order of preference for the crib
    """
    cards = original_hand.cards()
    assert len(cards) == 6
    discards: List[Discard] = []
    for discard_cards in itertools.combinations(cards, 2):
        hand = Hand(
            [c for c in cards if c not in discard_cards],
        )
        avg_score = sum(score_hand(hand, starter)[0] for starter in remaining_deck) / len(
            remaining_deck
        )
        discard = Discard(
            hand,
            discard_cards,
            avg_score,
            score_discard(discard_cards, players_crib=players_crib),
        )
        discards.append(discard)
    discards.sort(key=lambda d: d.hand_score + d.crib_score, reverse=True)
    return discards


def parse_discard(response, hand):
    """Given a string, return a list of cards that the string represents of the options provided."""
    try:
        discards = which_cards_do_i_mean(response, hand.cards())
    except KeyError as e:
        print(str(e).strip('"'))
        return False, None
    if len(discards) != 2:
        print("You must discard two cards")
        return False, None
    if discards[0] not in hand.cards():
        print(f"You don't have {discards[0]}.")
        return False, None
    if discards[1] not in hand.cards():
        print(f"You don't have {discards[1]}.")
        return False, None
    return True, discards


def main():
    """Play a game of choosing discards."""
    players_crib = True
    while True:
        deck = shuffled([Card(s, n) for s in Suit for n in range(1, 14)])
        player_hand = Hand(deck[0:6])
        players_crib = not players_crib
        print(f"Your hand: {player_hand.display()}")
        print("Your crib" if players_crib else "Opponent's crib")
        while True:
            guess_str = input("Discard: ")
            if guess_str in ["exit", "quit"]:
                sys.exit()
            success, discard_guess = parse_discard(guess_str, player_hand)
            if success:
                break
        ranked_discards = rank_discards(player_hand, deck[6:], players_crib=players_crib)
        if players_crib:
            print("        Hand               Discard  (hand   crib   total)")
        else:
            print("        Hand               Discard  (hand    crib   total)")
        for i, d in enumerate(ranked_discards):
            if discard_guess[0] in d.discard and discard_guess[1] in d.discard:
                print(colored("->", "yellow"), f"{str(i+1).rjust(2)}:  {display_discard(d)}")
            else:
                print(f"{str(i+1).rjust(5)}:  {display_discard(d)}")
        print()


if __name__ == "__main__":
    main()
