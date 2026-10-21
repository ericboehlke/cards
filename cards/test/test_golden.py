"""
Golden fixture tests: the committed fixtures in testdata/golden must match what the Python
implementation produces now, and deck injection must behave as documented.
"""

import unittest
from pathlib import Path

import gen_golden
from cards.cards.card import card_from_id
from cards.cribbage.api import CribbageEnv
from cards.cribbage.cribbage import Cribbage, IllegalAction, PlayState
from cards.cribbage.players import Player

SEED_HAND = (3, ["4H", "5D", "7C", "8D", "8S", "JH"])  # recorded before decks were added
GOLDEN = Path(__file__).resolve().parents[2] / "testdata" / "golden"


class TestGoldenFixtures(unittest.TestCase):
    """Regenerate every fixture in memory and compare it with the committed file."""

    @classmethod
    def setUpClass(cls):
        cls.generated = gen_golden.build_all()

    def test_fixtures_match(self):
        for filename, text in self.generated.items():
            with self.subTest(filename):
                committed = (GOLDEN / filename).read_text()
                self.assertEqual(
                    committed,
                    text,
                    f"{filename} is out of date; run python -m cards.test.gen_golden --out testdata/golden",
                )

    def test_no_stray_fixtures(self):
        self.assertEqual(
            sorted(p.name for p in GOLDEN.glob("*.json")), sorted(self.generated)
        )

    def test_generation_is_deterministic(self):
        self.assertEqual(self.generated, gen_golden.build_all())


class TestDeckInjection(unittest.TestCase):
    """CribbageEnv(decks=...) and Cribbage(decks=...)."""

    def setUp(self):
        self.decks = gen_golden.random_decks(5)

    def test_cards_are_dealt_from_the_top(self):
        env = CribbageEnv(decks=self.decks, first_dealer="opponent")
        obs = env.observation()
        self.assertEqual(sorted(obs["your_hand"]), sorted(self.decks[0][:6]))
        self.assertEqual(obs["dealer"], "opponent")
        self.assertEqual(obs["opponent_cards_in_hand"], 4)  # it has already discarded

    def test_same_decks_same_game_and_reset_replays(self):
        first = gen_golden.play_game("a", 5, "you", probe=False)
        second = gen_golden.play_game("a", 5, "you", probe=False)
        self.assertEqual(first, second)
        env = CribbageEnv(decks=self.decks)
        self.assertEqual(env.reset(), env.reset())

    def test_decks_exhausted(self):
        game = Cribbage(decks=[[card_from_id(c) for c in self.decks[0]]], first_dealer=Player.PLAYER1)
        game.deal()
        while game.state() != PlayState.SHOW:
            player = game.to_act()[0]
            game.apply(player, game.legal_actions(player)[0])
        with self.assertRaises(IllegalAction) as raised:
            game.deal()
        self.assertEqual(raised.exception.code, "decks_exhausted")

    def test_bad_decks_rejected(self):
        with self.assertRaises(ValueError):
            CribbageEnv(decks=[self.decks[0][:51]])
        with self.assertRaises(ValueError):
            Cribbage(decks=[], first_dealer=None)
        with self.assertRaises(ValueError):
            CribbageEnv(decks=self.decks, first_dealer="nobody")

    def test_seeded_behaviour_unchanged(self):
        self.assertEqual(CribbageEnv(seed=3).observation(), CribbageEnv(seed=3).observation())
        self.assertEqual(
            CribbageEnv(seed=SEED_HAND[0]).observation()["your_hand"], SEED_HAND[1]
        )

    def test_empty_decks_rejected(self):
        with self.assertRaises(ValueError):
            CribbageEnv(decks=[])

    def test_duplicate_card_deck_rejected(self):
        bad = list(self.decks[0])
        bad[1] = bad[0]
        with self.assertRaises(ValueError):
            CribbageEnv(decks=[bad])
        with self.assertRaises(ValueError):
            Cribbage(decks=[[card_from_id(c) for c in bad]], first_dealer=Player.PLAYER1)

    def test_default_first_dealer_is_you(self):
        self.assertEqual(CribbageEnv(decks=self.decks).observation()["dealer"], "you")

    def test_dealer_alternates(self):
        env = CribbageEnv(decks=self.decks, first_dealer="you")
        dealers = [env.observation()["dealer"]]
        result = env.reset()
        while not result["done"]:
            result = env.step(result["observation"]["legal_actions"][0])
            for event in result["events"]:
                if event["type"] == "deal":
                    dealers.append(event["dealer"])
        self.assertGreater(len(dealers), 2)
        for i, dealer in enumerate(dealers):
            self.assertEqual(dealer, "you" if i % 2 == 0 else "opponent")

    def test_caller_mutating_decks_has_no_effect(self):
        decks = [list(d) for d in self.decks]
        env = CribbageEnv(decks=decks)
        expected = env.observation()["your_hand"]
        decks[0].reverse()
        decks.clear()
        self.assertEqual(env.reset()["observation"]["your_hand"], expected)

    def test_exhaustion_in_env_ends_game_cleanly(self):
        env = CribbageEnv(decks=self.decks[:1])
        result = env.reset()
        while not result["done"]:
            result = env.step(result["observation"]["legal_actions"][0])
        self.assertEqual(result["events"][-1]["type"], "decks_exhausted")
        obs = result["observation"]
        self.assertTrue(result["ok"])
        self.assertEqual(obs["phase"], "complete")
        self.assertIsNone(obs["winner"])
        self.assertEqual(obs["legal_actions"], [])
        again = env.step({"type": "play", "card": "AH"})
        self.assertFalse(again["ok"])
        self.assertEqual(again["error"]["code"], "game_over")
        self.assertEqual(env.observation(), obs)

    def test_no_state_change_after_decks_exhausted_in_engine(self):
        game = Cribbage(decks=[[card_from_id(c) for c in self.decks[0]]], first_dealer=Player.PLAYER1)
        game.deal()
        while game.state() != PlayState.SHOW:
            player = game.to_act()[0]
            game.apply(player, game.legal_actions(player)[0])
        before = (game.state(), game.dealer(), game.points(Player.PLAYER1), game.points(Player.PLAYER2))
        with self.assertRaises(IllegalAction):
            game.deal()
        after = (game.state(), game.dealer(), game.points(Player.PLAYER1), game.points(Player.PLAYER2))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
