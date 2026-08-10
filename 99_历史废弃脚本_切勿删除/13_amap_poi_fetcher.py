import requests
import json
import pandas as pd
import time
import os

API_KEY = 'ce57767f63d6778e17108504b299870a'

# 六大核心锚点坐标
CORE_POIS = {
    '哈尔滨冰雪大世界': '126.562459,45.777005',
    '中央大街': '126.618958,45.773941',
    '圣索菲亚教堂': '126.627215,45.770125',
    '太阳岛风景区': '126.597880,45.791584',
    '哈尔滨站': '126.632690,45.761621',
    '哈尔滨西站': '126.577304,45.707228'
}

# 抓取的 POI 大类
TYPES_TO_FETCH = {
    '餐饮服务': '050000',
    '住宿服务': '100000',
    '交通设施服务': '150000',
    '公共设施': '200000'
}

def fetch_around(location, types, radius=5000):
    all_pois = []
    page = 1
    while page <= 40: # Max 1000 results (25 per page)
        url = f'https://restapi.amap.com/v3/place/around?key={API_KEY}&location={location}&radius={radius}&types={types}&offset=25&page={page}&extensions=base'
        try:
            resp = requests.get(url).json()
            if resp.get('status') == '1' and resp.get('pois'):
                pois = resp['pois']
                all_pois.extend(pois)
                if len(pois) < 25:
                    break # Last page
            else:
                break
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break
        page += 1
        time.sleep(0.1) # Rate limit protection
    return all_pois

def main():
    output_dir = r'D:\多元大数据分析\02_高德底图模块'
    os.makedirs(output_dir, exist_ok=True)
    
    for type_name, type_code in TYPES_TO_FETCH.items():
        print(f"Fetching {type_name}...")
        type_pois = []
        for anchor_name, location in CORE_POIS.items():
            print(f"  -> Around {anchor_name}")
            pois = fetch_around(location, type_code)
            
            for p in pois:
                lon, lat = p.get('location', ',').split(',')
                type_pois.append({
                    'id': p.get('id'),
                    'name': p.get('name'),
                    'type': p.get('type'),
                    'typecode': p.get('typecode'),
                    'address': p.get('address'),
                    'lon': lon,
                    'lat': lat,
                    'anchor': anchor_name
                })
        
        # Deduplicate
        df = pd.DataFrame(type_pois)
        if not df.empty:
            df = df.drop_duplicates(subset=['id'])
            out_file = os.path.join(output_dir, f'amap_{type_name}.csv')
            df.to_csv(out_file, index=False, encoding='utf-8-sig')
            print(f"Saved {len(df)} unique POIs to {out_file}")
        else:
            print(f"No data for {type_name}")

if __name__ == '__main__':
    main()
