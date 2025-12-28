import numpy as np
import collections

class PlayerProficiency:
    """
    Tracks player performance on specific champions over time to generate
    predictive features (Win Rate, Usage, Gold/XP averages, Lethality).

    Prevents data leakage by updating stats *after* features are generated.
    """
    def __init__(self):
        # Structure:
        # self.player_stats[puuid] = {
        #     'total_games': 0,
        #     'patches': { '14.1': 0, ... },
        #     'champions': {
        #         champion_id: {
        #             'history': deque([...]),  # Stores last N match outcomes
        #             'stats_sums': {...},      # Stores sums for long-term averages (Gold, XP)
        #             'stats_counts': {...},    # Counts for long-term averages
        #             'patch_stats': {          # Per-patch aggregates
        #                 '14.1': {'kills': 0, 'deaths': 0, 'games': 0}
        #             }
        #         }
        #     }
        # }
        self.player_stats = {}

        # Configuration
        self.WINRATE_WINDOW = 10
        self.LETHALITY_WINDOW = 15

    def _init_player(self, puuid):
        if puuid not in self.player_stats:
            self.player_stats[puuid] = {
                'total_games': 0,
                'patches': collections.defaultdict(int),
                'champions': {}
            }

    def _init_champion(self, puuid, champion_id):
        if champion_id not in self.player_stats[puuid]['champions']:
            self.player_stats[puuid]['champions'][champion_id] = {
                # History for sliding windows: list of dicts
                # Each dict: {'win': 0/1, 'kills': int, 'deaths': int, 'patch': str}
                'history': [],

                # Long-term accumulators for Gold/XP
                'total_gold_15': 0, 'count_gold_15': 0,
                'total_gold_30': 0, 'count_gold_30': 0,
                'total_gold_40': 0, 'count_gold_40': 0,
                'total_xp_15': 0, 'count_xp_15': 0,
                'total_xp_30': 0, 'count_xp_30': 0,
                'total_xp_40': 0, 'count_xp_40': 0,

                # Per-patch aggregates for Lethality
                'patch_stats': collections.defaultdict(lambda: {'kills': 0, 'deaths': 0, 'games': 0})
            }

    def get_features(self, blue_participants, red_participants, current_patch):
        """
        Generates features for both teams.
        participants: List of dicts or rows containing 'puuid' and 'champion_id'.
        """
        features = {}

        # Helper to process a team
        def process_team(participants, prefix):
            team_stats = []

            for p in participants:
                puuid = p['puuid']
                cid = p['champion_id']

                # Default values if no history
                p_feats = {
                    'winrate_last_10': 0.5,
                    'usage_global': 0.0,
                    'usage_patch': 0.0,
                    'avg_gold_15': 0.0, 'avg_gold_30': 0.0, 'avg_gold_40': 0.0,
                    'avg_xp_15': 0.0, 'avg_xp_30': 0.0, 'avg_xp_40': 0.0,
                    'lethality_kills_last_15': 0.0,
                    'lethality_deaths_last_15': 0.0,
                    'lethality_diff_last_15': 0.0,
                    'lethality_kills_patch': 0.0,
                    'lethality_deaths_patch': 0.0,
                    'lethality_diff_patch': 0.0,
                    'avg_kda_last_10': 0.0
                }

                if puuid in self.player_stats:
                    p_data = self.player_stats[puuid]

                    # 1. Usage Percentage
                    total_games = p_data['total_games']
                    if total_games > 0:
                        champ_data = p_data['champions'].get(cid)
                        if champ_data:
                            # Global Usage
                            games_on_champ = len(champ_data['history']) # Len history grows indefinitely? No, need total counter.
                            # Correction: 'history' might be truncated if I optimized memory, but here I keep it.
                            # To be safe, let's use sum of patch games or just len(history) if we don't truncate.
                            # For simplicity, len(history) is total games on champ if we don't pop.
                            # UPDATE: If I truncate history for memory, I need a separate counter.
                            # Let's assume history grows or add a counter. I'll add a 'total_games' to champ struct.
                            p_feats['usage_global'] = champ_data.get('total_games_champ', 0) / total_games

                            # Patch Usage
                            patch_total = p_data['patches'].get(current_patch, 0)
                            if patch_total > 0:
                                patch_champ = champ_data['patch_stats'].get(current_patch, {'games': 0})['games']
                                p_feats['usage_patch'] = patch_champ / patch_total

                            # 2. Win Rate (Last 10)
                            history = champ_data['history']
                            last_10 = history[-self.WINRATE_WINDOW:] if history else []
                            if last_10:
                                wins = sum(1 for h in last_10 if h['win'])
                                p_feats['winrate_last_10'] = wins / len(last_10)

                                # KDA Last 10
                                kills_10 = sum(h['kills'] for h in last_10)
                                deaths_10 = sum(h['deaths'] for h in last_10)
                                assists_10 = sum(h['assists'] for h in last_10)
                                p_feats['avg_kda_last_10'] = (kills_10 + assists_10) / max(1, deaths_10)

                            # 3. Gold & XP Averages (All History)
                            def get_avg(key_sum, key_count):
                                return champ_data[key_sum] / champ_data[key_count] if champ_data[key_count] > 0 else 0

                            p_feats['avg_gold_15'] = get_avg('total_gold_15', 'count_gold_15')
                            p_feats['avg_gold_30'] = get_avg('total_gold_30', 'count_gold_30')
                            p_feats['avg_gold_40'] = get_avg('total_gold_40', 'count_gold_40')
                            p_feats['avg_xp_15'] = get_avg('total_xp_15', 'count_xp_15')
                            p_feats['avg_xp_30'] = get_avg('total_xp_30', 'count_xp_30')
                            p_feats['avg_xp_40'] = get_avg('total_xp_40', 'count_xp_40')

                            # 4. Lethality - Last 15 Matches
                            last_15 = history[-self.LETHALITY_WINDOW:] if history else []
                            if last_15:
                                k_15 = sum(h['kills'] for h in last_15) / len(last_15)
                                d_15 = sum(h['deaths'] for h in last_15) / len(last_15)
                                p_feats['lethality_kills_last_15'] = k_15
                                p_feats['lethality_deaths_last_15'] = d_15
                                p_feats['lethality_diff_last_15'] = k_15 - d_15

                            # 5. Lethality - Patch Average
                            p_stats = champ_data['patch_stats'].get(current_patch)
                            if p_stats and p_stats['games'] > 0:
                                k_patch = p_stats['kills'] / p_stats['games']
                                d_patch = p_stats['deaths'] / p_stats['games']
                                p_feats['lethality_kills_patch'] = k_patch
                                p_feats['lethality_deaths_patch'] = d_patch
                                p_feats['lethality_diff_patch'] = k_patch - d_patch

                team_stats.append(p_feats)

            # Aggregate team stats (Average of the 5 players)
            # Or should I return individual stats? The orchestrator usually flattens specific metrics.
            # But here we have 5 roles. Standard approach in this repo seems to be:
            # - Diffs per role?
            # - Team averages?
            # The prompt asks for "Calculate...".
            # Winrates.py returns: blue_avg, red_avg, diff_total, diff_pos_X.
            # I will follow that pattern: Team Averages and Position Diffs.
            return team_stats

        blue_stats = process_team(blue_participants, 'blue')
        red_stats = process_team(red_participants, 'red')

        # Keys to aggregate
        keys = blue_stats[0].keys()

        # 1. Team Averages
        for k in keys:
            b_avg = sum(s[k] for s in blue_stats) / 5
            r_avg = sum(s[k] for s in red_stats) / 5
            features[f'blue_avg_{k}'] = b_avg
            features[f'red_avg_{k}'] = r_avg
            features[f'diff_avg_{k}'] = b_avg - r_avg

        # 2. Position Diffs (Top vs Top, etc.)
        positions = ['top', 'jungle', 'mid', 'adc', 'sup']
        for i in range(5):
            pos = positions[i]
            for k in keys:
                diff = blue_stats[i][k] - red_stats[i][k]
                features[f'diff_{pos}_{k}'] = diff

        return features

    def update(self, participants_df, timeline_df, winner_team):
        """
        Updates internal stats with the results of the match.
        participants_df: DataFrame with 'puuid', 'champion_id', 'win', 'kills', 'deaths', 'assists', 'participant_id'
        timeline_df: DataFrame with 'participant_id', 'timestamp', 'total_gold', 'total_xp'
        winner_team: 100 or 200 (not strictly needed if 'win' col is in participants_df)
        """
        # Ensure we are working with specific patch version?
        # The Orchestrator passes 'patch'. I need to know the patch of THIS match.
        # I'll update signature to accept patch, or infer it?
        # Actually, orchestrator loop has `patch`. I should pass it.
        pass
        # (Implemented below with proper signature)

    def update_with_patch(self, participants_df, timeline_df, patch_version):
        """
        Full update logic.
        """
        # Group timeline by participant
        # Timestamps are in milliseconds usually? Or minutes?
        # Check database: timestamp is INTEGER. Usually milliseconds in Riot API.
        # 15 min = 900000, 30 min = 1800000, 40 min = 2400000.

        # Pre-filter timeline for efficiency
        targets = [15, 30, 40]
        # target_ms = [t * 60 * 1000 for t in targets]
        # Actually let's just grab the rows closest to these times for each participant

        # Helper to get stats at minute
        def get_stats_at(pid, minute):
            ms = minute * 60 * 1000
            # Find row with timestamp >= ms (closest)
            # Assuming timeline is sorted.
            rows = timeline_df[timeline_df['participant_id'] == pid]
            if rows.empty: return None, None

            # Find the row closest to the target time
            # Filter rows where timestamp <= target + tolerance?
            # Or just take the last one <= target?
            # Riot timeline is usually per minute.
            # Let's find the record closest to 'ms'

            # Optimization: Exact match or nearest
            # records = rows[rows['timestamp'] >= ms]
            # if not records.empty:
            #     row = records.iloc[0]
            #     return row['total_gold'], row['total_xp']
            # else:
            #     # Game ended before this time
            #     return None, None

            # Better approach:
            # If game duration < 15 min, return None.
            # If game duration > 15 min, find timestamp closest to 15m.

            closest_idx = (rows['timestamp'] - ms).abs().idxmin()
            row = rows.loc[closest_idx]

            # Check if the timestamp is reasonably close (e.g., within 2 minutes)
            # If the game ended at 20min, asking for 40min should yield None.
            if abs(row['timestamp'] - ms) > 2 * 60 * 1000:
                return None, None

            return row['total_gold'], row['total_xp']

        for _, row in participants_df.iterrows():
            puuid = row['puuid']
            cid = row['champion_id']
            pid = row['participant_id']
            win = row['win'] # Boolean or 0/1
            kills = row['kills']
            deaths = row['deaths']
            assists = row['assists']

            self._init_player(puuid)
            self._init_champion(puuid, cid)

            p_data = self.player_stats[puuid]
            c_data = p_data['champions'][cid]

            # 1. Update Global Counters
            p_data['total_games'] += 1
            p_data['patches'][patch_version] += 1
            c_data.setdefault('total_games_champ', 0)
            c_data['total_games_champ'] += 1

            # 2. Update History (Win, K/D/A)
            match_record = {
                'win': 1 if win else 0,
                'kills': kills,
                'deaths': deaths,
                'assists': assists,
                'patch': patch_version
            }
            c_data['history'].append(match_record)

            # 3. Update Patch Stats
            p_stats = c_data['patch_stats'][patch_version]
            p_stats['games'] += 1
            p_stats['kills'] += kills
            p_stats['deaths'] += deaths

            # 4. Update Gold/XP Averages
            # We only update if the match actually reached that time.
            # Efficiently querying timeline_df

            # Filter timeline for this participant once
            p_timeline = timeline_df[timeline_df['participant_id'] == pid]

            if not p_timeline.empty:
                for minute in [15, 30, 40]:
                    ms = minute * 60 * 1000
                    # Find closest timestamp
                    # p_timeline is sorted by timestamp usually

                    # We want the row where timestamp is closest to ms
                    # But if the game ended at 20min, asking for 30min is invalid.
                    # Simple check: max timestamp of this participant
                    max_ts = p_timeline['timestamp'].max()

                    if max_ts >= ms - (60*1000): # Allow 1 min margin
                        # Find closest row
                        idx = (p_timeline['timestamp'] - ms).abs().idxmin()
                        r = p_timeline.loc[idx]

                        gold = r['total_gold']
                        xp = r['total_xp']

                        c_data[f'total_gold_{minute}'] += gold
                        c_data[f'count_gold_{minute}'] += 1
                        c_data[f'total_xp_{minute}'] += xp
                        c_data[f'count_xp_{minute}'] += 1
