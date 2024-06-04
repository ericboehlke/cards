"""
Functions to score cribbage hands.
"""

import math
import itertools
from collections import namedtuple
from typing import List, Tuple, Union, Dict

from cards.cards.card import Card, Suit, JACK, shuffled
from cards.cribbage.hand import Hand

Score = namedtuple("Score", "total cards")


def card_value(card: Card) -> int:
    """Return the value of a card for play in cribbage."""
    return min(card.number(), 10)


def is_fifteen(cards: List[Card]) -> bool:
    """Return True if the sum of the value of the cards is 15."""
    return sum(card_value(c) for c in cards) == 15


def score_hand_fifteens(hand: Hand, starter: Card) -> Score:
    """Score the fifteens in a cribbage hand."""
    cards = hand.cards() + [starter]
    combs = []
    for i in range(2, len(cards) + 1):
        els = [list(x) for x in itertools.combinations(cards, i)]
        combs.extend(els)
    fifteens = [cs for cs in combs if is_fifteen(cs)]
    return Score(total=2 * len(fifteens), cards=fifteens)


def is_pair(cards: Union[List[Card], Tuple[Card, Card]]) -> bool:
    """Return True if the two cards are a pair."""
    return len(cards) == 2 and cards[0].number() == cards[1].number()


def score_hand_pairs(hand: Hand, starter: Card) -> Score:
    """Score the pairs in a cribbage hand."""
    cards = hand.cards() + [starter]
    pairs = [list(cs) for cs in itertools.combinations(cards, 2) if is_pair(cs)]
    return Score(total=2 * len(pairs), cards=pairs)


def score_hand_flush(hand: Hand, starter: Card) -> Score:
    """Score the flush in a cribbage hand."""
    if all(c.suit() == starter.suit() for c in hand.cards()):
        return Score(total=5, cards=[hand.cards() + [starter]])
    if not hand.is_crib:
        if all(c.suit() == hand.cards()[0].suit() for c in hand.cards()):
            return Score(total=4, cards=[hand.cards()])
    return Score(total=0, cards=[])


def score_hand_his_nobs(hand: Hand, starter: Card) -> Score:
    """Score his nobs in a cribbage hand."""
    for card in hand.cards():
        if card.number() == JACK and card.suit() == starter.suit():
            return Score(total=1, cards=[[card, starter]])
    return Score(total=0, cards=[])


def score_hand_runs(hand: Hand, starter: Card) -> Score:
    """Score the runs in a cribbage hand."""

    def run_length(run: List[Card]) -> int:
        return len(set(card.number() for card in run))

    def calculate_run_score(run: List[Card]) -> int:
        counts: Dict[int, int] = {}
        for card in run:
            if card.number() in counts:
                counts[card.number()] += 1
            else:
                counts[card.number()] = 1
        multiplier = math.prod(counts.values())
        run_len = run_length(run)
        return run_len * multiplier

    cards = hand.cards() + [starter]
    sorted_cards = sorted(cards, key=lambda card: card.number())
    run = [sorted_cards[0]]
    for card in sorted_cards[1:]:
        if card.number() == run[-1].number() + 1 or card.number() == run[-1].number():
            run.append(card)
        else:
            if run_length(run) >= 3:
                return Score(total=calculate_run_score(run), cards=[run])
            run = [card]
    if run_length(run) >= 3:
        return Score(total=calculate_run_score(run), cards=[run])
    return Score(total=0, cards=[])


HandScore = namedtuple("HandScore", "fifteens pairs runs flush his_nobs")


def score_hand(hand: Hand, starter: Card) -> Tuple[int, HandScore]:
    """Score a cribbage hand."""
    scores = HandScore(
        fifteens=score_hand_fifteens(hand, starter),
        pairs=score_hand_pairs(hand, starter),
        runs=score_hand_runs(hand, starter),
        flush=score_hand_flush(hand, starter),
        his_nobs=score_hand_his_nobs(hand, starter),
    )
    total = sum(
        (
            scores.fifteens[0],
            scores.pairs[0],
            scores.runs[0],
            scores.flush[0],
            scores.his_nobs[0],
        )
    )
    return total, scores


def print_explanations(explanation):
    """Print the explanations for the cribbage score."""
    if explanation.fifteens.total > 0:
        print(f"Fifteens: {explanation.fifteens.total} points")
        for cs in explanation.fifteens.cards:
            print("  ", " ".join([Card.display(c) for c in cs]))
    if explanation.pairs.total > 0:
        print(f"Pairs: {explanation.pairs.total} points")
        for cs in explanation.pairs.cards:
            print("  ", " ".join([Card.display(c) for c in cs]))
    if explanation.runs.total > 0:
        print(f"Runs: {explanation.runs.total} points")
        for cs in explanation.runs.cards:
            print("  ", " ".join([Card.display(c) for c in cs]))
    if explanation.flush.total > 0:
        print(f"Flush: {explanation.flush.total} points")
        for cs in explanation.flush.cards:
            print("  ", " ".join([Card.display(c) for c in cs]))
    if explanation.his_nobs.total > 0:
        print(f"His Nobs: {explanation.his_nobs.total} points")
        for cs in explanation.his_nobs.cards:
            print("  ", " ".join([Card.display(c) for c in cs]))


def main():
    """Play a game of scoring cribbage hands."""
    while True:
        deck = shuffled([Card(s, n) for s in Suit for n in range(1, 14)])
        player_hand = Hand(deck[0:4])
        starter = deck[5]
        score, explanation = score_hand(player_hand, starter)
        print()
        print(f"Hand: {player_hand.display()} Starter: {starter}")
        try:
            score_guess = int(input("Score: "))
        except ValueError:
            print(f"Exiting, score was {score}")
            break
        if score_guess == score:
            print("Correct!")
        else:
            print(f"Incorrect, score is {score}")
            print_explanations(explanation)


if __name__ == "__main__":
    main()
