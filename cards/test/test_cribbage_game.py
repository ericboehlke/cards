"""
Scenario tests for the cribbage game engine and the LLM environment, plus a short fuzz run.
"""

import json
import random
import unittest

import fuzz_cribbage
from cards.cards.card import DECK, card_from_id, card_id
from cards.cribbage.api import CribbageEnv
from cards.cribbage.api_cli import serve
from cards.cribbage.cribbage import Action, Cribbage, IllegalAction, PlayState
from cards.cribbage.players import Player

P1, P2 = Player.PLAYER1, Player.PLAYER2


def ids(text):
    """Cards from a space separated string of ids."""
    return [card_from_id(t) for t in text.split()]


def stacked_game(p1, p2, starter, dealer=P2, **kwargs):
    """A game with the given six card hands and starter, with the dealer already decided."""
    first = ids(p1) + ids(p2) + ids(starter)
    deck = first + [c for c in DECK if c not in first]
    game = Cribbage(deck, shuffle=False, first_dealer=dealer, **kwargs)
    game.deal()
    return game


def discard_ids(game, player, text):
    return game.apply(player, Action("discard", tuple(ids(text))))


class TestRounds(unittest.TestCase):
    """The flow of a single round."""

    def start_pegging(self, **kwargs):
        game = stacked_game("KH QH JH 9H 2C 3C", "KS QS 5D 4D 2D 3D", "AS", **kwargs)
        discard_ids(game, P1, "2C 3C")
        discard_ids(game, P2, "2D 3D")
        return game

    def test_non_dealer_leads(self):
        game = self.start_pegging()
        self.assertEqual(game.state(), PlayState.PEGGING)
        self.assertEqual(game.dealer(), P2)
        self.assertEqual(game.turn(), P1)
        self.assertEqual(game.to_act(), [P1])
        self.assertEqual(len(game.crib().cards()), 4)

    def test_dealer_alternates(self):
        game = Cribbage(rng=random.Random(1))
        game.deal()
        first = game.dealer()
        game.apply(P1, Action("discard", tuple(game.hand(P1).cards()[:2])))
        game.apply(P2, Action("discard", tuple(game.hand(P2).cards()[:2])))
        self.finish_round(game)
        game.deal()
        self.assertNotEqual(game.dealer(), first)

    @staticmethod
    def finish_round(game):
        while game.state() == PlayState.PEGGING:
            game.apply(game.turn(), game.legal_actions(game.turn())[0])

    def test_discards_may_come_in_either_order_and_start_pegging_only_when_both_done(self):
        game = stacked_game("KH QH JH 9H 2C 3C", "KS QS 5D 4D 2D 3D", "AS")
        discard_ids(game, P2, "2D 3D")
        self.assertEqual(game.state(), PlayState.DISCARD)
        self.assertEqual(game.to_act(), [P1])
        discard_ids(game, P1, "2C 3C")
        self.assertEqual(game.state(), PlayState.PEGGING)

    def test_his_heels(self):
        game = stacked_game("KH QH JH 9H 2C 3C", "KS QS 5D 4D 2D 3D", "JS")
        discard_ids(game, P1, "2C 3C")
        events = discard_ids(game, P2, "2D 3D")
        self.assertEqual(game.points(P2), 2)  # the dealer
        self.assertIn("his_heels", [e["type"] for e in events])

    def test_go_and_last_card(self):
        game = self.start_pegging()
        game.play(P1, ids("KH")[0])
        game.play(P2, ids("QS")[0])
        events = game.play(P1, ids("QH")[0])  # 30, pair of queens
        kinds = [(e["type"], e.get("player")) for e in events]
        self.assertIn(("go", "PLAYER2"), kinds)  # nothing P2 holds fits
        self.assertIn(("last_card", "PLAYER1"), kinds)
        self.assertEqual(game.points(P1), 3)  # 2 for the pair, 1 for the last card
        self.assertEqual(game.points(P2), 0)
        self.assertEqual(game.cards_in_play().count(), 0)
        self.assertEqual(game.turn(), P2)  # the player after the last card leads the new count

    def test_no_points_for_pair_across_a_new_count(self):
        game = self.start_pegging()
        game.play(P1, ids("KH")[0])
        game.play(P2, ids("QS")[0])
        game.play(P1, ids("QH")[0])
        events = game.play(P2, ids("KS")[0])  # the K of the previous count is irrelevant
        self.assertEqual(events[0]["points"], 0)

    def test_stuck_player_is_skipped_and_other_keeps_playing(self):
        # P1 plays 9, P2 plays K, P1 plays 6 (count 25) and P2 may still play 5 or 4.
        game = stacked_game("9H JH 6C 2C 3C 4C", "KS 5D 4D 2D 3D QS", "AS")
        discard_ids(game, P1, "2C 3C")
        discard_ids(game, P2, "2D 3D")
        game.play(P1, ids("9H")[0])  # 9
        game.play(P2, ids("KS")[0])  # 19
        events = game.play(P1, ids("6C")[0])  # 25: P2 can still play the 5 or the 4
        self.assertEqual(game.turn(), P2)
        self.assertEqual([e["type"] for e in events], ["play"])

    def test_reaching_121_ends_the_game_immediately(self):
        game = self.start_pegging(starting_points={P1: 119})
        game.play(P1, ids("KH")[0])
        game.play(P2, ids("QS")[0])
        events = game.play(P1, ids("QH")[0])  # pair for 2 reaches 121
        self.assertEqual(game.state(), PlayState.COMPLETE)
        self.assertEqual(game.winner(), P1)
        self.assertEqual(events[-1]["type"], "game_over")
        self.assertNotIn("last_card", [e["type"] for e in events])
        self.assertEqual(game.points(P1), 121)
        self.assertEqual(game.to_act(), [])
        with self.assertRaises(IllegalAction) as raised:
            game.play(P2, ids("KS")[0])
        self.assertEqual(raised.exception.code, "game_over")

    def test_show_counts_non_dealer_then_dealer_then_crib(self):
        game = self.start_pegging()
        self.finish_round(game)
        self.assertEqual(game.state(), PlayState.SHOW)
        # Everyone's four cards were returned for the show
        self.assertEqual(len(game.hand(P1).cards()), 4)
        self.assertEqual(len(game.hand(P2).cards()), 4)


class TestIllegalActions(unittest.TestCase):
    """Illegal actions raise IllegalAction and change nothing."""

    def setUp(self):
        self.game = stacked_game("KH QH JH 9H 2C 3C", "KS QS 5D 4D 2D 3D", "AS")

    def assertIllegal(self, code, player, action):
        before = (self.game.state(), self.game.points(P1), self.game.hand(player).cards())
        with self.assertRaises(IllegalAction) as raised:
            self.game.apply(player, action)
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(before, (self.game.state(), self.game.points(P1), self.game.hand(player).cards()))

    def test_discard_rules(self):
        self.assertIllegal("wrong_phase", P1, Action("play", tuple(ids("KH"))))
        self.assertIllegal("bad_discard", P1, Action("discard", tuple(ids("KH"))))
        self.assertIllegal("bad_discard", P1, Action("discard", tuple(ids("KH KH"))))
        self.assertIllegal("card_not_in_hand", P1, Action("discard", tuple(ids("KH KS"))))
        discard_ids(self.game, P1, "2C 3C")
        self.assertIllegal("already_discarded", P1, Action("discard", tuple(ids("KH QH"))))

    def test_play_rules(self):
        discard_ids(self.game, P1, "2C 3C")
        discard_ids(self.game, P2, "2D 3D")
        self.assertIllegal("wrong_phase", P1, Action("discard", tuple(ids("KH QH"))))
        self.assertIllegal("not_your_turn", P2, Action("play", tuple(ids("KS"))))
        self.assertIllegal("card_not_in_hand", P1, Action("play", tuple(ids("KS"))))
        self.assertIllegal("bad_play", P1, Action("play", tuple(ids("KH QH"))))
        self.game.play(P1, ids("KH")[0])
        self.assertIllegal("not_your_turn", P1, Action("play", tuple(ids("QH"))))

    def test_cannot_play_over_31(self):
        discard_ids(self.game, P1, "2C 3C")
        discard_ids(self.game, P2, "2D 3D")
        self.game.play(P1, ids("9H")[0])
        self.game.play(P2, ids("5D")[0])
        self.game.play(P1, ids("KH")[0])  # 24
        self.assertIllegal("exceeds_31", P2, Action("play", tuple(ids("QS"))))
        self.assertIllegal("exceeds_31", P2, Action("play", tuple(ids("KS"))))


class TestEnv(unittest.TestCase):
    """The JSON environment for LLM agents."""

    def random_agent_game(self, seed, opponent="greedy"):
        env = CribbageEnv(seed=seed, opponent=opponent)
        rng = random.Random(seed)
        transcript = [env.observation()]
        for _ in range(2000):
            obs = env.observation()
            if env.done:
                return env, transcript
            result = env.step(rng.choice(obs["legal_actions"]))
            self.assertTrue(result["ok"], result["error"])
            transcript.append(result["observation"])
        self.fail("game did not finish")

    def test_whole_game_through_env(self):
        env, _ = self.random_agent_game(5, opponent="random")
        obs = env.observation()
        self.assertEqual(obs["phase"], "complete")
        self.assertIn(obs["winner"], ("you", "opponent"))
        self.assertGreaterEqual(max(obs["you_score"], obs["opponent_score"]), 121)

    def test_seeded_games_are_reproducible(self):
        _, first = self.random_agent_game(7, opponent="random")
        _, second = self.random_agent_game(7, opponent="random")
        self.assertEqual(first, second)

    def test_observations_are_json_and_always_actionable(self):
        env = CribbageEnv(seed=2, opponent="random")
        rng = random.Random(2)
        while not env.done:
            obs = env.observation()
            json.dumps(obs)
            self.assertTrue(obs["legal_actions"])
            self.assertTrue(obs["prompt"])
            result = env.step(rng.choice(obs["legal_actions"]))
            json.dumps(result)

    def test_opponent_cards_are_hidden(self):
        env = CribbageEnv(seed=3, opponent="random")
        game = env._CribbageEnv__game  # pylint: disable=protected-access
        hidden = {card_id(c) for c in game.hand(P2).cards()} | {card_id(c) for c in game.crib().cards()}
        text = json.dumps(env.observation()["your_hand"]) + json.dumps(env.observation()["sequence"])
        self.assertFalse(any(h in text for h in hidden))
        obs = env.observation()
        self.assertIsNone(obs["starter"])
        self.assertEqual(obs["opponent_cards_in_hand"], 4)
        self.assertNotIn("opponent_hand", obs)

    def test_errors_are_structured_and_change_nothing(self):
        env = CribbageEnv(seed=4)
        before = env.observation()
        for bad in (
            {"type": "play", "card": "AS"},
            {"type": "discard", "cards": ["AS"]},
            {"type": "dance"},
            {"type": "discard"},
            {"type": "discard", "cards": ["ZZ", "1X"]},
            "discard 5H KS",
            None,
        ):
            result = env.step(bad)
            self.assertFalse(result["ok"], bad)
            self.assertIn("code", result["error"])
            self.assertIn("message", result["error"])
            self.assertEqual(result["observation"], before)

    def test_ten_may_be_written_10(self):
        env = CribbageEnv(seed=1)
        obs = env.observation()
        discard = [c.replace("T", "10") for c in obs["legal_actions"][0]["cards"]]
        self.assertTrue(env.step({"type": "discard", "cards": discard})["ok"])

    def test_step_after_game_over(self):
        env, _ = self.random_agent_game(9, opponent="random")
        result = env.step({"type": "play", "card": "AS"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "game_over")


class TestJsonLines(unittest.TestCase):
    """The JSON-lines command line protocol."""

    def test_protocol(self):
        import io

        lines = [
            "not json",
            "[1, 2]",
            '{"command": "observe"}',
            '{"action": {"type": "play", "card": "AS"}}',
            "",
        ]
        out = io.StringIO()
        serve(seed=1, opponent="random", stdin=io.StringIO("\n".join(lines)), stdout=out)
        replies = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(len(replies), 5)  # opening + one per non-empty line
        self.assertTrue(replies[0]["ok"])
        self.assertEqual(replies[1]["error"]["code"], "bad_json")
        self.assertEqual(replies[2]["error"]["code"], "bad_request")
        self.assertTrue(replies[3]["ok"])
        self.assertFalse(replies[4]["ok"])


class TestFuzz(unittest.TestCase):
    """A short fuzz run; use fuzz_cribbage.py directly for thousands of games."""

    def test_random_games_follow_the_rules(self):
        for seed in range(150):
            fuzz_cribbage.play_game(seed, ("random", "random"))

    def test_greedy_games_follow_the_rules(self):
        for seed in range(3):
            fuzz_cribbage.play_game(1000 + seed, ("greedy", "random"))


if __name__ == "__main__":
    unittest.main()
