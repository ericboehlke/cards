"""
Game of Cribbage

`Cribbage` is a turn-tracking state machine: ask `to_act()` who may move and `legal_actions()` what
they may do, then `apply()` an action. It returns a list of plain-dict events describing what
happened (plays, go, last card, show scores...) and raises `IllegalAction` without changing any
state when an action is not allowed.
"""

import itertools
import random
import sys
from collections import namedtuple
from typing import Dict, List, Optional
from enum import Enum

from cards.cards.card import Card, DECK, shuffled, rest_of_deck, card_id
from cards.cribbage.hand import Hand
from cards.cribbage.discards import (
    rank_discards,
    parse_discard,
)
from cards.cribbage.players import Player
from cards.cribbage.pegging import parse_pegging, CardsInPlay, play_ai, other
from cards.cribbage.scoring import score_hand

WINNING_SCORE = 121


class PlayState(Enum):
    """State of the game for Cribbage."""

    READY = -1
    DISCARD = 0
    PEGGING = 1
    SHOW = 2
    COMPLETE = 3


class IllegalAction(ValueError):
    """An action that is not allowed right now. `code` is a stable machine readable reason."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class _GameOver(Exception):
    """Raised internally the moment a player reaches the winning score."""

    def __init__(self, winner: Player):
        super().__init__(winner)
        self.winner = winner


Action = namedtuple("Action", ["type", "cards"])  # type is "discard" (2 cards) or "play" (1 card)


class Cribbage:
    """A class to represent a game of Cribbage."""

    def __init__(
        self,
        deck=None,
        rng: Optional[random.Random] = None,
        first_dealer=None,
        shuffle=True,
        starting_points: Optional[Dict[Player, int]] = None,
        decks: Optional[List[List[Card]]] = None,
    ):
        """
        `rng` makes shuffling and the cut for first deal reproducible. `shuffle=False` deals the
        deck in the order given (player 1 gets the first six, player 2 the next six, the starter is
        the 13th card), which makes scripted scenarios possible, as does `starting_points`.

        `decks` is a list of complete card orders, one per deal (the first deal uses `decks[0]`,
        and so on), each used exactly as given with no shuffling. Cards are dealt as above. It
        needs `first_dealer` (there is no cut) and dealing past the last deck raises
        IllegalAction("decks_exhausted"). `deck` is ignored when `decks` is given and `shuffle` has no
        effect. No randomness is used, so games are reproducible.
        """
        if decks is not None:
            if first_dealer is None:
                raise ValueError("decks requires first_dealer")
            for order in decks:
                if len(order) != len(DECK) or set(order) != set(DECK):
                    raise ValueError("each deck must be a permutation of all 52 cards")
        self.__decks = [list(order) for order in decks] if decks is not None else None
        self.__deck = list(deck) if deck is not None else list(DECK)
        self.__rng = rng or random.Random()
        self.__shuffle = shuffle
        self.__hands: Dict[Player, Optional[Hand]] = {Player.PLAYER1: None, Player.PLAYER2: None}
        self._played_cards = CardsInPlay()
        self.__points = {Player.PLAYER1: 0, Player.PLAYER2: 0, **(starting_points or {})}
        self.__crib: Optional[Hand] = None
        self.__starter: Optional[Card] = None
        self.__dealer: Optional[Player] = first_dealer
        self.__deals = 0
        self.__discarded: set = set()
        self.__turn: Optional[Player] = None
        self.__winner: Optional[Player] = None
        self.__state = PlayState.READY

    # ---- queries -------------------------------------------------------------------------

    def state(self):
        return self.__state

    def points(self, player: Player):
        return self.__points[player]

    def hand(self, player: Player):
        return self.__hands[player]

    def dealer(self):
        return self.__dealer

    def winner(self) -> Optional[Player]:
        return self.__winner

    def turn(self) -> Optional[Player]:
        """The player who must play a card, during pegging."""
        return self.__turn if self.__state == PlayState.PEGGING else None

    def starter(self) -> Optional[Card]:
        return self.__starter

    def crib(self) -> Optional[Hand]:
        return self.__crib

    def cards_in_play(self) -> CardsInPlay:
        return self._played_cards

    def opponent(self, player: Player):
        return other(player)

    def to_act(self) -> List[Player]:
        """The players who currently have a legal action."""
        return [player for player in Player if self.legal_actions(player)]

    def legal_actions(self, player: Player) -> List[Action]:
        """Every action the player may take right now."""
        if self.__state == PlayState.DISCARD and player not in self.__discarded:
            return [Action("discard", pair) for pair in itertools.combinations(self.__hands[player].cards(), 2)]
        if self.__state == PlayState.PEGGING and player == self.__turn:
            return [
                Action("play", (card,))
                for card in self.__hands[player].cards()
                if self._played_cards.can_play(card)
            ]
        return []

    # ---- actions -------------------------------------------------------------------------

    def deal(self) -> List[dict]:
        """Deal a new round; the deal passes to the other player after the first round."""
        if self.__state not in (PlayState.READY, PlayState.SHOW):
            raise IllegalAction("wrong_phase", f"Cannot deal during {self.__state.name}")
        if self.__decks is not None and self.__deals >= len(self.__decks):
            raise IllegalAction("decks_exhausted", f"Only {len(self.__decks)} decks were supplied.")
        if self.__dealer is None:
            self.__dealer = self.__rng.choice(list(Player))  # the cut for first deal
        elif self.__deals > 0:
            self.__dealer = other(self.__dealer)
        if self.__decks is not None:
            self.__deck = self.__decks[self.__deals]
        self.__deals += 1
        if self.__shuffle and self.__decks is None:
            self.__deck = shuffled(self.__deck, self.__rng)
        self.__hands[Player.PLAYER1] = Hand(self.__deck[:6])
        self.__hands[Player.PLAYER2] = Hand(self.__deck[6:12])
        self._played_cards = CardsInPlay()
        self.__crib = Hand([], is_crib=True)
        self.__starter = self.__deck[12]
        self.__discarded = set()
        self.__turn = None
        self.__state = PlayState.DISCARD
        return [{"type": "deal", "dealer": self.__dealer.name}]

    def apply(self, player: Player, action: Action) -> List[dict]:
        """Apply an action by a player, returning the events it caused."""
        self._validate(player, action)
        events: List[dict] = []
        try:
            if action.type == "discard":
                self._discard(player, action.cards, events)
            else:
                self._play(player, action.cards[0], events)
        except _GameOver as over:
            self.__winner = over.winner
            self.__state = PlayState.COMPLETE
            self.__turn = None
            events.append({"type": "game_over", "winner": over.winner.name})
        return events

    def discard(self, player: Player, discard: List[Card]) -> List[dict]:
        """Put two cards from the player's hand into the crib."""
        return self.apply(player, Action("discard", tuple(discard)))

    def play(self, player: Player, card: Card) -> List[dict]:
        """Play a card during pegging."""
        return self.apply(player, Action("play", (card,)))

    def _validate(self, player: Player, action: Action) -> None:
        """Raise IllegalAction if the action is not allowed. Never changes any state."""
        if self.__state == PlayState.COMPLETE:
            raise IllegalAction("game_over", "The game is over.")
        if action.type not in ("discard", "play"):
            raise IllegalAction("unknown_action", f"Unknown action type {action.type!r}")
        hand = self.__hands[player]
        cards = list(action.cards)
        if action.type == "discard":
            if self.__state != PlayState.DISCARD:
                raise IllegalAction("wrong_phase", f"Cannot discard during {self.__state.name}")
            if player in self.__discarded:
                raise IllegalAction("already_discarded", "You already discarded to the crib.")
            if len(cards) != 2 or cards[0] == cards[1]:
                raise IllegalAction("bad_discard", "Discard exactly two different cards.")
        else:
            if self.__state != PlayState.PEGGING:
                raise IllegalAction("wrong_phase", f"Cannot play a card during {self.__state.name}")
            if player != self.__turn:
                raise IllegalAction("not_your_turn", f"It is {self.__turn.name}'s turn.")
            if len(cards) != 1:
                raise IllegalAction("bad_play", "Play exactly one card.")
        for card in cards:
            if card not in hand.cards():
                raise IllegalAction("card_not_in_hand", f"{card_id(card)} is not in your hand.")
        if action.type == "play" and not self._played_cards.can_play(cards[0]):
            raise IllegalAction(
                "exceeds_31",
                f"Playing {card_id(cards[0])} would take the count over 31 "
                f"(count is {self._played_cards.count()}).",
            )

    def _discard(self, player: Player, cards, events: List[dict]) -> None:
        for card in cards:
            self.__crib.add(self.__hands[player].discard(card))
        self.__discarded.add(player)
        events.append({"type": "discard", "player": player.name})
        if len(self.__discarded) == len(Player):
            self.__state = PlayState.PEGGING
            events.append({"type": "starter", "card": card_id(self.__starter)})
            if self.__starter.number() == 11:
                self._add_points(
                    self.__dealer, 2, {"type": "his_heels", "player": self.__dealer.name}, events
                )
            self._settle(events)

    def _play(self, player: Player, card: Card, events: List[dict]) -> None:
        self.__hands[player].discard(card)
        count_before = self._played_cards.count()
        score = self._played_cards.play(player, card)[player]
        event = {
            "type": "play",
            "player": player.name,
            "card": card_id(card),
            "count": count_before + min(card.number(), 10),
            "fifteen": score.fifteen,
            "thirtyone": score.thirtyone,
            "pair": score.pair,
            "run": score.run,
        }
        self._add_points(player, score.total, event, events)
        self._settle(events)

    def _add_points(self, player: Player, points: int, event: dict, events: List[dict]) -> None:
        """Append the event with its points, score them, and stop the game at the winning score."""
        event["points"] = points
        events.append(event)
        self.__points[player] += points
        if self.__points[player] >= WINNING_SCORE:
            raise _GameOver(player)

    def _settle(self, events: List[dict]) -> None:
        """
        Decide who plays next, saying go for anyone who cannot, awarding the last card, and moving
        to the show once every card has been played.
        """
        cip = self._played_cards
        while True:
            last = cip.last_player() or self.__dealer
            for player in (other(last), last):
                if self.__hands[player].cards() and any(
                    cip.can_play(card) for card in self.__hands[player].cards()
                ):
                    self.__turn = player
                    return
                if cip.sequence() and not cip.has_said_go(player):
                    events.append(
                        {
                            "type": "go",
                            "player": player.name,
                            "no_cards": not self.__hands[player].cards(),
                        }
                    )
                result = cip.go(player)
                for scorer, score in result.items():
                    if score.total:
                        self._add_points(
                            scorer, score.total, {"type": "last_card", "player": scorer.name}, events
                        )
            if not any(hand.cards() for hand in self.__hands.values()):
                self._show(events)
                return

    def _show(self, events: List[dict]) -> None:
        """Count the hands (non-dealer first) and the crib."""
        self.__state = PlayState.SHOW
        self.__turn = None
        for player in (other(self.__dealer), self.__dealer):
            self.__hands[player] = Hand(self._played_cards.return_cards(player))
        self._played_cards = CardsInPlay()
        shown = [
            (other(self.__dealer), "hand", self.__hands[other(self.__dealer)]),
            (self.__dealer, "hand", self.__hands[self.__dealer]),
            (self.__dealer, "crib", self.__crib),
        ]
        for player, what, hand in shown:
            total, parts = score_hand(hand, self.__starter)
            event = {
                "type": "show",
                "player": player.name,
                "what": what,
                "cards": [card_id(c) for c in hand.cards()],
                "starter": card_id(self.__starter),
                "fifteens": parts.fifteens.total,
                "pairs": parts.pairs.total,
                "runs": parts.runs.total,
                "flush": parts.flush.total,
                "his_nobs": parts.his_nobs.total,
            }
            self._add_points(player, total, event, events)

    # ---- display -------------------------------------------------------------------------

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


def describe_event(event: dict, names: Optional[Dict[str, str]] = None) -> str:
    """A one line plain-text description of an event; `names` relabels PLAYER1/PLAYER2."""
    names = names or {}
    kind = event["type"]
    who = names.get(event.get("player", ""), event.get("player", ""))
    if kind == "deal":
        dealer = names.get(event["dealer"], event["dealer"])
        return f"New round. Dealer (owns the crib): {dealer}."
    if kind == "discard":
        return f"{who} put two cards in the crib."
    if kind == "starter":
        return f"Starter card turned up: {event['card']}."
    if kind == "his_heels":
        return f"His heels: {who} scored 2 for a jack starter."
    if kind == "play":
        parts = [
            f"{name} {event[key]}"
            for key, name in (
                ("fifteen", "fifteen"),
                ("thirtyone", "thirty-one"),
                ("pair", "pair"),
                ("run", "run"),
            )
            if event[key]
        ]
        scored = f", scored {event['points']} ({', '.join(parts)})" if event["points"] else ""
        return f"{who} played {event['card']}, count {event['count']}{scored}."
    if kind == "go":
        if event.get("no_cards"):
            return f"{who} has no cards left (go)."
        return f"{who} said go (cannot play without going over 31)."
    if kind == "last_card":
        return f"{who} scored 1 for the last card."
    if kind == "show":
        parts = [
            f"{name} {event[key]}"
            for key, name in (
                ("fifteens", "fifteens"),
                ("pairs", "pairs"),
                ("runs", "runs"),
                ("flush", "flush"),
                ("his_nobs", "his nobs"),
            )
            if event[key]
        ]
        detail = f" ({', '.join(parts)})" if parts else ""
        return (
            f"Show: {who} {event['what']} {' '.join(event['cards'])} with starter "
            f"{event['starter']} scored {event['points']}{detail}."
        )
    if kind == "decks_exhausted":
        return "The supplied decks ran out; the game is over with no winner."
    if kind == "game_over":
        return f"Game over: {names.get(event['winner'], event['winner'])} won."
    return str(event)


class CribbageAI:
    """A greedy computer player: best-ranked discard, then the highest scoring legal play."""

    def __init__(self, game: Cribbage, player: Player = Player.PLAYER2):
        self.__game = game
        self.__player = player

    def choose(self) -> Action:
        """Choose an action for the current game state; there must be a legal action."""
        hand = self.__game.hand(self.__player)
        if self.__game.state() == PlayState.DISCARD:
            discards = rank_discards(
                hand, rest_of_deck(hand.cards()), self.__game.dealer() == self.__player
            )
            return Action("discard", tuple(discards[0].discard))
        card = play_ai(hand, self.__game.cards_in_play())
        return Action("play", (card,))

    def act(self) -> List[dict]:
        """Choose and apply an action."""
        return self.__game.apply(self.__player, self.choose())

    def discard(self):
        """Discard to the crib, returning the discarded cards."""
        action = self.choose()
        self.__game.apply(self.__player, action)
        return list(action.cards)

    def play(self) -> Optional[Card]:
        """Play a card, returning it."""
        action = self.choose()
        self.__game.apply(self.__player, action)
        return action.cards[0]


class CribbageHelper:
    """Interactive terminal game against the computer."""

    def __init__(self):
        self.__game = Cribbage()
        self.__ai = CribbageAI(self.__game)

    def parse_input(self, input_str) -> bool:
        if input_str == "exit":
            sys.exit()
        if input_str == "help":
            print("Commands: exit, help")
            return True
        return False

    def show_events(self, events):
        for event in events:
            print(describe_event(event))

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
            self.__ai.act()
            print("Opponent discarded")
            print()
            break

    def pegging(self):
        print(self.__game.display())
        while self.__game.state() == PlayState.PEGGING:
            if self.__game.turn() == Player.PLAYER1:
                while True:
                    response = input("Play: ")
                    if self.parse_input(response):
                        continue
                    success, card = parse_pegging(response, self.__game.hand(Player.PLAYER1))
                    if not success:
                        continue
                    try:
                        events = self.__game.play(Player.PLAYER1, card)
                    except IllegalAction as e:
                        print(e.message)
                        continue
                    break
            else:
                events = self.__ai.act()
            self.show_events(events)
            print(self.__game.display())
            print()

    def round(self):
        self.show_events(self.__game.deal())
        self.discarding()
        self.pegging()

    def play(self):
        while self.__game.state() != PlayState.COMPLETE:
            self.round()
        if self.__game.winner() == Player.PLAYER1:
            print("You win!")
        else:
            print("You lose!")


def main():
    """Play a game of Cribbage."""
    ch = CribbageHelper()
    ch.play()


if __name__ == "__main__":
    main()
