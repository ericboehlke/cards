"""
Play and Pegging in cribbage.
"""

import time
import random
from collections import namedtuple
from typing import List, Dict, Tuple, Union, Optional

from cards.cribbage.discards import which_cards_do_i_mean
from cards.cards.card import DECK, shuffled, Card
from cards.cribbage.players import Player
from cards.cribbage.hand import Hand
from cards.cribbage.scoring import card_value


def parse_pegging(response: str, hand: Hand):
    """Parse an input string and hand to determine the intended play."""
    if response.lower() == "go":
        return True, None
    try:
        cards = which_cards_do_i_mean(response, hand.cards(), suit_matters=False)
    except KeyError as e:
        print(str(e).strip('"'))
        return False, None
    if len(cards) != 1:
        print("You must choose one card or say go.")
        return False, None
    if cards[0] not in hand.cards():
        print(f"You don't have {cards[0]}.")
        return False, None
    return True, cards[0]


PlayedCard = namedtuple("PlayedCard", ["player", "card"])
PeggingScore = namedtuple("PeggingScore", ["fifteen", "thirtyone", "go", "pair", "run", "total"])

NO_SCORE = PeggingScore(0, 0, 0, 0, 0, 0)
MAX_COUNT = 31


def other(player: Player) -> Player:
    """Return the other player."""
    return Player.PLAYER1 if player == Player.PLAYER2 else Player.PLAYER2


class CardsInPlay:
    """
    The cards in play during pegging.

    Tracks the current sequence (reset at 31 or when both players are stuck) separately from every
    card played this round, which are needed to return the hands for the show.
    """

    def __init__(self) -> None:
        self.__played_cards: List[PlayedCard] = []
        self.__sequence: List[PlayedCard] = []
        self.__points: Dict[Player, int] = {Player.PLAYER1: 0, Player.PLAYER2: 0}
        self.__current_gos: Dict[Player, bool] = {Player.PLAYER1: False, Player.PLAYER2: False}

    def count(self) -> int:
        """Return the current play count."""
        return sum(card_value(played.card) for played in self.__sequence)

    def sequence(self) -> List[PlayedCard]:
        """Return the cards played since the count was last reset."""
        return list(self.__sequence)

    def played_cards(self) -> List[PlayedCard]:
        """Return every card played this round, including before the last count reset."""
        return list(self.__played_cards)

    def last_player(self) -> Optional[Player]:
        """Return the player who played the most recent card this round, if any."""
        return self.__played_cards[-1].player if self.__played_cards else None

    def points(self, player: Player) -> int:
        """Return the current points for a player in this round of play."""
        return self.__points[player]

    def can_play(self, card: Card) -> bool:
        """Return True if the card can be played without exceeding 31."""
        return self.count() + card_value(card) <= MAX_COUNT

    def has_said_go(self, player: Player) -> bool:
        """Return True if the player has already said go in the current sequence."""
        return self.__current_gos[player]

    def end_sequence(self) -> None:
        """Reset the count and the go flags to begin a new sequence."""
        self.__sequence = []
        self.__current_gos = {Player.PLAYER1: False, Player.PLAYER2: False}

    def play(self, player: Player, card) -> Dict[Player, PeggingScore]:
        """Play a card and return the points scored by each player."""
        valid_play, score = self.score_play(PlayedCard(player, card))
        if not valid_play:
            raise ValueError("Cannot play card that would exceed 31")
        played_card = PlayedCard(player, card)
        self.__played_cards.append(played_card)
        self.__sequence.append(played_card)
        self.__points[player] += score.total
        if self.count() == MAX_COUNT:
            self.end_sequence()
        return {player: score, other(player): NO_SCORE}

    def go(self, player: Player) -> Dict[Player, PeggingScore]:
        """
        Say go and return the points scored by each player.

        The first go scores nothing. When the other player has also said go (or cannot play), the
        sequence ends and the player who played the last card scores one point.
        """
        opponent = other(player)
        result = {player: NO_SCORE, opponent: NO_SCORE}
        if not self.__sequence:
            return result
        if self.__current_gos[opponent]:
            last = self.__sequence[-1].player
            result[last] = PeggingScore(0, 0, 1, 0, 0, 1)
            self.__points[last] += 1
            self.end_sequence()
        else:
            self.__current_gos[player] = True
        return result

    def return_cards(self, player: Player) -> List[Card]:
        """Return the cards played by a player."""
        return [
            played_card.card for played_card in self.__played_cards if played_card.player == player
        ]

    def score_play(self, played_card: PlayedCard) -> Tuple[bool, PeggingScore]:
        """
        Calculates the score for a play

        Returns a tuple of (valid_play, score)
        """
        new_count = self.count() + card_value(played_card.card)
        if new_count > MAX_COUNT:
            return False, NO_SCORE
        sequence = [pc.card for pc in self.__sequence] + [played_card.card]
        fifteen = 2 if new_count == 15 else 0
        thirtyone = 2 if new_count == MAX_COUNT else 0
        # Pairs: the trailing cards of the same rank
        same = 1
        while same < len(sequence) and sequence[-1 - same].number() == played_card.card.number():
            same += 1
        pair = {1: 0, 2: 2, 3: 6, 4: 12}[same]
        # Runs: the longest trailing group of three or more cards that are consecutive in any order
        run = 0
        for length in range(len(sequence), 2, -1):
            numbers = sorted(c.number() for c in sequence[-length:])
            if numbers == list(range(numbers[0], numbers[0] + length)):
                run = length
                break
        return (
            True,
            PeggingScore(
                fifteen=fifteen,
                thirtyone=thirtyone,
                go=0,
                pair=pair,
                run=run,
                total=fifteen + thirtyone + pair + run,
            ),
        )

    def display(self):
        """Return a string representation of the current sequence of cards in play."""
        opponent_string = ""
        player_string = ""
        for played_card in self.__sequence:
            if played_card.player == Player.PLAYER1:
                player_string += str(played_card.card) + " "
                opponent_string += "    "
            else:
                player_string += "    "
                opponent_string += str(played_card.card) + " "
        return opponent_string + "\n" + player_string


def ai_play(hand, cards_in_play) -> Tuple[Dict[Player, PeggingScore], Union[Card, None]]:
    """
    A greedy AI that plays the card that gives the most points

    Returns a tuple of (point dictionary, card)
    """
    played_card = play_ai(hand, cards_in_play)
    if played_card is None:
        return cards_in_play.go(Player.PLAYER2), None
    return cards_in_play.play(Player.PLAYER2, hand.discard(played_card)), played_card


def play_ai(hand, cards_in_play) -> Optional[Card]:
    """
    A greedy AI that determines the card that gives the most points during play

    Returns the card to play, or None if no card can be played.
    """
    valid_cards = [
        (cards_in_play.score_play(PlayedCard(Player.PLAYER2, card))[1].total, card)
        for card in hand.cards()
        if cards_in_play.can_play(card)
    ]
    if not valid_cards:
        return None
    return max(valid_cards, key=lambda scored: scored[0])[1]


def print_points(points):
    """Print the points scored by each player."""
    if points[Player.PLAYER1].total > 0:
        print("You scored:", points[Player.PLAYER1].total)
        if points[Player.PLAYER1].fifteen > 0:
            print("  Fifteen:", points[Player.PLAYER1].fifteen)
        if points[Player.PLAYER1].thirtyone > 0:
            print("  Thirty-one:", points[Player.PLAYER1].thirtyone)
        if points[Player.PLAYER1].pair > 0:
            print("  Pair:", points[Player.PLAYER1].pair)
        if points[Player.PLAYER1].run > 0:
            print("  Run:", points[Player.PLAYER1].run)
        if points[Player.PLAYER1].go > 0:
            print("  Go:", points[Player.PLAYER1].go)
    if points[Player.PLAYER2].total > 0:
        print("Opponent scored:", points[Player.PLAYER2].total)
        if points[Player.PLAYER2].fifteen > 0:
            print("  Fifteen:", points[Player.PLAYER2].fifteen)
        if points[Player.PLAYER2].thirtyone > 0:
            print("  Thirty-one:", points[Player.PLAYER2].thirtyone)
        if points[Player.PLAYER2].pair > 0:
            print("  Pair:", points[Player.PLAYER2].pair)
        if points[Player.PLAYER2].run > 0:
            print("  Run:", points[Player.PLAYER2].run)
        if points[Player.PLAYER2].go > 0:
            print("  Go:", points[Player.PLAYER2].go)


def print_end_of_game(
    cip: CardsInPlay, player_hand: Hand, opponent_hand: Hand, turn: Player
) -> None:
    """Print the end of game results."""
    print(
        "Your points:",
        cip.points(Player.PLAYER1),
        "Opponent's points",
        cip.points(Player.PLAYER2),
    )
    print("Current count:", cip.count())
    print("Opponent's turn" if turn == Player.PLAYER2 else "Your turn")
    print(opponent_hand.display(show=False))
    print(cip.display())
    print(player_hand.display())
    print("Game over!")
    if cip.points(Player.PLAYER1) == cip.points(Player.PLAYER2):
        print("Tie!")
    elif cip.points(Player.PLAYER1) > cip.points(Player.PLAYER2):
        print("You won!")
    else:
        print("You lost!")
    print()
    print()


def print_current_game(player_hand, opponent_hand, cip, turn):
    """Print the current state of the game."""
    print(
        "Your points:",
        cip.points(Player.PLAYER1),
        "Opponent's points",
        cip.points(Player.PLAYER2),
    )
    print("Current count:", cip.count())
    print("Opponent's turn" if turn == Player.PLAYER2 else "Your turn")
    print(opponent_hand.display(show=False))
    print(cip.display())
    print(player_hand.display())


def main():
    """Play a game of pegging."""

    while True:
        deck = shuffled(DECK)
        player_hand = Hand(deck[0:4])
        opponent_hand = Hand(deck[4:8])
        cip = CardsInPlay()
        turn = random.choice([Player.PLAYER1, Player.PLAYER2])
        print("New game of pegging!")
        while len(player_hand.cards()) > 0 or len(opponent_hand.cards()) > 0:
            if turn == Player.PLAYER1:
                print_current_game(player_hand, opponent_hand, cip, turn)
            if turn == Player.PLAYER2:
                time.sleep(1)
                points, card = ai_play(opponent_hand, cip)
                if card is None:
                    print("Opponent said go")
                else:
                    print("Opponent played:", card)
                print_points(points)
            else:
                while True:
                    success, card_to_play = parse_pegging(
                        input("Enter card to play: "), player_hand
                    )
                    if success:
                        break
                if card_to_play is None:
                    points = cip.go(Player.PLAYER1)
                    print("You said go")
                else:
                    points = cip.play(Player.PLAYER1, player_hand.discard(card_to_play))
                    print("You played:", card_to_play)
                print_points(points)
            turn = Player.PLAYER1 if turn == Player.PLAYER2 else Player.PLAYER2
            print()
        print_end_of_game(cip, player_hand, opponent_hand, turn)
        time.sleep(2)


if __name__ == "__main__":
    main()
