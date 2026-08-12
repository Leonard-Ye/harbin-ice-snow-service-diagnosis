# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import seaborn as sns
import os

# 配置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun']
plt.rcParams['axes.unicode_minus'] = False

# 仓库根目录 = 本脚本所在目录的上两级
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, '02_多源融合数据及核心脚本', 'V30_Multi_Source_Fusion_R2')
OUT_DIR = os.path.join(PROJECT_ROOT, '03_图表输出_V22_05R')
os.makedirs(OUT_DIR, exist_ok=True)

def run_charts():
    print("=== 开始生成 V22-05 核心数据诊断图表 ===")
    
    # 读数据
    df_index = pd.read_csv(os.path.join(DATA_DIR, 'anchor_index_v22_04R2.csv'))
    df_master = pd.read_csv(os.path.join(DATA_DIR, 'anchor_master_v22_04R2.csv'))
    df_xhs = pd.read_csv(os.path.join(DATA_DIR, 'xhs_demand_risk_statistics_v22_04R2.csv'))
    df_dp = pd.read_csv(os.path.join(DATA_DIR, 'dianping_pressure_statistics_v22_04R2.csv'))
    df_scale = pd.read_csv(os.path.join(DATA_DIR, 'scale_sensitivity_1_3_5km_v22_04R2.csv'))
    
    # 获取坐标
    df_index = pd.merge(df_index, df_master[['anchor_name']], on='anchor_name', how='left')
    
    # 1. 空间分布图
    plt.figure(figsize=(12, 10))
    scatter = plt.scatter(df_index['lng'], df_index['lat'], 
                          c=df_index['SMI'], cmap='coolwarm', 
                          s=(df_index['DHI'] - df_index['DHI'].min() + 1) * 200, 
                          alpha=0.8, edgecolors='black')
    plt.colorbar(scatter, label='供需错配指数 (SMI)')
    
    # 增加 adjust_text 智能避让
    from adjustText import adjust_text
    texts = []
    for idx, row in df_index.iterrows():
        texts.append(plt.text(row['lng'], row['lat'], row['anchor_name'], fontsize=9, 
                              bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1)))
    adjust_text(texts, expand_points=(1.2, 1.2), expand_text=(1.05, 1.05), arrowprops=dict(arrowstyle='-', color='gray', lw=0.5))
                     
    plt.title('哈尔滨核心文旅锚点空间分布图 (气泡大小=需求热度 DHI)', fontsize=16)
    plt.xlabel('经度')
    plt.ylabel('纬度')
    plt.grid(True, linestyle='--', alpha=0.5)
    
    plt.margins(0.15)
    plt.savefig(os.path.join(OUT_DIR, 'spatial_distribution_map.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("1. spatial_distribution_map.png 完成")
    
    # 1.5 主城区放大图
    # 中央大街区域的大致经纬度范围：经度 126.58 - 126.65, 纬度 45.73 - 45.79
    df_zoom = df_index[(df_index['lng'] > 126.55) & (df_index['lng'] < 126.68) & 
                       (df_index['lat'] > 45.70) & (df_index['lat'] < 45.80)]
                       
    plt.figure(figsize=(10, 8))
    scatter = plt.scatter(df_zoom['lng'], df_zoom['lat'], 
                          c=df_zoom['SMI'], cmap='coolwarm', 
                          s=(df_zoom['DHI'] - df_zoom['DHI'].min() + 1) * 300, 
                          alpha=0.8, edgecolors='black')
    plt.colorbar(scatter, label='供需错配指数 (SMI)')
    
    texts_zoom = []
    for idx, row in df_zoom.iterrows():
        texts_zoom.append(plt.text(row['lng'], row['lat'], row['anchor_name'], fontsize=10, 
                                   bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=1)))
    adjust_text(texts_zoom, expand_points=(1.3, 1.3), expand_text=(1.1, 1.1), arrowprops=dict(arrowstyle='-', color='gray', lw=0.8))
                     
    plt.title('哈尔滨核心文旅锚点主城区局部放大图', fontsize=16)
    plt.xlabel('经度')
    plt.ylabel('纬度')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.margins(0.15)
    plt.savefig(os.path.join(OUT_DIR, 'spatial_distribution_map_zoomed.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("1.5 spatial_distribution_map_zoomed.png 完成")
    
    # 2. SMI排名柱状图
    plt.figure(figsize=(10, 8))
    df_index_sorted = df_index.sort_values('SMI', ascending=False)
    ax = sns.barplot(x='SMI', y='anchor_name', data=df_index_sorted, palette='coolwarm_r')
    
    # 增加数值标签
    for i in ax.containers:
        ax.bar_label(i, fmt='%.2f', padding=3)
        
    plt.axvline(0, color='black', linestyle='-', linewidth=1)
    plt.title('核心空间锚点供需错配指数 (SMI) 排名', fontsize=16)
    plt.xlabel('供需错配指数 (SMI: Z-score)')
    plt.ylabel('')
    plt.savefig(os.path.join(OUT_DIR, 'smi_ranking_bar.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("2. smi_ranking_bar.png 完成")
    
    # 3. 供需象限图 (SSI vs DHI)
    plt.figure(figsize=(10, 10))
    bubble_size = (df_index['ERI'] - df_index['ERI'].min() + 0.5) * 200
    scatter = plt.scatter(df_index['SSI'], df_index['DHI'], s=bubble_size, c=df_index['SMI'], cmap='coolwarm', alpha=0.7, edgecolors='black')
    
    plt.axvline(0, color='grey', linestyle='--')
    plt.axhline(0, color='grey', linestyle='--')
    
    for idx, row in df_index.iterrows():
        ox, oy = 0.04, 0.04
        if row['anchor_name'] == '防洪纪念塔':
            ox, oy = 0.08, -0.15
        elif row['anchor_name'] == '伏尔加庄园':
            ox, oy = 0.08, 0.08
        plt.annotate(row['anchor_name'], (row['SSI']+ox, row['DHI']+oy), fontsize=9, 
                     bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=0.5))
        
    plt.title('空间供需特征象限分布\n', fontsize=16)
    plt.xlabel('物理供给指数 (SSI)')
    plt.ylabel('需求热度指数 (DHI)')
    plt.grid(True, alpha=0.3)
    
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='gray', markersize=10, label='气泡大小代表：体验风险指数 (ERI)'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=10, label='颜色偏红代表：供需错配越严重 (SMI>0)'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=10, label='颜色偏蓝代表：供需平衡或冗余 (SMI<0)')
    ]
    plt.legend(handles=legend_elements, loc='upper right', fontsize=10, framealpha=0.8)
    plt.margins(0.15)
    
    ax = plt.gca()
    props = dict(fontsize=12, fontweight='bold', clip_on=False)
    ax.text(-0.02, 1.02, '高需求-低供给\n[ 重点关注区 ]', transform=ax.transAxes, va='bottom', ha='right', color='red', **props)
    ax.text(1.02, 1.02, '高需求-高供给\n[ 高承载区 ]', transform=ax.transAxes, va='bottom', ha='left', color='green', **props)
    ax.text(1.02, -0.05, '低需求-高供给\n[ 疏解潜力区 ]', transform=ax.transAxes, va='top', ha='left', color='blue', **props)
    ax.text(-0.02, -0.05, '低需求-低供给\n[ 观察区 ]', transform=ax.transAxes, va='top', ha='right', color='dimgrey', **props)
    
    plt.savefig(os.path.join(OUT_DIR, 'supply_demand_quadrant.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("3. supply_demand_quadrant.png 完成")
    
    # 4. SMI-ERI 图
    plt.figure(figsize=(8, 8))
    # 去除拟合线，避免 n=20 时产生误导
    sns.regplot(x='SMI', y='ERI', data=df_index, scatter_kws={'s': 100, 'alpha': 0.7}, fit_reg=False)
    
    texts2 = []
    for idx, row in df_index.iterrows():
        texts2.append(plt.text(row['SMI'], row['ERI'], row['anchor_name'], fontsize=9, 
                               bbox=dict(facecolor='white', alpha=0.5, edgecolor='none', pad=0.5)))
    from adjustText import adjust_text
    adjust_text(texts2, expand_points=(1.2, 1.2), expand_text=(1.05, 1.05), arrowprops=dict(arrowstyle='-', color='gray', lw=0.5))
    
    plt.title('SMI 与 ERI 关系分布图\n(注: 二者旨在呈现分布而非严格独立检验\n部分锚点错配由供给不足驱动，部分由体验风险驱动，说明存在不同形成机制)', fontsize=13)
    plt.xlabel('供需错配指数 (SMI)')
    plt.ylabel('体验风险指数 (ERI)')
    plt.grid(True, alpha=0.3)
    plt.axvline(0, color='grey', linestyle='--', alpha=0.5)
    plt.axhline(0, color='grey', linestyle='--', alpha=0.5)
    plt.margins(0.15)
    plt.savefig(os.path.join(OUT_DIR, 'smi_eri_consistency_scatter.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("4. smi_eri_consistency_scatter.png 完成")
    
    # 5. 大众点评热力图 (相对强度 0-100)
    df_dp_active = df_dp[df_dp['dp_review_count'] > 0].set_index('anchor_name')
    dp_cols = ['dp_price_pressure', 'dp_queue_pressure', 'dp_service_pressure']
    df_dp_heat = df_dp_active[dp_cols].copy()
    df_dp_heat = (df_dp_heat - df_dp_heat.min()) / (df_dp_heat.max() - df_dp_heat.min()) * 100
    df_dp_heat.columns = ['价格压力', '排队压力', '服务负向压力']
    
    plt.figure(figsize=(8, 6))
    sns.heatmap(df_dp_heat, annot=True, cmap='YlOrRd', fmt='.1f', linewidths=.5)
    plt.title('重点商圈大众点评餐饮评论压力增强验证 (相对强度: 0-100)', fontsize=15)
    plt.ylabel('')
    plt.savefig(os.path.join(OUT_DIR, 'dianping_pressure_heatmap.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("5. dianping_pressure_heatmap.png 完成")
    
    # 6. 尺度敏感性图
    top_anchors = df_index_sorted['anchor_name'].head(5).tolist()
    df_scale_top = df_scale[df_scale['anchor_name'].isin(top_anchors)].copy()
    df_scale_top['total_supply'] = (df_scale_top['ctrip_lodging_count'] + df_scale_top['amap_dining_count'] + 
                                     df_scale_top['amap_transport_count'] + df_scale_top['amap_public_count'] + 
                                     df_scale_top['amap_shopping_count'] + df_scale_top['amap_medical_count'])
    
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df_scale_top, x='scale_km', y='total_supply', hue='anchor_name', marker='o', linewidth=2.5, markersize=8)
    plt.title('Top 5 错配锚点绝对物理供给量随缓冲圈 (1/3/5km) 增长曲线', fontsize=16)
    plt.xlabel('缓冲半径 (km)')
    plt.ylabel('基础设施总供应数量 (对数刻度)')
    plt.yscale('log')
    plt.xticks([1, 3, 5])
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(OUT_DIR, 'scale_sensitivity_line.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("6. scale_sensitivity_line.png 完成")
    
    # 7. 痛点画像热力图 (逆向计算剔除平滑噪声)
    # 通过还原真实的 count，规避 Laplace Smoothing 的相同零值问题
    mask_real_pain = ~((df_xhs['traffic_pain_rate'] == df_xhs['queue_pain_rate']) & 
                       (df_xhs['queue_pain_rate'] == df_xhs['cold_pain_rate']) & 
                       (df_xhs['cold_pain_rate'] == df_xhs['price_pain_rate']))
    df_xhs_filtered = df_xhs[mask_real_pain].copy()
    valid_anchors = df_xhs_filtered['anchor_name'].tolist()
    top_valid = [a for a in df_index_sorted['anchor_name'] if a in valid_anchors][:10]
    
    df_xhs_top = df_xhs_filtered[df_xhs_filtered['anchor_name'].isin(top_valid)].set_index('anchor_name')
    
    # 公式：rate = (count + 0.5) / (mentions + 1)  => count = rate * (mentions + 1) - 0.5
    for col in ['traffic', 'queue', 'cold', 'price']:
        df_xhs_top[f'{col}_raw_count'] = df_xhs_top[f'{col}_pain_rate'] * (df_xhs_top['xhs_mentions'] + 1) - 0.5
        # 规避浮点数误差和无效值，求算真实百分比率
        df_xhs_top[f'{col}_raw_rate'] = (df_xhs_top[f'{col}_raw_count'].clip(lower=0) / df_xhs_top['xhs_mentions']).clip(lower=0, upper=1)
        
    pain_cols_raw = ['traffic_raw_rate', 'queue_raw_rate', 'cold_raw_rate', 'price_raw_rate']
    df_pain_heat = df_xhs_top[pain_cols_raw].copy() * 100
    df_pain_heat.columns = ['交通痛点率(%)', '排队痛点率(%)', '防寒痛点率(%)', '价格痛点率(%)']
    
    plt.figure(figsize=(10, 8))
    # 为百分比添加后缀和保留两位小数
    sns.heatmap(df_pain_heat, annot=True, cmap='Reds', fmt='.2f', linewidths=.5, cbar_kws={'format': '%.0f%%'})
    plt.title('高频重点锚点多维体验痛点画像\n(注: 已逆向还原为真实触发率，消除平滑伪影；痛点率为文本触发比例，受总样本量影响，主要用于比较结构)', fontsize=13)
    plt.ylabel('')
    plt.savefig(os.path.join(OUT_DIR, 'painpoint_profile_heatmap.png'), dpi=300, bbox_inches='tight')
    plt.close()
    print("7. painpoint_profile_heatmap.png 完成")
    
    # 8. 写入数据源血缘追踪日志 (figure_source_log_v22_05.csv)
    import datetime
    log_file = os.path.join(OUT_DIR, 'figure_source_log_v22_05.csv')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    top_5_smi_str = "、".join(df_index_sorted['anchor_name'].head(5).tolist())
    
    logs = [
        {"figure_name": "spatial_distribution_map", "source_csv": "anchor_index_v22_04R2.csv", "source_version": "V30", "top_5_smi": top_5_smi_str, "generated_time": timestamp},
        {"figure_name": "spatial_distribution_map_zoomed", "source_csv": "anchor_index_v22_04R2.csv", "source_version": "V30", "top_5_smi": top_5_smi_str, "generated_time": timestamp},
        {"figure_name": "smi_ranking_bar", "source_csv": "anchor_index_v22_04R2.csv", "source_version": "V30", "top_5_smi": top_5_smi_str, "generated_time": timestamp},
        {"figure_name": "supply_demand_quadrant", "source_csv": "anchor_index_v22_04R2.csv", "source_version": "V30", "top_5_smi": top_5_smi_str, "generated_time": timestamp},
        {"figure_name": "smi_eri_consistency_scatter", "source_csv": "anchor_index_v22_04R2.csv", "source_version": "V30", "top_5_smi": top_5_smi_str, "generated_time": timestamp},
        {"figure_name": "dianping_pressure_heatmap", "source_csv": "dianping_pressure_statistics_v22_04R2.csv", "source_version": "V30", "top_5_smi": top_5_smi_str, "generated_time": timestamp},
        {"figure_name": "scale_sensitivity_line", "source_csv": "supply_buffer_statistics_v22_04R2.csv", "source_version": "V30", "top_5_smi": top_5_smi_str, "generated_time": timestamp},
        {"figure_name": "painpoint_profile_heatmap", "source_csv": "xhs_demand_risk_statistics_v22_04R2.csv", "source_version": "V30", "top_5_smi": top_5_smi_str, "generated_time": timestamp}
    ]
    pd.DataFrame(logs).to_csv(log_file, index=False, encoding='utf-8-sig')
    print("8. figure_source_log_v22_05.csv 完成")
    
    print("=== 图表生成完毕 ===")

if __name__ == '__main__':
    run_charts()
