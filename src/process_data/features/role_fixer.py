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
# 6:  Ghost (Fantasma)
# 1:  Cleanse (Purificar)

SPELL_WEIGHTS = {
    'TOP':     {12: 5, 14: 2, 6: 2},           # TP, Ignite, Ghost
    'JUNGLE':  {11: 50},                       # SMITE (Peso 50 = Garantia)
    'MIDDLE':  {12: 3, 14: 3, 21: 2, 6: 1},    # TP, Ignite, Barrier
    'BOTTOM':  {7: 5, 21: 3, 12: 1, 1: 1},     # Heal, Barrier, TP, Cleanse
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
    Retorna um dicionário: {Role: {'id': ChampionID, 'puuid': PUUID}}
    """
    
    # 1. Mapeamento Inicial e Preparação
    assignments = {r: [] for r in REQUIRED_ROLES}
    
    # Helper rápido para tags
    # Otimização: Criar um dict de lookup para evitar query no loop se df_champs for grande
    # Assumindo que df_champs é pequeno o suficiente ou indexado.
    # Mas vamos fazer um lookup simples aqui para garantir performance.
    champ_tags_map = {}
    if not df_champs.empty:
         for _, row in df_champs.iterrows():
             champ_tags_map[row['champion_key']] = str(row['tags']).split(',')

    players = []
    for _, row in team_df.iterrows():
        pos = row['lane']
        # Normalização de roles antigas/estranhas
        if pos == 'BOTTOM' and 'SUPPORT' in row['role']:
            pos = 'UTILITY'
        if pos == 'BOT': # As vezes aparece como BOT
            pos = 'BOTTOM'
            
        cid = row['champion_id']
        puuid = row['puuid']
        
        spells = [row.get('spell1Id', 0), row.get('spell2Id', 0)]
        
        player_obj = {
            'id': cid, 
            'puuid': puuid,
            'tags': champ_tags_map.get(cid, []),
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
    
    # Se tudo perfeito, retorna formato novo
    if not empty_roles and not overflow_roles:
        return {r: {'id': assignments[r][0]['id'], 'puuid': assignments[r][0]['puuid']} for r in REQUIRED_ROLES}

    # 3. Separar Jogadores Problemáticos
    problem_players = []
    
    # Quem está em roles duplicadas é problema
    for r in overflow_roles:
        problem_players.extend(assignments[r])
        # Reseta essa role para ser preenchida de novo
        assignments[r] = []
        if r not in empty_roles: # Evita duplicata se já estava vazia (impossível se overflow, mas ok)
            empty_roles.append(r)

    # Quem está em role 'NONE' ou inválida também é problema
    safe_puuids = set()
    for r in filled_roles:
        safe_puuids.add(assignments[r][0]['puuid'])

    for p in players:
        if p['puuid'] not in safe_puuids and p not in problem_players:
            problem_players.append(p)

    # Inicia o dict final com os que já estão certos
    final_dict = {r: {'id': assignments[r][0]['id'], 'puuid': assignments[r][0]['puuid']} for r in filled_roles}
    
    # 4. Cálculo de Score Híbrido (Tags + Spells)
    # Gera todas as combinações (Player, Role) possíveis para os problemáticos
    possibilities = []
    
    for p in problem_players:
        for role in empty_roles: # Só considera roles que precisam ser preenchidas
            score = 0
            
            # A. Score de Tag (Base)
            for tag in p['tags']:
                score += ROLE_WEIGHTS.get(role, {}).get(tag, 0)
            
            # B. Score de Feitiço (Tie Breaker Poderoso)
            for spell_id in p['spells']:
                score += SPELL_WEIGHTS.get(role, {}).get(spell_id, 0)

            # C. Bônus por posição original (se ele "disse" que era TOP, mas teve conflito, ainda tem preferência)
            if p['original_pos'] == role:
                 score += 10 # Peso alto para respeitar a intenção do jogo
            
            possibilities.append({'player': p, 'role': role, 'score': score})
    
    # Ordena: Maior score primeiro
    possibilities.sort(key=lambda x: x['score'], reverse=True)
    
    used_puuids = set()
    filled_empty_roles = set()
    
    # 5. Atribuição Gulosa
    for match in possibilities:
        p_obj = match['player']
        p_puuid = p_obj['puuid']
        role = match['role']
        
        if p_puuid not in used_puuids and role not in filled_empty_roles:
            final_dict[role] = {'id': p_obj['id'], 'puuid': p_puuid}
            used_puuids.add(p_puuid)
            filled_empty_roles.add(role)
            
    # 6. Fallback para sobras (preencher buracos com quem sobrou, se houver falha na lógica gulosa)
    if len(used_puuids) < len(problem_players):
        remaining_p = [p for p in problem_players if p['puuid'] not in used_puuids]
        remaining_r = [r for r in empty_roles if r not in filled_empty_roles]
        
        for i, p in enumerate(remaining_p):
            if i < len(remaining_r):
                final_dict[remaining_r[i]] = {'id': p['id'], 'puuid': p['puuid']}

    return final_dict
