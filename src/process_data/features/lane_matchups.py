import pandas as pd

# Definição das Rotas
ROLES = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']

def calculate_lane_matchups(blue_roles, red_roles, patch, df_champs, df_features):
    """
    Calcula diffs ESPECÍFICOS para cada rota.
    Top: Sustain vs Durability
    Jungle: Gank Potential (CC+Mobility)
    Mid: Roam vs Range
    ADC: DPS vs Range
    Sup: Utility vs Engage
    """
    
    # 1. Filtros de Dados (Stats e Features)
    df_stats_patch = df_champs[df_champs['patch_version'] == patch]
    df_feats_patch = df_features[df_features['patch_version'] == patch]
    
    # Fallback se não achar patch
    if df_stats_patch.empty:
        if not df_champs.empty:
            latest = df_champs['patch_version'].max()
            df_stats_patch = df_champs[df_champs['patch_version'] == latest]
            df_feats_patch = df_features[df_features['patch_version'] == latest]
        else:
            return _empty_result()

    # 2. Helper para montar o "Perfil Completo" do campeão (Stats + Features)
    def get_champ_profile(champ_id):
        if not champ_id: return None
        
        # Pega Stats Numéricos
        s_row = df_stats_patch[df_stats_patch['champion_key'] == champ_id]
        if s_row.empty: return None
        stats = s_row.iloc[0]
        
        # Pega Features Mecânicas (Tags)
        f_row = df_feats_patch[df_feats_patch['champion_key'] == champ_id]
        if f_row.empty: 
            # Se não tiver feature, cria zerado para não quebrar
            feats = pd.Series({'has_hard_cc':0, 'has_dash':0, 'has_heal':0, 'has_shield':0})
        else:
            feats = f_row.iloc[0]
            
        return stats, feats

    result = {}

    # 3. Lógica Especializada por Rota
    for role in ROLES:
        b_id = blue_roles.get(role)
        r_id = red_roles.get(role)
        
        blue_data = get_champ_profile(b_id)
        red_data = get_champ_profile(r_id)
        
        # Se faltar dados, zera tudo dessa lane
        if not blue_data or not red_data:
            _fill_zero_lane(result, role)
            continue
            
        b_stats, b_feats = blue_data
        r_stats, r_feats = red_data
        
        # --- CÁLCULOS ESPECÍFICOS ---
        
        # A. TOP LANE: A Ilha da Trocação
        # Foco: Sustentação (Regen + Heal) e Durabilidade (HP + Armor)
        if role == 'TOP':
            # Score de Sustain: HP Regen Base + (100 pontos se tiver skill de cura/escudo)
            b_sus = b_stats['hpregen'] + (50 if b_feats['has_heal'] or b_feats['has_shield'] else 0)
            r_sus = r_stats['hpregen'] + (50 if r_feats['has_heal'] or r_feats['has_shield'] else 0)
            
            # Score de Tankiness: HP Base + Armor Base
            b_tank = b_stats['hp'] + (b_stats['armor'] * 10)
            r_tank = r_stats['hp'] + (r_stats['armor'] * 10)
            
            result['diff_top_sustain'] = float(b_sus - r_sus)
            result['diff_top_tankiness'] = float(b_tank - r_tank)

        # B. JUNGLE: O Impacto no Mapa
        # Foco: Potencial de Gank (CC + Mobilidade) e Clear Speed (Attack Speed base ajuda)
        elif role == 'JUNGLE':
            # Score de Gank: Hard CC vale muito, Dash vale muito
            b_gank = b_feats['has_hard_cc'] + b_feats['has_dash'] + b_feats['has_blink']
            r_gank = r_feats['has_hard_cc'] + r_feats['has_dash'] + r_feats['has_blink']
            
            # Score de Clear/Farm (Proxy): Attack Speed Base
            b_clear = b_stats['attackspeed']
            r_clear = r_stats['attackspeed']
            
            result['diff_jungle_gank'] = int(b_gank - r_gank)
            result['diff_jungle_clear'] = float(b_clear - r_clear)

        # C. MID LANE: Controle vs Roaming
        # Foco: Roaming (MoveSpeed + Dash) e Controle (Range)
        elif role == 'MIDDLE':
            # Roaming Potential
            b_roam = b_stats['movespeed'] + (20 if b_feats['has_dash'] or b_feats['has_blink'] else 0)
            r_roam = r_stats['movespeed'] + (20 if r_feats['has_dash'] or r_feats['has_blink'] else 0)
            
            # Range Control (Mago vs Assassino)
            result['diff_mid_roam'] = float(b_roam - r_roam)
            result['diff_mid_range'] = float(b_stats['attackrange'] - r_stats['attackrange'])

        # D. ADC (BOTTOM): Quem carrega?
        # Foco: DPS Puro (AD * AS) e Segurança (Range)
        elif role == 'BOTTOM':
            # DPS Estimado Base
            b_dps = b_stats['attackdamage'] * b_stats['attackspeed']
            r_dps = r_stats['attackdamage'] * r_stats['attackspeed']
            
            result['diff_adc_dps'] = float(b_dps - r_dps)
            result['diff_adc_range'] = float(b_stats['attackrange'] - r_stats['attackrange'])

        # E. SUPPORT (UTILITY): A Proteção ou o Engage
        # Foco: Utilidade (Heal/Shield) e Lockdown (CC)
        elif role == 'UTILITY':
            # Score de Peel/Protection
            b_util = b_feats['has_heal'] + b_feats['has_shield'] + b_feats['has_immortality']
            r_util = r_feats['has_heal'] + r_feats['has_shield'] + r_feats['has_immortality']
            
            # Score de Engage/Lockdown
            b_cc = b_feats['has_hard_cc'] + b_feats['has_hook']
            r_cc = r_feats['has_hard_cc'] + r_feats['has_hook']
            
            result['diff_sup_utility'] = int(b_util - r_util)
            result['diff_sup_cc'] = int(b_cc - r_cc)

    return result

def _fill_zero_lane(res, role):
    if role == 'TOP':
        res['diff_top_sustain'] = 0.0; res['diff_top_tankiness'] = 0.0
    elif role == 'JUNGLE':
        res['diff_jungle_gank'] = 0; res['diff_jungle_clear'] = 0.0
    elif role == 'MIDDLE':
        res['diff_mid_roam'] = 0.0; res['diff_mid_range'] = 0.0
    elif role == 'BOTTOM':
        res['diff_adc_dps'] = 0.0; res['diff_adc_range'] = 0.0
    elif role == 'UTILITY':
        res['diff_sup_utility'] = 0; res['diff_sup_cc'] = 0

def _empty_result():
    res = {}
    for r in ROLES: _fill_zero_lane(res, r)
    return res