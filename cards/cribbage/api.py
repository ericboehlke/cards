"""
A text/JSON friendly environment for playing cribbage against the computer, e.g. by an LLM.

    env = CribbageEnv(seed=1)
    obs = env.reset()
    result = env.step({"type": "discard", "cards": ["5H", "KS"]})

For reproducible games across implementations pass `decks` (one 52 card order per deal, as card ids)
and `first_dealer` instead of relying on a seed; see `CribbageEnv`.

Everything in observations and results is plain JSON-serializable data. The agent is always "you";
the computer is "opponent". Opponent turns, the show, and dealing the next round all happen
automatically, so after every call it is the agent's move or the game is over.
"""

import random
from typing import Any, Dict, List, Optional

from cards.cards.card import card_id, card_from_id
from cards.cribbage.cribbage import (
    Action,
    Cribbage,
    CribbageAI,
    IllegalAction,
    PlayState,
    WINNING_SCORE,
    describe_event,
)
from cards.cribbage.players import Player

AGENT = Player.PLAYER1
OPPONENT = Player.PLAYER2
NAMES = {AGENT.name: "you", OPPONENT.name: "opponent"}

OPPONENTS = ("greedy", "random")


def _relabel(event: dict) -> dict:
    """Copy an event with player labels turned into "you" / "opponent" plus a text description."""
    result = {k: (NAMES.get(v, v) if k in ("player", "dealer", "winner") else v) for k, v in event.items()}
    result["text"] = describe_event(event, NAMES)
    return result


def _action_to_json(action: Action) -> dict:
    if action.type == "play":
        return {"type": "play", "card": card_id(action.cards[0])}
    return {"type": "discard", "cards": [card_id(c) for c in action.cards]}


def parse_action(data: Any) -> Action:
    """
    Convert a JSON action to an Action. Raises IllegalAction("bad_action") if malformed.

    Accepted: {"type": "discard", "cards": ["5H", "KS"]}, {"type": "play", "card": "7D"}
    ("cards": ["7D"] also works for a play).
    """
    try:
        kind = data["type"]
        if kind == "discard":
            return Action("discard", tuple(card_from_id(c) for c in data["cards"]))
        if kind == "play":
            ids = [data["card"]] if "card" in data else data["cards"]
            return Action("play", tuple(card_from_id(c) for c in ids))
    except (KeyError, TypeError, ValueError) as e:
        raise IllegalAction("bad_action", f"Malformed action {data!r}: {e}") from e
    raise IllegalAction("bad_action", f"Unknown action type {kind!r}; use 'discard' or 'play'.")


class CribbageEnv:
    """Play cribbage as `"you"` against a computer opponent."""

    def __init__(
        self,
        seed: Optional[int] = None,
        opponent: str = "greedy",
        decks: Optional[List[List[str]]] = None,
        first_dealer: str = "you",
    ):
        """
        `seed` makes shuffling, the cut for first deal and the "random" opponent reproducible.

        `decks` instead fixes the cards: a list of full 52 card orders as card ids, one per deal
        (deal N uses decks[N] exactly, unshuffled; the game must finish within len(decks) deals or
        dealing raises IllegalAction("decks_exhausted")). In each deal the cards are taken from the
        top: player 1 ("you") gets indexes 0-5, the opponent 6-11, and index 12 is the starter. With
        `decks` the first dealer is `first_dealer` ("you" or "opponent"; the dealer then alternates)
        rather than a random cut. The "greedy" opponent uses no randomness, so decks alone fully
        determine the game; the "random" opponent still depends on `seed`. `reset()` replays the
        same decks. `first_dealer` is ignored without `decks`.

        If the game is still undecided when the decks run out, the step that finishes the last
        round succeeds with a final {"type": "decks_exhausted"} event, and the game is then over
        with no winner (`done` is true, phase "complete", `winner` None, no legal actions).
        """
        if opponent not in OPPONENTS:
            raise ValueError(f"opponent must be one of {OPPONENTS}")
        if first_dealer not in ("you", "opponent"):
            raise ValueError('first_dealer must be "you" or "opponent"')
        if decks is not None and len(decks) == 0:
            raise ValueError("decks must contain at least one deck")
        self.__decks = (
            [[card_from_id(c) for c in order] for order in decks] if decks is not None else None
        )
        self.__exhausted = False
        self.__first_dealer = AGENT if first_dealer == "you" else OPPONENT
        self.__opponent_kind = opponent
        self.__seed = seed
        self.__game: Cribbage
        self.__ai: CribbageAI
        self.__opponent_rng: random.Random
        self.__log: List[dict] = []
        self.reset()

    # ---- public API -------------------------------------------------------------------

    def reset(self, seed: Optional[int] = None) -> dict:
        """Start a new game and return the first observation (see `result`)."""
        if seed is not None:
            self.__seed = seed
        rng = random.Random(self.__seed)
        self.__opponent_rng = random.Random(rng.random())
        if self.__decks is None:
            self.__game = Cribbage(rng=rng)
        else:
            self.__game = Cribbage(rng=rng, decks=self.__decks, first_dealer=self.__first_dealer)
        self.__ai = CribbageAI(self.__game, OPPONENT)
        self.__log = []
        self.__exhausted = False
        events = self.__game.deal()
        events += self.__advance()
        return self.__result(True, events)

    def step(self, action: dict) -> dict:
        """
        Apply the agent's action. Returns {"ok", "error", "events", "observation", "done"}.
        An illegal or malformed action returns ok=False with an error {"code", "message"} and
        changes nothing, so the agent can simply try again.
        """
        if self.__exhausted:
            return self.__result(False, [], {"code": "game_over", "message": "The game is over."})
        try:
            parsed = parse_action(action)
            events = self.__game.apply(AGENT, parsed)
        except IllegalAction as e:
            return self.__result(False, [], {"code": e.code, "message": e.message})
        events += self.__advance()
        return self.__result(True, events)

    def observation(self) -> dict:
        """The current observation."""
        game = self.__game
        state = game.state()
        if self.__exhausted:
            state = PlayState.COMPLETE
        phase = {
            PlayState.DISCARD: "discard",
            PlayState.PEGGING: "pegging",
            PlayState.COMPLETE: "complete",
        }.get(state, state.name.lower())
        cip = game.cards_in_play()
        revealed = state in (PlayState.PEGGING, PlayState.SHOW, PlayState.COMPLETE)
        actions = [_action_to_json(a) for a in game.legal_actions(AGENT)]
        winner = game.winner()
        obs = {
            "phase": phase,
            "you_score": game.points(AGENT),
            "opponent_score": game.points(OPPONENT),
            "target_score": WINNING_SCORE,
            "dealer": NAMES[game.dealer().name],
            "your_hand": [card_id(c) for c in game.hand(AGENT).cards()],
            "opponent_cards_in_hand": len(game.hand(OPPONENT).cards()),
            "crib_size": len(game.crib().cards()),
            "starter": card_id(game.starter()) if revealed else None,
            "count": cip.count(),
            "sequence": [
                {"player": NAMES[p.player.name], "card": card_id(p.card)} for p in cip.sequence()
            ],
            "played_this_round": [
                {"player": NAMES[p.player.name], "card": card_id(p.card)}
                for p in cip.played_cards()
            ],
            "legal_actions": actions,
            "winner": NAMES[winner.name] if winner else None,
        }
        obs["prompt"] = self.__prompt(obs)
        return obs

    @property
    def done(self) -> bool:
        return self.__game.state() == PlayState.COMPLETE or self.__exhausted

    # ---- internals --------------------------------------------------------------------

    def __advance(self) -> List[dict]:
        """Let the opponent act, count the show and deal the next round until it is the agent's move."""
        events: List[dict] = []
        game = self.__game
        while game.state() != PlayState.COMPLETE:
            if game.state() == PlayState.SHOW:
                try:
                    events += game.deal()
                except IllegalAction as e:
                    if e.code != "decks_exhausted":
                        raise
                    self.__exhausted = True
                    events.append({"type": "decks_exhausted"})
                    break
            elif OPPONENT in game.to_act():
                events += self.__opponent_act()
            else:
                break
        return events

    def __opponent_act(self) -> List[dict]:
        if self.__opponent_kind == "greedy":
            return self.__ai.act()
        actions = self.__game.legal_actions(OPPONENT)
        return self.__game.apply(OPPONENT, self.__opponent_rng.choice(actions))

    def __result(self, ok: bool, events: List[dict], error: Optional[dict] = None) -> dict:
        labelled = [_relabel(e) for e in events]
        self.__log += labelled
        return {
            "ok": ok,
            "error": error,
            "events": labelled,
            "observation": self.observation(),
            "done": self.done,
        }

    @staticmethod
    def __prompt(obs: dict) -> str:
        if obs["phase"] == "complete":
            if obs["winner"] is None:
                return f"Game over: the decks ran out at {obs['you_score']} to {obs['opponent_score']}."
            return f"Game over: {obs['winner']} won, {obs['you_score']} to {obs['opponent_score']}."
        if obs["phase"] == "discard":
            return (
                "Choose two cards from your hand to put in the crib "
                f"(the crib belongs to the dealer: {obs['dealer']}). Action: "
                '{"type": "discard", "cards": ["5H", "KS"]}'
            )
        return (
            f"Pegging: the count is {obs['count']}. Play one card that keeps the count at 31 or "
            'less. Action: {"type": "play", "card": "7D"}. If you cannot play, go is said for you.'
        )
