class RollingWinrate:
    """
    Manages incremental Winrate calculations (Rolling Window).
    Prevents Data Leakage by ensuring that a champion's statistics
    are based only on past matches within the SAME PATCH.
    """
    def __init__(self):
        self.current_patch = None

        # Structure: { (champion_id, role_index, side_id): {'wins': 0, 'games': 0} }
        # side_id: 100 for Blue, 200 for Red
        self.stats_role_side = {}

        # Structure: { (champion_id, enemy_champion_id, role_index): {'wins': 0, 'games': 0} }
        self.stats_matchup = {}

        # Position names for return dictionary keys
        self.positions = ['top', 'jungle', 'mid', 'adc', 'support']

    def _reset_if_new_patch(self, patch):
        """
        Resets all statistics if the patch has changed.
        """
        if self.current_patch != patch:
            self.current_patch = patch
            self.stats_role_side = {}
            self.stats_matchup = {}

    def _get_laplace_winrate(self, wins, games):
        """
        Calculates winrate using Laplace Smoothing.
        Formula: (Wins + 1) / (Games + 2)
        Pushes champions with few games towards 50% WR.
        """
        return (wins + 1) / (games + 2)

    def get_features(self, blue_team_ids, red_team_ids, patch):
        """
        Generates features based on accumulated history.
        Includes:
        - Winrate by Role + Side
        - Winrate by Matchup (Champion vs Enemy in same role)

        Automatically handles patch reset if a new patch is detected
        (though 'update' is responsible for populating).
        """
        self._reset_if_new_patch(patch)

        features = {}

        # Iterate through the 5 roles
        for i in range(5):
            pos = self.positions[i]

            # --- Blue Team Analysis ---
            blue_champ = blue_team_ids[i]
            red_champ = red_team_ids[i] # Direct opponent

            # 1. Role + Side Winrate (Blue Side = 100)
            rs_key = (blue_champ, i, 100)
            rs_data = self.stats_role_side.get(rs_key, {'wins': 0, 'games': 0})
            features[f'blue_{pos}_role_side_wr'] = self._get_laplace_winrate(rs_data['wins'], rs_data['games'])

            # 2. Matchup Winrate (Blue Champ vs Red Champ)
            # From Blue's perspective: did Blue Champ win against Red Champ?
            mu_key = (blue_champ, red_champ, i)
            mu_data = self.stats_matchup.get(mu_key, {'wins': 0, 'games': 0})
            features[f'blue_{pos}_matchup_wr'] = self._get_laplace_winrate(mu_data['wins'], mu_data['games'])

            # --- Red Team Analysis ---

            # 1. Role + Side Winrate (Red Side = 200)
            rs_key_red = (red_champ, i, 200)
            rs_data_red = self.stats_role_side.get(rs_key_red, {'wins': 0, 'games': 0})
            features[f'red_{pos}_role_side_wr'] = self._get_laplace_winrate(rs_data_red['wins'], rs_data_red['games'])

            # 2. Matchup Winrate (Red Champ vs Blue Champ)
            # From Red's perspective: did Red Champ win against Blue Champ?
            # Note: We track matchups as (MyChamp, EnemyChamp).
            # So for Red, it is (RedChamp, BlueChamp).
            mu_key_red = (red_champ, blue_champ, i)
            mu_data_red = self.stats_matchup.get(mu_key_red, {'wins': 0, 'games': 0})
            features[f'red_{pos}_matchup_wr'] = self._get_laplace_winrate(mu_data_red['wins'], mu_data_red['games'])

        return features

    def update(self, blue_team_ids, red_team_ids, winner_team, patch):
        """
        Updates victory and game history after the match ends.
        winner_team: 100 or 1 for Blue, 200 or 0 for Red.
        """
        self._reset_if_new_patch(patch)

        # Normalize winner to boolean (True if Blue won)
        blue_won = (winner_team == 1 or winner_team == 100)

        for i in range(5):
            blue_champ = blue_team_ids[i]
            red_champ = red_team_ids[i]

            # --- Update Blue Team (Side 100) ---
            # Role + Side
            rs_key_blue = (blue_champ, i, 100)
            if rs_key_blue not in self.stats_role_side:
                self.stats_role_side[rs_key_blue] = {'wins': 0, 'games': 0}
            self.stats_role_side[rs_key_blue]['games'] += 1
            if blue_won:
                self.stats_role_side[rs_key_blue]['wins'] += 1

            # Matchup (Blue vs Red)
            mu_key_blue = (blue_champ, red_champ, i)
            if mu_key_blue not in self.stats_matchup:
                self.stats_matchup[mu_key_blue] = {'wins': 0, 'games': 0}
            self.stats_matchup[mu_key_blue]['games'] += 1
            if blue_won:
                self.stats_matchup[mu_key_blue]['wins'] += 1

            # --- Update Red Team (Side 200) ---
            # Role + Side
            rs_key_red = (red_champ, i, 200)
            if rs_key_red not in self.stats_role_side:
                self.stats_role_side[rs_key_red] = {'wins': 0, 'games': 0}
            self.stats_role_side[rs_key_red]['games'] += 1
            if not blue_won:
                self.stats_role_side[rs_key_red]['wins'] += 1

            # Matchup (Red vs Blue)
            mu_key_red = (red_champ, blue_champ, i)
            if mu_key_red not in self.stats_matchup:
                self.stats_matchup[mu_key_red] = {'wins': 0, 'games': 0}
            self.stats_matchup[mu_key_red]['games'] += 1
            if not blue_won:
                self.stats_matchup[mu_key_red]['wins'] += 1
