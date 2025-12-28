import sqlite3
import warnings
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import os
import numpy as np

# Tenta importar SHAP
try:
    import shap
except ImportError:
    shap = None

# --- CONFIGURAÇÕES DE SILÊNCIO ---
warnings.filterwarnings('ignore')

# --- CONFIGURAÇÕES ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'lol_database.db')

# Parâmetros OTIMIZADOS (Best Trial 33 - Atualizado)
MODEL_PARAMS = {
    'objective': 'binary:logistic',
    'booster': 'gbtree',
    'eval_metric': ['logloss', 'error'],
    'random_state': 42,
    'n_jobs': -1,
    
    # Hiperparâmetros do Optuna (Trial 33)
    'n_estimators': 500,        # Quantidade razoável
    'learning_rate': 0.05,      # Mais rápido para aprender
    'max_depth': 6,             # Permite entender interações complexas (mid + jg + gold)
    'min_child_weight': 1,      # Permite isolar padrões mais específicos
    'gamma': 0.1,               # Baixa restrição para corte
    'subsample': 0.8,           # Padrão
    'colsample_bytree': 0.8,    # Padrão
    'reg_alpha': 0.1,           # Pouca regularização L1
    'reg_lambda': 1.0,          # Regularização L2 padrão
    'scale_pos_weight': 1,
    
    'early_stopping_rounds': 100
}

def load_dataset():
    if not os.path.exists(DB_PATH):
        print(f"❌ Erro: Banco de dados não encontrado em {DB_PATH}")
        return None

    conn = sqlite3.connect(DB_PATH)
    try:
        query = "SELECT * FROM game_features"
        df = pd.read_sql(query, conn)
        print(f"Dataset carregado: {len(df)} partidas.")
        return df
    except Exception as e:
        print(f"❌ Erro ao ler banco: {e}")
        return None
    finally:
        conn.close()

def train_model():
    print("--- 1. Preparação dos Dados ---")
    df = load_dataset()
    if df is None or df.empty: return

    # --- FILTRO ANTI-LEAKAGE ---
    metadata_cols = ['match_id', 'patch_version', 'winner_team']
    live_cols = [c for c in df.columns if c.startswith('live_')]
    cols_to_drop = metadata_cols + live_cols
    
    X = df.drop(columns=cols_to_drop, errors='ignore')
    y = df['winner_team']

    print(f"Features de Draft Selecionadas: {X.shape[1]}")

    # Divisão Treino/Teste
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=True)
    
    print("\n--- 2. Treinando XGBoost (Configuração Final) ---")
    model = xgb.XGBClassifier(**MODEL_PARAMS)
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_test, y_test)],
        verbose=100
    )
    
    print("Treinamento concluído.")

    print("\n--- 3. Avaliação ---")
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_prob)
    
    print(f"🎯 Acurácia:  {acc:.2%}")
    print(f"📈 AUC-ROC:   {auc:.4f}")
    
    print("\nMatriz de Confusão:")
    print(confusion_matrix(y_test, y_pred))

    # --- 4. Feature Importance (Weight & Gain) ---
    print("\n--- 4. Importância das Features (Weight & Gain) ---")
    
    booster = model.get_booster()
    scores_weight = booster.get_score(importance_type='weight')
    scores_gain = booster.get_score(importance_type='gain')
    
    features_list = []
    for ft in X.columns:
        features_list.append({
            'Feature': ft,
            'Gain': scores_gain.get(ft, 0),
            'Weight': scores_weight.get(ft, 0)
        })
    
    df_imp = pd.DataFrame(features_list).sort_values(by='Gain', ascending=False)
    
    pd.set_option('display.max_rows', None)
    print(df_imp.head(40).to_string(index=False)) # Top 40
    pd.reset_option('display.max_rows')

    # --- 5. SHAP ---
    if shap:
        print("\n--- 5. Gerando Análise SHAP Detalhada ---")
        try:
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_test)
            
            # Gráfico 1: Summary Plot (Barra - Importância Geral)
            plt.figure(figsize=(10, 8))
            plt.title("SHAP Feature Importance (Barra)")
            shap.summary_plot(shap_values, X_test, plot_type="bar", show=False, max_display=20)
            plt.tight_layout()
            plt.show()

            # Gráfico 2: Summary Plot (Beeswarm - Impacto Positivo/Negativo)
            plt.figure(figsize=(12, 10))
            plt.title("SHAP Summary (Impacto no Resultado)")
            shap.summary_plot(shap_values, X_test, show=False, max_display=30) # Ampliado para 30 features
            plt.tight_layout()
            plt.show()
            
            # Gráfico 3: Dependence Plots para as Top Features
            # Mostra a relação exata (linear, curva, etc) da feature com o resultado
            print("Gerando gráficos de dependência para as Top 6 features...")
            top_features = df_imp['Feature'].head(6).tolist()
            
            for ft in top_features:
                if ft in X_test.columns:
                    plt.figure(figsize=(8, 5))
                    shap.dependence_plot(ft, shap_values, X_test, show=False)
                    plt.title(f"Dependência SHAP: {ft}")
                    plt.tight_layout()
                    plt.show()

        except Exception as e:
            print(f"Erro SHAP: {e}")

if __name__ == "__main__":
    train_model()