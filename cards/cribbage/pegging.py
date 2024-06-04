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


class CardsInPlay:
    """
    The cards in play during pegging.
    """

    def __init__(self) -> None:
        self.__played_cards: List[PlayedCard] = []
        self.__current_count: int = 0
        self.__points: Dict[Player, int] = {Player.PLAYER1: 0, Player.PLAYER2: 0}
        self.__current_run: List[PlayedCard] = []
        self.__current_gos: Dict[Player, bool] = {Player.PLAYER1: False, Player.PLAYER2: False}

    def count(self) -> int:
        """Return the current play count."""
        return self.__current_count

    def points(self, player: Player) -> int:
        """Return the current points for a player in this round of play."""
        return self.__points[player]

    def play(self, player: Player, card) -> Dict[Player, PeggingScore]:
        """Play a card and return the points scored by each player."""
        valid_play, extend_run, score = self.score_play(PlayedCard(player, card))
        if not valid_play:
            raise ValueError("Cannot play card that would exceed 31")
        played_card = PlayedCard(player, card)
        self.__played_cards.append(played_card)
        if extend_run:
            self.__current_run.append(played_card)
        else:
            self.__current_run = self.__played_cards[-2:]
        self.__current_count += card_value(card)
        self.__points[player] += score.total
        opponent = Player.PLAYER1 if player == Player.PLAYER2 else Player.PLAYER2
        if self.__current_count == 31:
            self.__current_gos[player] = False
            self.__current_gos[opponent] = False
            self.__current_count = 0
            self.__current_run = []
        return {player: score, opponent: PeggingScore(0, 0, 0, 0, 0, 0)}

    def go(self, player: Player) -> Dict[Player, PeggingScore]:
        """Say go and return the points scored by each player."""
        opponent = Player.PLAYER1 if player == Player.PLAYER2 else Player.PLAYER2
        if self.__current_gos[opponent]:
            self.__current_gos[player] = False
            self.__current_gos[opponent] = False
            self.__current_count = 0
            self.__current_run = []
            return {
                player: PeggingScore(0, 0, 0, 0, 0, 0),
                opponent: PeggingScore(0, 0, 0, 0, 0, 0),
            }
        if not self.__current_gos[player]:
            self.__current_gos[player] = True
            self.__points[opponent] += 1
            return {
                player: PeggingScore(0, 0, 0, 0, 0, 0),
                opponent: PeggingScore(fifteen=0, thirtyone=0, go=1, pair=0, run=0, total=1),
            }
        return {
            player: PeggingScore(0, 0, 0, 0, 0, 0),
            opponent: PeggingScore(0, 0, 0, 0, 0, 0),
        }

    def return_cards(self, player: Player) -> List[Card]:
        """Return the cards played by a player."""
        return [
            played_card.card for played_card in self.__played_cards if played_card.player == player
        ]

    def score_play(self, played_card: PlayedCard) -> Tuple[bool, bool, PeggingScore]:
        """
        Calculates the score for a play

        Returns a tuple of (valid_play, extend_run, score)
        """
        points = {"fifteen": 0, "thirtyone": 0, "go": 0, "pair": 0, "run": 0}
        extend_run = False
        new_count = self.__current_count + card_value(played_card.card)
        if new_count > 31:
            return False, False, PeggingScore(0, 0, 0, 0, 0, 0)
        # Fifteen
        if new_count == 15:
            points["fifteen"] += 2
        # Thirty-one
        if new_count == 31:
            points["thirtyone"] += 2
        # Pair
        if (
            len(self.__played_cards) > 0
            and self.__played_cards[-1].card.number() == played_card.card.number()
        ):
            if (
                len(self.__played_cards) > 1
                and self.__played_cards[-2].card.number() == played_card.card.number()
            ):
                if (
                    len(self.__played_cards) > 2
                    and self.__played_cards[-3].card.number() == played_card.card.number()
                ):
                    points["pair"] += 6
                points["pair"] += 4
            points["pair"] += 2
        # Run
        if len(self.__current_run) == 0:
            extend_run = False
        else:
            proposed_run = self.__current_run + [played_card]
            proposed_run = sorted(proposed_run, key=lambda pc: pc.card.number())
            gaps = [
                proposed_run[i].card.number() - proposed_run[i - 1].card.number()
                for i in range(1, len(proposed_run))
            ]
            if all((gap == 1 for gap in gaps)):
                if len(proposed_run) >= 3:
                    points["run"] += len(proposed_run)
                extend_run = True
            else:
                extend_run = False
        return (
            True,
            extend_run,
            PeggingScore(
                fifteen=points["fifteen"],
                thirtyone=points["thirtyone"],
                go=points["go"],
                pair=points["pair"],
                run=points["run"],
                total=sum(points.values()),
            ),
        )

    def display(self):
        """Return a string representation of the cards in play."""
        opponent_string = ""
        player_string = ""
        for played_card in self.__played_cards:
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
    return (
        (
            cards_in_play.play(
                Player.PLAYER2,
                hand.discard(played_card),
            ),
            played_card,
        )
        if (played_card := play_ai(hand, cards_in_play)) is None
        else (cards_in_play.go(Player.PLAYER2), None)
    )


def play_ai(hand, cards_in_play) -> Optional[Card]:
    """
    A greedy AI that determines the card that gives the most points during play

    Returns a tuple of (point dictionary, card)
    """
    return (
        (max(valid_cards, key=lambda t: t[0][2].total)[1])
        if len(
            (
                valid_cards := [
                    (valid_play, card)
                    for card in hand.cards()
                    if (valid_play := cards_in_play.score_play(PlayedCard(Player.PLAYER2, card)))[0]
                ]
            )
        )
        > 0
        else None
    )


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
