# -*- coding: utf-8 -*-
import pandas as pd
import requests
import time
import os

API_KEY = 'ce57767f63d6778e17108504b299870a'
BASE_DIR = r'D:\多元大数据分析'
OUT_DIR = os.path.join(BASE_DIR, '03_方法加固与审计模块', 'V27_Amap_Expansion')
MASTER_CSV = os.path.join(OUT_DIR, 'amap_poi_master_unlimited.csv')

TARGET_TYPES = {
    '050000': '餐饮服务',
    '150000': '交通设施服务',
    '200000': '公共设施',
    '100000': '住宿服务',
    '060000': '购物服务',
    '090000': '医疗保健服务'
}

# 伏尔加庄园周边网格 (126.896, 45.670) -> 扩大到 5km 覆盖范围
LON_MIN, LON_MAX = 126.82, 126.96
LAT_MIN, LAT_MAX = 45.60, 45.72
STEP = 0.02 # 郊区稀疏，可以用大网格

def fetch_polygon_poi(polygon_str, types_code):
    all_pois = []
    page = 1
    while True:
        url = f"https://restapi.amap.com/v3/place/polygon?key={API_KEY}&polygon={polygon_str}&types={types_code}&offset=25&page={page}"
        try:
            resp = requests.get(url, timeout=10).json()
            if resp.get('status') == '1':
                pois = resp.get('pois', [])
                if not pois:
                    break
                for poi in pois:
                    location = poi.get('location', '')
                    lon, lat = location.split(',') if ',' in location else (None, None)
                    if lon and lat:
                        all_pois.append({
                            'poi_id': poi.get('id', ''),
                            'name': poi.get('name', ''),
                            'type': poi.get('type', ''),
                            'typecode': poi.get('typecode', ''),
                            'lon': float(lon),
                            'lat': float(lat)
                        })
                page += 1
                time.sleep(0.1)
            else:
                break
        except Exception as e:
            print("Error:", e)
            time.sleep(1)
    return all_pois

def run():
    print("=== 开始补抓伏尔加庄园周边高德 POI ===")
    total_new = []
    
    lon_grids = int((LON_MAX - LON_MIN) / STEP) + 1
    lat_grids = int((LAT_MAX - LAT_MIN) / STEP) + 1
    
    for i in range(lon_grids):
        for j in range(lat_grids):
            cur_lon = LON_MIN + i * STEP
            cur_lat = LAT_MIN + j * STEP
            next_lon = cur_lon + STEP
            next_lat = cur_lat + STEP
            
            polygon_str = f"{cur_lon},{cur_lat}|{next_lon},{cur_lat}|{next_lon},{next_lat}|{cur_lon},{next_lat}"
            
            for type_code, type_name in TARGET_TYPES.items():
                res = fetch_polygon_poi(polygon_str, type_code)
                for item in res:
                    item['category_group'] = type_name
                total_new.extend(res)
                print(f"Grid ({cur_lon:.2f}, {cur_lat:.2f}) -> {type_name}: 抓取到 {len(res)} 条")
                
    if not total_new:
        print("未抓取到任何新数据。")
        return
        
    df_new = pd.DataFrame(total_new)
    df_new.drop_duplicates(subset=['poi_id'], inplace=True)
    print(f"\n去重后补抓总量: {len(df_new)} 条")
    
    # 拼接到 Master
    if os.path.exists(MASTER_CSV):
        df_old = pd.read_csv(MASTER_CSV)
        df_merged = pd.concat([df_old, df_new]).drop_duplicates(subset=['poi_id'])
        df_merged.to_csv(MASTER_CSV, index=False, encoding='utf-8-sig')
        print(f"追加写入完成！Master 表更新为 {len(df_merged)} 条")
    else:
        df_new.to_csv(MASTER_CSV, index=False, encoding='utf-8-sig')
        print("创建了新的 Master 表。")

if __name__ == '__main__':
    run()
