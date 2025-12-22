import pandas as pd

def calculate_class_counts(blue_ids, red_ids, patch, df_champs):
    """
    Conta a quantidade de campeões de cada classe principal (Tank, Fighter, Mage, Marksman, Assassin, Support).
    
    Args:
        blue_ids (list): IDs do time Azul.
        red_ids (list): IDs do time Vermelho.
        patch (str): Versão do patch.
        df_champs (pd.DataFrame): Tabela de campeões.
        
    Returns:
        dict: Contagem de cada classe para ambos os times.
    """
    
    # 1. Filtro de Patch
    df_patch = df_champs[df_champs['patch_version'] == patch]
    
    if df_patch.empty:
        if not df_champs.empty:
            latest = df_champs['patch_version'].max()
            df_patch = df_champs[df_champs['patch_version'] == latest]
        else:
            return _empty_result()

    # 2. Função de Contagem
    def get_team_counts(team_ids):
        team_df = df_patch[df_patch['champion_key'].isin(team_ids)]
        
        counts = {
            'tank': 0,
            'fighter': 0,
            'mage': 0,
            'marksman': 0,
            'assassin': 0,
            'support': 0
        }
        
        for tags_str in team_df['tags']:
            # Normaliza para string e minúsculo para busca segura
            t = str(tags_str).lower()
            
            # Um campeão pode ter duas tags (Ex: Mage, Support). 
            # Aqui contaremos ambas, pois ele exerce as duas funções.
            if 'tank' in t: counts['tank'] += 1
            if 'fighter' in t: counts['fighter'] += 1
            if 'mage' in t: counts['mage'] += 1
            if 'marksman' in t: counts['marksman'] += 1
            if 'assassin' in t: counts['assassin'] += 1
            if 'support' in t: counts['support'] += 1
            
        return counts

    # 3. Execução
    b_counts = get_team_counts(blue_ids)
    r_counts = get_team_counts(red_ids)
    
    # Achatando o resultado para o retorno
    return {
        'blue_count_tank': b_counts['tank'], 'red_count_tank': r_counts['tank'],
        'blue_count_fighter': b_counts['fighter'], 'red_count_fighter': r_counts['fighter'],
        'blue_count_mage': b_counts['mage'], 'red_count_mage': r_counts['mage'],
        'blue_count_marksman': b_counts['marksman'], 'red_count_marksman': r_counts['marksman'],
        'blue_count_assassin': b_counts['assassin'], 'red_count_assassin': r_counts['assassin'],
        'blue_count_support': b_counts['support'], 'red_count_support': r_counts['support']
    }

def _empty_result():
    # Retorna 0 para tudo em caso de erro
    keys = ['tank', 'fighter', 'mage', 'marksman', 'assassin', 'support']
    result = {}
    for k in keys:
        result[f'blue_count_{k}'] = 0
        result[f'red_count_{k}'] = 0
    return result