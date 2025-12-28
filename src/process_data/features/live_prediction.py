import pandas as pd

# Momentos chaves para análise Live
SNAPSHOTS = [10, 20] 
ROLES = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']

def calculate_live_features(match_id, blue_roles, red_roles, df_timeline_stats, df_timeline_participants):
    """
    Calcula o estado real da partida (Ouro, XP, Dragões) em momentos chave.
    
    Args:
        match_id (str): ID da partida.
        blue_roles (dict): { 'TOP': champ_id, ... } (Vindo do Role Fixer)
        red_roles (dict): { 'TOP': champ_id, ... }
        df_timeline_stats (pd.DataFrame): Dados da tabela match_timeline_stats filtrados para este match.
        df_timeline_participants (pd.DataFrame): Dados da tabela match_timeline_participants filtrados.
        
    Returns:
        dict: Features de estado de jogo (Ex: live_10_gold_diff, live_10_top_gold_diff).
    """
    
    result = {}
    
    # Se não tiver dados de timeline (jogo muito curto ou erro de download), zera tudo
    if df_timeline_stats.empty or df_timeline_participants.empty:
        return _empty_result()

    for minute in SNAPSHOTS:
        prefix = f"live_{minute}"
        
        # --- 1. MACRO (Time vs Time) ---
        # Filtra pelo minuto
        stats_min = df_timeline_stats[df_timeline_stats['timestamp'] == minute]
        
        if stats_min.empty:
            _fill_zero_snapshot(result, minute)
            continue
            
        # Pega stats do time Azul (100) e Vermelho (200)
        try:
            blue_macro = stats_min[stats_min['team_id'] == 100].iloc[0]
            red_macro = stats_min[stats_min['team_id'] == 200].iloc[0]
            
            # Features Globais
            result[f'{prefix}_gold_diff'] = float(blue_macro['total_gold'] - red_macro['total_gold'])
            result[f'{prefix}_xp_diff'] = float(blue_macro['total_xp'] - red_macro['total_xp'])
            result[f'{prefix}_kills_diff'] = int(blue_macro['kills_at_time'] - red_macro['kills_at_time'])
            result[f'{prefix}_dragons_diff'] = int(blue_macro['dragons_at_time'] - red_macro['dragons_at_time'])
            result[f'{prefix}_towers_diff'] = int(blue_macro['towers_at_time'] - red_macro['towers_at_time'])
        except IndexError:
            # Caso falte dados de um dos times
            _fill_zero_snapshot(result, minute)
            continue

        # --- 2. MICRO (Lane vs Lane) ---
        # Aqui cruzamos o desempenho individual
        
        # Filtra participantes neste minuto
        parts_min = df_timeline_participants[df_timeline_participants['timestamp'] == minute]
        
        if 'champion_id' not in parts_min.columns:
            # Se não tiver a coluna, não podemos calcular lane diff com precisão
            # Retorna 0 para lanes e segue vida
            _fill_zero_lanes(result, minute)
            continue

        # Helper rápido
        def get_p_stats(cid):
            row = parts_min[parts_min['champion_id'] == cid]
            if row.empty: return None
            return row.iloc[0]

        for role in ROLES:
            b_id = blue_roles.get(role)
            r_id = red_roles.get(role)
            
            b_p = get_p_stats(b_id)
            r_p = get_p_stats(r_id)
            
            role_key = role.lower()
            if role == 'BOTTOM': role_key = 'adc'
            if role == 'UTILITY': role_key = 'sup'
            if role == 'MIDDLE': role_key = 'mid'
            
            lane_prefix = f"{prefix}_{role_key}"
            
            if b_p is not None and r_p is not None:
                # Diff de Ouro (Vantagem econômica)
                result[f'{lane_prefix}_gold_diff'] = float(b_p['total_gold'] - r_p['total_gold'])
                # Diff de XP (Vantagem de Nível)
                result[f'{lane_prefix}_xp_diff'] = float(b_p['total_xp'] - r_p['total_xp'])
                # Diff de Farm (CS)
                b_cs = b_p['minions_killed'] + b_p['jungle_minions_killed']
                r_cs = r_p['minions_killed'] + r_p['jungle_minions_killed']
                result[f'{lane_prefix}_cs_diff'] = int(b_cs - r_cs)
            else:
                result[f'{lane_prefix}_gold_diff'] = 0.0
                result[f'{lane_prefix}_xp_diff'] = 0.0
                result[f'{lane_prefix}_cs_diff'] = 0

    return result

def _fill_zero_snapshot(res, minute):
    p = f"live_{minute}"
    res[f'{p}_gold_diff'] = 0.0
    res[f'{p}_xp_diff'] = 0.0
    res[f'{p}_kills_diff'] = 0
    res[f'{p}_dragons_diff'] = 0
    res[f'{p}_towers_diff'] = 0
    _fill_zero_lanes(res, minute)

def _fill_zero_lanes(res, minute):
    p = f"live_{minute}"
    for role in ['top', 'jungle', 'mid', 'adc', 'sup']:
        res[f'{p}_{role}_gold_diff'] = 0.0
        res[f'{p}_{role}_xp_diff'] = 0.0
        res[f'{p}_{role}_cs_diff'] = 0

def _empty_result():
    res = {}
    for m in SNAPSHOTS:
        _fill_zero_snapshot(res, m)
    return res
