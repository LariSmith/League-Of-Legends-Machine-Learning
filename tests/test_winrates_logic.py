import unittest
import sys
import os

# Add src to path to import the class
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'process_data', 'features'))

try:
    from winrates import RollingWinrate
except ImportError:
    # If run from root
    sys.path.append(os.path.join(os.getcwd(), 'src', 'process_data', 'features'))
    from winrates import RollingWinrate

class TestRollingWinrate(unittest.TestCase):
    def setUp(self):
        self.wr = RollingWinrate()

    def test_patch_reset(self):
        # Match 1 on Patch 14.1
        # Blue Team: [1, 2, 3, 4, 5] (Won)
        # Red Team:  [6, 7, 8, 9, 10]
        # Top Lane: 1 vs 6
        self.wr.update([1, 2, 3, 4, 5], [6, 7, 8, 9, 10], 100, "14.1")

        # Check features for same patch, should have data
        # Check Champion 1 (Blue Top)
        # 1 win, 1 game -> (1+1)/(1+2) = 0.666...
        feats = self.wr.get_features([1, 2, 3, 4, 5], [6, 7, 8, 9, 10], "14.1")

        self.assertAlmostEqual(feats['blue_top_role_side_wr'], 2/3, places=2)

        # Change Patch to 14.2
        # Data should be wiped. Champion 1 should be back to 0.5 (0 wins, 0 games)
        # (0+1)/(0+2) = 0.5
        feats_new_patch = self.wr.get_features([1, 2, 3, 4, 5], [6, 7, 8, 9, 10], "14.2")
        self.assertEqual(feats_new_patch['blue_top_role_side_wr'], 0.5)

    def test_granularity(self):
        # Match 1: Blue [1...] vs Red [6...] (Blue Wins)
        # Champ 1 is Top Blue
        self.wr.update([1, 2, 3, 4, 5], [6, 7, 8, 9, 10], 100, "14.1")

        # Scenario 1: Champ 1 plays Top Blue again.
        # Should have high winrate (0.66)
        feats = self.wr.get_features([1, 2, 3, 4, 5], [6, 7, 8, 9, 10], "14.1")
        self.assertAlmostEqual(feats['blue_top_role_side_wr'], 2/3, places=2)

        # Scenario 2: Champ 1 plays Top RED.
        # Should have no history for RED side Top. -> 0.5
        # We simulate a match where Red Team has champ 1 at Top (index 0)
        feats_red = self.wr.get_features([11, 12, 13, 14, 15], [1, 7, 8, 9, 10], "14.1")
        self.assertEqual(feats_red['red_top_role_side_wr'], 0.5)

    def test_matchup_logic(self):
        # Match 1: Blue Top (1) vs Red Top (6). Blue Wins.
        self.wr.update([1, 2, 3, 4, 5], [6, 7, 8, 9, 10], 100, "14.1")

        # Check Matchup: 1 vs 6
        # From Blue (1) perspective: Won against 6. -> 0.66
        feats = self.wr.get_features([1, 2, 3, 4, 5], [6, 7, 8, 9, 10], "14.1")
        self.assertAlmostEqual(feats['blue_top_matchup_wr'], 2/3, places=2)

        # From Red (6) perspective: Lost against 1. -> (0+1)/(1+2) = 0.33
        self.assertAlmostEqual(feats['red_top_matchup_wr'], 1/3, places=2)

        # Check Matchup: 1 vs 99 (New opponent)
        # Should be 0.5
        feats_new_opp = self.wr.get_features([1, 2, 3, 4, 5], [99, 7, 8, 9, 10], "14.1")
        self.assertEqual(feats_new_opp['blue_top_matchup_wr'], 0.5)

if __name__ == '__main__':
    unittest.main()
