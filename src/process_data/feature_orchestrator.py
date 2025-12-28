import sqlite3
import pandas as pd
import os
import time
import sys

# Ajuste de path e imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'features'))

try:
    from src.process_data.features.mechanics import calculate_mechanics
    from src.process_data.features.stats import calculate_stats
    from src.process_data.features.damage_profile import calculate_damage_profile
    from src.process_data.features.classes import calculate_class_counts
    from src.process_data.features.lane_matchups import calculate_lane_matchups
    from src.process_data.features.role_fixer import resolve_team_roles
    from src.process_data.features.live_prediction import calculate_live_features
    from src.process_data.features.winrates import RollingWinrate
except ImportError:
    from features.mechanics import calculate_mechanics
    from features.stats import calculate_stats
    from features.damage_profile import calculate_damage_profile
    from features.classes import calculate_class_counts
    from features.lane_matchups import calculate_lane_matchups
    from features.role_fixer import resolve_team_roles
    from features.live_prediction import calculate_live_features
    from features.winrates import RollingWinrate

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'lol_database.db')

def load_reference_data(conn):
    print("Carregando dados estáticos...")
    # Restaurando todas as colunas necessárias para os cálculos de stats e mecânicas
    query_champs = """
        SELECT 
            champion_key, patch_version, name, tags,
            hp, hp_per_level, 
            mp, mp_per_level,
            armor, armor_per_level, 
            spellblock, spellblock_per_level,
            attackrange, 
            hpregen, hpregen_per_level,
            attackdamage, attackdamage_per_level, 
            attackspeed, attackspeed_per_level,
            movespeed
        FROM champions
    """
    df_champs = pd.read_sql(query_champs, conn)
    query_features = "SELECT * FROM champion_features"
    df_features = pd.read_sql(query_features, conn)
    return df_champs, df_features

def create_dynamic_table(conn, feature_keys):
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS game_features")
    
    columns_sql = [
        "match_id TEXT PRIMARY KEY",
        "patch_version TEXT",
        "winner_team INTEGER"
    ]
    for key in feature_keys:
        columns_sql.append(f"{key} REAL")
        
    sql = f"CREATE TABLE game_features ({', '.join(columns_sql)})"
    cursor.execute(sql)
    conn.commit()

def run_orchestrator():
    start_time = time.time()
    conn = sqlite3.connect(DB_PATH)
    
    try:
        df_champs, df_features_ref = load_reference_data(conn)
    except Exception as e:
        print(f"Erro ao carregar referências: {e}")
        return

    print("Buscando partidas ordenadas por tempo...")
    query_matches = """
        SELECT m.match_id, m.game_version, m.winner_team, 
               p.team_id, p.champion_id, p.lane, p.role
        FROM matches m
        JOIN match_participants p ON m.match_id = p.match_id
        ORDER BY m.match_id ASC
    """
    df_matches = pd.read_sql(query_matches, conn)
    unique_match_ids = df_matches['match_id'].unique()
    
    winrate_model = RollingWinrate()
    rows_to_insert = []
    feature_columns_order = [] 
    table_created = False
    processed_count = 0
    grouped_matches = df_matches.groupby('match_id')

    # Ordem canónica das posições para garantir consistência nas features
    ROLE_ORDER = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']

    for match_id in unique_match_ids:
        group = grouped_matches.get_group(match_id)
        first_row = group.iloc[0]
        patch = ".".join(first_row['game_version'].split(".")[:2])
        winner = 1 if int(first_row['winner_team']) == 100 else 0
        
        df_blue = group[group['team_id'] == 100]
        df_red = group[group['team_id'] == 200]
        
        if len(df_blue) < 5 or len(df_red) < 5: continue

        # Resolve posições
        blue_roles_dict = resolve_team_roles(df_blue, df_champs)
        red_roles_dict = resolve_team_roles(df_red, df_champs)

        # CRUCIAL: Criar listas baseadas na ROLE_ORDER para o RollingWinrate funcionar por posição
        blue_list = [blue_roles_dict.get(role, 0) for role in ROLE_ORDER]
        red_list = [red_roles_dict.get(role, 0) for role in ROLE_ORDER]
        
        # Ignora partidas onde a resolução de roles falhou (ex: IDs duplicados ou roles faltando)
        if 0 in blue_list or 0 in red_list: continue
            
        # 1. Features Estáticas e Matchups
        feat_mech = calculate_mechanics(blue_list, red_list, patch, df_features_ref)
        feat_stats = calculate_stats(blue_list, red_list, patch, df_champs)
        feat_dmg = calculate_damage_profile(blue_list, red_list, patch, df_champs)
        feat_class = calculate_class_counts(blue_list, red_list, patch, df_champs)
        feat_lane = calculate_lane_matchups(blue_roles_dict, red_roles_dict, patch, df_champs, df_features_ref)
        
        # 2. Features de Winrate (Rolling) - Agora inclui diferenciais por posição
        feat_rolling = winrate_model.get_features(blue_list, red_list)
        
        # 3. Live Prediction (Timeline)
        query_ts = "SELECT * FROM match_timeline_stats WHERE match_id = ?"
        df_ts = pd.read_sql(query_ts, conn, params=(match_id,))
        query_tp = """
            SELECT tp.*, p.champion_id FROM match_timeline_participants tp
            JOIN match_participants p ON tp.match_id = p.match_id AND tp.participant_id = p.participant_id
            WHERE tp.match_id = ?
        """
        df_tp = pd.read_sql(query_tp, conn, params=(match_id,))
        feat_live = calculate_live_features(match_id, blue_roles_dict, red_roles_dict, df_ts, df_tp)

        # 4. Identity IDs
        feat_ids = {}
        for i, role in enumerate(ROLE_ORDER):
            r_label = ['top', 'jungle', 'mid', 'adc', 'sup'][i]
            feat_ids[f'blue_{r_label}_id'] = blue_list[i]
            feat_ids[f'red_{r_label}_id'] = red_list[i]

        # 5. Merge
        all_features = {
            **feat_mech, **feat_stats, **feat_dmg, **feat_class, 
            **feat_lane, **feat_live, **feat_ids, **feat_rolling 
        }
        
        if not table_created:
            feature_columns_order = list(all_features.keys())
            create_dynamic_table(conn, feature_columns_order)
            table_created = True
            
        row_values = [match_id, patch, winner]
        for key in feature_columns_order:
            row_values.append(all_features.get(key, 0))
            
        rows_to_insert.append(tuple(row_values))
        
        # 6. Atualização do Aprendizado (Update DEPOIS de extrair as features)
        winrate_model.update(blue_list, red_list, winner)

        processed_count += 1
        if processed_count % 500 == 0:
            print(f"Processadas: {processed_count}")

    if rows_to_insert:
        print(f"\nSalvando {len(rows_to_insert)} partidas em game_features...")
        cursor = conn.cursor()
        total_cols = 3 + len(feature_columns_order)
        placeholders = ",".join(["?"] * total_cols)
        sql = f"INSERT OR REPLACE INTO game_features VALUES ({placeholders})"
        cursor.executemany(sql, rows_to_insert)
        conn.commit()
    
    conn.close()
    print(f"Concluído em {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    run_orchestrator()