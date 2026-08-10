# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from sklearn.neighbors import BallTree
import os

# 仓库根目录 = 本脚本所在目录的上两级（02_多源融合数据及核心脚本/ 的上级）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = PROJECT_ROOT
MAPPED_DIR = os.path.join(BASE_DIR, '02_多源融合数据及核心脚本', 'V25_Full_Mapping')
EXPANDED_DIR = os.path.join(BASE_DIR, '02_多源融合数据及核心脚本', 'V27_Amap_Expansion')
OUT_DIR = os.path.join(BASE_DIR, '02_多源融合数据及核心脚本', 'V30_Multi_Source_Fusion_R2') # output V22_04R2 files
os.makedirs(OUT_DIR, exist_ok=True)

# 1. 人工白名单与别名映射
WHITELIST_ANCHORS = [
    '中央大街', '圣索菲亚教堂', '冰雪大世界', '松花江', '太阳岛', '中华巴洛克风情街', 
    '红专街早市', '防洪纪念塔', '哈药六厂', '极地公园', '东北虎林园', '哈尔滨站', 
    '伏尔加庄园', '中东铁路桥', '果戈里大街', '哈西站', '师大夜市', '群力', '龙塔',
    '哈尔滨工业大学', '黑龙江大学', '融创茂', '秋林公司', '音乐公园'
]

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
    '火车站': '哈尔滨站',
    '哈尔滨西站': '哈西站',
    '哈西': '哈西站',
    '松花江铁路桥': '中东铁路桥',
    '滨州铁路桥': '中东铁路桥',
    '中华巴洛克/老道外': '中华巴洛克风情街',
    '中华巴洛克': '中华巴洛克风情街',
    '老道外': '中华巴洛克风情街',
    '哈工大': '哈尔滨工业大学',
    '雪博会': '太阳岛'  # 遵照用户要求，雪博会合并至太阳岛
}

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
    '果戈里商圈': '果戈里大街',
    '黑大/服装城商圈': '黑龙江大学',
    '融创茂/王府井商圈': '融创茂',
    '顾乡/群力商圈': '群力',
    '道外区': '中华巴洛克风情街'
}

def determine_exclusion_reason(term):
    term_str = str(term)
    if '冰箱贴' in term_str or '伴手礼' in term_str or '文创' in term_str or '好物' in term_str or '墨镜' in term_str:
        return '商品词'
    if '东北' in term_str or '浪漫' in term_str or '穿搭' in term_str or '亲子游' in term_str or '研学' in term_str or '攻略' in term_str or '推荐' in term_str or '爱吃' in term_str or '好吃' in term_str or '一点就透' in term_str or '波波夫' in term_str or '住宿' in term_str:
        return '主题词/情绪词'
    if '雪乡' in term_str or '亚布力' in term_str or '长白山' in term_str or '延吉' in term_str:
        return '城市外延地点'
    if '太平机场' in term_str or '机场' in term_str:
        return '偏远交通枢纽(剔除主模型)'
    return '未命中白名单/非核心地理锚点'

def safe_zscore(s):
    if s.std() == 0 or pd.isna(s.std()):
        return np.zeros(len(s))
    return (s - s.mean()) / s.std()

def run_pipeline():
    print("=== 启动 V22-04R2 多源锚点融合引擎 (人工白名单版) ===")
    
    df_xhs = pd.read_csv(os.path.join(MAPPED_DIR, 'xhs_to_amap_full_mapped.csv'))
    df_dp = pd.read_csv(os.path.join(MAPPED_DIR, 'dianping_to_amap_full_mapped.csv'))
    df_amap = pd.read_csv(os.path.join(EXPANDED_DIR, 'amap_poi_master_unlimited.csv'))
    df_ctrip = pd.read_csv(os.path.join(BASE_DIR, '00_原始基座数据', '携程经纬度.csv'))
    
    ctrip_lon_col = df_ctrip.columns[1]
    ctrip_lat_col = df_ctrip.columns[2]
    
    # 清洗双引号
    df_xhs['clean_loc'] = df_xhs['normalized_location'].astype(str).str.replace('"', '').str.replace("'", "")
    df_xhs['clean_loc'] = df_xhs['clean_loc'].apply(lambda x: x.strip('[]'))
    
    # 别名映射
    df_xhs['standard_anchor'] = df_xhs['clean_loc'].apply(lambda x: ALIAS_MAP.get(x, x))
    
    # 划分保留与剔除
    valid_mask = df_xhs['standard_anchor'].isin(WHITELIST_ANCHORS)
    df_valid = df_xhs[valid_mask]
    df_excluded = df_xhs[~valid_mask]
    
    # 导出剔除词汇报告
    ex_counts = df_excluded['clean_loc'].value_counts().reset_index()
    ex_counts.columns = ['term', 'mentions']
    ex_counts['reason'] = ex_counts['term'].apply(determine_exclusion_reason)
    ex_counts.to_csv(os.path.join(OUT_DIR, 'excluded_terms_v22_04R2.csv'), index=False, encoding='utf-8-sig')
    print(f"已剔除 {len(ex_counts)} 种非地理词汇，详见 excluded_terms_v22_04R2.csv")
    
    # 构建 Anchor Master
    anchor_counts = df_valid['standard_anchor'].value_counts()
    
    # 确定经纬度
    master_anchors = []
    
    # 手工修正异常坐标库
    MANUAL_COORDS = {
        '哈药六厂': (126.685324, 45.771216), # 真实地址：道外区南直路
        '中东铁路桥': (126.626354, 45.787358), # 避免与松花江坐标完全重叠
        '松花江': (126.560000, 45.780000) # 手动分离
    }
    
    for i, anchor in enumerate(anchor_counts.index):
        if anchor in MANUAL_COORDS:
            lon, lat = MANUAL_COORDS[anchor]
        else:
            pts = df_valid[df_valid['standard_anchor'] == anchor]
            lon = pts['lon'].median()
            lat = pts['lat'].median()
        
        if pd.isna(lon) or pd.isna(lat):
            continue
            
        master_anchors.append({
            'anchor_id': f"A{i+1:03d}",
            'anchor_name': anchor,
            'source': 'XHS',
            'anchor_type': 'POI',
            'lng': lon,
            'lat': lat,
            'merge_rule': 'manual_whitelist',
            'confidence': 'A',
            'review_status': 'reviewed'
        })
        
    df_anchor_master = pd.DataFrame(master_anchors)
    df_anchor_master.to_csv(os.path.join(OUT_DIR, 'anchor_master_v22_04R2.csv'), index=False, encoding='utf-8-sig')
    print(f"最终保留 {len(df_anchor_master)} 个纯正地理锚点！")
    
    # 构建供给缓冲
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
    df_supply.to_csv(os.path.join(OUT_DIR, 'supply_buffer_statistics_v22_04R2.csv'), index=False, encoding='utf-8-sig')
    
    # 挂接需求与痛点
    xhs_risk = []
    for anchor in df_anchor_master['anchor_name']:
        subset = df_valid[df_valid['standard_anchor'] == anchor]
        mentions = len(subset)
        
        neg_count = len(subset[subset['Sentiment'] == -1])
        neg_rate = (neg_count + 0.5) / (mentions + 1)
        
        def has_pain(x, keywords):
            if pd.isna(x): return False
            for k in keywords:
                if k in str(x): return True
            return False
            
        traffic = sum(subset['PainPoints'].apply(lambda x: has_pain(x, ['交通', '车', '路', '堵'])))
        queue = sum(subset['PainPoints'].apply(lambda x: has_pain(x, ['排队', '人多', '挤', '等'])))
        cold = sum(subset['PainPoints'].apply(lambda x: has_pain(x, ['冷', '寒', '冻', '气温'])))
        price = sum(subset['PainPoints'].apply(lambda x: has_pain(x, ['价格', '贵', '坑', '宰客'])))
        
        traffic_rate = (traffic + 0.5) / (mentions + 1)
        queue_rate = (queue + 0.5) / (mentions + 1)
        cold_rate = (cold + 0.5) / (mentions + 1)
        price_rate = (price + 0.5) / (mentions + 1)
        
        xhs_risk.append({
            'anchor_name': anchor,
            'xhs_mentions': mentions,
            'xhs_heat_proxy': mentions,
            'xhs_negative_rate': neg_rate,
            'traffic_pain_rate': traffic_rate,
            'queue_pain_rate': queue_rate,
            'cold_pain_rate': cold_rate,
            'price_pain_rate': price_rate
        })
        
    df_xhs_risk = pd.DataFrame(xhs_risk)
    df_xhs_risk.to_csv(os.path.join(OUT_DIR, 'xhs_demand_risk_statistics_v22_04R2.csv'), index=False, encoding='utf-8-sig')
    
    # 大众点评
    dp_cols = df_dp.columns.tolist()
    area_col = [c for c in dp_cols if '商圈' in str(c) or '景区' in str(c)]
    price_col = [c for c in dp_cols if '元' in str(c) or '均' in str(c)]
    queue_col = [c for c in dp_cols if '队' in str(c)]
    service_col = [c for c in dp_cols if '服务' in str(c)]
    
    area_col = area_col[0] if area_col else dp_cols[3]
    price_col = price_col[0] if price_col else dp_cols[4]
    queue_col = queue_col[0] if queue_col else dp_cols[10]
    service_col = service_col[0] if service_col else dp_cols[11]
    
    dp_risk = []
    def find_dp_areas(anchor_name):
        return [dp_a for dp_a, mapped_a in DP_ANCHOR_MAP.items() if mapped_a == anchor_name]
        
    for anchor in df_anchor_master['anchor_name']:
        target_areas = find_dp_areas(anchor)
        subset = df_dp[df_dp[area_col].isin(target_areas)] if target_areas else pd.DataFrame()
        
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
                'anchor_name': anchor, 'dp_review_count': 0,
                'dp_price_pressure': 0.0, 'dp_queue_pressure': 0.0, 'dp_service_pressure': 0.0
            })
            
    df_dp_risk = pd.DataFrame(dp_risk)
    df_dp_risk.to_csv(os.path.join(OUT_DIR, 'dianping_pressure_statistics_v22_04R2.csv'), index=False, encoding='utf-8-sig')
    
    # 合并与指数重算
    merged_all = []
    for scale in [1, 3, 5]:
        df_sup_scale = df_supply[df_supply['scale_km'] == scale]
        m1 = pd.merge(df_anchor_master, df_sup_scale, on='anchor_name')
        m2 = pd.merge(m1, df_xhs_risk, on='anchor_name')
        base = pd.merge(m2, df_dp_risk, on='anchor_name')
        merged_all.append(base)
        
    df_base_full = pd.concat(merged_all)
    df_base_full.to_csv(os.path.join(OUT_DIR, 'scale_sensitivity_1_3_5km_v22_04R2.csv'), index=False, encoding='utf-8-sig')
    
    base_3km = df_base_full[df_base_full['scale_km'] == 3].copy()
    base_3km.to_csv(os.path.join(OUT_DIR, 'anchor_supply_demand_base_v22_04R2.csv'), index=False, encoding='utf-8-sig')
    
    # 重新计算 Z-score 确保没有污染
    base_3km['DHI'] = safe_zscore(np.log1p(base_3km['xhs_mentions']))
    
    z_lodging = safe_zscore(np.log1p(base_3km['ctrip_lodging_count']))
    z_dining = safe_zscore(np.log1p(base_3km['amap_dining_count']))
    z_trans = safe_zscore(np.log1p(base_3km['amap_transport_count']))
    z_pub = safe_zscore(np.log1p(base_3km['amap_public_count']))
    z_shop = safe_zscore(np.log1p(base_3km['amap_shopping_count']))
    z_med = safe_zscore(np.log1p(base_3km['amap_medical_count']))
    base_3km['SSI'] = (z_lodging + z_dining + z_trans + z_pub + z_shop + z_med) / 6.0
    
    z_neg = safe_zscore(base_3km['xhs_negative_rate'])
    z_t = safe_zscore(base_3km['traffic_pain_rate'])
    z_q = safe_zscore(base_3km['queue_pain_rate'])
    z_c = safe_zscore(base_3km['cold_pain_rate'])
    z_p = safe_zscore(base_3km['price_pain_rate'])
    base_3km['ERI'] = (z_neg + z_t + z_q + z_c + z_p) / 5.0
    
    z_dp_q = safe_zscore(base_3km['dp_queue_pressure'])
    z_dp_p = safe_zscore(base_3km['dp_price_pressure'])
    z_dp_s = safe_zscore(base_3km['dp_service_pressure'])
    base_3km['ERI_plus'] = (base_3km['ERI'] + z_dp_q + z_dp_p + z_dp_s) / 4.0
    
    base_3km['SMI'] = safe_zscore(base_3km['DHI']) + safe_zscore(base_3km['ERI']) - safe_zscore(base_3km['SSI'])
    base_3km.sort_values(by='SMI', ascending=False, inplace=True)
    base_3km['mismatch_rank'] = range(1, len(base_3km) + 1)
    
    out_cols = ['anchor_name', 'lng', 'lat', 'DHI', 'SSI', 'ERI', 'ERI_plus', 'SMI', 'mismatch_rank']
    df_idx = base_3km[out_cols].copy()
    df_idx.to_csv(os.path.join(OUT_DIR, 'anchor_index_v22_04R2.csv'), index=False, encoding='utf-8-sig')
    
    print("V22-04R2 SMI 前五高错配区：")
    print(df_idx[['anchor_name', 'SMI']].head(5).to_string(index=False))

if __name__ == '__main__':
    run_pipeline()
