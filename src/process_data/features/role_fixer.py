import pandas as pd

# --- CONFIGURAÇÃO DE PESOS ---

# IDs dos Feitiços (Summoner Spells)
# 11: Smite (Golpear) - O mais importante
# 12: Teleport (Teleporte)
# 14: Ignite (Incendiar)
# 7:  Heal (Curar)
# 3:  Exhaust (Exaustão)
# 21: Barrier (Barreira)
# 4:  Flash (Quase todo mundo usa, peso baixo/nulo)

SPELL_WEIGHTS = {
    'TOP':     {12: 5, 14: 2, 6: 2},           # TP, Ignite, Ghost
    'JUNGLE':  {11: 50},                       # SMITE (Peso 50 = Garantia)
    'MIDDLE':  {12: 3, 14: 3, 21: 2},          # TP, Ignite, Barrier
    'BOTTOM':  {7: 5, 21: 3, 12: 1},           # Heal, Barrier, TP
    'UTILITY': {3: 5, 14: 3, 7: 2}             # Exhaust, Ignite, Heal
}

ROLE_WEIGHTS = {
    'TOP': {'Tank': 2, 'Fighter': 2, 'Mage': 0.5, 'Assassin': 0.5},
    'JUNGLE': {'Fighter': 2, 'Assassin': 2, 'Tank': 1.5, 'Mage': 0.5},
    'MIDDLE': {'Mage': 2, 'Assassin': 2, 'Fighter': 1, 'Marksman': 0.5},
    'BOTTOM': {'Marksman': 4, 'Mage': 1, 'Fighter': 0.1},
    'UTILITY': {'Support': 4, 'Mage': 1.5, 'Tank': 1, 'Marksman': 0.1}
}

REQUIRED_ROLES = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']

def resolve_team_roles(team_df, df_champs):
    """
    Resolve conflitos de role usando Tags de Campeão E Feitiços de Invocador.
    """
    
    # 1. Mapeamento Inicial
    assignments = {r: [] for r in REQUIRED_ROLES}
    
    def get_champ_tags(cid):
        row = df_champs[df_champs['champion_key'] == cid]
        if row.empty: return []
        return str(row.iloc[0]['tags']).split(',')

    players = []
    for _, row in team_df.iterrows():
        pos = row['lane']
        if pos == 'BOTTOM' and 'SUPPORT' in row['role']:
            pos = 'UTILITY'
            
        cid = row['champion_id']
        
        # Pega os feitiços da linha (precisamos garantir que o SQL traga isso)
        spells = [row.get('spell1Id', 0), row.get('spell2Id', 0)]
        
        player_obj = {
            'id': cid, 
            'tags': get_champ_tags(cid), 
            'spells': spells,
            'original_pos': pos
        }
        players.append(player_obj)
        
        if pos in assignments:
            assignments[pos].append(player_obj)

    # 2. Identificar Problemas
    filled_roles = [r for r in assignments if len(assignments[r]) == 1]
    empty_roles = [r for r in assignments if len(assignments[r]) == 0]
    overflow_roles = [r for r in assignments if len(assignments[r]) > 1]
    
    # Se tudo estiver correto, retorna rápido
    if not empty_roles and not overflow_roles:
        return {r: assignments[r][0]['id'] for r in REQUIRED_ROLES}

    # 3. Separar Jogadores Problemáticos
    # Consideramos problemáticos: quem está em lane duplicada OU quem está em lane 'NONE'
    # Quem está sozinho numa lane válida (ex: único TOP) deixamos quieto para não bagunçar o que está certo.
    problem_players = []
    
    # Adiciona todos das lanes duplicadas
    for r in overflow_roles:
        problem_players.extend(assignments[r])
        assignments[r] = [] 
        empty_roles.append(r) 

    # Adiciona quem não foi assignado a lugar nenhum ou estava em NONE
    # (Verifica se o player já está numa role 'filled', se não, é problema)
    safe_ids = [assignments[r][0]['id'] for r in filled_roles]
    for p in players:
        if p['id'] not in safe_ids and p not in problem_players:
            problem_players.append(p)

    final_dict = {r: assignments[r][0]['id'] for r in filled_roles}
    
    # 4. Cálculo de Score Híbrido (Tags + Spells)
    possibilities = []
    
    for p in problem_players:
        for role in empty_roles:
            score = 0
            
            # A. Score de Tag (Base)
            for tag in p['tags']:
                score += ROLE_WEIGHTS.get(role, {}).get(tag, 0)
            
            # B. Score de Feitiço (O "Tie Breaker" Poderoso)
            for spell_id in p['spells']:
                # Se tiver Smite (11) e a role for Jungle, ganha +50 pontos.
                # Se tiver Heal (7) e for ADC, ganha +5 pontos.
                score += SPELL_WEIGHTS.get(role, {}).get(spell_id, 0)
            
            possibilities.append({'player': p, 'role': role, 'score': score})
    
    # Ordena: Maior score primeiro
    possibilities.sort(key=lambda x: x['score'], reverse=True)
    
    used_players = set()
    filled_empty_roles = set()
    
    # 5. Atribuição Gulosa
    for match in possibilities:
        p_id = match['player']['id']
        role = match['role']
        
        if p_id not in used_players and role not in filled_empty_roles:
            final_dict[role] = p_id
            used_players.add(p_id)
            filled_empty_roles.add(role)
            
    # Fallback para sobras (preencher buracos com quem sobrou)
    if len(used_players) < len(problem_players):
        remaining_p = [p for p in problem_players if p['id'] not in used_players]
        remaining_r = [r for r in empty_roles if r not in filled_empty_roles]
        
        for i, p in enumerate(remaining_p):
            if i < len(remaining_r):
                final_dict[remaining_r[i]] = p['id']

    return final_dict