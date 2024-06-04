"""
Game of Cribbage
"""

from typing import List
from enum import Enum

from cards.cards.card import Card, shuffled, DECK, rest_of_deck
from cards.cribbage.hand import Hand
from cards.cribbage.discards import (
    rank_discards,
    parse_discard,
)
from cards.cribbage.players import Player
from cards.cribbage.pegging import parse_pegging, CardsInPlay, play_ai
from cards.cribbage.scoring import score_hand


class PlayState(Enum):
    """State of the game for Cribbage."""

    READY = -1
    DISCARD = 0
    PEGGING = 1
    SHOW = 2
    COMPLETE = 3


class Cribbage:
    """A class to represent a game of Cribbage."""

    def __init__(self, deck):
        self.__deck = deck
        self.__hands = {Player.PLAYER1: None, Player.PLAYER2: None}
        self._played_cards = CardsInPlay()
        self.__points = {Player.PLAYER1: 0, Player.PLAYER2: 0}
        self.__crib = None
        self.__starter = None
        self.__dealer = Player.PLAYER1
        self.__state = PlayState.READY

    def deal(self):
        self.__dealer = Player.PLAYER1 if self.__dealer == Player.PLAYER2 else Player.PLAYER2
        self.__deck = shuffled(self.__deck)
        self.__hands[Player.PLAYER1] = Hand(self.__deck[:6])
        self.__hands[Player.PLAYER2] = Hand(self.__deck[6:12])
        self._played_cards = CardsInPlay()
        self.__crib = Hand([], is_crib=True)
        self.__starter = self.__deck[12]
        self.__state = PlayState.DISCARD

    def display(self):
        starter = (
            Card.display(self.__starter)
            if self.__state in [PlayState.PEGGING, PlayState.SHOW, PlayState.COMPLETE]
            else Card.FACEDOWN
        )
        show_player2 = self.__state in [PlayState.SHOW, PlayState.COMPLETE]
        show_crib = self.__state in [PlayState.SHOW, PlayState.COMPLETE]
        played_cards_top, played_cards_bottom = self._played_cards.display().split("\n")
        dealer_duck_opponent = "🦆" if self.__dealer == Player.PLAYER2 else "  "
        dealer_duck_player = "🦆" if self.__dealer == Player.PLAYER1 else "  "

        def hand_score(hand: Hand) -> str:
            if self.__state not in [PlayState.SHOW, PlayState.COMPLETE]:
                return ""
            return " = " + str(score_hand(hand, self.__starter)[0]).rjust(2)

        result = "-" * 40 + "\n"
        if self.__state == PlayState.PEGGING:
            result += f"Play Count: {self._played_cards.count()}\n"
        if self.__state == PlayState.DISCARD:
            result += f"Discarding: {self.__dealer.name}'s crib\n"
        result += f"{dealer_duck_opponent} {str(self.points(Player.PLAYER2)).rjust(3)}  "
        result += f"{self.hand(Player.PLAYER2).display(show=show_player2)}"
        result += hand_score(self.__hands[Player.PLAYER2]) + "\n"
        result += f"       {played_cards_top}\n"
        result += f"{starter}     {self.__crib.display(show=show_crib)}"
        result += hand_score(self.__crib) + "\n"
        result += f"       {played_cards_bottom}\n"
        result += f"{dealer_duck_player} {str(self.points(Player.PLAYER1)).rjust(3)}  "
        result += f"{self.hand(Player.PLAYER1).display()}"
        result += hand_score(self.__hands[Player.PLAYER1]) + "\n"
        result += f"State: {self.__state.name}"
        return result

    def state(self):
        return self.__state

    def points(self, player: Player):
        return self.__points[player]

    def hand(self, player: Player):
        return self.__hands[player]

    def dealer(self):
        return self.__dealer

    def discard(self, player: Player, discard: List[Card]):
        for card in discard:
            self.__crib.add(self.__hands[player].discard(card))
        self.__state = PlayState.PEGGING

    def opponent(self, player: Player):
        return Player.PLAYER1 if player == Player.PLAYER2 else Player.PLAYER2

    def play(self, player: Player, card: Card):
        points = self._played_cards.play(player, card)
        self.__hands[player].discard(card)
        opponent = self.opponent(player)
        self.__points[player] += points[player].total
        self.__points[opponent] += points[opponent].total
        self.check_for_win()
        if all((len(hand.cards()) == 0 for hand in self.__hands.values())):
            self.__state = PlayState.SHOW
            self.count_hands()
        return points

    def go(self, player: Player):
        points = self._played_cards.go(player)
        opponent = self.opponent(player)
        self.__points[player] += points[player].total
        self.__points[opponent] += points[opponent].total
        self.check_for_win()
        if all((len(hand.cards()) == 0 for hand in self.__hands.values())):
            self.__state = PlayState.SHOW
            self.count_hands()
        return points

    def count_hands(self):
        for player in [self.opponent(self.__dealer), self.__dealer]:
            self.__hands[player] = Hand(self._played_cards.return_cards(player), is_crib=False)
            points, _ = score_hand(self.__hands[player], self.__starter)
            self.__points[player] += points
            self.check_for_win()
        crib_points, _ = score_hand(self.__crib, self.__starter)
        self.__points[self.__dealer] += crib_points
        self.check_for_win()
        self._played_cards = CardsInPlay()

    def check_for_win(self):
        if self.__points[Player.PLAYER1] >= 121:
            self.__state = PlayState.COMPLETE
            return Player.PLAYER1
        if self.__points[Player.PLAYER2] >= 121:
            self.__state = PlayState.COMPLETE
            return Player.PLAYER2
        return None


class CribbageAI:

    def __init__(self, game: Cribbage):
        self.__game = game

    def discard(self):
        discards = rank_discards(
            self.__game.hand(Player.PLAYER2),
            rest_of_deck(self.__game.hand(Player.PLAYER2).cards()),
            self.__game.dealer() == Player.PLAYER2,
        )
        discard = discards[0].discard
        self.__game.discard(Player.PLAYER2, discard)
        return discard

    def play(self):
        played_card = play_ai(self.__game.hand(Player.PLAYER2), self.__game._played_cards)
        if played_card is None:
            self.__game.go(Player.PLAYER2)
        else:
            self.__game.play(Player.PLAYER2, played_card)
        return played_card


class CribbageHelper:

    def __init__(self):
        self.__game = Cribbage(shuffled(DECK))
        self.__ai = CribbageAI(self.__game)

    def parse_input(self, input_str) -> bool:
        if input_str == "exit":
            exit()
        if input_str == "help":
            print("Commands: exit, help")
            return True
        return False

    def discarding(self):
        print(self.__game.display())
        while True:
            response = input("Discard: ")
            if self.parse_input(response):
                continue
            success, discards = parse_discard(response, self.__game.hand(Player.PLAYER1))
            if not success:
                continue
            self.__game.discard(Player.PLAYER1, discards)
            print(f"Discarding {discards}")
            self.__ai.discard()
            print("Opponent discarded")
            print()
            break

    def pegging(self):
        print(self.__game.display())
        turn = Player.PLAYER1
        while self.__game.state() == PlayState.PEGGING:
            if turn == Player.PLAYER1:
                while True:
                    response = input("Play: ")
                    if self.parse_input(response):
                        continue
                    success, card = parse_pegging(response, self.__game.hand(Player.PLAYER1))
                    if not success:
                        continue
                    if card is None:
                        self.__game.go(player=Player.PLAYER1)
                    else:
                        try:
                            self.__game.play(Player.PLAYER1, card)
                            print(f"Playing {card}")
                        except ValueError as e:
                            print(str(e).strip('"'))
                            continue
                    break
            else:
                opponent_play = self.__ai.play()
                if opponent_play is None:
                    print("Opponent said go")
                else:
                    print(f"Opponent played: {opponent_play}")
            turn = Player.PLAYER1 if turn == Player.PLAYER2 else Player.PLAYER2
            print(self.__game.display())
            print()

    def round(self):
        self.__game.deal()
        self.discarding()
        self.pegging()

    def play(self):
        while self.__game.state() != PlayState.COMPLETE:
            self.round()
        winner = self.__game.check_for_win()
        if winner == Player.PLAYER1:
            print("You win!")
        else:
            print("You lose!")


def main():
    """Play a game of Cribbage."""
    ch = CribbageHelper()
    ch.play()


if __name__ == "__main__":
    main()
