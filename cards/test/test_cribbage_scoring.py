"""
Tests for scoring hands in cribbage.
"""

import unittest
from cards.cribbage.scoring import (
    score_hand_fifteens,
    score_hand_pairs,
    score_hand_flush,
    score_hand_runs,
    score_hand_his_nobs,
)
from cards.cribbage.hand import Hand
from cards.cards.card_shortcuts import *  # pylint: disable=wildcard-import, unused-wildcard-import


class TestScoringFifteen(unittest.TestCase):
    """Test scoring fifteens."""

    def test_no_fifteens(self):
        """Test no 15s in hand."""
        hand = Hand([ACE_OF_HEARTS, ACE_OF_DIAMONDS, ACE_OF_SPADES, ACE_OF_CLUBS])
        starter = TWO_OF_HEARTS
        score, _ = score_hand_fifteens(hand, starter)
        self.assertEqual(score, 0)

    def test_best_hand(self):
        """Test a very high scoring hand."""
        hand = Hand([HJ, D5, S5, C5])
        starter = H5
        score, _ = score_hand_fifteens(hand, starter)
        self.assertEqual(score, 16)

    def test_67895(self):
        """Test a 6, 7, 8, 9 with a 5"""
        hand = Hand([H6, D7, S8, C9])
        starter = H5
        score, _ = score_hand_fifteens(hand, starter)
        self.assertEqual(score, 4)

    def test_33456(self):
        """Test a 3, 3, 4, 5 with a 6"""
        hand = Hand([H3, D3, S4, C5])
        starter = H6
        score, _ = score_hand_fifteens(hand, starter)
        self.assertEqual(score, 4)

    def test_jj55a(self):
        """Test a J, J, 5, 5 with an A"""
        hand = Hand([HJ, DJ, S5, CA])
        starter = H5
        score, _ = score_hand_fifteens(hand, starter)
        self.assertEqual(score, 8)


class TestScoringPair(unittest.TestCase):
    """Test scoring pairs."""

    def test_double_pair_royal(self):
        """Test a double pair royal (four aces)."""
        hand = Hand([ACE_OF_HEARTS, ACE_OF_DIAMONDS, ACE_OF_SPADES, ACE_OF_CLUBS])
        starter = TWO_OF_HEARTS
        score, _ = score_hand_pairs(hand, starter)
        self.assertEqual(score, 12)

    def test_pair_royal(self):
        """Test a pair royal (three aces)."""
        hand = Hand([ACE_OF_HEARTS, ACE_OF_DIAMONDS, ACE_OF_SPADES, C5])
        starter = HJ
        score, _ = score_hand_pairs(hand, starter)
        self.assertEqual(score, 6)

    def test_pair_royal_and_pair(self):
        """Test a pair royal and a pair."""
        hand = Hand([ACE_OF_HEARTS, ACE_OF_DIAMONDS, ACE_OF_SPADES, C5])
        starter = H5
        score, _ = score_hand_pairs(hand, starter)
        self.assertEqual(score, 8)

    def test_single_pair_with_starter(self):
        """Test a pair with the starter card."""
        hand = Hand([HJ, D8, S7, C6])
        starter = HJ
        score, _ = score_hand_pairs(hand, starter)
        self.assertEqual(score, 2)

    def test_single_pair(self):
        """Test a single pair."""
        hand = Hand([HJ, D8, S8, C6])
        starter = HA
        score, _ = score_hand_pairs(hand, starter)
        self.assertEqual(score, 2)

    def test_double_pair(self):
        """Test two pairs."""
        hand = Hand([HJ, D8, S8, C6])
        starter = H6
        score, _ = score_hand_pairs(hand, starter)
        self.assertEqual(score, 4)

    def test_no_pairs(self):
        """Test no pairs."""
        hand = Hand([HJ, DQ, SK, CT])
        starter = HA
        score, _ = score_hand_pairs(hand, starter)
        self.assertEqual(score, 0)


class TestScoringFlush(unittest.TestCase):
    """Test scoring of flushes."""

    def test_no_flush(self):
        """Test no flushes."""
        hand = Hand([HJ, DQ, SK, CT])
        starter = HA
        score, _ = score_hand_flush(hand, starter)
        self.assertEqual(score, 0)

    def test_no_flush_4_same_suit(self):
        """Test no flush but 4 of the same suit."""
        hand = Hand([HJ, HQ, HK, DA])
        starter = HT
        score, _ = score_hand_flush(hand, starter)
        self.assertEqual(score, 0)

    def test_flush(self):
        """Test 4 flush."""
        hand = Hand([HJ, HQ, HK, HA])
        starter = DT
        score, _ = score_hand_flush(hand, starter)
        self.assertEqual(score, 4)

    def test_flush_with_starter(self):
        """Test 5 flush."""
        hand = Hand([HJ, HQ, HK, HA])
        starter = HT
        score, _ = score_hand_flush(hand, starter)
        self.assertEqual(score, 5)

    def test_flush_in_crib(self):
        """Test 5 flush in the crib."""
        hand = Hand([HJ, HQ, HK, HA], is_crib=True)
        starter = HT
        score, _ = score_hand_flush(hand, starter)
        self.assertEqual(score, 5)

    def test_4_flush_in_crib(self):
        """Test no flush but 4 of the same suit in the crib."""
        hand = Hand([HJ, HQ, HK, HA], is_crib=True)
        starter = DT
        score, _ = score_hand_flush(hand, starter)
        self.assertEqual(score, 0)

    def test_no_flush_bug(self):
        """Test that the first card suit matching the starter suit is not a flush."""
        hand = Hand([S7, D10, HK, CK])
        starter = S9
        score, _ = score_hand_flush(hand, starter)
        self.assertEqual(score, 0)


class TestScoringNobs(unittest.TestCase):
    """Test scoring his nobs."""

    def test_no_his_nobs(self):
        """Test no his nobs."""
        hand = Hand([SJ, DQ, SK, CT])
        starter = HA
        score, _ = score_hand_his_nobs(hand, starter)
        self.assertEqual(score, 0)

    def test_his_nobs(self):
        """Test his nobs."""
        hand = Hand([HJ, DQ, SK, CT])
        starter = HA
        score, _ = score_hand_his_nobs(hand, starter)
        self.assertEqual(score, 1)

    def test_his_nobs_in_crib(self):
        """Test his nobs in the crib."""
        hand = Hand([HJ, DQ, SK, CT], is_crib=True)
        starter = H5
        score, _ = score_hand_his_nobs(hand, starter)
        self.assertEqual(score, 1)

    def test_no_his_nobs_in_crib(self):
        """Test no his nobs in the crib."""
        hand = Hand([SA, DQ, SJ, CT], is_crib=True)
        starter = D5
        score, _ = score_hand_his_nobs(hand, starter)
        self.assertEqual(score, 0)


class TestScoringRuns(unittest.TestCase):
    """Test scoring runs."""

    def test_no_runs(self):
        """Test no runs."""
        hand = Hand([HA, D3, S5, C6])
        starter = H9
        score, _ = score_hand_runs(hand, starter)
        self.assertEqual(score, 0)

    def test_run_of_3(self):
        """Test run of 3."""
        hand = Hand([H3, D4, S5, C7])
        starter = H9
        score, _ = score_hand_runs(hand, starter)
        self.assertEqual(score, 3)

    def test_double_run_of_3(self):
        """Test double run of 3."""
        hand = Hand([H3, D4, S5, C4])
        starter = H9
        score, _ = score_hand_runs(hand, starter)
        self.assertEqual(score, 6)

    def test_double_run_of_3_starter(self):
        """Test double run of 3 with the starter."""
        hand = Hand([H3, D4, S5, C7])
        starter = H3
        score, _ = score_hand_runs(hand, starter)
        self.assertEqual(score, 6)

    def test_run_of_4(self):
        """Test run of 4."""
        hand = Hand([H3, D4, S5, C6])
        starter = HA
        score, _ = score_hand_runs(hand, starter)
        self.assertEqual(score, 4)

    def test_double_run_of_4(self):
        """Test double run of 4."""
        hand = Hand([H3, D4, S5, C6])
        starter = H4
        score, _ = score_hand_runs(hand, starter)
        self.assertEqual(score, 8)

    def test_run_of_5(self):
        """Test run of 5."""
        hand = Hand([H3, D4, S5, C6])
        starter = H7
        score, _ = score_hand_runs(hand, starter)
        self.assertEqual(score, 5)

    def test_triple_run_of_3(self):
        """Test triple run of 3."""
        hand = Hand([H3, D4, S4, C4])
        starter = H5
        score, _ = score_hand_runs(hand, starter)
        self.assertEqual(score, 9)

    def test_double_double_run_of_3(self):
        """Test double double run of 3."""
        hand = Hand([H3, D4, S4, C5])
        starter = H3
        score, _ = score_hand_runs(hand, starter)
        self.assertEqual(score, 12)

    def test_run_of_face_cards(self):
        """Test run of face cards."""
        hand = Hand([HJ, DK, SQ, CA])
        starter = H9
        score, _ = score_hand_runs(hand, starter)
        self.assertEqual(score, 3)

    def test_double_run_of_2(self):
        """Test double run of 2 is not a run."""
        hand = Hand([C7, S7, S8, SJ])
        starter = C2
        score, _ = score_hand_runs(hand, starter)
        self.assertEqual(score, 0)

    def test_2qqk9(self):
        """Test 2, Q, Q, K with a 9 is not a run."""
        hand = Hand([D2, CQ, SQ, CK])
        starter = S9
        score, _ = score_hand_runs(hand, starter)
        self.assertEqual(score, 0)


if __name__ == "__main__":
    unittest.main()
