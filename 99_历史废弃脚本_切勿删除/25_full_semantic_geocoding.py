# -*- coding: utf-8 -*-
import pandas as pd
import requests
import time
import os
import json

API_KEY = 'ce57767f63d6778e17108504b299870a'
BASE_DIR = r'D:\多元大数据分析'
OUT_DIR = os.path.join(BASE_DIR, '03_方法加固与审计模块', 'V25_Full_Mapping')
os.makedirs(OUT_DIR, exist_ok=True)

DICT_PATH = os.path.join(OUT_DIR, 'amap_geocoded_dictionary.csv')

def geocode_amap(address):
    # 如果地址很短或者不包含哈尔滨，前置哈尔滨以提高准确率
    search_addr = address
    if "哈尔滨" not in address:
        search_addr = "哈尔滨市" + address
        
    url = f"https://restapi.amap.com/v3/geocode/geo?key={API_KEY}&address={search_addr}&city=哈尔滨"
    try:
        resp = requests.get(url, timeout=5).json()
        if resp.get('status') == '1' and resp.get('geocodes'):
            location = resp['geocodes'][0].get('location', '')
            if location:
                lon, lat = location.split(',')
                return lon, lat, resp['geocodes'][0].get('formatted_address', '')
    except Exception as e:
        print(f"Error geocoding {address}: {e}")
    return None, None, None

def load_or_create_dict():
    if os.path.exists(DICT_PATH):
        return pd.read_csv(DICT_PATH, encoding='utf-8-sig').to_dict('records')
    return []

def save_dict(dict_list):
    pd.DataFrame(dict_list).to_csv(DICT_PATH, index=False, encoding='utf-8-sig')

def main():
    print("=== 开始全量逐条地理编码与映射 ===")
    
    # 1. 提取去重地名池
    print("读取原始数据...")
    # 大众点评
    dp_path = os.path.join(BASE_DIR, '哈尔滨冬季大众点评评论.xlsx')
    df_dp = pd.read_excel(dp_path)
    dp_locations = df_dp['商圈/景区'].dropna().unique().tolist()
    
    # 小红书
    xhs_long_path = os.path.join(BASE_DIR, '01_小红书分析模块', 'analysis_outputs_phase4', 'tables', 'xhs_checkin_locations_long.csv')
    df_xhs_long = pd.read_csv(xhs_long_path, encoding='utf-8-sig')
    xhs_locations = df_xhs_long['normalized_location'].dropna().unique().tolist()
    
    all_locations = list(set(dp_locations + xhs_locations))
    print(f"共发现 {len(all_locations)} 个独立地名需要进行高德逆向解析。")
    
    # 2. 地理编码 (带缓存断点续传)
    geo_dict = load_or_create_dict()
    processed_locs = {d['location']: (d['lon'], d['lat']) for d in geo_dict}
    
    new_records = []
    count = 0
    total = len(all_locations)
    
    for loc in all_locations:
        loc_str = str(loc).strip()
        if not loc_str or loc_str in processed_locs:
            continue
            
        lon, lat, formatted = geocode_amap(loc_str)
        record = {
            'location': loc_str,
            'lon': lon,
            'lat': lat,
            'formatted_address': formatted
        }
        geo_dict.append(record)
        new_records.append(record)
        processed_locs[loc_str] = (lon, lat)
        
        count += 1
        if count % 50 == 0:
            print(f"  Geocoding 进度: {count} / {total - len(processed_locs) + count}")
            save_dict(geo_dict)
            
        time.sleep(0.05) # QPS limit
        
    if new_records:
        save_dict(geo_dict)
    print("高德 API 地理编码完成！")
    
    # 3. 映射大众点评 7000 条
    print("映射大众点评数据...")
    df_geo = pd.DataFrame(geo_dict)
    
    # 拼接
    df_dp_mapped = df_dp.merge(
        df_geo[['location', 'lon', 'lat', 'formatted_address']], 
        left_on='商圈/景区', 
        right_on='location', 
        how='left'
    )
    df_dp_mapped.to_csv(os.path.join(OUT_DIR, 'dianping_to_amap_full_mapped.csv'), index=False, encoding='utf-8-sig')
    print(f"大众点评映射完毕：总计 {len(df_dp_mapped)} 条，成功坐标化 {df_dp_mapped['lon'].notna().sum()} 条。")
    
    # 4. 映射小红书 10000+ 条
    print("映射小红书数据...")
    xhs_sent_path = os.path.join(BASE_DIR, '01_小红书分析模块', 'analysis_outputs', 'tables', 'cleaned_structured_sentiment_timefixed.csv')
    df_xhs_sent = pd.read_csv(xhs_sent_path, encoding='utf-8-sig')
    
    # 第一步 Join：用 source_id 把 long 表接上来
    # 注意：一个 source_id 可能对应多个 location，这会导致 sentiment 原文展开为多行，这是对的（因为同一次评价抱怨了多个地点）
    df_xhs_bridge = df_xhs_sent.merge(
        df_xhs_long[['source_id', 'normalized_location', 'confidence']], 
        on='source_id', 
        how='inner' # inner join 过滤掉那些完全没有提到地点的原笔记
    )
    
    # 第二步 Join：把经纬度接上来
    df_xhs_mapped = df_xhs_bridge.merge(
        df_geo[['location', 'lon', 'lat', 'formatted_address']],
        left_on='normalized_location',
        right_on='location',
        how='left'
    )
    
    # 清理多余列并输出
    df_xhs_mapped.to_csv(os.path.join(OUT_DIR, 'xhs_to_amap_full_mapped.csv'), index=False, encoding='utf-8-sig')
    print(f"小红书映射完毕：原生舆情参与映射的源笔记共产生 {len(df_xhs_mapped)} 次地点提及，")
    print(f"成功获得精确坐标并落图的记录数：{df_xhs_mapped['lon'].notna().sum()} 条。")
    
    print("=== 全量逐条映射流程结束 ===")

if __name__ == '__main__':
    main()
