import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# 解决中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei']  
plt.rcParams['axes.unicode_minus'] = False 

def analyze_temporal_trend(input_csv):
    if not os.path.exists(input_csv):
        print(f"找不到 {input_csv}")
        return

    df = pd.read_csv(input_csv)
    
    # 过滤缺少时间的数据
    df = df[df['publish_time'].notna()]
    
    # 清洗时间数据，尝试转换为 datetime
    try:
        # 小红书的时间有时是 "今天", "昨天", "12-15", 或者标准日期
        # 为简化，我们过滤并只取能被 pandas 解析的时间
        df['date'] = pd.to_datetime(df['publish_time'], errors='coerce')
        df = df[df['date'].notna()]
        
        # 截取到月份或具体的周
        df['week'] = df['date'].dt.to_period('W').apply(lambda r: r.start_time)
        
        # 按周统计：总热度和负面舆情率
        temporal_df = df.groupby('week').agg(
            TotalMentions=('Sentiment', 'count'),
            NegativeMentions=('Sentiment', lambda x: (x == -1).sum())
        ).reset_index()
        
        temporal_df['NegativeRatio'] = (temporal_df['NegativeMentions'] / temporal_df['TotalMentions']) * 100
        
        # 绘制双轴折线图
        fig, ax1 = plt.subplots(figsize=(12, 6))
        
        # 轴 1：总热度 (柱状图)
        color = 'tab:blue'
        ax1.set_xlabel('时间序列 (周)', fontsize=12)
        ax1.set_ylabel('全网总讨论热度 (条)', color=color, fontsize=12)
        ax1.bar(temporal_df['week'], temporal_df['TotalMentions'], width=4, color=color, alpha=0.5, label='讨论热度')
        ax1.tick_params(axis='y', labelcolor=color)
        
        # 轴 2：负面率 (折线图)
        ax2 = ax1.twinx()  
        color = 'tab:red'
        ax2.set_ylabel('负面舆情占比 (%)', color=color, fontsize=12)  
        ax2.plot(temporal_df['week'], temporal_df['NegativeRatio'], color=color, marker='o', linewidth=2, label='负面率')
        ax2.tick_params(axis='y', labelcolor=color)
        
        fig.suptitle('冰雪旅游热度与设施承载力(负面率)时效性追踪', fontsize=16)
        fig.tight_layout()  
        plt.savefig('chart_temporal_trend.png', dpi=300)
        print("图表已生成: chart_temporal_trend.png")
        
    except Exception as e:
        print(f"时间解析错误，可能需要更复杂的时间清洗逻辑: {e}")

if __name__ == '__main__':
    analyze_temporal_trend('structured_sentiment.csv')
