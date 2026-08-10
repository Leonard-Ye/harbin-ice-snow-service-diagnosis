# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from sklearn.neighbors import BallTree
import os

BASE_DIR = r'D:\多元大数据分析'
MAPPED_DIR = os.path.join(BASE_DIR, '03_方法加固与审计模块', 'V25_Full_Mapping')
EXPANDED_DIR = os.path.join(BASE_DIR, '03_方法加固与审计模块', 'V27_Amap_Expansion')
OUT_DIR = os.path.join(BASE_DIR, '03_方法加固与审计模块', 'V28_Multi_Source_Fusion') # We output V22_04R files here
os.makedirs(OUT_DIR, exist_ok=True)

ALIAS_MAP = {
    '大世界': '冰雪大世界',
    '冰雪世界': '冰雪大世界',
    '哈尔滨冰雪大世界': '冰雪大世界',
    '索菲亚': '圣索菲亚教堂',
    '索菲亚教堂': '圣索菲亚教堂',
    '圣索菲亚': '圣索菲亚教堂',
    '索菲亚广场': '圣索菲亚教堂',
    '中央街': '中央大街',
    '中央大街步行街': '中央大街',
    '哈站': '哈尔滨站',
    '哈西': '哈西站',
    '火车站': '哈尔滨站',
    '机场': '太平机场',
    '松花江铁路桥': '中东铁路桥', # Separate from general Songhua River
    '滨州铁路桥': '中东铁路桥'
}

# EXCLUDE NON-GEOGRAPHICAL AND OUT-OF-CITY ANCHORS
EXCLUDE_ANCHORS = [
    '好想去东北', '哈尔滨亲子游', '哈尔滨冰箱贴', '哈尔滨伴手礼', '哈尔滨研学手册', '雪乡', '亚布力', '长白山', '东北'
]

# MAP DIANPING BUSINESS AREAS TO OUR STANDARD ANCHORS
DP_ANCHOR_MAP = {
    '中央大街商圈': '中央大街',
    '索菲亚商圈': '圣索菲亚教堂',
    '冰雪大世界/太阳岛周边': '冰雪大世界',
    '哈站商圈': '哈尔滨站',
    '哈西商圈': '哈西站',
    '防洪纪念塔商圈': '防洪纪念塔',
    '红专街早市': '红专街早市',
    '师大夜市': '师大夜市',
    '中华巴洛克': '中华巴洛克风情街',
    '秋林/果戈里商圈': '秋林公司',
    '秋林商圈': '秋林公司',
    '果戈里商圈': '秋林公司',
    '黑大/服装城商圈': '黑龙江大学',
    '融创茂/王府井商圈': '融创茂',
    '顾乡/群力商圈': '群力',
    '道外区': '道外',
    '南岗区': '南岗',
    '道里区': '道里',
    '松北区': '松北',
    '香坊区': '香坊'
}

def safe_zscore(s):
    if s.std() == 0 or pd.isna(s.std()):
        return np.zeros(len(s))
    return (s - s.mean()) / s.std()

def run_pipeline():
    print("=== 启动 V22-04R 多源锚点融合引擎 (修正版) ===")
    
    # 1. 载入所有底表
    print("正在加载空间映射底表...")
    df_xhs = pd.read_csv(os.path.join(MAPPED_DIR, 'xhs_to_amap_full_mapped.csv'))
    df_dp = pd.read_csv(os.path.join(MAPPED_DIR, 'dianping_to_amap_full_mapped.csv'))
    df_amap = pd.read_csv(os.path.join(EXPANDED_DIR, 'amap_poi_master_unlimited.csv'))
    df_ctrip = pd.read_csv(os.path.join(BASE_DIR, '携程经纬度.csv'))
    
    # 解析携程列名
    ctrip_lon_col = df_ctrip.columns[1]
    ctrip_lat_col = df_ctrip.columns[2]
    
    # ==========================================
    # 步骤一：构建 Anchor Master
    # ==========================================
    # 小红书归一化别名
    df_xhs['standard_anchor'] = df_xhs['normalized_location'].apply(lambda x: ALIAS_MAP.get(str(x), str(x)))
    
    # 过滤无效锚点
    df_xhs = df_xhs[~df_xhs['standard_anchor'].isin(EXCLUDE_ANCHORS)]
    
    # 统计小红书频次，取 Top 35 锚点 (预留剔除无效后的空间)
    anchor_counts = df_xhs['standard_anchor'].value_counts()
    top_candidates = anchor_counts.head(35).index.tolist()
    
    # 确定经纬度
    master_anchors = []
    valid_count = 0
    
    for anchor in top_candidates:
        if valid_count >= 28: # Target exactly 28 solid geographical anchors
            break
            
        pts = df_xhs[df_xhs['standard_anchor'] == anchor]
        lon = pts['lon'].median()
        lat = pts['lat'].median()
        
        if pd.isna(lon) or pd.isna(lat):
            continue
            
        master_anchors.append({
            'anchor_id': f"A{valid_count+1:03d}",
            'anchor_name': anchor,
            'source': 'XHS',
            'anchor_type': 'POI',
            'lng': lon,
            'lat': lat,
            'merge_rule': 'alias' if anchor in ALIAS_MAP.values() else 'manual',
            'confidence': 'A',
            'review_status': 'reviewed' # All V22-04R anchors are reviewed
        })
        valid_count += 1
        
    df_anchor_master = pd.DataFrame(master_anchors)
    df_anchor_master.to_csv(os.path.join(OUT_DIR, 'anchor_master_v22_04R.csv'), index=False, encoding='utf-8-sig')
    print(f"锚点主表生成完毕 (Top {len(df_anchor_master)} 核心锚点)")
    
    # ==========================================
    # 步骤二：构建 BallTree 供给缓冲统计
    # ==========================================
    print("构建空间索引与缓冲统计 (1km / 3km / 5km)...")
    
    amap_coords = np.radians(df_amap[['lat', 'lon']].dropna().values)
    amap_tree = BallTree(amap_coords, metric='haversine')
    
    ctrip_pts = df_ctrip[[ctrip_lat_col, ctrip_lon_col]].dropna()
    ctrip_coords = np.radians(ctrip_pts.values)
    ctrip_tree = BallTree(ctrip_coords, metric='haversine')
    
    EARTH_RADIUS = 6371.0
    buffer_results = []
    
    for idx, row in df_anchor_master.iterrows():
        center = np.radians([[row['lat'], row['lng']]])
        for scale in [1, 3, 5]:
            r = scale / EARTH_RADIUS
            
            idx_amap = amap_tree.query_radius(center, r=r)[0]
            amap_subset = df_amap.iloc[idx_amap]
            
            dining = len(amap_subset[amap_subset['category_group'] == '餐饮服务'])
            transport = len(amap_subset[amap_subset['category_group'] == '交通设施服务'])
            public = len(amap_subset[amap_subset['category_group'] == '公共设施'])
            shopping = len(amap_subset[amap_subset['category_group'] == '购物服务'])
            medical = len(amap_subset[amap_subset['category_group'] == '医疗保健服务'])
            amap_lodging = len(amap_subset[amap_subset['category_group'] == '住宿服务'])
            
            idx_ctrip = ctrip_tree.query_radius(center, r=r)[0]
            ctrip_lodging = len(idx_ctrip)
            
            buffer_results.append({
                'anchor_name': row['anchor_name'],
                'scale_km': scale,
                'ctrip_lodging_count': ctrip_lodging,
                'amap_dining_count': dining,
                'amap_transport_count': transport,
                'amap_public_count': public,
                'amap_shopping_count': shopping,
                'amap_medical_count': medical,
                'amap_lodging_count_optional': amap_lodging
            })
            
    df_supply = pd.DataFrame(buffer_results)
    df_supply.to_csv(os.path.join(OUT_DIR, 'supply_buffer_statistics_v22_04R.csv'), index=False, encoding='utf-8-sig')
    
    # ==========================================
    # 步骤三：小红书需求与真实痛点风险统计
    # ==========================================
    print("挂接小红书需求与痛点风险...")
    xhs_risk = []
    for anchor in df_anchor_master['anchor_name']:
        subset = df_xhs[df_xhs['standard_anchor'] == anchor]
        mentions = len(subset)
        
        neg_count = len(subset[subset['Sentiment'] == -1])
        neg_rate = (neg_count + 0.5) / (mentions + 1)
        
        # Calculate actual pain points
        # Assuming PainPoints is a string like "['拥挤与排队', '气候与防寒']" or standard string "拥挤与排队"
        
        def has_pain(x, keyword):
            if pd.isna(x): return False
            return keyword in str(x)
            
        traffic = sum(subset['PainPoints'].apply(lambda x: has_pain(x, '交通')))
        queue = sum(subset['PainPoints'].apply(lambda x: has_pain(x, '排队') or has_pain(x, '拥挤')))
        cold = sum(subset['PainPoints'].apply(lambda x: has_pain(x, '气候') or has_pain(x, '防寒') or has_pain(x, '冷')))
        price = sum(subset['PainPoints'].apply(lambda x: has_pain(x, '价格') or has_pain(x, '性价比')))
        
        traffic_rate = (traffic + 0.5) / (mentions + 1)
        queue_rate = (queue + 0.5) / (mentions + 1)
        cold_rate = (cold + 0.5) / (mentions + 1)
        price_rate = (price + 0.5) / (mentions + 1)
        
        xhs_risk.append({
            'anchor_name': anchor,
            'xhs_mentions': mentions,
            'xhs_heat_proxy': mentions, # Fix: Rename and remove fake 1.5 multiplier
            'xhs_negative_rate': neg_rate,
            'traffic_pain_rate': traffic_rate,
            'queue_pain_rate': queue_rate,
            'cold_pain_rate': cold_rate,
            'price_pain_rate': price_rate
        })
        
    df_xhs_risk = pd.DataFrame(xhs_risk)
    df_xhs_risk.to_csv(os.path.join(OUT_DIR, 'xhs_demand_risk_statistics_v22_04R.csv'), index=False, encoding='utf-8-sig')
    
    # ==========================================
    # 步骤四：大众点评压力统计
    # ==========================================
    print("挂接大众点评压力层...")
    dp_cols = df_dp.columns.tolist()
    
    # Robustly find columns
    area_col = [c for c in dp_cols if '商圈' in str(c) or '景区' in str(c)]
    price_col = [c for c in dp_cols if '元' in str(c) or '均' in str(c)]
    queue_col = [c for c in dp_cols if '队' in str(c)]
    service_col = [c for c in dp_cols if '服务' in str(c)]
    
    area_col = area_col[0] if area_col else dp_cols[3]
    price_col = price_col[0] if price_col else dp_cols[4]
    queue_col = queue_col[0] if queue_col else dp_cols[10]
    service_col = service_col[0] if service_col else dp_cols[11]
    
    dp_risk = []
    
    # Helper to map anchor string names if Dianping uses region matching
    def find_dp_areas(anchor_name):
        areas = []
        for dp_a, mapped_a in DP_ANCHOR_MAP.items():
            if mapped_a == anchor_name:
                areas.append(dp_a)
        return areas
        
    for anchor in df_anchor_master['anchor_name']:
        target_areas = find_dp_areas(anchor)
        
        subset = pd.DataFrame()
        if target_areas:
            subset = df_dp[df_dp[area_col].isin(target_areas)]
        
        # If no explicit mapping, try substring match on the area column
        if len(subset) == 0:
            subset = df_dp[df_dp[area_col].astype(str).str.contains(anchor, na=False)]
            
        mentions = len(subset)
        if mentions > 0:
            prices = pd.to_numeric(subset[price_col], errors='coerce').fillna(0)
            queues = pd.to_numeric(subset[queue_col], errors='coerce').fillna(0)
            services = pd.to_numeric(subset[service_col], errors='coerce').fillna(5.0)
            
            price_p = (len(prices[prices > 100]) + 0.5) / (mentions + 1)
            queue_p = (len(queues[queues > 30]) + 0.5) / (mentions + 1)
            service_p = (len(services[services < 3.5]) + 0.5) / (mentions + 1)
            
            dp_risk.append({
                'anchor_name': anchor,
                'dp_review_count': mentions,
                'dp_price_pressure': price_p,
                'dp_queue_pressure': queue_p,
                'dp_service_pressure': service_p
            })
        else:
            dp_risk.append({
                'anchor_name': anchor,
                'dp_review_count': 0,
                'dp_price_pressure': 0.0,
                'dp_queue_pressure': 0.0,
                'dp_service_pressure': 0.0
            })
            
    df_dp_risk = pd.DataFrame(dp_risk)
    df_dp_risk.to_csv(os.path.join(OUT_DIR, 'dianping_pressure_statistics_v22_04R.csv'), index=False, encoding='utf-8-sig')
    
    # ==========================================
    # 步骤五 & 六：合并基表与指数计算 (SMI)
    # ==========================================
    print("正在融合六表并计算 SMI (Log1p + Z-score)...")
    merged_all = []
    
    for scale in [1, 3, 5]:
        df_sup_scale = df_supply[df_supply['scale_km'] == scale]
        m1 = pd.merge(df_anchor_master, df_sup_scale, on='anchor_name')
        m2 = pd.merge(m1, df_xhs_risk, on='anchor_name')
        base = pd.merge(m2, df_dp_risk, on='anchor_name')
        merged_all.append(base)
        
    df_base_full = pd.concat(merged_all)
    df_base_full.to_csv(os.path.join(OUT_DIR, 'scale_sensitivity_1_3_5km_v22_04R.csv'), index=False, encoding='utf-8-sig')
    
    base_3km = df_base_full[df_base_full['scale_km'] == 3].copy()
    base_3km.to_csv(os.path.join(OUT_DIR, 'anchor_supply_demand_base_v22_04R.csv'), index=False, encoding='utf-8-sig')
    
    # DHI = mean[Z(log1p(xhs_mentions))]
    z_m = safe_zscore(np.log1p(base_3km['xhs_mentions']))
    base_3km['DHI'] = z_m
    
    # SSI = mean[Z(log1p(ctrip)), Z(log1p(dining)), Z(log1p(trans)), Z(log1p(pub)), Z(log1p(shop)), Z(log1p(med))]
    z_lodging = safe_zscore(np.log1p(base_3km['ctrip_lodging_count']))
    z_dining = safe_zscore(np.log1p(base_3km['amap_dining_count']))
    z_trans = safe_zscore(np.log1p(base_3km['amap_transport_count']))
    z_pub = safe_zscore(np.log1p(base_3km['amap_public_count']))
    z_shop = safe_zscore(np.log1p(base_3km['amap_shopping_count']))
    z_med = safe_zscore(np.log1p(base_3km['amap_medical_count']))
    
    base_3km['SSI'] = (z_lodging + z_dining + z_trans + z_pub + z_shop + z_med) / 6.0
    
    # ERI = Z(neg_rate) ONLY for now (if pain rates are 0.5/(N+1), they will have Z=0 and not affect it much)
    # But since we fixed the logic, let's include them.
    z_neg = safe_zscore(base_3km['xhs_negative_rate'])
    z_t = safe_zscore(base_3km['traffic_pain_rate'])
    z_q = safe_zscore(base_3km['queue_pain_rate'])
    z_c = safe_zscore(base_3km['cold_pain_rate'])
    z_p = safe_zscore(base_3km['price_pain_rate'])
    
    base_3km['ERI'] = (z_neg + z_t + z_q + z_c + z_p) / 5.0
    
    # ERI_plus = mean[ERI, Z(dp_queue), Z(dp_price), Z(dp_service)]
    z_dp_q = safe_zscore(base_3km['dp_queue_pressure'])
    z_dp_p = safe_zscore(base_3km['dp_price_pressure'])
    z_dp_s = safe_zscore(base_3km['dp_service_pressure'])
    
    base_3km['ERI_plus'] = (base_3km['ERI'] + z_dp_q + z_dp_p + z_dp_s) / 4.0
    
    # SMI = DHI + ERI - SSI
    base_3km['SMI'] = safe_zscore(base_3km['DHI']) + safe_zscore(base_3km['ERI']) - safe_zscore(base_3km['SSI'])
    
    base_3km.sort_values(by='SMI', ascending=False, inplace=True)
    base_3km['mismatch_rank'] = range(1, len(base_3km) + 1)
    
    out_cols = ['anchor_name', 'lng', 'lat', 'DHI', 'SSI', 'ERI', 'ERI_plus', 'SMI', 'mismatch_rank']
    df_idx = base_3km[out_cols].copy()
    
    out_file = os.path.join(OUT_DIR, 'anchor_index_v22_04R.csv')
    df_idx.to_csv(out_file, index=False, encoding='utf-8-sig')
    
    print(f"全部 6 大指标与核心表运算完毕！产出位于 {OUT_DIR}")
    print("V22-04R SMI 排名前五的高错配区域：")
    print(df_idx[['anchor_name', 'SMI']].head(5).to_string(index=False))

if __name__ == '__main__':
    run_pipeline()
