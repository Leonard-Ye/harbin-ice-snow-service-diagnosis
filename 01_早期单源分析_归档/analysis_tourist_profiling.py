import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

# 解决中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei']  
plt.rcParams['axes.unicode_minus'] = False 

def analyze_tourist_profiling(input_csv):
    if not os.path.exists(input_csv):
        print(f"找不到 {input_csv}")
        return

    df = pd.read_csv(input_csv)
    
    # 过滤掉未知 IP 和未知画像
    df_ip = df[df['ip_location'].notna() & (df['ip_location'] != '未知')]
    df_persona = df[df['TouristPersona'].notna() & (df['TouristPersona'] != '未知')]

    # 1. 绘制客源地 TOP 10 柱状图
    plt.figure(figsize=(10, 6))
    top_ips = df_ip['ip_location'].value_counts().head(10)
    sns.barplot(x=top_ips.index, y=top_ips.values, color='skyblue')
    plt.title('游客核心客源地分布 (Top 10)', fontsize=16)
    plt.ylabel('讨论热度 / 人数', fontsize=12)
    plt.xlabel('省份 / 地区', fontsize=12)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('chart_tourist_source_provinces.png', dpi=300)
    print("图表已生成: chart_tourist_source_provinces.png")
    
    # 2. 绘制不同游客画像的关注维度热力图
    # 交叉表：画像 vs 关注维度
    if not df_persona.empty:
        persona_aspect_crosstab = pd.crosstab(df_persona['TouristPersona'], df_persona['Aspect'])
        
        # 归一化：看每类人群内部的关注比例
        persona_aspect_norm = persona_aspect_crosstab.div(persona_aspect_crosstab.sum(axis=1), axis=0) * 100
        
        plt.figure(figsize=(12, 6))
        sns.heatmap(persona_aspect_norm, annot=True, fmt=".1f", cmap="YlGnBu", linewidths=.5)
        plt.title('不同游客画像的关注维度偏好热力图 (%)', fontsize=16)
        plt.ylabel('游客画像', fontsize=12)
        plt.xlabel('服务/体验维度', fontsize=12)
        plt.tight_layout()
        plt.savefig('chart_tourist_persona_preferences.png', dpi=300)
        print("图表已生成: chart_tourist_persona_preferences.png")

if __name__ == '__main__':
    analyze_tourist_profiling('structured_sentiment.csv')
