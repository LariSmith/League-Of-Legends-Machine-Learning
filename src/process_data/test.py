import sqlite3
import pandas as pd
import numpy as np
import os

# Configuração do caminho (ajuste se necessário)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'lol_database.db')

def run_audit():
    if not os.path.exists(DB_PATH):
        print(f"Erro: Banco de dados não encontrado em {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    
    print("--- Iniciando Auditoria da Tabela game_features ---")
    
    # 1. Carregamento dos dados
    df = pd.read_sql("SELECT * FROM game_features", conn)
    conn.close()

    if df.empty:
        print("A tabela está vazia!")
        return

    total_rows = len(df)
    print(f"Total de registros: {total_rows}")

    # 2. Verificação de Nulos e Zeros
    print("\n--- Integridade de Dados ---")
    null_counts = df.isnull().sum().sum()
    print(f"Valores nulos encontrados: {null_counts}")
    
    # Verificar se os IDs de campeões foram preenchidos
    id_cols = [c for c in df.columns if '_id' in c]
    zero_ids = (df[id_cols] == 0).sum().sum()
    print(f"IDs de campeões zerados: {zero_ids} (Esperado: 0 se o role_fixer funcionou)")

    # 3. Auditoria Específica de Winrates (A nova implementação)
    wr_cols = [
        'blue_avg_winrate', 'red_avg_winrate', 'winrate_diff_total',
        'diff_winrate_top', 'diff_winrate_jungle', 'diff_winrate_mid', 
        'diff_winrate_adc', 'diff_winrate_support'
    ]
    
    print("\n--- Estatísticas de Rolling Winrates ---")
    wr_stats = df[wr_cols].describe().loc[['mean', 'min', 'max', 'std']]
    print(wr_stats)

    # Verificação de Variância (Rolling Windows devem variar conforme as partidas passam)
    # Se o std for 0, as estatísticas não estão sendo atualizadas.
    for col in wr_cols:
        if df[col].std() == 0:
            print(f"ALERTA: Feature {col} tem variância ZERO. Verifique se o update() está funcionando.")

    # 4. Verificação de Consistência Matemática
    # winrate_diff_total deve ser igual a blue_avg - red_avg
    calc_diff = df['blue_avg_winrate'] - df['red_avg_winrate']
    error = np.abs(df['winrate_diff_total'] - calc_diff).max()
    print(f"\nErro máximo de cálculo (diff_total): {error:.6f}")

    # 5. Evolução Temporal (Check de Data Leakage vs Aprendizado)
    # Nas primeiras partidas, os winrates devem estar muito próximos de 0.5 (devido ao Laplace)
    # No final, a dispersão deve ser maior.
    print("\n--- Verificação de Evolução (Rolling Window) ---")
    first_100 = df.head(100)['winrate_diff_total'].std()
    last_100 = df.tail(100)['winrate_diff_total'].std()
    print(f"Desvio Padrão (Primeiras 100): {first_100:.4f}")
    print(f"Desvio Padrão (Últimas 100): {last_100:.4f}")
    
    if last_100 > first_100:
        print("OK: A variância aumentou, indicando que o modelo acumulou histórico.")
    else:
        print("AVISO: A variância não aumentou. Pode haver poucos dados ou erro no update.")

    # 6. Correlação com o Vencedor (Poder Preditivo)
    print("\n--- Correlação com winner_team (Target) ---")
    correlations = df[wr_cols + ['winner_team']].corr()['winner_team'].sort_values(ascending=False)
    print(correlations)

    # 7. Check de Features "Live" (10 e 20 min)
    live_cols = [c for c in df.columns if 'live_' in c]
    if live_cols:
        print("\n--- Check de Dados Live (Timeline) ---")
        live_zeros = (df[live_cols] == 0).sum().mean()
        print(f"Média de zeros em colunas live: {live_zeros:.2f} (Comum em jogos que terminam cedo)")

if __name__ == "__main__":
    run_audit()