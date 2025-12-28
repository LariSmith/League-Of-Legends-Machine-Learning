class RollingWinrate:
    """
    Gerencia o cálculo incremental de Winrates (Rolling Window).
    Evita Data Leakage garantindo que as estatísticas de um campeão
    sejam baseadas apenas em partidas passadas.
    """
    def __init__(self):
        # Estrutura: { champion_id: {'wins': 0, 'games': 0} }
        self.stats = {}
        # Nomes das posições para as chaves do dicionário de retorno
        self.positions = ['top', 'jungle', 'mid', 'adc', 'support']

    def _get_single_winrate(self, champion_id):
        """
        Calcula o winrate de um único campeão usando Suavização de Laplace.
        Fórmula: (Vitórias + 1) / (Jogos + 2)
        Isso empurra campeões com poucos jogos para 50% de WR.
        """
        data = self.stats.get(champion_id, {'wins': 0, 'games': 0})
        return (data['wins'] + 1) / (data['games'] + 2)

    def get_features(self, blue_team_ids, red_team_ids):
        """
        Gera features baseadas no histórico acumulado, incluindo diferenças por posição.
        Assume que as listas blue_team_ids e red_team_ids estão na mesma ordem de posições.
        """
        # Calcula winrates individuais para cada campeão
        blue_wrs = [self._get_single_winrate(cid) for cid in blue_team_ids]
        red_wrs = [self._get_single_winrate(cid) for cid in red_team_ids]

        # Médias globais dos times
        blue_avg = sum(blue_wrs) / len(blue_wrs) if blue_wrs else 0.5
        red_avg = sum(red_wrs) / len(red_wrs) if red_wrs else 0.5

        # Dicionário base com as médias
        features = {
            'blue_avg_winrate': blue_avg,
            'red_avg_winrate': red_avg,
            'winrate_diff_total': blue_avg - red_avg,
        }

        # Calcula a diferença de Winrate por posição (Blue WR - Red WR)
        # Assume que as listas possuem 5 elementos correspondentes
        for i in range(min(len(blue_wrs), len(red_wrs))):
            pos_name = self.positions[i] if i < len(self.positions) else f'pos_{i}'
            features[f'diff_winrate_{pos_name}'] = blue_wrs[i] - red_wrs[i]

        return features

    def update(self, blue_team_ids, red_team_ids, winner_team):
        """
        Atualiza o histórico de vitórias e jogos após o término da partida.
        winner_team: 100 ou 1 para Blue, 200 ou 0 para Red.
        """
        # Normaliza vencedor para booleano (True se Blue ganhou)
        blue_won = (winner_team == 1 or winner_team == 100)

        # Atualiza estatísticas do time azul
        for cid in blue_team_ids:
            if cid not in self.stats: 
                self.stats[cid] = {'wins': 0, 'games': 0}
            self.stats[cid]['games'] += 1
            if blue_won:
                self.stats[cid]['wins'] += 1

        # Atualiza estatísticas do time vermelho
        for cid in red_team_ids:
            if cid not in self.stats: 
                self.stats[cid] = {'wins': 0, 'games': 0}
            self.stats[cid]['games'] += 1
            if not blue_won:
                self.stats[cid]['wins'] += 1

# Exemplo de uso:
# rw = RollingWinrate()
# features = rw.get_features([1, 2, 3, 4, 5], [6, 7, 8, 9, 10])
# print(features)