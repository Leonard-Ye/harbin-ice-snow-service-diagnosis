import pandas as pd
import os
import matplotlib.pyplot as plt
import seaborn as sns

def set_chinese_font():
    """设置 matplotlib 支持中文显示"""
    import platform
    system = platform.system()
    if system == 'Windows':
        plt.rcParams['font.sans-serif'] = ['SimHei']  # Windows 黑体
    elif system == 'Darwin':
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS'] # Mac
    else:
        plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei'] # Linux
    plt.rcParams['axes.unicode_minus'] = False # 正常显示负号

def plot_top_negative_locations(df):
    plt.figure(figsize=(10, 6))
    top_10 = df.head(10)
    sns.barplot(x='NegativeMentions', y='Location', data=top_10, palette='Reds_r')
    plt.title('哈尔滨核心景区/地点负面舆情提及频次 Top10', fontsize=16)
    plt.xlabel('负面舆情提及次数', fontsize=12)
    plt.ylabel('地点名称', fontsize=12)
    plt.tight_layout()
    plt.savefig('chart_top_negative_locations.png', dpi=300)
    print("生成图表: chart_top_negative_locations.png")

def plot_sentiment_distribution():
    input_path = 'structured_sentiment.csv'
    if not os.path.exists(input_path):
        return
    df_sent = pd.read_csv(input_path)
    
    # 按照维度(Aspect)统计情感分布
    aspect_sent = pd.crosstab(df_sent['Aspect'], df_sent['Sentiment'])
    if aspect_sent.empty:
        return
    
    # 将列名替换为中文标签
    aspect_sent.columns = ['负面 (-1)', '中性 (0)', '正面 (1)'] if len(aspect_sent.columns) == 3 else aspect_sent.columns
    
    aspect_sent.plot(kind='bar', stacked=True, figsize=(12, 7), color=['#d62728', '#bcbd22', '#2ca02c'])
    plt.title('各服务维度的情感极性分布图', fontsize=16)
    plt.xlabel('服务维度', fontsize=12)
    plt.ylabel('提及频次', fontsize=12)
    plt.xticks(rotation=45)
    plt.legend(title='情感极性')
    plt.tight_layout()
    plt.savefig('chart_aspect_sentiment.png', dpi=300)
    print("生成图表: chart_aspect_sentiment.png")

def main():
    print("开始生成可视化图表...")
    try:
        set_chinese_font()
    except Exception as e:
        print(f"设置中文字体失败，图表可能无法显示中文: {e}")
        
    input_path = 'spatial_painpoints.csv'
    if not os.path.exists(input_path):
        print(f"找不到聚合结果文件 {input_path}，无法生成图表。")
        return

    df = pd.read_csv(input_path)
    if df.empty:
        print("聚合数据为空，跳过图表生成。")
        return
        
    try:
        plot_top_negative_locations(df)
        plot_sentiment_distribution()
        print("所有图表生成完毕！可以用于结题报告。")
    except Exception as e:
        print(f"生成图表时发生错误，请检查是否安装了 matplotlib 和 seaborn 库: {e}")

if __name__ == '__main__':
    main()
