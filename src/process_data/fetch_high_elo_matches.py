import requests
import sqlite3
import time
import os
import sys 

# --- CONFIGURAÇÕES ---
# ⚠️ COLOQUE SUA CHAVE ABAIXO
API_KEY = "RGAPI-8d34b713-b106-4956-9759-b47a7075d081" 

REGION_API = "br1"       
MATCH_API = "americas"   
MATCHES_PER_PLAYER = 100  # Aumentado para garantir cobertura total do patch
QUEUE_TYPE = "RANKED_SOLO_5x5"

# ⚠️ CONFIGURAÇÃO DE CONTINUAÇÃO
START_INDEX = 0

# Caminhos
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # Ajustado para rodar no diretorio atual
if not os.path.exists(os.path.join(BASE_DIR, 'data')):
    os.makedirs(os.path.join(BASE_DIR, 'data'))
DB_PATH = os.path.join(BASE_DIR, 'data', 'lol_database.db')

# Headers Padrão
HEADERS = {"X-Riot-Token": API_KEY}

def init_match_db(conn):
    """
    Recria o banco de dados com a estrutura MAIS COMPLETA POSSÍVEL.
    """
    cursor = conn.cursor()
    # Verifica se a tabela já existe para não resetar sem querer
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='matches'")
    if cursor.fetchone():
        print("⚠️ Tabela 'matches' já existe. Mantendo dados atuais.")
        return

    print("🔄 Criando estrutura do banco de dados (Schema Completo)...")
    
    # 1. Tabela Principal (Meta)
    cursor.execute('''
        CREATE TABLE matches (
            match_id TEXT PRIMARY KEY,
            game_version TEXT,
            game_duration INTEGER,
            winner_team INTEGER
        )
    ''')

    # 2. Tabela de Times
    cursor.execute('''
        CREATE TABLE match_teams (
            match_id TEXT,
            team_id INTEGER,
            win BOOLEAN,
            baron_kills INTEGER, dragon_kills INTEGER, rift_herald_kills INTEGER, void_grub_kills INTEGER,
            tower_kills INTEGER, inhibitor_kills INTEGER,
            first_blood BOOLEAN, first_tower BOOLEAN, first_dragon BOOLEAN, first_baron BOOLEAN,
            FOREIGN KEY (match_id) REFERENCES matches(match_id)
        )
    ''')

    # 3. Tabela de Participantes
    cursor.execute('''
        CREATE TABLE match_participants (
            match_id TEXT,
            puuid TEXT,
            champion_id INTEGER,
            team_id INTEGER,
            participant_id INTEGER,
            win BOOLEAN,
            kills INTEGER, deaths INTEGER, assists INTEGER,
            gold_earned INTEGER, gold_spent INTEGER,
            total_minions_killed INTEGER, neutral_minions_killed INTEGER,
            vision_score INTEGER, wards_placed INTEGER, wards_killed INTEGER,
            spell1Id INTEGER, spell2Id INTEGER,
            perk_primary_style INTEGER, perk_sub_style INTEGER,
            item0 INTEGER, item1 INTEGER, item2 INTEGER, item3 INTEGER, 
            item4 INTEGER, item5 INTEGER, item6 INTEGER,
            total_damage_dealt INTEGER, physical_damage_dealt_to_champions INTEGER,
            magic_damage_dealt_to_champions INTEGER, true_damage_dealt_to_champions INTEGER,
            total_damage_taken INTEGER, damage_dealt_to_turrets INTEGER, damage_self_mitigated INTEGER,
            time_ccing_others INTEGER, total_heal INTEGER, total_units_healed INTEGER,
            lane TEXT, role TEXT,
            PRIMARY KEY (match_id, puuid),
            FOREIGN KEY (match_id) REFERENCES matches(match_id)
        )
    ''')

    # 4. Tabela de Bans
    cursor.execute('''
        CREATE TABLE match_bans (
            match_id TEXT,
            team_id INTEGER,
            champion_id INTEGER,
            pick_turn INTEGER,
            FOREIGN KEY (match_id) REFERENCES matches(match_id)
        )
    ''')

    # 5. Tabela de Timeline Times
    cursor.execute('''
        CREATE TABLE match_timeline_stats (
            match_id TEXT,
            timestamp INTEGER,
            team_id INTEGER,
            total_gold INTEGER, total_xp INTEGER, total_minions INTEGER,
            kills_at_time INTEGER, towers_at_time INTEGER, dragons_at_time INTEGER,
            gold_diff INTEGER,
            FOREIGN KEY (match_id) REFERENCES matches(match_id)
        )
    ''')

    # 6. Tabela de Timeline Individual
    cursor.execute('''
        CREATE TABLE match_timeline_participants (
            match_id TEXT,
            timestamp INTEGER,
            participant_id INTEGER,
            total_gold INTEGER, current_gold INTEGER, total_xp INTEGER, level INTEGER,
            minions_killed INTEGER, jungle_minions_killed INTEGER,
            position_x INTEGER, position_y INTEGER,
            FOREIGN KEY (match_id) REFERENCES matches(match_id)
        )
    ''')
    
    conn.commit()
    print("✅ Banco de dados pronto!")

# --- UI HELPER (BARRA DE PROGRESSO) ---

def print_progress(player_idx, total_players, player_name, current_match, total_matches, total_saved, status):
    """Exibe uma barra de progresso limpa que se sobrescreve."""
    
    # Barra de progresso dos jogos do jogador atual
    bar_len = 15
    if total_matches > 0:
        filled_len = int(bar_len * current_match // total_matches)
        pct = (current_match / total_matches) * 100
    else:
        filled_len = 0
        pct = 0
        
    bar = "█" * filled_len + "-" * (bar_len - filled_len)
    
    # Formata a string (limitando o tamanho do nome para não quebrar linha)
    p_name = (player_name[:10] + '..') if len(player_name) > 10 else player_name
    
    # \r volta pro inicio, \033[K limpa o resto da linha
    msg = f"\r[{player_idx}/{total_players}] {p_name:<12} |{bar}| {pct:.0f}% | DB: {total_saved} | {status}"
    
    # Garante que a linha apague o texto anterior se for mais curto
    sys.stdout.write(msg + "\033[K") 
    sys.stdout.flush()

# --- FUNÇÕES DE API ---

def request_riot(url):
    """Wrapper com rate limit silencioso."""
    retries = 0
    while retries < 5:
        try:
            resp = requests.get(url, headers=HEADERS)
            
            if resp.status_code == 200:
                return resp.json()
            
            elif resp.status_code == 429:
                retry_after = int(resp.headers.get('Retry-After', 5))
                if retry_after > 5:
                    print(f"\n⏳ Rate Limit! Pausa de {retry_after}s...")
                time.sleep(retry_after)
                retries += 1
                continue
                
            elif resp.status_code == 403:
                print(f"\n❌ ERRO 403: API Key inválida ou expirada.")
                sys.exit(1) # Para o script se a chave for ruim
                
            elif resp.status_code == 404:
                return None 
                
            else:
                # Erros de servidor (500, 503)
                time.sleep(2)
                retries += 1
                
        except Exception as e:
            time.sleep(2)
            retries += 1
            
    return None

def get_current_patch_prefix():
    data = request_riot("https://ddragon.leagueoflegends.com/api/versions.json")
    if data:
        # Ex: "14.3.1" -> "14.3"
        return ".".join(data[0].split(".")[:2])
    return None

def get_high_elo_players():
    """
    Busca TODOS os jogadores de Challenger, Grandmaster e Master.
    """
    tiers = [
        ("Desafiante", "challengerleagues"),
        ("Grão-Mestre", "grandmasterleagues"),
        ("Mestre", "masterleagues")
    ]
    
    all_players = []
    
    for tier_name, endpoint in tiers:
        print(f"🔍 Baixando lista de {tier_name}...")
        url = f"https://{REGION_API}.api.riotgames.com/lol/league/v4/{endpoint}/by-queue/{QUEUE_TYPE}"
        data = request_riot(url)
        
        if data and 'entries' in data:
            players = data['entries']
            # Ordena por LP apenas para garantir que pegamos os melhores primeiro se o script parar
            players.sort(key=lambda x: x['leaguePoints'], reverse=True)
            all_players.extend(players)
            print(f"   -> {len(players)} jogadores adicionados.")
        
        time.sleep(1) # Pequena pausa entre requests de liga
            
    print(f"✅ Total de jogadores High Elo encontrados: {len(all_players)}")
    return all_players

def get_puuid(summoner_id):
    url = f"https://{REGION_API}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
    data = request_riot(url)
    return data['puuid'] if data else None

def get_match_ids(puuid, count):
    # queue=420 é Ranked Solo/Duo
    url = f"https://{MATCH_API}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={count}&queue=420"
    return request_riot(url) or []

def get_match_details(match_id):
    return request_riot(f"https://{MATCH_API}.api.riotgames.com/lol/match/v5/matches/{match_id}")

def get_match_timeline(match_id):
    return request_riot(f"https://{MATCH_API}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline")

def match_exists_in_db(conn, match_id):
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM matches WHERE match_id = ?", (match_id,))
    return cursor.fetchone() is not None

# --- LÓGICA DE PERSISTÊNCIA ---

def save_match_full(details, timeline, conn):
    cursor = conn.cursor()
    info = details['info']
    match_id = details['metadata']['matchId']
    
    # Dupla verificação para segurança
    if match_exists_in_db(conn, match_id): return False

    winner_team = 0
    for team in info['teams']:
        if team['win']: winner_team = team['teamId']
        objs = team.get('objectives', {})
        
        cursor.execute('''
            INSERT INTO match_teams VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            match_id, team['teamId'], team['win'],
            objs.get('baron', {}).get('kills', 0),
            objs.get('dragon', {}).get('kills', 0),
            objs.get('riftHerald', {}).get('kills', 0),
            objs.get('horde', {}).get('kills', 0),
            objs.get('tower', {}).get('kills', 0),
            objs.get('inhibitor', {}).get('kills', 0),
            objs.get('champion', {}).get('first', False),
            objs.get('tower', {}).get('first', False),
            objs.get('dragon', {}).get('first', False),
            objs.get('baron', {}).get('first', False)
        ))

        for ban in team.get('bans', []):
            cursor.execute('''INSERT INTO match_bans VALUES (?, ?, ?, ?)''', 
                           (match_id, team['teamId'], ban['championId'], ban['pickTurn']))

    cursor.execute('''INSERT INTO matches VALUES (?, ?, ?, ?)''', 
                   (match_id, info['gameVersion'], info['gameDuration'], winner_team))

    for p in info['participants']:
        perk_primary, perk_sub = 0, 0
        try:
            perk_primary = p['perks']['styles'][0]['style']
            perk_sub = p['perks']['styles'][1]['style']
        except: pass

        values = (
            match_id, p['puuid'], p['championId'], p['teamId'], p['participantId'], p['win'],
            p['kills'], p['deaths'], p['assists'], 
            p['goldEarned'], p['goldSpent'],
            p['totalMinionsKilled'], p['neutralMinionsKilled'],
            p['visionScore'], p['wardsPlaced'], p['wardsKilled'],
            p.get('summoner1Id', 0), p.get('summoner2Id', 0),
            perk_primary, perk_sub,
            p.get('item0', 0), p.get('item1', 0), p.get('item2', 0), p.get('item3', 0),
            p.get('item4', 0), p.get('item5', 0), p.get('item6', 0),
            p['totalDamageDealtToChampions'], p['physicalDamageDealtToChampions'],
            p['magicDamageDealtToChampions'], p['trueDamageDealtToChampions'],
            p['totalDamageTaken'], p['damageDealtToTurrets'], p['damageSelfMitigated'],
            p['timeCCingOthers'], p['totalHeal'], p['totalUnitsHealed'],
            p.get('lane', 'NONE'), p.get('role', 'NONE')
        )
        
        placeholders = ",".join(["?"] * len(values))
        cursor.execute(f'INSERT INTO match_participants VALUES ({placeholders})', values)

    if timeline:
        _process_timeline_snapshots(match_id, timeline, conn)

    conn.commit()
    return True

def _process_timeline_snapshots(match_id, timeline_data, conn):
    cursor = conn.cursor()
    frames = timeline_data['info']['frames']
    snapshots = [10, 20, 30] 
    
    for minute in snapshots:
        if len(frames) <= minute: continue
        current_frame = frames[minute]
        
        team_stats = {100: {'gold':0, 'xp':0, 'minions':0, 'kills':0, 'towers':0, 'dragons':0},
                      200: {'gold':0, 'xp':0, 'minions':0, 'kills':0, 'towers':0, 'dragons':0}}
        
        p_frames = current_frame['participantFrames']
        for p_id_str, p_data in p_frames.items():
            p_id = int(p_id_str)
            # Safe check for team ID logic (participants 1-5 = 100, 6-10 = 200)
            team = 100 if p_id <= 5 else 200
            
            p_gold = p_data['totalGold']
            p_xp = p_data['xp']
            p_minions = p_data['minionsKilled'] + p_data['jungleMinionsKilled']
            
            cursor.execute('''INSERT INTO match_timeline_participants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (match_id, minute, p_id, p_gold, p_data['currentGold'], p_xp, p_data['level'],
                 p_data['minionsKilled'], p_data['jungleMinionsKilled'],
                 p_data.get('position', {}).get('x', 0), p_data.get('position', {}).get('y', 0)))
            
            team_stats[team]['gold'] += p_gold
            team_stats[team]['xp'] += p_xp
            team_stats[team]['minions'] += p_minions
            
        # Events Aggregation
        for i in range(minute + 1):
            for event in frames[i]['events']:
                ev_type = event['type']
                if ev_type == 'CHAMPION_KILL':
                    killer = event.get('killerId', 0)
                    if 1 <= killer <= 5: team_stats[100]['kills'] += 1
                    elif 6 <= killer <= 10: team_stats[200]['kills'] += 1
                elif ev_type == 'BUILDING_KILL' and event.get('buildingType') == 'TOWER_BUILDING':
                    loser = event.get('teamId')
                    winner = 100 if loser == 200 else 200
                    team_stats[winner]['towers'] += 1
                elif ev_type == 'ELITE_MONSTER_KILL' and event.get('monsterType') == 'DRAGON':
                    killer = event.get('killerTeamId')
                    if killer in [100, 200]: team_stats[killer]['dragons'] += 1

        for team in [100, 200]:
            enemy = 200 if team == 100 else 100
            cursor.execute('''INSERT INTO match_timeline_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (match_id, minute, team, team_stats[team]['gold'], team_stats[team]['xp'], team_stats[team]['minions'],
                 team_stats[team]['kills'], team_stats[team]['towers'], team_stats[team]['dragons'],
                 team_stats[team]['gold'] - team_stats[enemy]['gold']))

# --- LOOP PRINCIPAL ---

def run():
    patch_prefix = get_current_patch_prefix()
    if not patch_prefix: 
        print("❌ Erro ao detectar patch atual.")
        return
        
    print(f"\n🎯 Crawler Iniciado | Foco: Patch {patch_prefix}.x Completo\n")
    
    conn = sqlite3.connect(DB_PATH)
    init_match_db(conn)
    
    all_high_elo = get_high_elo_players()
    if not all_high_elo: return
    
    # Estatísticas iniciais
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM matches")
    total_saved = cursor.fetchone()[0]
    
    # Conjunto para cache rápido de memória (evita bater no DB toda hora para check)
    # Carregando IDs já existentes para memória para performance extrema
    print("⏳ Carregando cache de partidas existentes...")
    cursor.execute("SELECT match_id FROM matches")
    processed_matches = set(row[0] for row in cursor.fetchall())
    print(f"📦 Cache carregado: {len(processed_matches)} partidas ignoradas se aparecerem novamente.")

    total_players = len(all_high_elo)
    
    print(f"\n🚀 Iniciando coleta a partir do índice {START_INDEX}...\n")
    
    for i, player in enumerate(all_high_elo):
        if i < START_INDEX:
            continue
            
        p_name = player.get('summonerName', 'Anon')
        p_idx = i + 1
        
        # UI Inicial do Jogador
        print_progress(p_idx, total_players, p_name, 0, MATCHES_PER_PLAYER, total_saved, "Buscando PUUID...")
        
        # 1. PUUID
        puuid = None
        if 'puuid' in player: puuid = player['puuid']
        elif 'summonerId' in player:
            time.sleep(0.1) # Pequeno delay
            puuid = get_puuid(player['summonerId'])
            
        if not puuid:
            print_progress(p_idx, total_players, p_name, 0, MATCHES_PER_PLAYER, total_saved, "Erro PUUID")
            continue
        
        # 2. Lista de Partidas
        print_progress(p_idx, total_players, p_name, 0, MATCHES_PER_PLAYER, total_saved, "Listando Partidas...")
        time.sleep(0.5) 
        match_ids = get_match_ids(puuid, count=MATCHES_PER_PLAYER)
        
        if not match_ids: continue
        
        # 3. Processamento das Partidas
        for m_idx, m_id in enumerate(match_ids):
            current_status = ""
            stop_player = False
            
            # Passo A: Verifica Cache (Memória + DB)
            if m_id in processed_matches:
                current_status = "Já existe"
                # Não paramos o loop aqui, pois o jogador pode ter jogado uma partida NOVA
                # que já foi baixada por OUTRO jogador, mas ainda precisamos checar se
                # as próximas partidas dele são antigas ou novas.
                # Como a lista vem ordenada cronologicamente (mais nova -> mais velha),
                # se já existe, provavelmente é do patch atual. Continuamos verificando.
            else:
                # Passo B: Download Real
                time.sleep(1.2) # Respeitando Rate Limit (100 reqs/2 min = ~0.83 reqs/seg)
                details = get_match_details(m_id)
                
                if details:
                    try:
                        game_version = details['info']['gameVersion']
                        
                        # VERIFICAÇÃO CRÍTICA DO PATCH
                        if game_version.startswith(patch_prefix):
                            # É do patch atual -> Baixa Timeline e Salva
                            time.sleep(1.2)
                            timeline = get_match_timeline(m_id)
                            
                            if save_match_full(details, timeline, conn):
                                total_saved += 1
                                processed_matches.add(m_id) # Adiciona ao cache
                                current_status = "Salvo!"
                            else:
                                current_status = "Erro Salvar"
                                
                        else:
                            # Encontrou partida de patch antigo
                            # Como a lista é ordenada, TODAS as próximas também serão antigas.
                            current_status = f"Patch Antigo ({game_version})"
                            stop_player = True # Pula para o próximo jogador
                            
                    except Exception as e:
                        current_status = f"Erro: {str(e)[:10]}"
                else:
                    current_status = "Erro Download"
                
            # Atualiza Barra
            print_progress(p_idx, total_players, p_name, m_idx + 1, len(match_ids), total_saved, current_status)
            
            if stop_player:
                break

    conn.close()
    print(f"\n\n🏁 Coleta finalizada. Total no banco: {total_saved}")

if __name__ == "__main__":
    run()