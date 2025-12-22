import pandas as pd

def acalculate_damage_profile(blue_ids, red_ids, patch, df_champs):
    """
    Calcula o perfil de dano do time.
    Lógica:
        - Classes AD (Marksman, Fighter, Assassin) contam como -1.
        - Classes AP (Mage) contam como +1.
        - Outros (Tank, Support puro) contam como 0 (Neutro).
    
    Retorno:
        Valor negativo: Tendência AD.
        Valor zero: Misto/Neutro.
        Valor positivo: Tendência AP.
    """
    
    # 1. Filtro de Patch
    df_patch = df_champs[df_champs['patch_version'] == patch]
    
    if df_patch.empty:
        if not df_champs.empty:
            latest = df_champs['patch_version'].max()
            df_patch = df_champs[df_champs['patch_version'] == latest]
        else:
            return {'blue_damage_score': 0, 'red_damage_score': 0}

    # 2. Função de Cálculo de Score
    def get_team_damage_score(team_ids):
        # Filtra os dados dos 5 campeões
        team_df = df_patch[df_patch['champion_key'].isin(team_ids)]
        
        score = 0
        
        for tags_str in team_df['tags']:
            # As tags vêm como string "Mage, Support" ou "Fighter"
            # Precisamos normalizar para garantir a busca correta
            t = str(tags_str)
            
            # ORDEM DE PRIORIDADE IMPORTA AQUI
            
            # Se tem Mage na tag, quase sempre causa dano mágico predominante
            # (Ex: Ahri é Mage/Assassin -> AP | Sylas é Mage/Fighter -> AP)
            if 'Mage' in t:
                score += 1
                
            # Se não é Mage, mas é de classe física
            elif 'Marksman' in t or 'Fighter' in t or 'Assassin' in t:
                score -= 1
            
            # Tanks e Supports (sem tag Mage) ficam como 0
            # Isso ajuda a não "puxar" o score erradamente. 
            # Um Tank causa pouco dano, então ele é neutro no perfil ofensivo.
            
        return score

    # 3. Execução
    b_score = get_team_damage_score(blue_ids)
    r_score = get_team_damage_score(red_ids)
    
    return {
        'blue_damage_score': b_score,
        'red_damage_score': r_score
    }