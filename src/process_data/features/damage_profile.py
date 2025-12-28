import pandas as pd

# Exceções manuais para campeões cuja Tag não reflete o tipo de dano principal.
# 1 = Predominantemente Mágico (AP)
# 0 = Híbrido / Dano Misto
# -1 = Predominantemente Físico (AD)
SPECIAL_CASES = {
    # Atiradores que causam dano Mágico ou Híbrido
    'Corki': 1,        # Passiva converte AA em Mágico + Skills Mágicas
    'Kog\'Maw': 0,     # Dano Híbrido significativo (W + R)
    'Kai\'Sa': 0,      # Frequentemente builda Híbrido/AP
    'Varus': 0,        # Builds de AP ou On-hit híbrido são comuns
    'Twitch': 0,       # Veneno (True) + Builds AP
    'Kayle': 1,        # Late game é majoritariamente ondas de dano mágico
    'Teemo': 1,        # Marksman/Mage -> Dano Mágico
    'Azir': 1,         # Marksman (Soldados) -> Dano Mágico

    # Lutadores/Tanques que causam dano Mágico (AP Bruisers)
    'Gwen': 1,         # Fighter -> Dano Mágico
    'Mordekaiser': 1,  # Fighter -> Dano Mágico
    'Rumble': 1,       # Fighter -> Dano Mágico
    'Singed': 1,       # Tank/Fighter -> Dano Mágico
    'Lillia': 1,       # Fighter -> Dano Mágico
    'Diana': 1,        # Fighter -> Dano Mágico
    'Gragas': 1,       # Fighter/Tank -> Dano Mágico
    'Volibear': 0,     # Híbrido (Raios/Mordida)
    'Warwick': 0,      # Dano Mágico na passiva/Q/R, builda AD/Tank
    'Udyr': 0,         # Fênix (Mágico) ou Tigre (Físico) - Híbrido por segurança
    'Shyvana': 0,      # Híbrido (Dano base mágico alto)

    # Assassinos de Dano Mágico (que as vezes não tem tag Mage)
    'Akali': 1,
    'Evelynn': 1,
    'Ekko': 1,
    'Fizz': 1,
    'Katarina': 1,
    'Kassadin': 1,
    'Nidalee': 1,
    'Elise': 1,
    'Shaco': 0         # Caixinhas (AP) ou Crítico (AD) -> Híbrido
}

def calculate_damage_profile(blue_ids, red_ids, patch, df_champs):
    """
    Calcula o perfil de dano do time baseado em TAGS e EXCEÇÕES (Dados Estáticos).
    
    Lógica:
        1. Verifica lista de exceções (Hardcoded).
        2. Se não for exceção, usa Tags:
           - Mage = +1 (AP)
           - Marksman/Fighter/Assassin = -1 (AD)
           - Outros = 0
    
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
        
        if team_df.empty:
            return 0

        for _, champ_row in team_df.iterrows():
            name = champ_row['name']
            tags_str = champ_row['tags']
            
            # --- VERIFICAÇÃO DE EXCEÇÃO (Hardcoded) ---
            if name in SPECIAL_CASES:
                score += SPECIAL_CASES[name]
                continue # Pula a lógica de tags se já achou exceção
            
            # --- LÓGICA PADRÃO DE TAGS ---
            t = str(tags_str) if pd.notna(tags_str) else ""
            
            # Se tem Mage na tag, quase sempre causa dano mágico predominante
            # (Ex: Ahri é Mage/Assassin -> AP | Sylas é Mage/Fighter -> AP)
            if 'Mage' in t:
                score += 1
                
            # Se não é Mage, mas é de classe física
            elif 'Marksman' in t or 'Fighter' in t or 'Assassin' in t:
                score -= 1
            
            # Tanks e Supports puros ficam como 0 (Neutros)
            
        return score

    # 3. Execução
    b_score = get_team_damage_score(blue_ids)
    r_score = get_team_damage_score(red_ids)
    
    return {
        'blue_damage_score': b_score,
        'red_damage_score': r_score
    }