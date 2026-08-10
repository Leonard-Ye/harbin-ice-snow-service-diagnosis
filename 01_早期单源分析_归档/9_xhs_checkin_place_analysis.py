# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import re
from pathlib import Path
import ast
import json
import matplotlib.pyplot as plt
import seaborn as sns

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

PROJECT_DIR = Path(r"D:\舆情分析")
OUT_TABLE_DIR = PROJECT_DIR / "analysis_outputs_phase4" / "tables"
OUT_FIG_DIR = PROJECT_DIR / "analysis_outputs_phase4" / "figures"
OUT_QA_DIR = PROJECT_DIR / "analysis_outputs_phase4" / "qa"
OUT_GIS_DIR = PROJECT_DIR / "analysis_outputs_phase4" / "gis"

def compute_harbin_relevance(row):
    text = str(row.get('title', '')) + str(row.get('content', '')) + str(row.get('tags', ''))
    score = 0
    if "哈尔滨" in text: score += 2
    if "尔滨" in text: score += 2
    if "黑龙江" in text: score += 1
    
    poi_keywords = ["中央大街", "索菲亚", "冰雪大世界", "太阳岛", "巴洛克", "老道外", "防洪纪念塔", "松花江", "极地公园", "哈药六厂", "亚布力", "红专早市"]
    if any(k in text for k in poi_keywords): score += 3
        
    travel_keywords = ["旅游", "旅行", "攻略", "打卡", "出片", "拍照", "景点"]
    if any(k in text for k in travel_keywords): score += 1
        
    other_cities = ["长沙", "杭州", "武隆", "迪士尼", "重庆", "三亚", "成都", "北京", "上海"]
    if any(k in text for k in other_cities) and "哈尔滨" not in text and "尔滨" not in text:
        score -= 3
        
    return score

# 地点分类体系
POI_TYPE_MAPPING = {
    "中央大街": "城市地标类", "索菲亚教堂": "城市地标类", "防洪纪念塔": "城市地标类", "龙塔": "城市地标类", "松花江铁路桥": "城市地标类",
    "冰雪大世界": "冰雪景观类", "太阳岛雪博会": "冰雪景观类", "亚布力": "冰雪景观类", "冰雪大世界园区": "冰雪景观类", "松花江": "冰雪景观类", "雪博会": "冰雪景观类",
    "中华巴洛克/老道外": "历史文化类", "哈药六厂": "历史文化类", "七三一遗址": "历史文化类", "731": "历史文化类", "731遗址": "历史文化类",
    "红专街早市": "市井美食类", "道里菜市场": "市井美食类", "师大夜市": "市井美食类", "安静街": "市井美食类", "果戈里大街": "市井美食类",
    "太阳岛": "自然生态类", "东北虎林园": "自然生态类", "伏尔加庄园": "自然生态类", "雪乡": "自然生态类", "长白山": "自然生态类",
    "极地公园": "休闲娱乐类", "洗浴": "休闲娱乐类", "商场": "休闲娱乐类",
    "哈尔滨站": "交通门户类", "哈尔滨西站": "交通门户类", "太平机场": "交通门户类",
    "酒店": "住宿关联类", "民宿": "住宿关联类", "公寓": "住宿关联类",
    "道里": "区域商圈类", "道外": "区域商圈类", "江北": "区域商圈类", "群力": "区域商圈类", "松北": "区域商圈类",
    "哈尔滨工业大学": "人文科教类", "哈工大": "人文科教类"
}

def assign_poi_type(loc):
    return POI_TYPE_MAPPING.get(loc, "其他类")

# 内容分类
CONTENT_RULES = {
    "避坑提醒型": [r"避雷", r"踩坑", r"别去", r"坑", r"贵", r"被骗"],
    "求助互动型": [r"求推荐", r"怎么去", r"住哪里", r"有没有人"],
    "攻略路线型": [r"攻略", r"路线", r"几天几夜", r"保姆级", r"怎么玩", r"Day"],
    "景观展示型": [r"出片", r"拍照", r"机位", r"氛围感", r"大片", r"绝美"],
    "美食消费型": [r"美食", r"吃什么", r"餐厅", r"早市", r"锅包肉", r"铁锅炖"],
    "住宿出行型": [r"酒店", r"民宿", r"住哪", r"打车", r"机场", r"火车站", r"地铁"],
    "特产购物型": [r"特产", r"伴手礼", r"红肠", r"大列巴", r"买什么"],
    "体验评价型": [r"好玩", r"值不值", r"体验", r"推荐", r"不推荐"]
}

def extract_content_types(text):
    text = str(text)
    labels = []
    for cat, rules in CONTENT_RULES.items():
        if any(re.search(r, text) for r in rules):
            labels.append(cat)
    if not labels:
        labels.append("其他型")
    return labels

def main():
    print("=== 开始执行小红书网红打卡地空间与分类研究 ===")
    df_notes = pd.read_csv(PROJECT_DIR / "final_notes.csv", encoding='utf-8-sig')
    df_cleaned = pd.read_csv(PROJECT_DIR / "cleaned_data.csv", encoding='utf-8-sig')
    df_sent = pd.read_csv(PROJECT_DIR / "analysis_outputs" / "tables" / "cleaned_structured_sentiment_timefixed.csv", encoding='utf-8-sig')
    
    # 建立 note_id -> source_id 映射
    df_cleaned['source_id'] = df_cleaned.index
    note_mask = df_cleaned['source_type'] == 'note'
    mapping_dict = dict(zip(df_cleaned[note_mask]['original_id'].astype(str), df_cleaned[note_mask]['source_id']))
    df_notes['source_id'] = df_notes['note_id'].astype(str).map(mapping_dict)
    
    # 抽取映射审计表
    df_mapping = df_notes[['note_id', 'source_id', 'title', 'content']].copy()
    df_mapping['match_status'] = np.where(df_mapping['source_id'].notna(), 'Matched', 'Unmatched')
    df_mapping.to_csv(OUT_TABLE_DIR / "xhs_checkin_note_source_mapping.csv", index=False, encoding="utf-8-sig")
    
    # 基础信息填补
    df_notes['note_text'] = df_notes['title'].fillna('') + df_notes['content'].fillna('') + df_notes['tags'].fillna('')
    for col in ['like_count', 'collect_count', 'comment_count', 'share_count']:
        if col in df_notes.columns:
            df_notes[col] = pd.to_numeric(df_notes[col], errors='coerce').fillna(0)
    df_notes['is_video'] = (df_notes['note_type'] == '视频').astype(int)
    df_notes['publish_month'] = pd.to_datetime(df_notes['publish_time'], errors='coerce').dt.strftime('%Y-%m')
    df_notes.to_csv(OUT_TABLE_DIR / "xhs_checkin_note_base.csv", index=False, encoding="utf-8-sig")
    
    # 筛选相关笔记
    df_notes['harbin_relevance_score'] = df_notes.apply(compute_harbin_relevance, axis=1)
    df_subset = df_notes[df_notes['harbin_relevance_score'] >= 2].copy()
    df_subset.to_csv(OUT_TABLE_DIR / "xhs_checkin_note_subset.csv", index=False, encoding="utf-8-sig")
    
    # 构建地点库
    black_list = ["在", "这里", "附近", "太香了", "哈尔滨", "黑龙江", "中国", "东北", "未知", "nan", "none", "尔滨果然是一点就透", "好想去东北", "总要吹吹松花江畔的晚风", '["哈尔滨"', '"哈尔滨"', '"哈尔滨"]', '道里', '道外', '江北', '松北']
    stop_words = ["旅游", "旅行", "攻略", "美食", "吃喝玩乐", "打卡", "探店", "拍照", "周末", "计划", "安利", "南方", "大学生", "夜市", "夜景", "必去"]
    
    poi_dict = ["中央大街", "索菲亚", "防洪纪念塔", "松花江", "铁路桥", "冰雪大世界", "太阳岛", "雪博会", "中华巴洛克", "老道外", "红专", "早市", "师大夜市", "果戈里", "伏尔加庄园", "东北虎林园", "极地", "龙塔", "哈药六厂", "亚布力", "哈尔滨站", "哈站", "哈西", "太平机场", "道里", "群力", "江北", "松北", "道外"]

    candidates = []
    for _, row in df_subset.iterrows():
        sid = row['source_id']
        nid = row['note_id']
        nat_loc = str(row.get('location', '')).strip()
        if nat_loc and nat_loc.lower() not in black_list and nat_loc != 'nan':
            candidates.append({'note_id': nid, 'source_id': sid, 'raw_location': nat_loc, 'location_source': 'native_location', 'confidence': 0.6})
            
        if pd.notna(sid):
            sent_rows = df_sent[df_sent['source_id'] == sid]
            if not sent_rows.empty:
                llm_locs_str = str(sent_rows.iloc[0]['Locations'])
                if llm_locs_str and llm_locs_str != 'nan':
                    try:
                        llm_locs = ast.literal_eval(llm_locs_str)
                        if isinstance(llm_locs, list):
                            for loc in llm_locs:
                                candidates.append({'note_id': nid, 'source_id': sid, 'raw_location': loc, 'location_source': 'llm_locations', 'confidence': 0.9})
                    except:
                        pass
                        
        text = str(row.get('note_text', ''))
        for pd_k in poi_dict:
            if pd_k in text:
                candidates.append({'note_id': nid, 'source_id': sid, 'raw_location': pd_k, 'location_source': 'regex_dictionary', 'confidence': 0.85})
                
        tags = str(row.get('tags', ''))
        tag_list = tags.split(',')
        for t in tag_list:
            t = t.strip()
            if t:
                candidates.append({'note_id': nid, 'source_id': sid, 'raw_location': t, 'location_source': 'tags', 'confidence': 0.75})

    df_cand = pd.DataFrame(candidates)
    
    # 清洗 candidates
    df_cand['raw_location'] = df_cand['raw_location'].astype(str).str.strip()
    def is_valid_loc(l):
        if len(l) < 2 and l != "冰": return False
        if l.lower() in black_list: return False
        for sw in stop_words:
            if sw in l and not any(k in l for k in poi_dict):
                return False
        return True
        
    df_cand = df_cand[df_cand['raw_location'].apply(is_valid_loc)]
    df_cand_max = df_cand.groupby(['note_id', 'source_id', 'raw_location'])['confidence'].max().reset_index()
    
    # 归一化映射
    def normalize_loc(l):
        if "索菲亚" in l: return "索菲亚教堂"
        if "中央大街" in l: return "中央大街"
        if "大世界" in l: return "冰雪大世界"
        if "铁路桥" in l: return "松花江铁路桥"
        if "巴洛克" in l or "老道外" in l: return "中华巴洛克/老道外"
        if "极地" in l: return "极地公园"
        if "太阳岛" in l: return "太阳岛"
        if "哈药" in l or "六厂" in l: return "哈药六厂"
        if "红专" in l or ("早市" in l and "红专" not in l): return "红专街早市"
        if "师大" in l: return "师大夜市"
        if "果戈里" in l: return "果戈里大街"
        if "防洪" in l: return "防洪纪念塔"
        if "伏尔加" in l: return "伏尔加庄园"
        if "虎" in l: return "东北虎林园"
        if "亚布力" in l: return "亚布力"
        if "哈西" in l: return "哈尔滨西站"
        if "哈站" in l or "哈尔滨站" in l: return "哈尔滨站"
        if "机场" in l: return "太平机场"
        if "松花江" in l: return "松花江"
        return l
        
    df_cand_max['normalized_location'] = df_cand_max['raw_location'].apply(normalize_loc)
    df_cand_max.to_csv(OUT_TABLE_DIR / "xhs_checkin_locations_long.csv", index=False, encoding="utf-8-sig")
    
    alias_map = df_cand_max[['raw_location', 'normalized_location']].drop_duplicates()
    alias_map.to_csv(OUT_TABLE_DIR / "xhs_checkin_poi_alias_mapping.csv", index=False, encoding="utf-8-sig")
    
    # 将地点连回 subset
    # 每个 note_id 保留其最高 confidence 的那些 normalized_location
    df_loc_agg = df_cand_max.groupby('note_id')['normalized_location'].apply(lambda x: list(set(x))).reset_index()
    df_subset = df_subset.merge(df_loc_agg, on='note_id', how='inner') # 只保留有地点的笔记
    
    df_subset['content_labels'] = df_subset['note_text'].apply(extract_content_types)
    df_subset['primary_content_type'] = df_subset['content_labels'].apply(lambda x: x[0])
    
    # 传播热度计算
    df_subset['raw_interaction_total'] = df_subset['like_count'] + df_subset['collect_count'] + df_subset['comment_count'] + df_subset['share_count']
    df_subset['checkin_heat_score'] = (
        1.0 * np.log1p(df_subset['like_count']) +
        1.3 * np.log1p(df_subset['collect_count']) +
        1.1 * np.log1p(df_subset['comment_count']) +
        1.5 * np.log1p(df_subset['share_count'])
    )
    df_subset.to_csv(OUT_TABLE_DIR / "xhs_checkin_note_metrics.csv", index=False, encoding="utf-8-sig")
    
    # 展开地长表以计算 POI 聚合
    poi_records = []
    for _, row in df_subset.iterrows():
        for loc in row['normalized_location']:
            d = row.to_dict()
            d['normalized_location'] = loc
            poi_records.append(d)
    df_poi_long = pd.DataFrame(poi_records)
    
    df_poi_long['poi_type_primary'] = df_poi_long['normalized_location'].apply(assign_poi_type)
    
    # 关键修改：在这里彻底剔除"其他类"，确保后续所有表、所有图均干净！
    df_poi_long = df_poi_long[df_poi_long['poi_type_primary'] != '其他类'].copy()
    
    # 聚合 POI
    poi_agg = df_poi_long.groupby('normalized_location').agg({
        'poi_type_primary': 'first',
        'note_id': 'count',
        'like_count': 'sum',
        'collect_count': 'sum',
        'comment_count': 'sum',
        'share_count': 'sum',
        'raw_interaction_total': 'sum',
        'checkin_heat_score': 'sum'
    }).rename(columns={'note_id': 'note_count', 'checkin_heat_score': 'total_heat_score'}).reset_index()
    
    poi_agg['avg_heat_score'] = poi_agg['total_heat_score'] / poi_agg['note_count']
    poi_agg = poi_agg.sort_values('total_heat_score', ascending=False)
    poi_agg.to_csv(OUT_TABLE_DIR / "xhs_checkin_poi_summary.csv", index=False, encoding="utf-8-sig")
    
    # 类型聚合
    type_agg = poi_agg.groupby('poi_type_primary')['note_count'].sum().reset_index()
    type_agg.to_csv(OUT_TABLE_DIR / "xhs_checkin_poi_type_summary.csv", index=False, encoding="utf-8-sig")
    
    content_agg = df_poi_long.groupby('primary_content_type')['note_id'].count().reset_index()
    content_agg.to_csv(OUT_TABLE_DIR / "xhs_checkin_content_type_summary.csv", index=False, encoding="utf-8-sig")
    
    poi_content_matrix = pd.crosstab(df_poi_long['poi_type_primary'], df_poi_long['primary_content_type'])
    poi_content_matrix.to_csv(OUT_TABLE_DIR / "xhs_checkin_poi_type_content_matrix.csv", encoding="utf-8-sig")
    
    # 合并舆情风险
    df_sent_heat = pd.read_csv(PROJECT_DIR / "analysis_outputs" / "tables" / "poi_sentiment_heat.csv", encoding='utf-8-sig')
    poi_join = poi_agg.merge(df_sent_heat[['normalized_location', '负面提及数', '负面率', '总提及热度']], on='normalized_location', how='left')
    poi_join.rename(columns={'负面提及数': 'negative_mentions', '负面率': 'negative_ratio'}, inplace=True)
    poi_join['negative_mentions'] = poi_join['negative_mentions'].fillna(0)
    poi_join['negative_ratio'] = poi_join['negative_ratio'].fillna(0)
    
    poi_join.to_csv(OUT_TABLE_DIR / "xhs_checkin_poi_sentiment_join.csv", index=False, encoding="utf-8-sig")
    
    # 象限分析
    valid_poi = poi_join[(poi_join['note_count'] >= 3) | (poi_join['总提及热度'] >= 5)].copy()
    
    if not valid_poi.empty:
        heat_p75 = valid_poi['total_heat_score'].quantile(0.75)
        note_p75 = valid_poi['note_count'].quantile(0.75)
        risk_med = valid_poi['negative_ratio'].median()
        
        def get_quadrant(r):
            is_high_heat = r['total_heat_score'] >= heat_p75 or r['note_count'] >= note_p75
            is_high_risk = r['negative_mentions'] >= 3 and r['negative_ratio'] >= risk_med
            if is_high_heat and is_high_risk: return "重点治理点"
            if is_high_heat and not is_high_risk: return "城市形象样板点"
            if not is_high_heat and is_high_risk: return "潜在雷区"
            return "潜力培育点"
            
        valid_poi['quadrant_type'] = valid_poi.apply(get_quadrant, axis=1)
        valid_poi.to_csv(OUT_TABLE_DIR / "xhs_checkin_heat_risk_quadrant.csv", index=False, encoding="utf-8-sig")
    
    # 导出 GIS
    gis_df = poi_join.head(30).copy()
    gis_df['district'] = ''
    gis_df['longitude'] = ''
    gis_df['latitude'] = ''
    gis_df.to_excel(OUT_GIS_DIR / "xhs_checkin_geocode_template.xlsx", index=False)
    
    # 月度分析
    month_trend = df_poi_long.groupby(['publish_month', 'poi_type_primary']).size().reset_index(name='note_count')
    month_trend.to_csv(OUT_TABLE_DIR / "xhs_checkin_monthly_trend.csv", index=False, encoding="utf-8-sig")
    
    # 图表绘制
    fig, ax = plt.subplots(figsize=(10, 6))
    top20 = poi_agg.head(20)
    sns.barplot(data=top20, y='normalized_location', x='total_heat_score', color="#3498db", ax=ax)
    ax.set_title("小红书高频打卡地传播热度 Top 20", fontsize=14)
    ax.set_xlabel("传播热度得分")
    ax.set_ylabel("打卡地")
    plt.tight_layout()
    plt.savefig(OUT_FIG_DIR / "xhs_checkin_top_poi_bar.png", dpi=300)
    plt.close()
    
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=type_agg.sort_values('note_count', ascending=False), y='poi_type_primary', x='note_count', color="#2ecc71", ax=ax)
    ax.set_title("小红书打卡地空间类型结构分布", fontsize=14)
    ax.set_xlabel("内容发布量 (篇)")
    ax.set_ylabel("打卡地空间类型")
    plt.tight_layout()
    plt.savefig(OUT_FIG_DIR / "xhs_checkin_poi_type_bar.png", dpi=300)
    plt.close()
    
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=content_agg.sort_values('note_id', ascending=False), y='primary_content_type', x='note_id', color="#9b59b6", ax=ax)
    ax.set_title("小红书打卡内容表达类型分布", fontsize=14)
    ax.set_xlabel("内容发布量 (篇)")
    ax.set_ylabel("内容表达类型")
    plt.tight_layout()
    plt.savefig(OUT_FIG_DIR / "xhs_checkin_content_type_bar.png", dpi=300)
    plt.close()
    
    fig, ax = plt.subplots(figsize=(10, 8))
    import matplotlib.colors as mcolors
    cmap_base = plt.get_cmap("Blues")
    cmap_custom = mcolors.LinearSegmentedColormap.from_list("custom", cmap_base(np.linspace(0.15, 1.0, 100)))
    sns.heatmap(poi_content_matrix, cmap=cmap_custom, annot=True, fmt="d", ax=ax, robust=True)
    ax.set_title("打卡地类型与内容表达方式交叉热力图", fontsize=14)
    ax.set_xlabel("内容表达方式")
    ax.set_ylabel("打卡地空间类型")
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(OUT_FIG_DIR / "xhs_checkin_poi_type_content_heatmap.png", dpi=300)
    plt.close()
    
    if not valid_poi.empty:
        try:
            from adjustText import adjust_text
        except ImportError:
            adjust_text = None
            
        fig, ax = plt.subplots(figsize=(10, 8))
        colors = {"重点治理点": "#e74c3c", "城市形象样板点": "#2ecc71", "潜在雷区": "#f39c12", "潜力培育点": "#95a5a6"}
        
        texts = []
        for t, g in valid_poi.groupby('quadrant_type'):
            ax.scatter(g['total_heat_score'], g['negative_ratio'], s=g['note_count']*5, c=colors[t], label=t, alpha=0.6, edgecolors='w')
            for _, r in g.head(10).iterrows():
                texts.append(ax.text(r['total_heat_score'], r['negative_ratio'], r['normalized_location'], fontsize=9))
                
        if adjust_text and texts:
            adjust_text(texts, ax=ax, arrowprops=dict(arrowstyle='-', color='gray', lw=0.5))
                
        ax.set_title("小红书打卡地传播热度—体验风险象限图", fontsize=14)
        ax.set_xlabel("传播热度得分")
        ax.set_ylabel("负面率")
        ax.axvline(heat_p75, color='gray', linestyle='--')
        ax.axhline(risk_med, color='gray', linestyle='--')
        ax.legend()
        plt.tight_layout()
        plt.savefig(OUT_FIG_DIR / "xhs_checkin_heat_sentiment_quadrant.png", dpi=300)
        plt.close()

    # 月度分析图表
    if not month_trend.empty:
        # 过滤掉无法解析的月份并限定到 2025-10 到 2026-04 冰雪季
        valid_trend = month_trend[month_trend['publish_month'].notna()].copy()
        valid_trend = valid_trend[(valid_trend['publish_month'] >= '2025-10') & (valid_trend['publish_month'] <= '2026-04')]
        if not valid_trend.empty:
            # 找到 top 4 类型
            top_types = valid_trend.groupby('poi_type_primary')['note_count'].sum().nlargest(4).index
            plot_data = valid_trend[valid_trend['poi_type_primary'].isin(top_types)]
            
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.lineplot(data=plot_data, x='publish_month', y='note_count', hue='poi_type_primary', marker='o', ax=ax)
            ax.set_title("2025.10—2026.04 哈尔滨冰雪季小红书打卡趋势", fontsize=14)
            ax.set_xlabel("发布月份")
            ax.set_ylabel("内容发布量")
            plt.xticks(rotation=45)
            plt.legend(title="空间类型")
            plt.tight_layout()
            plt.savefig(OUT_FIG_DIR / "xhs_checkin_monthly_trend.png", dpi=300)
            plt.close()

    print("=== 小红书网红打卡地空间与分类分析执行完毕 ===")

if __name__ == '__main__':
    main()
