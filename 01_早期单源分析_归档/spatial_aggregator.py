import pandas as pd
import os
from collections import Counter

def main():
    print("开始空间痛点聚合分析...")
    input_path = 'structured_sentiment.csv'
    output_path = 'spatial_painpoints.csv'
    
    if not os.path.exists(input_path):
        print(f"找不到提取结果文件 {input_path}")
        return

    df = pd.read_csv(input_path)
    
    # 过滤掉无法识别地点的记录
    df = df[df['Location'] != 'Unknown']
    df = df[df['Location'] != 'Error']
    df = df.dropna(subset=['Location'])
    
    # 初始化聚合数据结构
    # { "LocationName": { "total_mentions": 0, "negative_mentions": 0, "painpoints": Counter() } }
    agg_data = {}
    
    for _, row in df.iterrows():
        loc = str(row['Location']).strip()
        sentiment = row.get('Sentiment', 0)
        pain_points_str = str(row.get('PainPoints', ''))
        
        if loc not in agg_data:
            agg_data[loc] = {
                "total_mentions": 0,
                "negative_mentions": 0,
                "painpoints": Counter()
            }
            
        agg_data[loc]["total_mentions"] += 1
        
        if sentiment == -1:
            agg_data[loc]["negative_mentions"] += 1
            if pain_points_str and pain_points_str.lower() != 'nan':
                # 分割痛点
                pts = [p.strip() for p in pain_points_str.split('、') if p.strip()]
                agg_data[loc]["painpoints"].update(pts)

    # 转化为 DataFrame 输出
    results = []
    for loc, data in agg_data.items():
        # 获取 Top3 痛点
        top_pts = data["painpoints"].most_common(3)
        top_pts_str = "、".join([f"{k}({v}次)" for k, v in top_pts]) if top_pts else "无明显痛点"
        
        results.append({
            "Location": loc,
            "TotalMentions": data["total_mentions"],
            "NegativeMentions": data["negative_mentions"],
            "NegativeRatio": round(data["negative_mentions"] / data["total_mentions"], 2) if data["total_mentions"] > 0 else 0,
            "TopPainPoints": top_pts_str
        })
        
    res_df = pd.DataFrame(results)
    # 按负面提及次数降序排列
    res_df = res_df.sort_values(by='NegativeMentions', ascending=False)
    
    res_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"空间聚合完成！已提取各景区的核心痛点，并保存至 {output_path}")
    print(">> 注意：若您已有 POI 数据，后续可以将此 CSV 的 Location 字段与 POI 数据中的名称进行 Left Join，以生成带经纬度的 QGIS 热力图底表。")

if __name__ == '__main__':
    main()
