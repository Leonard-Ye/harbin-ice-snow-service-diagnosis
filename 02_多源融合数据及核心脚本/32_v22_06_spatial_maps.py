import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as cx
from adjustText import adjust_text
import os

# Set output directory
out_dir = r"D:\多元大数据分析\03_图表输出_V22_05R"
if not os.path.exists(out_dir):
    os.makedirs(out_dir)

# Set fonts for Chinese
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

# Load data
print("Loading data...")
anchors_df = pd.read_csv(r"D:\多元大数据分析\02_多源融合数据及核心脚本\V30_Multi_Source_Fusion_R2\anchor_index_v22_04R2.csv")

poi_dir = r"D:\多元大数据分析\01_早期单源分析_归档"
dining_df = pd.read_csv(os.path.join(poi_dir, "amap_餐饮服务.csv"))
transport_df = pd.read_csv(os.path.join(poi_dir, "amap_交通设施服务.csv"))
public_df = pd.read_csv(os.path.join(poi_dir, "amap_公共设施.csv"))

# Convert to GeoDataFrames
anchors_gdf = gpd.GeoDataFrame(anchors_df, geometry=gpd.points_from_xy(anchors_df.lng, anchors_df.lat), crs="EPSG:4326")
dining_gdf = gpd.GeoDataFrame(dining_df, geometry=gpd.points_from_xy(dining_df.lon, dining_df.lat), crs="EPSG:4326")
transport_gdf = gpd.GeoDataFrame(transport_df, geometry=gpd.points_from_xy(transport_df.lon, transport_df.lat), crs="EPSG:4326")
public_gdf = gpd.GeoDataFrame(public_df, geometry=gpd.points_from_xy(public_df.lon, public_df.lat), crs="EPSG:4326")

# Convert to Web Mercator (EPSG:3857) for Contextily and accurate buffer distances in meters
anchors_gdf_3857 = anchors_gdf.to_crs(epsg=3857)
dining_gdf_3857 = dining_gdf.to_crs(epsg=3857)
transport_gdf_3857 = transport_gdf.to_crs(epsg=3857)
public_gdf_3857 = public_gdf.to_crs(epsg=3857)

# Calculate bounds
minx, miny, maxx, maxy = anchors_gdf_3857.total_bounds
padding = 10000 # 10km padding


# --- Map 1: POI Spatial Distribution ---
print("Generating Map 1...")
fig1, ax1 = plt.subplots(figsize=(14, 12))

# Plot POIs
dining_gdf_3857.plot(ax=ax1, color='#FFA07A', markersize=0.5, alpha=0.3, label='餐饮服务')
transport_gdf_3857.plot(ax=ax1, color='#20B2AA', markersize=0.5, alpha=0.3, label='交通设施')
public_gdf_3857.plot(ax=ax1, color='#9370DB', markersize=0.5, alpha=0.3, label='公共设施')

# Plot Anchors
anchors_gdf_3857.plot(ax=ax1, color='red', marker='*', markersize=150, edgecolor='black', zorder=5, label='核心文旅锚点')

# Add Basemap
cx.add_basemap(ax1, crs=anchors_gdf_3857.crs.to_string(), source=cx.providers.CartoDB.Positron)

# Customize
ax1.set_title("图1：哈尔滨主城区高德设施 POI 与核心文旅锚点空间分布", fontsize=18, pad=15)
ax1.axis('off')
ax1.legend(loc='upper right', markerscale=20, fontsize=12)

# Set bounds slightly zoomed in
ax1.set_xlim(minx - padding, maxx + padding)
ax1.set_ylim(miny - padding, maxy + padding)

plt.tight_layout()
fig1.savefig(os.path.join(out_dir, 'spatial_poi_distribution_map.png'), dpi=300)
plt.close(fig1)


# --- Map 2: Mismatch Diagnosis ---
print("Generating Map 2...")
fig2, ax2 = plt.subplots(figsize=(14, 12))

# Calculate DHI mapping for size (ensure no negative sizes)
min_dhi = anchors_gdf_3857['DHI'].min()
dhi_shifted = anchors_gdf_3857['DHI'] - min_dhi + 0.5  # shift to strictly positive
sizes = dhi_shifted * 500  # Scaling factor

# Plot anchors with size=DHI and color=SMI
scatter = ax2.scatter(
    anchors_gdf_3857.geometry.x, anchors_gdf_3857.geometry.y,
    s=sizes, c=anchors_gdf_3857['SMI'], cmap='coolwarm',
    alpha=0.8, edgecolors='black', linewidth=1, zorder=4
)

# Colorbar
cbar = plt.colorbar(scatter, ax=ax2, shrink=0.7)
cbar.set_label('SMI 服务错配指数 (蓝: 低错配, 红: 高错配)', fontsize=12)

# Highlight buffers (3km = 3000m)
target_anchors = ['防洪纪念塔', '冰雪大世界', '伏尔加庄园', '松花江', '哈药六厂']
for idx, row in anchors_gdf_3857.iterrows():
    if row['anchor_name'] in target_anchors:
        # Create a circle patch in meters
        circle = plt.Circle((row.geometry.x, row.geometry.y), 3000, 
                            color='red', fill=False, linestyle='--', linewidth=1.5, zorder=3, alpha=0.7)
        ax2.add_patch(circle)

# Labels
texts = []
for idx, row in anchors_gdf_3857.iterrows():
    # Format top 5 slightly differently
    if row['mismatch_rank'] <= 5:
        txt = f"{row['anchor_name']}\n(Top {int(row['mismatch_rank'])})"
        texts.append(ax2.text(row.geometry.x, row.geometry.y, txt, 
                              fontsize=11, fontweight='bold', color='darkred',
                              bbox=dict(facecolor='white', alpha=0.7, edgecolor='red', boxstyle='round,pad=0.2')))
    else:
        texts.append(ax2.text(row.geometry.x, row.geometry.y, row['anchor_name'], 
                              fontsize=9, color='black'))

# Adjust text positions to avoid overlaps
adjust_text(texts, ax=ax2, force_text=0.5, arrowprops=dict(arrowstyle='-', color='gray', lw=0.5))

# Add Basemap
cx.add_basemap(ax2, crs=anchors_gdf_3857.crs.to_string(), source=cx.providers.CartoDB.Positron)

# Legend for bubble size (DHI)
# Create proxy artists for size legend
import matplotlib.lines as mlines
l1 = ax2.scatter([],[], s=0.5 * 500, c='gray', alpha=0.5, edgecolors='black')
l2 = ax2.scatter([],[], s=2.0 * 500, c='gray', alpha=0.5, edgecolors='black')
l3 = ax2.scatter([],[], s=4.0 * 500, c='gray', alpha=0.5, edgecolors='black')
labels = ["DHI 低热度", "DHI 中热度", "DHI 高热度"]
ax2.legend([l1, l2, l3], labels, title="圆圈大小 = 需求热度 (DHI)", loc='upper left', frameon=True, fontsize=10)

ax2.set_title("图2：核心文旅锚点服务错配空间诊断图 (3km缓冲圈)", fontsize=18, pad=15)
ax2.axis('off')

# Set bounds slightly zoomed in
ax2.set_xlim(minx - padding, maxx + padding)
ax2.set_ylim(miny - padding, maxy + padding)

plt.tight_layout()
fig2.savefig(os.path.join(out_dir, 'spatial_mismatch_diagnosis_map.png'), dpi=300)
plt.close(fig2)
print("Done!")
