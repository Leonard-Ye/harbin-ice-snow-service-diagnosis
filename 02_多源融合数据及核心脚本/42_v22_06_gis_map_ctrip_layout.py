import math
import requests
from PIL import Image
import io
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import geopandas as gpd
from adjustText import adjust_text
import os
import pyproj

# Coordinate Conversion (GCJ-02 to WGS-84)
pi = 3.1415926535897932384626
a = 6378245.0
ee = 0.00669342162296594323

def out_of_china(lng, lat):
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)

def transformlat(lng, lat):
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 * math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * pi) + 40.0 * math.sin(lat / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * pi) + 320 * math.sin(lat * pi / 30.0)) * 2.0 / 3.0
    return ret

def transformlng(lng, lat):
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 * math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * pi) + 40.0 * math.sin(lng / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * pi) + 300.0 * math.sin(lng / 30.0 * pi)) * 2.0 / 3.0
    return ret

def gcj02_to_wgs84(lng, lat):
    if out_of_china(lng, lat):
        return lng, lat
    dlat = transformlat(lng - 105.0, lat - 35.0)
    dlng = transformlng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    mglat = lat + dlat
    mglng = lng + dlng
    return lng * 2 - mglng, lat * 2 - mglat

def convert_df(df, lon_col, lat_col):
    df['wgs84_lng'], df['wgs84_lat'] = zip(*df.apply(lambda row: gcj02_to_wgs84(row[lon_col], row[lat_col]), axis=1))
    return df

# Gaode Tile fetching
def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)

def tile_to_mercator(xtile, ytile, zoom):
    lat_deg, lon_deg = num2deg(xtile, ytile, zoom)
    x = lon_deg * 20037508.34 / 180
    y = math.log(math.tan(math.pi/4 + math.radians(lat_deg)/2)) * 20037508.34 / math.pi
    return x, y

def fetch_gaode_tiles(min_lon, max_lon, min_lat, max_lat, zoom):
    min_x, min_y = deg2num(max_lat, min_lon, zoom)
    max_x, max_y = deg2num(min_lat, max_lon, zoom)
    print(f"Fetching Map tiles from x:{min_x}-{max_x}, y:{min_y}-{max_y} at zoom {zoom}")
    img_w = (max_x - min_x + 1) * 256
    img_h = (max_y - min_y + 1) * 256
    out_img = Image.new('RGB', (img_w, img_h))
    headers = {'User-Agent': 'Mozilla/5.0'}
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            url = f"https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={zoom}"
            try:
                resp = requests.get(url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    tile_img = Image.open(io.BytesIO(resp.content)).convert('RGB')
                    out_img.paste(tile_img, ((x - min_x) * 256, (y - min_y) * 256))
            except:
                pass
    left, top = tile_to_mercator(min_x, min_y, zoom)
    right, bottom = tile_to_mercator(max_x + 1, max_y + 1, zoom)
    return np.array(out_img), [left, right, bottom, top]

# Load Data
out_dir = r"D:\多元大数据分析\03_图表输出_V22_05R"
data_dir = r"D:\多元大数据分析\01_早期单源分析_归档"
anchor_path = r"D:\多元大数据分析\02_多源融合数据及核心脚本\V30_Multi_Source_Fusion_R2\anchor_index_v22_04R2.csv"
ctrip_path = r"D:\多元大数据分析\00_原始基座数据\携程经纬度.csv"

anchor_df = pd.read_csv(anchor_path)
try:
    ctrip_df = pd.read_csv(ctrip_path, encoding='utf-8-sig')
except:
    ctrip_df = pd.read_csv(ctrip_path, encoding='gbk')

lon_col = ctrip_df.columns[1]
lat_col = ctrip_df.columns[2]
ctrip_df['wgs84_lng'] = ctrip_df[lon_col]
ctrip_df['wgs84_lat'] = ctrip_df[lat_col]

anchor_df['wgs84_lng'] = anchor_df['lng']
anchor_df['wgs84_lat'] = anchor_df['lat']

crs_wgs84 = "EPSG:4326"
crs_projected = "EPSG:3857"

# ONLY CTRIP
supply_all = ctrip_df[['wgs84_lng', 'wgs84_lat']].dropna()
supply_gdf = gpd.GeoDataFrame(supply_all, geometry=gpd.points_from_xy(supply_all.wgs84_lng, supply_all.wgs84_lat), crs=crs_wgs84)
supply_gdf_proj = supply_gdf.to_crs(crs_projected)

anchors_gdf = gpd.GeoDataFrame(anchor_df, geometry=gpd.points_from_xy(anchor_df.wgs84_lng, anchor_df.wgs84_lat), crs=crs_wgs84)
anchors_gdf_proj = anchors_gdf.to_crs(crs_projected)

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

def plot_ctrip_map(ax_A, bounds_deg, is_zoom=False):
    min_lon, max_lon, min_lat, max_lat = bounds_deg
    zoom_level = 14 if is_zoom else 12
    
    img, extent = fetch_gaode_tiles(min_lon, max_lon, min_lat, max_lat, zoom_level)
    ax_A.imshow(img, extent=extent, zorder=0, alpha=0.85)
    
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    minx, miny = transformer.transform(min_lon, min_lat)
    maxx, maxy = transformer.transform(max_lon, max_lat)
    
    x = supply_gdf_proj.geometry.x
    y = supply_gdf_proj.geometry.y
    
    # Use hexbin for density, but specifically tailored to Ctrip color (maybe Purple/OrRd)
    hb = ax_A.hexbin(x, y, gridsize=100 if is_zoom else 250, extent=(minx, maxx, miny, maxy), visible=False)
    counts = hb.get_array()
    log_counts = np.log1p(counts)
    vmax_val = np.percentile(log_counts[log_counts > 0], 95) if len(log_counts[log_counts > 0]) > 0 else 1
    
    hb2 = ax_A.hexbin(x, y, gridsize=100 if is_zoom else 250, extent=(minx, maxx, miny, maxy), 
                      cmap='Purples', alpha=0.75, edgecolors='none', 
                      reduce_C_function=lambda vals: np.log1p(len(vals)), zorder=3)
    hb2.set_clim(vmin=0, vmax=vmax_val)
    
    ax_A.set_xlim(minx, maxx)
    ax_A.set_ylim(miny, maxy)
    
    from mpl_toolkits.axes_grid1.inset_locator import inset_axes
    cax = inset_axes(ax_A, width="30%", height="3%", loc='lower right', borderpad=2)
    cb = plt.colorbar(hb2, cax=cax, orientation='horizontal')
    cb.set_label('log(1+携程住宿设施数)', fontsize=10, weight='bold')
    cax.xaxis.set_ticks_position('top')
    cax.xaxis.set_label_position('top')
    
    ax_A.scatter(anchors_gdf_proj.geometry.x, anchors_gdf_proj.geometry.y, s=40, color='white', edgecolor='black', linewidth=1, zorder=5, label='核心文旅锚点')
    
    ax_A.legend(loc='lower left', frameon=True, facecolor='white', framealpha=0.85, edgecolor='black', fontsize=11)
    
    texts_A = []
    key_anchors_A = ['中央大街', '圣索菲亚教堂', '防洪纪念塔', '冰雪大世界', '太阳岛', '哈尔滨站', '哈西站', '伏尔加庄园']
    for idx, row in anchors_gdf_proj.iterrows():
        if row['anchor_name'] in key_anchors_A:
            if minx <= row.geometry.x <= maxx and miny <= row.geometry.y <= maxy:
                texts_A.append(ax_A.text(row.geometry.x, row.geometry.y, row['anchor_name'], fontsize=11, fontweight='bold',
                                         bbox=dict(facecolor='white', alpha=0.75, edgecolor='black', pad=1), zorder=6))
    
    adjust_text(texts_A, ax=ax_A, force_text=0.1, arrowprops=None)
    
    title = "携程住宿空间设施分布图"
    if is_zoom:
        title += " (主城区放大)"
    ax_A.set_title(title, fontsize=16, pad=15)
    ax_A.axis('off')
    
    ax_A.text(0.02, 0.95, 'Coordinate System: GCJ-02 (Pseudo Web Mercator)\nBasemap: Amap (高德)\nData: Ctrip Only', 
              transform=ax_A.transAxes, fontsize=8, color='black', zorder=10,
              bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1))

# Layout adjustment
fig_A_full, ax_A_full = plt.subplots(figsize=(12, 7.5), dpi=300)
plot_ctrip_map(ax_A_full, (126.48, 126.95, 45.64, 45.84), is_zoom=False)
fig_A_full.tight_layout()
fig_A_full.savefig(os.path.join(out_dir, "fig_gis_ctrip_supply_full.png"), dpi=300)
plt.close(fig_A_full)

fig_A_core, ax_A_core = plt.subplots(figsize=(10, 7), dpi=300)
plot_ctrip_map(ax_A_core, (126.52, 126.72, 45.72, 45.82), is_zoom=True)
fig_A_core.tight_layout()
fig_A_core.savefig(os.path.join(out_dir, "fig_gis_ctrip_supply_core.png"), dpi=300)
plt.close(fig_A_core)

print("Done Ctrip Map!")
