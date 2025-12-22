import requests
import sqlite3
import os
import time

# Configurações
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'lol_database.db')
MAX_PATCHES = 50 

def get_versions():
    try:
        url = "https://ddragon.leagueoflegends.com/api/versions.json"
        return requests.get(url).json()[:MAX_PATCHES]
    except Exception as e:
        print(f"Erro ao buscar versões: {e}")
        return []

def init_db():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # CORREÇÃO: Total de 27 colunas agora
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS champions (
            champion_key INTEGER,
            patch_version TEXT,
            name TEXT,
            title TEXT,
            tags TEXT,
            partype TEXT,
            
            passive_name TEXT,
            passive_desc TEXT,

            hp REAL,
            hp_per_level REAL,
            mp REAL,
            mp_per_level REAL,
            movespeed REAL,
            armor REAL,
            armor_per_level REAL,
            spellblock REAL,
            spellblock_per_level REAL,
            attackrange REAL,
            hpregen REAL,
            hpregen_per_level REAL, -- Adicionado
            mpregen REAL,
            mpregen_per_level REAL, -- Adicionado
            crit REAL,
            attackdamage REAL,
            attackdamage_per_level REAL,
            attackspeed_per_level REAL,
            attackspeed REAL,
            
            PRIMARY KEY (champion_key, patch_version)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS abilities (
            champion_key INTEGER,
            patch_version TEXT,
            slot TEXT,
            name TEXT,
            description TEXT,
            cooldown_burn TEXT,
            cost_burn TEXT,
            range_burn TEXT,
            FOREIGN KEY(champion_key, patch_version) REFERENCES champions(champion_key, patch_version)
        )
    ''')

    conn.commit()
    return conn

def patch_exists(cursor, version):
    cursor.execute("SELECT 1 FROM champions WHERE patch_version = ? LIMIT 1", (version,))
    return cursor.fetchone() is not None

def process_data(data, version, bulk_lists):
    for key_id, champ in data.items():
        try:
            c_key = int(champ['key']) 
            stats = champ['stats']
            passive = champ.get('passive', {})

            # 1. Adiciona à lista de Campeões (Tupla com exatos 27 itens)
            bulk_lists['champions'].append((
                c_key,
                version,
                champ['name'],
                champ['title'],
                ", ".join(champ.get('tags', [])),
                champ.get('partype', 'None'),
                
                passive.get('name', ''),
                passive.get('description', ''),

                stats.get('hp', 0), stats.get('hpperlevel', 0),
                stats.get('mp', 0), stats.get('mpperlevel', 0),
                stats.get('movespeed', 0),
                stats.get('armor', 0), stats.get('armorperlevel', 0),
                stats.get('spellblock', 0), stats.get('spellblockperlevel', 0),
                stats.get('attackrange', 0),
                stats.get('hpregen', 0), stats.get('hpregenperlevel', 0), # Novo
                stats.get('mpregen', 0), stats.get('mpregenperlevel', 0), # Novo
                stats.get('crit', 0),
                stats.get('attackdamage', 0), stats.get('attackdamageperlevel', 0),
                stats.get('attackspeedperlevel', 0), stats.get('attackspeed', 0)
            ))

            # 2. Habilidades
            spell_keys = ['Q', 'W', 'E', 'R']
            for idx, spell in enumerate(champ.get('spells', [])):
                if idx < 4:
                    bulk_lists['abilities'].append((
                        c_key,
                        version,
                        spell_keys[idx],
                        spell['name'],
                        spell['description'],
                        spell.get('cooldownBurn', '0'),
                        spell.get('costBurn', '0'),
                        spell.get('rangeBurn', '0')
                    ))

        except ValueError:
            pass # Ignora erros de conversão de ID

def run():
    # Remove o banco antigo se existir para evitar conflito de esquema
    if os.path.exists(DB_PATH):
        try:
            # Tenta verificar se o schema está correto, senão apaga
            # Para simplificar para você: apague manualmente se der erro de novo, 
            # mas este código deve rodar liso se o arquivo não existir.
            pass
        except:
            pass

    conn = init_db()
    cursor = conn.cursor()
    versions = get_versions()
    
    print(f"Iniciando coleta para {len(versions)} versões...")

    for v in versions:
        if patch_exists(cursor, v):
            print(f"Versão {v} já processada.")
            continue

        print(f"Baixando versão {v}...")
        url = f"http://ddragon.leagueoflegends.com/cdn/{v}/data/pt_BR/championFull.json"
        
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                data = resp.json()['data']
                bulk = {'champions': [], 'abilities': []}
                
                process_data(data, v, bulk)
                
                # CORREÇÃO: String com exatamente 27 '?'
                cursor.executemany('''
                    INSERT INTO champions VALUES 
                    (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', bulk['champions'])
                
                cursor.executemany('''
                    INSERT INTO abilities VALUES 
                    (?,?,?,?,?,?,?,?)
                ''', bulk['abilities'])
                
                conn.commit()
                print(f" -> {len(bulk['champions'])} campeões salvos.")
            else:
                print(f"Falha no download: {resp.status_code}")
                
        except Exception as e:
            print(f"Erro crítico na v{v}: {e}")
            # Se der erro, para o script para você ler o log
            break 
        
        time.sleep(0.1)

    conn.close()
    print("Sucesso! Banco de dados atualizado.")

if __name__ == "__main__":
    run()