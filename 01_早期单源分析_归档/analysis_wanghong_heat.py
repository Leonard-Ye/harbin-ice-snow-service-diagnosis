import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# 解决中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei']  
plt.rcParams['axes.unicode_minus'] = False 

def analyze_wanghong_heat(input_csv):
    if not os.path.exists(input_csv):
        print(f"找不到 {input_csv}")
        return

    df = pd.read_csv(input_csv)
    
    # 剔除无效地点
    valid_locations = df[df['Location'] != 'Unknown']
    
    # 统计每个地点的热度（被提及次数）和整体情感指数
    # 情感指数 = (正面次数 - 负面次数) / 总次数
    
    heat_df = valid_locations.groupby('Location').agg(
        TotalHeat=('Sentiment', 'count'),
        PositiveMentions=('Sentiment', lambda x: (x == 1).sum()),
        NegativeMentions=('Sentiment', lambda x: (x == -1).sum())
    ).reset_index()
    
    # 过滤掉热度极低的偶然地点（比如提及不到2次的）
    heat_df = heat_df[heat_df['TotalHeat'] >= 2]
    
    heat_df['SentimentIndex'] = (heat_df['PositiveMentions'] - heat_df['NegativeMentions']) / heat_df['TotalHeat']
    
    # 获取热度前15的网红打卡地
    top_15_heat = heat_df.sort_values(by='TotalHeat', ascending=False).head(15)
    
    # 绘制气泡图：X轴为热度，Y轴为情感指数，气泡大小代表总热度
    plt.figure(figsize=(12, 7))
    scatter = sns.scatterplot(
        data=top_15_heat,
        x='TotalHeat', 
        y='SentimentIndex',
        size='TotalHeat',
        sizes=(100, 2000),
        hue='SentimentIndex',
        palette='RdYlGn',
        alpha=0.8,
        legend=False
    )
    
    # 添加地点标签
    for i in range(top_15_heat.shape[0]):
        plt.text(
            x=top_15_heat['TotalHeat'].iloc[i] + 0.5, 
            y=top_15_heat['SentimentIndex'].iloc[i], 
            s=top_15_heat['Location'].iloc[i], 
            fontsize=10
        )
        
    plt.axhline(y=0, color='gray', linestyle='--')
    plt.title('哈尔滨 Top15 网红打卡地热度与口碑矩阵图', fontsize=16)
    plt.xlabel('讨论热度 (总提及次数)', fontsize=12)
    plt.ylabel('情感指数 (越接近1口碑越好，越接近-1槽点越多)', fontsize=12)
    
    plt.tight_layout()
    plt.savefig('chart_wanghong_matrix.png', dpi=300)
    print("图表已生成: chart_wanghong_matrix.png")

if __name__ == '__main__':
    analyze_wanghong_heat('structured_sentiment.csv')
