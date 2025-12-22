import pandas as pd

def calculate_mechanics(blue_ids, red_ids, patch, df_features):
    """
    Calcula o diferencial granular das mecânicas (Blue - Red).
    Quebra as categorias em 11 features distintas.
    """
    
    # 1. Filtragem de Patch
    df_patch = df_features[df_features['patch_version'] == patch]
    
    if df_patch.empty:
        if not df_features.empty:
            latest_patch = df_features['patch_version'].max()
            df_patch = df_features[df_features['patch_version'] == latest_patch]
        else:
            return _empty_result()

    # 2. Função interna de soma granular
    def get_team_sum(team_ids):
        team_stats = df_patch[df_patch['champion_key'].isin(team_ids)]
        
        # Se team_stats estiver vazio (ex: ids errados), .sum() retorna 0, o que é seguro.
        return {
            # Controle
            'hard_cc': team_stats['has_hard_cc'].sum(),
            'soft_cc': team_stats['has_soft_cc'].sum(), # Slows, Silences
            'hook': team_stats['has_hook'].sum(),       # Blitz, Thresh, Pyke
            
            # Sobrevivência
            'heal': team_stats['has_heal'].sum(),
            'shield': team_stats['has_shield'].sum(),
            'immortality': team_stats['has_immortality'].sum(), # Zilean, Kayle
            
            # Mobilidade
            'dash': team_stats['has_dash'].sum(),
            'blink': team_stats['has_blink'].sum(),
            
            # Ofensiva Especializada
            'true_dmg': team_stats['has_true_damage'].sum(), # Counter de Tank
            'execute': team_stats['has_execute'].sum(),      # Pyke, Urgot
            'stealth': team_stats['has_stealth'].sum()       # Evelyn, Twitch
        }

    # 3. Executa para os dois lados
    blue = get_team_sum(blue_ids)
    red = get_team_sum(red_ids)
    
    # 4. Cálculo dos Diferenciais (Loop dinâmico para evitar repetição de código)
    result = {}
    keys_to_process = [
        'hard_cc', 'soft_cc', 'hook', 
        'heal', 'shield', 'immortality', 
        'dash', 'blink', 
        'true_dmg', 'execute', 'stealth'
    ]
    
    for k in keys_to_process:
        result[f'diff_{k}'] = int(blue[k] - red[k])
        
    return result

def _empty_result():
    keys = [
        'hard_cc', 'soft_cc', 'hook', 'heal', 'shield', 'immortality', 
        'dash', 'blink', 'true_dmg', 'execute', 'stealth'
    ]
    return {f'diff_{k}': 0 for k in keys}