# -*- coding: utf-8 -*-
import pandas as pd
import requests
import time
import os

API_KEY = 'ce57767f63d6778e17108504b299870a'
BASE_DIR = r'D:\多元大数据分析'
OUT_DIR = os.path.join(BASE_DIR, '03_方法加固与审计模块', 'V27_Amap_Expansion')
os.makedirs(OUT_DIR, exist_ok=True)

# 目标类别 (包括原有四项 + 新增两项)
TARGET_TYPES = {
    '050000': '餐饮服务',
    '150000': '交通设施服务',
    '200000': '公共设施',
    '100000': '住宿服务',
    '060000': '购物服务',  # 新增保暖相关
    '090000': '医疗保健服务' # 新增急救/防寒伤病相关
}

# 哈尔滨核心城区 Bounding Box
LON_MIN, LON_MAX = 126.50, 126.75
LAT_MIN, LAT_MAX = 45.70, 45.85
STEP = 0.015 # 约 1.5km x 1.5km 的细分网格，确保单一网格单一类别极难超过 1000 条

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
                    all_pois.append({
                        'poi_id': poi.get('id'),
                        'name': poi.get('name'),
                        'type': poi.get('type'),
                        'typecode': poi.get('typecode'),
                        'lon': lon,
                        'lat': lat,
                        'address': poi.get('address'),
                        'adname': poi.get('adname'),
                        'biz_type': poi.get('biz_type'),
                        'category_group': TARGET_TYPES[types_code]
                    })
                # 判断是否还有下一页
                count = int(resp.get('count', 0))
                if page * 25 >= count:
                    break
                page += 1
                time.sleep(0.05)
            else:
                print(f"API Error: {resp.get('info')}")
                break
        except Exception as e:
            print(f"Request Error: {e}")
            break
            
        # 强制保护，防止死循环
        if page > 40: # 40*25 = 1000, 达到高德单次多边形检索上限
            print(f"Warning: Grid {polygon_str} reached 1000 limit for {types_code}!")
            break
            
    return all_pois

def main():
    print("=== 开始高德 POI 网格化解限全量抓取 ===")
    
    # 划分网格
    lons = []
    curr_lon = LON_MIN
    while curr_lon < LON_MAX:
        lons.append(curr_lon)
        curr_lon += STEP
        
    lats = []
    curr_lat = LAT_MIN
    while curr_lat < LAT_MAX:
        lats.append(curr_lat)
        curr_lat += STEP
        
    total_grids = len(lons) * len(lats)
    print(f"核心区共划分出 {total_grids} 个细分网格。即将扫描 {len(TARGET_TYPES)} 个核心类别。")
    
    master_poi_list = []
    grid_count = 0
    
    for lon in lons:
        for lat in lats:
            grid_count += 1
            # 构造多边形 左上、右上、右下、左下
            lon_right = lon + STEP
            lat_top = lat + STEP
            polygon_str = f"{lon},{lat_top}|{lon_right},{lat_top}|{lon_right},{lat}|{lon},{lat}"
            
            for type_code, type_name in TARGET_TYPES.items():
                pois = fetch_polygon_poi(polygon_str, type_code)
                master_poi_list.extend(pois)
                time.sleep(0.05)
                
            if grid_count % 10 == 0:
                print(f"  进度: {grid_count} / {total_grids} 网格完成. 当前累计 POI: {len(master_poi_list)}")
                
    # 去重处理
    print("抓取完毕，开始基于 POI ID 进行绝对去重...")
    df_pois = pd.DataFrame(master_poi_list)
    
    if len(df_pois) > 0:
        initial_len = len(df_pois)
        df_pois.drop_duplicates(subset=['poi_id'], inplace=True)
        final_len = len(df_pois)
        print(f"去重前: {initial_len} 条 | 去重后: {final_len} 条 (剔除边缘重叠 {initial_len - final_len} 条)")
        
        # 输出
        out_path = os.path.join(OUT_DIR, 'amap_poi_master_unlimited.csv')
        df_pois.to_csv(out_path, index=False, encoding='utf-8-sig')
        print(f"全量解限底图已输出至: {out_path}")
        
        # 分类统计
        print("\n各类别最终入库数量分布：")
        print(df_pois['category_group'].value_counts().to_string())
    else:
        print("未抓取到任何数据！")

if __name__ == '__main__':
    main()
