import optuna
import xgboost as xgb
import pandas as pd
import sqlite3
import os
import sys
import warnings
import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score

# --- CONFIGURAÇÕES DE SILÊNCIO ---
warnings.filterwarnings('ignore')
optuna.logging.set_verbosity(optuna.logging.WARNING)

# --- CONFIGURAÇÕES GERAIS ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'lol_database.db')
N_TRIALS = 100

def load_data_for_tuning():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Banco não encontrado em {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM game_features", conn)
    finally:
        conn.close()

    metadata_cols = ['match_id', 'patch_version', 'winner_team']
    live_cols = [c for c in df.columns if c.startswith('live_')]
    cols_to_drop = metadata_cols + live_cols
    
    X = df.drop(columns=cols_to_drop, errors='ignore')
    y = df['winner_team']
    
    return X, y

def objective(trial):
    X, y = load_data_for_tuning()
    
    # --- ESPAÇO DE BUSCA GLOBAL (Resetado e Aberto) ---
    # Objetivo: Remover amarras que causavam underfitting (gamma/alpha altos)
    param = {
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'booster': 'gbtree',
        'n_jobs': -1,
        'verbosity': 0,
        
        # Árvores: Faixa ampla (100 a 2000)
        'n_estimators': trial.suggest_int('n_estimators', 100, 2000), 
        
        # Learning Rate: De conservador (0.005) a agressivo (0.3)
        'learning_rate': trial.suggest_float('learning_rate', 0.005, 0.3, log=True),
        
        # Profundidade: Permitir árvores mais rasas e mais profundas
        'max_depth': trial.suggest_int('max_depth', 2, 10),
        
        # Controle de ruído nas folhas (Valores mais baixos = mais sensível a detalhes)
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
        
        # Amostragem
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        
        # Regularização: CRUCIAL - Permitir 0.0 (Sem regularização)
        # Removido log=True para garantir amostragem uniforme perto de zero
        'gamma': trial.suggest_float('gamma', 0.0, 5.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 5.0),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 5.0),
        
        'scale_pos_weight': trial.suggest_float('scale_pos_weight', 0.8, 1.2)
    }

    # --- CROSS-VALIDATION (5-Fold) ---
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    accuracies = []
    
    for i, (train_idx, valid_idx) in enumerate(skf.split(X, y)):
        X_train, X_valid = X.iloc[train_idx], X.iloc[valid_idx]
        y_train, y_valid = y.iloc[train_idx], y.iloc[valid_idx]
        
        model = xgb.XGBClassifier(**param)
        
        model.fit(X_train, y_train, verbose=False)
        
        preds = model.predict(X_valid)
        acc = accuracy_score(y_valid, preds)
        accuracies.append(acc)
        
        # Reporta média atual para o Pruner
        trial.report(np.mean(accuracies), i)
        
        # Poda automática do Optuna (MedianPruner configurado abaixo)
        if trial.should_prune():
            raise optuna.TrialPruned()

    mean_accuracy = np.mean(accuracies)
    
    try:
        best_so_far = trial.study.best_value
    except ValueError:
        best_so_far = 0
    current_best = max(best_so_far, mean_accuracy)
    
    msg = f"\rTrial {trial.number + 1}/{N_TRIALS} | CV Acc: {mean_accuracy:.2%} | Best: {current_best:.2%}"
    sys.stdout.write(msg + " " * 15)
    sys.stdout.flush()
    
    return mean_accuracy

if __name__ == "__main__":
    print(f"--- Otimização GLOBAL SEARCH (Reset de Viés) ---")
    print(f"Trials: {N_TRIALS} | CV: 5-Fold")
    print("Estratégia: Busca ampla sem travas de regularização e pruner tolerante.\n")
    
    # MedianPruner: Mais tolerante que o Hyperband para datasets instáveis
    # n_startup_trials=5: Garante que os 5 primeiros rodem até o fim sem poda
    study = optuna.create_study(
        direction="maximize", 
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1)
    )
    
    try:
        study.optimize(objective, n_trials=N_TRIALS)
        print("\n\n--- Otimização Concluída ---")
    except KeyboardInterrupt:
        print("\n\nOtimização interrompida!")

    if len(study.trials) > 0:
        print(f"Melhor Trial: {study.best_trial.number}")
        print(f"Melhor Acurácia Média (CV): {study.best_value:.4%}")
        
        print("\n--- Melhores Hiperparâmetros ---")
        for key, value in study.best_params.items():
            print(f"    '{key}': {value},")

        print("\nCopie o dicionário acima para MODEL_PARAMS no arquivo src/models/train_xgboost.py")
    else:
        print("Nenhum trial completado.")