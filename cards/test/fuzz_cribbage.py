"""
Full-game fuzzer for cribbage.

Plays many seeded games through the engine with random and greedy players and checks the rules of
cribbage after every action, using the independent oracle in oracle_cribbage.py. Run directly:

    python fuzz_cribbage.py --games 2000 --seed 0
"""

import argparse
import random
import sys
from typing import List

import oracle_cribbage as oracle
from cards.cards.card import DECK, card_from_id, card_id
from cards.cribbage.cribbage import Action, Cribbage, CribbageAI, IllegalAction, PlayState
from cards.cribbage.pegging import other
from cards.cribbage.players import Player


def raw(card):
    """Convert an engine card to the oracle's representation."""
    return (card.number(), card.suit().name)


class RuleViolation(AssertionError):
    """The game did something that is against the rules of cribbage."""


def check(condition: bool, message: str) -> None:
    """Raise RuleViolation with the message unless the condition holds."""
    if not condition:
        raise RuleViolation(message)


class RuleChecker:
    """Watches one game, comparing every action and event with the rules."""

    def __init__(self, game: Cribbage):
        self.game = game
        self.sequence: List = []  # raw cards in the current pegging sequence
        self.last_player = None
        self.plays_this_round = 0
        self.last_points = {p: 0 for p in Player}
        self.dealer = None

    def snapshot(self) -> dict:
        """Everything about the game state that an illegal action must not change."""
        game = self.game
        return {
            "state": game.state(),
            "points": {p: game.points(p) for p in Player},
            "hands": {p: tuple(game.hand(p).cards()) if game.hand(p) else None for p in Player},
            "crib": tuple(game.crib().cards()) if game.crib() else None,
            "count": game.cards_in_play().count(),
            "turn": game.turn(),
            "to_act": game.to_act(),
        }

    def on_deal(self, events) -> None:
        game = self.game
        check(game.state() == PlayState.DISCARD, "deal did not enter DISCARD")
        if self.dealer is not None:
            check(game.dealer() == other(self.dealer), "dealer did not alternate")
        self.dealer = game.dealer()
        for player in Player:
            check(len(game.hand(player).cards()) == 6, "each player must be dealt six cards")
        self.sequence = []
        self.last_player = self.dealer
        self.plays_this_round = 0
        self.check_cards()

    def check_cards(self) -> None:
        """No card is ever duplicated or lost."""
        game = self.game
        cip = game.cards_in_play()
        cards = []
        for player in Player:
            cards += game.hand(player).cards()
            cards += cip.return_cards(player)
        cards += game.crib().cards()
        cards.append(game.starter())
        check(len(cards) == len(set(cards)), "a card appears twice")
        check(all(c in DECK for c in cards), "unknown card")
        state = game.state()
        if state == PlayState.DISCARD:
            check(len(cards) == 12 + 1 - len(game.crib().cards()) + len(game.crib().cards()), "card count")
        if state in (PlayState.PEGGING, PlayState.SHOW, PlayState.COMPLETE) and state != PlayState.COMPLETE:
            check(len(game.crib().cards()) == 4, "crib must have four cards")

    def before_action(self, player: Player, action: Action) -> None:
        """Rules that depend on the state before the action."""
        game = self.game
        if game.state() == PlayState.PEGGING and action.type == "play":
            if not self.sequence:
                last = self.last_player
                leader = other(last) if game.hand(other(last)).cards() else last
                check(player == leader, f"{player} led but {leader} should have")
            check(player == game.turn(), "turn mismatch")

    def after_action(self, player: Player, action: Action, events: List[dict], before: dict) -> None:
        """Compare the events (and the resulting state) with the oracle."""
        game = self.game
        check(not (before["state"] == PlayState.COMPLETE), "action accepted after game over")
        over = False
        for event in events:
            check(not over, "event after game_over")
            kind = event["type"]
            if kind == "play":
                actor = Player[event["player"]]
                card = card_from_id(event["card"])
                expected = oracle.peg_play_score(self.sequence, raw(card))
                got = event["fifteen"] + event["thirtyone"] + event["pair"] + event["run"]
                check(got == event["points"], "play points do not add up")
                check(got == expected, f"{self.sequence} then {card_id(card)}: engine {got}, oracle {expected}")
                self.sequence.append(raw(card))
                self.last_player = actor
                self.plays_this_round += 1
                count = sum(oracle.value(r) for r, _ in self.sequence)
                check(count <= 31, "count over 31")
                check(count == event["count"], "event count wrong")
                if count == 31:
                    self.sequence = []
            elif kind == "go":
                stuck = Player[event["player"]]
                check(bool(self.sequence), "go with nothing played")
                count = sum(oracle.value(r) for r, _ in self.sequence)
                held = [c for c in before["hands"][stuck] if c not in (action.cards if stuck == player else ())]
                check(
                    all(oracle.value(c.number()) + count > 31 for c in held),
                    "go said while holding a playable card",
                )
            elif kind == "last_card":
                check(Player[event["player"]] == self.last_player, "last card to wrong player")
                check(event["points"] == 1, "last card must be one point")
                check(bool(self.sequence), "last card with empty sequence")
                self.sequence = []
            elif kind == "his_heels":
                check(Player[event["player"]] == self.dealer, "his heels to non-dealer")
                check(game.starter().number() == 11, "his heels without a jack")
            elif kind == "show":
                starter = raw(game.starter())
                cards = [raw(card_from_id(c)) for c in event["cards"]]
                expected = oracle.hand_score(cards, starter, event["what"] == "crib")
                check(len(cards) == 4, "shown hand must have four cards")
                check(event["points"] == expected, f"show {cards}+{starter}: engine {event['points']}, oracle {expected}")
            elif kind == "game_over":
                over = True
        if over:
            self.check_game_over()
            return
        # points only ever go up and never reach the target silently
        for p in Player:
            check(game.points(p) >= self.last_points[p], "points went down")
            self.last_points[p] = game.points(p)
            check(game.points(p) < 121, "someone reached 121 without the game ending")
        state = game.state()
        if state == PlayState.PEGGING:
            check(game.turn() is not None, "pegging with nobody to play")
            check(game.to_act() == [game.turn()], "exactly the player on turn may act")
            for p in Player:
                check(len(game.hand(p).cards()) + len(game.cards_in_play().return_cards(p)) == 4, "four cards each")
        if state == PlayState.SHOW:
            check(self.plays_this_round == 8, "the show began before all eight cards were played")
            check(not self.sequence, "show began mid-sequence (missing last card point)")
        self.check_cards()

    def check_game_over(self) -> None:
        game = self.game
        check(game.state() == PlayState.COMPLETE, "game_over without COMPLETE")
        winner = game.winner()
        check(winner is not None and game.points(winner) >= 121, "winner has fewer than 121")
        check(game.points(other(winner)) < 121 or game.points(other(winner)) >= 0, "loser score")
        check(game.to_act() == [], "players can still act after the game")
        for player in Player:
            check(not game.legal_actions(player), "legal actions after game over")
        for p in Player:
            check(game.points(p) >= self.last_points[p], "points went down")


def play_game(seed: int, policies=("random", "random")) -> int:
    """Play one full game. Returns the number of actions taken. Raises RuleViolation on a bug."""
    rng = random.Random(seed)
    game = Cribbage(rng=random.Random(seed))
    checker = RuleChecker(game)
    ais = {p: CribbageAI(game, p) for p in Player}
    kinds = dict(zip(Player, policies))
    actions = 0
    for _ in range(100000):
        if game.state() == PlayState.COMPLETE:
            check(game.winner() is not None, "complete without a winner")
            return actions
        if game.state() in (PlayState.READY, PlayState.SHOW):
            events = game.deal()
            checker.on_deal(events)
            continue
        actors = game.to_act()
        check(bool(actors), f"deadlock in {game.state()}")
        player = rng.choice(actors)
        legal = game.legal_actions(player)
        action = ais[player].choose() if kinds[player] == "greedy" else rng.choice(legal)
        check(action in legal, "chosen action is not legal")
        # an illegal action must be rejected without changing anything
        before = checker.snapshot()
        probe = bad_action(rng, game, player, legal)
        if probe is not None:
            try:
                game.apply(player, probe)
            except IllegalAction:
                pass
            else:
                raise RuleViolation(f"illegal action accepted: {probe}")
            check(checker.snapshot() == before, "an illegal action changed the game")
        checker.before_action(player, action)
        events = game.apply(player, action)
        checker.after_action(player, action, events, before)
        actions += 1
    raise RuleViolation("game did not finish")


def bad_action(rng, game, player, legal):
    """Return an action that should be rejected right now, or None."""
    choices = []
    hand = game.hand(player).cards()
    other_hand = game.hand(other(player)).cards()
    if game.state() == PlayState.DISCARD:
        choices.append(Action("play", (hand[0],)))
        choices.append(Action("discard", (hand[0],)))
        choices.append(Action("discard", (hand[0], hand[0])))
        choices.append(Action("discard", tuple(hand[:3])))
        choices.append(Action("discard", (hand[0], DECK[0] if DECK[0] not in hand else DECK[-1])))
    if game.state() == PlayState.PEGGING:
        choices.append(Action("discard", tuple(hand[:2])))
        choices.append(Action("play", ()))
        choices.append(Action("play", tuple(hand[:2])))
        if other_hand:
            choices.append(Action("play", (other_hand[0],)))
        stuck = [c for c in hand if not game.cards_in_play().can_play(c)]
        if stuck:
            choices.append(Action("play", (stuck[0],)))
        waiting = other(player)
        if waiting != game.turn() and hand:
            choices.append(Action("play", (hand[0],)))
    if game.state() in (PlayState.SHOW, PlayState.READY):
        choices.append(Action("play", (DECK[0],)))
    choices = [c for c in choices if c not in legal]
    return rng.choice(choices) if choices else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=500)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--random-only", action="store_true", help="skip the slow greedy players")
    args = parser.parse_args()
    mixes = [("random", "random"), ("greedy", "random"), ("greedy", "greedy")]
    if args.random_only:
        mixes = mixes[:1]
    failures = 0
    for i in range(args.games):
        seed = args.seed + i
        mix = mixes[i % len(mixes)]
        try:
            play_game(seed, mix)
        except RuleViolation as e:
            failures += 1
            print(f"seed {seed} {mix}: {e}")
            if failures >= 10:
                break
    print(f"{args.games} games, {failures} rule violations")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
