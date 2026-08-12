import pandas as pd
import requests
import time
import os

API_KEY = 'ce57767f63d6778e17108504b299870a'
CSV_PATH = r'D:\多元大数据分析\analysis\V27_Amap_Expansion\amap_poi_master_unlimited.csv'

TARGET_TYPES = {
    '050000': '餐饮服务',
    '150000': '交通设施服务',
    '200000': '公共设施',
    '100000': '住宿服务',
    '060000': '购物服务',  
    '090000': '医疗保健服务' 
}

LON_MIN, LON_MAX = 126.40, 127.10
LAT_MIN, LAT_MAX = 45.50, 45.95
STEP = 0.015

def get_grid_id(lon, lat):
    return (int((lon - 126.0) / STEP), int((lat - 45.0) / STEP))

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
                            'poi_id': poi.get('id'),
                            'name': poi.get('name'),
                            'type': poi.get('type'),
                            'typecode': poi.get('typecode'),
                            'lon': float(lon),
                            'lat': float(lat),
                            'address': poi.get('address'),
                            'adname': poi.get('adname'),
                            'biz_type': poi.get('biz_type'),
                            'category_group': TARGET_TYPES[types_code]
                        })
                count = int(resp.get('count', 0))
                if page * 25 >= count:
                    break
                page += 1
                time.sleep(0.05)
            else:
                info = resp.get('info', '')
                print(f"API Error: {info}")
                if 'LIMIT' in info.upper() or 'QUOTA' in info.upper() or 'EXCEED' in info.upper():
                    return all_pois, True # True means over limit
                break
        except Exception as e:
            print(f"Request Error: {e}")
            break
            
        if page > 40:
            print(f"Warning: Grid {polygon_str} reached 1000 limit for {types_code}!")
            break
            
    return all_pois, False

def main():
    print("=== 继续高德 POI 全量解限爬取 ===")
    
    if os.path.exists(CSV_PATH):
        df_existing = pd.read_csv(CSV_PATH)
        existing_pois = df_existing.to_dict('records')
        
        # Determine scraped grids
        scraped_grids = set()
        for idx, row in df_existing.iterrows():
            lon = float(row['lon'])
            lat = float(row['lat'])
            scraped_grids.add(get_grid_id(lon, lat))
            
        # We also manually add the bounding box that we suspect was already 100% scraped 
        # (even if some sparse areas had 0 POIs) to avoid re-crawling empty areas in the old box.
        # The old box was likely 126.50 to 126.97 and 45.61 to 45.85
        curr_lon = 126.50
        while curr_lon <= 126.97:
            curr_lat = 45.61
            while curr_lat <= 45.85:
                scraped_grids.add(get_grid_id(curr_lon, curr_lat))
                curr_lat += STEP
            curr_lon += STEP
            
        print(f"Loaded {len(existing_pois)} existing POIs.")
    else:
        existing_pois = []
        scraped_grids = set()
        print("No existing CSV found, starting from scratch!")

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
        
    total_target_grids = len(lons) * len(lats)
    grids_to_scrape = []
    
    for lon in lons:
        for lat in lats:
            gid = get_grid_id(lon, lat)
            if gid not in scraped_grids:
                grids_to_scrape.append((lon, lat))
                
    print(f"Total grids in target area: {total_target_grids}. Remaining to scrape: {len(grids_to_scrape)}")
    
    if not grids_to_scrape:
        print("All grids in the target area are already scraped!")
        return

    new_pois = []
    over_limit = False
    
    for i, (lon, lat) in enumerate(grids_to_scrape):
        lon_right = lon + STEP
        lat_top = lat + STEP
        polygon_str = f"{lon},{lat_top}|{lon_right},{lat_top}|{lon_right},{lat}|{lon},{lat}"
        
        for type_code, type_name in TARGET_TYPES.items():
            pois, hit_limit = fetch_polygon_poi(polygon_str, type_code)
            new_pois.extend(pois)
            if hit_limit:
                over_limit = True
                break
            time.sleep(0.05)
            
        if over_limit:
            print("API LIMIT REACHED! Stopping immediately.")
            break
            
        if (i + 1) % 5 == 0:
            print(f"  Scraped {i+1} / {len(grids_to_scrape)} new grids. New POIs so far: {len(new_pois)}")
            
        # Optional: stop early if we've scraped a lot just to be safe and save
        if (i + 1) >= 80:
            print("Scraped 80 grids in this run. Stopping to save and take a break.")
            break
            
    if new_pois:
        all_pois = existing_pois + new_pois
        df_all = pd.DataFrame(all_pois)
        initial_len = len(df_all)
        df_all.drop_duplicates(subset=['poi_id'], inplace=True)
        final_len = len(df_all)
        print(f"去重前: {initial_len} | 去重后: {final_len} (新增唯一 POI {final_len - len(existing_pois)} 条)")
        df_all.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
        print(f"已保存增量数据到 {CSV_PATH}")
    else:
        print("没有抓取到新的 POI 数据。")

if __name__ == '__main__':
    main()
