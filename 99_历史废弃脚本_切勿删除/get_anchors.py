import pandas as pd
df = pd.read_csv('D:/多元大数据分析/03_方法加固与审计模块/V25_Full_Mapping/xhs_to_amap_full_mapped.csv')
counts = df['normalized_location'].astype(str).str.replace('"', '').str.replace("'", "").value_counts()
with open('D:/多元大数据分析/top_anchors.txt', 'w', encoding='utf-8-sig') as f:
    for k, v in counts.head(50).items():
        f.write(f"{k}: {v}\n")
