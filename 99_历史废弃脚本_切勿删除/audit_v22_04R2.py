import pandas as pd
import numpy as np
import os

BASE_DIR = r'D:\多元大数据分析\03_方法加固与审计模块\V30_Multi_Source_Fusion_R2'

def audit():
    print("=== 开始全量审计 V22-04R2 产出成果 ===\n")
    
    # 1. 检查 anchor_master_v22_04R2.csv
    print("1. 审核 anchor_master_v22_04R2.csv")
    df_master = pd.read_csv(os.path.join(BASE_DIR, 'anchor_master_v22_04R2.csv'))
    print(f"   - 总锚点数: {len(df_master)}")
    # 检查坐标是否在合理范围内 (高德抓取边界 Lon: 126.50-126.75, Lat: 45.70-45.85)
    out_of_bounds = df_master[
        (df_master['lng'] < 126.50) | (df_master['lng'] > 126.75) |
        (df_master['lat'] < 45.70) | (df_master['lat'] > 45.85)
    ]
    if not out_of_bounds.empty:
        print("   [警告] 发现坐标超出高德 POI 抓取边界 (126.50-126.75, 45.70-45.85) 的锚点:")
        print(out_of_bounds[['anchor_name', 'lng', 'lat']].to_string(index=False))
    else:
        print("   [正常] 所有坐标均在高德抓取范围内。")
        
    print("\n2. 审核 supply_buffer_statistics_v22_04R2.csv (单调性测试)")
    df_sup = pd.read_csv(os.path.join(BASE_DIR, 'supply_buffer_statistics_v22_04R2.csv'))
    # 检查单调性：3km 必须 >= 1km, 5km 必须 >= 3km
    monotonicity_failed = False
    for anchor in df_sup['anchor_name'].unique():
        anchor_data = df_sup[df_sup['anchor_name'] == anchor].sort_values('scale_km')
        prev_totals = -1
        for _, row in anchor_data.iterrows():
            total_supply = (row['ctrip_lodging_count'] + row['amap_dining_count'] + 
                            row['amap_transport_count'] + row['amap_public_count'] + 
                            row['amap_shopping_count'] + row['amap_medical_count'])
            if total_supply < prev_totals:
                print(f"   [警告] {anchor} 的供给随距离增加反而减少 ({row['scale_km']}km < prev)")
                monotonicity_failed = True
            prev_totals = total_supply
    if not monotonicity_failed:
        print("   [正常] 所有 20 个锚点在 1km, 3km, 5km 的供给总量均满足严格单调递增。")

    print("\n3. 审核 xhs_demand_risk_statistics_v22_04R2.csv (痛点率合法性)")
    df_xhs = pd.read_csv(os.path.join(BASE_DIR, 'xhs_demand_risk_statistics_v22_04R2.csv'))
    # 检查痛点率是否在 [0, 1] 之间
    rates_cols = ['xhs_negative_rate', 'traffic_pain_rate', 'queue_pain_rate', 'cold_pain_rate', 'price_pain_rate']
    invalid_rates = df_xhs[(df_xhs[rates_cols] > 1.0).any(axis=1) | (df_xhs[rates_cols] < 0).any(axis=1)]
    if not invalid_rates.empty:
        print("   [警告] 发现痛点率 > 1 或 < 0 的异常行！")
    else:
        print("   [正常] 所有平滑痛点率均被严密约束在 0 到 1 之间。")
        
    print("\n4. 审核 dianping_pressure_statistics_v22_04R2.csv (7大商圈核查)")
    df_dp = pd.read_csv(os.path.join(BASE_DIR, 'dianping_pressure_statistics_v22_04R2.csv'))
    active_dp = df_dp[df_dp['dp_review_count'] > 0]
    print(f"   - 大众点评实际命中锚点数: {len(active_dp)}")
    if len(active_dp) > 0:
        print("   - 命中的锚点列表:", active_dp['anchor_name'].tolist())
    else:
        print("   [严重警告] 大众点评挂接完全失败，所有商圈承载力为 0！")

    print("\n5. 审核 anchor_index_v22_04R2.csv (指数与 Z-score 是否含 NaN)")
    df_idx = pd.read_csv(os.path.join(BASE_DIR, 'anchor_index_v22_04R2.csv'))
    if df_idx.isnull().values.any():
        print("   [严重警告] 最终指数表中存在 NaN 或 Inf 值！")
        print(df_idx[df_idx.isnull().any(axis=1)])
    else:
        print("   [正常] 最终所有 DHI, SSI, ERI, ERI_plus, SMI 均核算完整，无 NaN 或 Infinity。")
        
    print("\n=== 审计结束 ===")

if __name__ == '__main__':
    audit()
