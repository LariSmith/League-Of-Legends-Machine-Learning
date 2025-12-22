import sqlite3
import pandas as pd
import os
import re

# Configuração de caminhos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'lol_database.db')

def load_data(conn):
    """Carrega campeões e habilidades, unindo os textos."""
    print("Carregando dados do banco...")
    
    # Carrega dados base
    df_champs = pd.read_sql("""
        SELECT champion_key, patch_version, name, passive_name, passive_desc 
        FROM champions
    """, conn)
    
    # Carrega habilidades
    df_abilities = pd.read_sql("""
        SELECT champion_key, patch_version, name as spell_name, description 
        FROM abilities
    """, conn)
    
    # Agrupa todas as habilidades de um campeão em uma única string
    # Ex: Um texto só contendo a descrição do Q, W, E e R juntos
    df_abilities_grouped = df_abilities.groupby(['champion_key', 'patch_version'])['description'].apply(lambda x: ' '.join(x)).reset_index()
    df_abilities_grouped.rename(columns={'description': 'spells_desc'}, inplace=True)
    
    # Junta (Merge) as tabelas
    df_full = pd.merge(df_champs, df_abilities_grouped, on=['champion_key', 'patch_version'], how='left')
    
    # Cria uma coluna 'full_text' com TUDO (Passiva + Skills) e converte para minúsculo
    df_full['full_text'] = (
        df_full['passive_name'].fillna('') + " " + 
        df_full['passive_desc'].fillna('') + " " + 
        df_full['spells_desc'].fillna('')
    ).str.lower()
    
    return df_full

def apply_keywords(df):
    """Aplica regras de keywords para gerar features binárias."""
    print("Aplicando engenharia de features (Keywords em PT-BR)...")

    # Dicionário de mecânicas e suas palavras-chave
    mechanics = {
        # --- Controle de Grupo (CC) ---
        'has_hard_cc': ['atordo', 'stun', 'arremess', 'knockup', 'temor', 'fear', 'suprim', 'provoca', 'taunt', 'enraíz', 'root', 'adormec', 'sleep'],
        'has_soft_cc': ['lentid', 'slow', 'cegueira', 'blind', 'silêncio', 'silence', 'polimorf'],
        'has_hook': ['puxa', 'arrasta', 'gancho'], # Ex: Blitz, Thresh, Nautilus

        # --- Sustentação e Defesa ---
        'has_heal': ['curar', 'restaura vida', 'curam', 'regenera'],
        'has_shield': ['escudo', 'barreira', 'shield'],
        'has_immortality': ['imortal', 'não pode morrer', 'revive', 'zumbis'], # Ex: Trynda, Zilean, Sion

        # --- Dano e Ofensiva ---
        'has_true_damage': ['dano verdadeiro', 'true damage'],
        'has_execute': ['executa', 'abaixo de', 'vida perdida'], # Ex: Pyke, Garen, Riven
        'has_percent_hp_dmg': ['vida máxima', 'vida atual', '% da vida'], # Anti-tank
        
        # --- Mobilidade ---
        'has_dash': ['avança', 'investida', 'dash', 'desliza'],
        'has_blink': ['teleporte', 'transloca', 'piscar', 'blink', 'surgir atrás'], # Ex: Ezreal, Kat, Zed
        'has_ms_buff': ['velocidade de movimento', 'bônus de velocidade'],

        # --- Mecânicas Específicas ---
        'has_stealth': ['invisí', 'camufla', 'furtiv'],
        'has_summon': ['invoca', 'cria', 'torre', 'margarida', 'tibbers', 'voidling'], # Pets
        'is_stacking': ['acúmulo', 'permanentemente', 'infinito', 'stacks'] # Nasus, Veigar, Aurelion
    }

    # Aplica a lógica: Se qualquer palavra da lista estiver no texto, valor = 1, senão 0
    for feature, keywords in mechanics.items():
        # Regex pattern: procura qualquer palavra da lista
        # O '|' funciona como OR no regex. Ex: "atordo|stun|arremess"
        pattern = '|'.join(keywords)
        df[feature] = df['full_text'].str.contains(pattern, na=False, regex=True).astype(int)

    return df

def save_features(df, conn):
    """Salva a nova tabela de features no banco."""
    
    # Seleciona apenas as colunas chaves + features criadas
    # Remove colunas de texto cru para economizar espaço
    cols_to_keep = ['champion_key', 'patch_version'] + [col for col in df.columns if col.startswith('has_') or col.startswith('is_')]
    
    df_final = df[cols_to_keep]
    
    print(f"Salvando tabela 'champion_features' com {len(df_final)} linhas...")
    df_final.to_sql('champion_features', conn, if_exists='replace', index=False)
    print("Sucesso!")

def run():
    conn = sqlite3.connect(DB_PATH)
    try:
        df = load_data(conn)
        df_features = apply_keywords(df)
        
        # Validar um exemplo antes de salvar
        print("\n--- Validação: Blitzcrank (Deve ter Hook, CC e Shield) ---")
        check = df_features[df_features['name'] == 'Blitzcrank'].iloc[0]
        print(f"Hook: {check['has_hook']}")
        print(f"Hard CC: {check['has_hard_cc']}")
        print(f"Shield: {check['has_shield']}")
        print("----------------------------------------------------------\n")

        save_features(df_features, conn)
        
    finally:
        conn.close()

if __name__ == "__main__":
    run()