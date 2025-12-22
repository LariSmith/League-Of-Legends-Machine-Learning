import pandas as pd
import numpy as np

def calculate_stats(blue_ids, red_ids, patch, df_champs):
    """
    Calcula diffs, mismatches e Curvas de Poder (Early/Mid/Late).
    """
    
    # 1. Filtro de Patch
    df_patch = df_champs[df_champs['patch_version'] == patch]
    
    if df_patch.empty:
        if not df_champs.empty:
            latest = df_champs['patch_version'].max()
            df_patch = df_champs[df_champs['patch_version'] == latest]
        else:
            return _empty_result()

    # 2. Helper para extrair métricas
    def get_team_metrics(team_ids):
        stats = df_patch[df_patch['champion_key'].isin(team_ids)]
        if stats.empty: return _get_zeroed_metrics()
        
        # Retorna todas as colunas necessárias para o cálculo
        return {
            'hp': stats['hp'].mean(), 'hp_pl': stats['hp_per_level'].mean(),
            'ad': stats['attackdamage'].mean(), 'ad_pl': stats['attackdamage_per_level'].mean(),
            'as': stats['attackspeed'].mean(), 'as_pl': stats['attackspeed_per_level'].mean(),
            'armor': stats['armor'].mean(), 'armor_pl': stats['armor_per_level'].mean(),
            'mr': stats['spellblock'].mean(), 'mr_pl': stats['spellblock_per_level'].mean(),
            'range': stats['attackrange'].mean(),
            'movespeed': stats['movespeed'].mean(),
            'hpregen': stats['hpregen'].mean()
        }

    b = get_team_metrics(blue_ids)
    r = get_team_metrics(red_ids)
    
    # --- CÁLCULO DE CURVAS DE PODER (Novidade) ---
    
    def calculate_power_at_level(metrics, level):
        """
        Estima um 'Power Score' genérico para um time em um nível específico.
        Power = (Vida Efetiva) + (Potencial de Dano Bruto)
        """
        # Fórmula: Stat_Atual = Base + (Crescimento * (Nivel - 1))
        lvl_mult = level - 1
        
        # 1. Status Defensivos no Nível X
        current_hp = metrics['hp'] + (metrics['hp_pl'] * lvl_mult)
        current_armor = metrics['armor'] + (metrics['armor_pl'] * lvl_mult)
        current_mr = metrics['mr'] + (metrics['mr_pl'] * lvl_mult)
        
        # "Vida Efetiva" simplificada (HP * média das resistências)
        # Dividimos por 100 para normalizar a escala e não ficar gigante
        defensive_score = current_hp * (1 + (current_armor + current_mr)/200)
        
        # 2. Status Ofensivos no Nível X
        current_ad = metrics['ad'] + (metrics['ad_pl'] * lvl_mult)
        current_as = metrics['as'] + (metrics['as_pl'] * lvl_mult)
        
        # "DPS Estimado"
        offensive_score = current_ad * current_as * 10 # Multiplicador arbitrário para peso
        
        return defensive_score + offensive_score

    # Calculamos a força relativa em 3 momentos do jogo
    # EARLY GAME (Nível 3)
    blue_early = calculate_power_at_level(b, 3)
    red_early = calculate_power_at_level(r, 3)
    diff_power_early = blue_early - red_early
    
    # MID GAME (Nível 11)
    blue_mid = calculate_power_at_level(b, 11)
    red_mid = calculate_power_at_level(r, 11)
    diff_power_mid = blue_mid - red_mid
    
    # LATE GAME (Nível 16)
    blue_late = calculate_power_at_level(b, 16)
    red_late = calculate_power_at_level(r, 16)
    diff_power_late = blue_late - red_late

    # --- Outros Diffs e Mismatches (Mantidos do anterior) ---
    
    # Kiting e Poke
    blue_kite = b['range'] - r['movespeed']
    red_kite = r['range'] - b['movespeed']
    mismatch_kiting = blue_kite - red_kite
    
    # Physical Matchup (Baseado no Nível 11 para ser média)
    b_ad_11 = b['ad'] + (b['ad_pl'] * 10)
    r_ar_11 = r['armor'] + (r['armor_pl'] * 10)
    r_ad_11 = r['ad'] + (r['ad_pl'] * 10)
    b_ar_11 = b['armor'] + (b['armor_pl'] * 10)
    
    mismatch_ad_armor = (b_ad_11 - r_ar_11) - (r_ad_11 - b_ar_11)

    return {
        # Curvas de Poder (O que você pediu)
        'diff_power_early': float(diff_power_early),
        'diff_power_mid': float(diff_power_mid),
        'diff_power_late': float(diff_power_late),
        
        # Stats Táticos
        'diff_avg_range': float(b['range'] - r['range']),
        'diff_avg_movespeed': float(b['movespeed'] - r['movespeed']),
        'mismatch_ad_armor': float(mismatch_ad_armor),
        'mismatch_kiting': float(mismatch_kiting)
    }

def _get_zeroed_metrics():
    # Helper para inicializar dict com zeros
    keys = ['hp', 'hp_pl', 'ad', 'ad_pl', 'as', 'as_pl', 
            'armor', 'armor_pl', 'mr', 'mr_pl', 'range', 'movespeed', 'hpregen']
    return {k: 0.0 for k in keys}

def _empty_result():
    keys = ['diff_power_early', 'diff_power_mid', 'diff_power_late', 
            'diff_avg_range', 'diff_avg_movespeed', 
            'mismatch_ad_armor', 'mismatch_kiting']
    return {k: 0.0 for k in keys}