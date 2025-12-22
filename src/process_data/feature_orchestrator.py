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
    # NOVO: Importa o fixador de roles
    from src.process_data.features.role_fixer import resolve_team_roles
except ImportError:
    # Fallback para execução direta
    from features.mechanics import calculate_mechanics
    from features.stats import calculate_stats
    from features.damage_profile import calculate_damage_profile
    from features.classes import calculate_class_counts
    from features.lane_matchups import calculate_lane_matchups
    from features.role_fixer import resolve_team_roles

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'lol_database.db')

def load_reference_data(conn):
    """Carrega dados de Champions respeitando o Schema existente."""
    print("Carregando dados de referência...")
    
    # Nota: Mantendo nomes snake_case conforme seu banco de dados
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
    """Cria a tabela 'game_features'."""
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS game_features")
    
    columns_sql = [
        "match_id TEXT PRIMARY KEY",
        "patch_version TEXT",
        "winner_team INTEGER" # 1 (Blue) ou 0 (Red)
    ]
    
    for key in feature_keys:
        columns_sql.append(f"{key} REAL")
        
    sql = f"CREATE TABLE game_features ({', '.join(columns_sql)})"
    
    print(f"Criando tabela 'game_features' com {len(columns_sql)} colunas...")
    cursor.execute(sql)
    conn.commit()

def run_orchestrator():
    start_time = time.time()
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Carrega Referências
    try:
        df_champs, df_features_ref = load_reference_data(conn)
    except Exception as e:
        print(f"ERRO AO CARREGAR DADOS DE CAMPEÕES: {e}")
        return

    # 2. Busca Partidas
    print("Buscando partidas no banco...")
    
    # ATUALIZADO: Inclui spell1Id e spell2Id para o Role Fixer
    query_matches = """
        SELECT m.match_id, m.game_version, m.winner_team, 
               p.team_id, p.champion_id, p.lane, p.role,
               p.spell1Id, p.spell2Id
        FROM matches m
        JOIN match_participants p ON m.match_id = p.match_id
    """
    df_matches = pd.read_sql(query_matches, conn)
    grouped_matches = df_matches.groupby('match_id')
    
    print(f"Total de partidas encontradas: {len(grouped_matches)}")
    
    rows_to_insert = []
    feature_columns_order = [] 
    table_created = False
    
    processed_count = 0
    saved_count = 0
    dropped_count = 0
    
    for match_id, group in grouped_matches:
        processed_count += 1
        first_row = group.iloc[0]
        patch = ".".join(first_row['game_version'].split(".")[:2])
        
        # --- CORREÇÃO DO WINNER TEAM ---
        # Converte para int nativo (evita bug numpy/sqlite)
        raw_winner = int(first_row['winner_team'])
        winner = 1 if raw_winner == 100 else 0
        
        # Separa os DataFrames dos times
        df_blue = group[group['team_id'] == 100]
        df_red = group[group['team_id'] == 200]
        
        # Validação Básica: Precisa ter 5 linhas no DB para cada lado
        if len(df_blue) < 5 or len(df_red) < 5:
            dropped_count += 1
            continue

        # --- TENTATIVA DE CORREÇÃO DE ROLES (ROLE FIXER) ---
        # Usa Tags + Smite/Spells para resolver duplicatas
        blue_roles_dict = resolve_team_roles(df_blue, df_champs)
        red_roles_dict = resolve_team_roles(df_red, df_champs)
        
        # Cria as listas limpas baseadas no dicionário resolvido
        blue_list = list(blue_roles_dict.values())
        red_list = list(red_roles_dict.values())
        
        # Validação Final: Se mesmo após o fix não tivermos 5 campeões únicos
        if len(set(blue_list)) < 5 or len(set(red_list)) < 5:
            dropped_count += 1
            # print(f"[WARN] Dropando {match_id} - Erro grave de integridade.")
            continue
            
        # --- CÁLCULO DE FEATURES ---
        
        # Features Globais (Usam a lista limpa)
        feat_mech = calculate_mechanics(blue_list, red_list, patch, df_features_ref)
        feat_stats = calculate_stats(blue_list, red_list, patch, df_champs)
        feat_dmg = calculate_damage_profile(blue_list, red_list, patch, df_champs)
        feat_class = calculate_class_counts(blue_list, red_list, patch, df_champs)
        
        # Features de Lane (Usam o dicionário corrigido com posições inferidas)
        feat_lane = calculate_lane_matchups(blue_roles_dict, red_roles_dict, patch, df_champs, df_features_ref)
        
        # Merge de tudo
        all_features = {**feat_mech, **feat_stats, **feat_dmg, **feat_class, **feat_lane}
        
        # Setup da tabela na primeira iteração válida
        if not table_created:
            feature_columns_order = list(all_features.keys())
            create_dynamic_table(conn, feature_columns_order)
            table_created = True
            
        # Montagem da linha
        row_values = [match_id, patch, winner]
        for key in feature_columns_order:
            row_values.append(all_features.get(key, 0))
            
        rows_to_insert.append(tuple(row_values))
        saved_count += 1
        
        if processed_count % 500 == 0:
            print(f"Processadas: {processed_count} | Salvas: {saved_count} | Dropadas: {dropped_count}")

    # 4. Salvar no Banco
    if rows_to_insert:
        print(f"\nSalvando {len(rows_to_insert)} linhas na tabela 'game_features'...")
        print(f"Total dropadas (irrecuperáveis): {dropped_count}")
        
        cursor = conn.cursor()
        total_cols = 3 + len(feature_columns_order)
        placeholders = ",".join(["?"] * total_cols)
        sql = f"INSERT OR REPLACE INTO game_features VALUES ({placeholders})"
        
        try:
            cursor.executemany(sql, rows_to_insert)
            conn.commit()
            print("Sucesso! Tabela populada.")
        except Exception as e:
            print(f"Erro ao salvar no banco: {e}")
    else:
        print("Nenhuma partida válida foi gerada.")

    conn.close()
    print(f"Orquestração finalizada em {time.time() - start_time:.2f} segundos.")

if __name__ == "__main__":
    run_orchestrator()