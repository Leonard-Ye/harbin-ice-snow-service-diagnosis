import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import contextily as cx
from adjustText import adjust_text
import os

out_dir = r"D:\多元大数据分析\outputs"
anchor_path = r"D:\多元大数据分析\analysis\V30_Multi_Source_Fusion_R2\anchor_index_v22_04R2.csv"

anchor_df = pd.read_csv(anchor_path)
# In anchor_df, lng/lat are from Amap API (GCJ-02). We treat them directly as EPSG:4326 to project to Web Mercator.
# This pseudo-Web Mercator will exactly match GaoDe's tile system.
anchor_df['gcj02_lng'] = anchor_df['lng']
anchor_df['gcj02_lat'] = anchor_df['lat']

crs_pseudo_wgs84 = "EPSG:4326"
crs_projected = "EPSG:3857"

anchors_gdf = gpd.GeoDataFrame(anchor_df, geometry=gpd.points_from_xy(anchor_df.gcj02_lng, anchor_df.gcj02_lat), crs=crs_pseudo_wgs84)
anchors_gdf_proj = anchors_gdf.to_crs(crs_projected)
anchors_gdf_proj['smi_rank'] = anchors_gdf_proj['SMI'].rank(ascending=False)

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

gaode_tiles = "https://wprd01.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=7"

def plot_smi_map(ax_B, bounds, is_zoom=False):
    minx, maxx, miny, maxy = bounds
    
    # Safe zoom levels
    zoom_level = 14 if is_zoom else 12
    
    # Add GaoDe map (highly detailed, fast, matches GCJ-02 perfectly)
    cx.add_basemap(ax_B, crs=crs_projected, source=gaode_tiles, zoom=zoom_level, alpha=0.7)
    
    top5_names = anchors_gdf_proj[anchors_gdf_proj['smi_rank'] <= 5]['anchor_name'].tolist()
    
    norm = TwoSlopeNorm(vcenter=0, vmin=anchors_gdf_proj['SMI'].min(), vmax=anchors_gdf_proj['SMI'].max())
    dhi_min = anchors_gdf_proj['DHI'].min()
    dhi_max = anchors_gdf_proj['DHI'].max()
    sizes = 60 + (anchors_gdf_proj['DHI'] - dhi_min) / (dhi_max - dhi_min) * (350 - 60)
    
    non_top5 = anchors_gdf_proj[anchors_gdf_proj['smi_rank'] > 5]
    non_top5_sizes = sizes[anchors_gdf_proj['smi_rank'] > 5]
    ax_B.scatter(
        non_top5.geometry.x, non_top5.geometry.y,
        s=non_top5_sizes, c=non_top5['SMI'], cmap='RdBu_r', norm=norm,
        alpha=0.9, edgecolors='black', linewidth=0.8, zorder=4
    )
    
    top5 = anchors_gdf_proj[anchors_gdf_proj['smi_rank'] <= 5]
    top5_sizes = sizes[anchors_gdf_proj['smi_rank'] <= 5]
    scatter = ax_B.scatter(
        top5.geometry.x, top5.geometry.y,
        s=top5_sizes, c=top5['SMI'], cmap='RdBu_r', norm=norm,
        alpha=1.0, edgecolors='black', linewidth=2, zorder=5
    )
    
    cbar = plt.colorbar(scatter, ax=ax_B, shrink=0.6, pad=0.02, aspect=30)
    cbar.set_label('SMI 服务错配指数', fontsize=12)
    
    texts_B = []
    key_anchors_B = list(set(top5_names + ['中央大街', '圣索菲亚教堂', '冰雪大世界', '哈尔滨站', '哈西站', '防洪纪念塔', '伏尔加庄园']))
    for idx, row in anchors_gdf_proj.iterrows():
        if row['anchor_name'] in key_anchors_B:
            if minx <= row.geometry.x <= maxx and miny <= row.geometry.y <= maxy:
                fontweight = 'bold' if row['anchor_name'] in top5_names else 'normal'
                texts_B.append(ax_B.text(row.geometry.x, row.geometry.y, row['anchor_name'], 
                                        fontsize=11 if is_zoom else 9, fontweight=fontweight,
                                        bbox=dict(facecolor='white', alpha=0.85, edgecolor='black', boxstyle='round,pad=0.2', linewidth=0.5), zorder=6))
                
    adjust_text(texts_B, ax=ax_B, force_text=0.2, arrowprops=None)
    
    ax_B.set_xlim(minx, maxx)
    ax_B.set_ylim(miny, maxy)
    
    import matplotlib.lines as mlines
    l1 = ax_B.scatter([],[], s=60, c='gray', alpha=0.5, edgecolors='black', linewidth=0.5)
    l2 = ax_B.scatter([],[], s=60 + (350-60)*0.5, c='gray', alpha=0.5, edgecolors='black', linewidth=0.5)
    l3 = ax_B.scatter([],[], s=350, c='gray', alpha=0.5, edgecolors='black', linewidth=0.5)
    l5 = mlines.Line2D([], [], color='black', marker='o', linestyle='None', markersize=6, label='普通锚点', markeredgewidth=0.8, markerfacecolor='gray')
    l6 = mlines.Line2D([], [], color='black', marker='o', markerfacecolor='gray', markeredgewidth=2, linestyle='None', markersize=9, label='SMI Top 5')
    
    ax_B.legend([l1, l2, l3, l5, l6], 
                ["低热度", "中热度", "高热度", "普通锚点", "SMI Top 5 锚点"], 
                title="DHI 需求热度与锚点", loc='center left', bbox_to_anchor=(1.15, 0.5), frameon=False, fontsize=11)
    
    title = "图 X 核心文旅锚点服务错配空间诊断图"
    if is_zoom:
        title += " (主城区放大)"
    ax_B.set_title(title, fontsize=16, pad=15)
    ax_B.axis('off')
    
    ax_B.text(0.02, 0.02, 'Coordinate System: GCJ-02 (Pseudo Web Mercator)\nBasemap: Amap (高德)', 
              transform=ax_B.transAxes, fontsize=8, color='black', zorder=10,
              bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1))

bounds_full = gpd.GeoDataFrame(geometry=[gpd.points_from_xy([126.48, 126.95], [45.64, 45.84])[0], gpd.points_from_xy([126.48, 126.95], [45.64, 45.84])[1]], crs=crs_pseudo_wgs84).to_crs(crs_projected)
bounds_full_tuple = (bounds_full.geometry.x[0], bounds_full.geometry.x[1], bounds_full.geometry.y[0], bounds_full.geometry.y[1])

fig_B_full, ax_B_full = plt.subplots(figsize=(14, 9), dpi=300)
plot_smi_map(ax_B_full, bounds_full_tuple, is_zoom=False)
fig_B_full.tight_layout(rect=[0, 0, 0.82, 1])
fig_B_full.savefig(os.path.join(out_dir, "fig_gis_B_smi_full.png"), dpi=300)
fig_B_full.savefig(os.path.join(out_dir, "fig_gis_B_smi_full.svg"), dpi=300)
plt.close(fig_B_full)

bounds_core = gpd.GeoDataFrame(geometry=[gpd.points_from_xy([126.52, 126.72], [45.72, 45.82])[0], gpd.points_from_xy([126.52, 126.72], [45.72, 45.82])[1]], crs=crs_pseudo_wgs84).to_crs(crs_projected)
bounds_core_tuple = (bounds_core.geometry.x[0], bounds_core.geometry.x[1], bounds_core.geometry.y[0], bounds_core.geometry.y[1])

fig_B_core, ax_B_core = plt.subplots(figsize=(14, 9), dpi=300)
plot_smi_map(ax_B_core, bounds_core_tuple, is_zoom=True)
fig_B_core.tight_layout(rect=[0, 0, 0.82, 1])
fig_B_core.savefig(os.path.join(out_dir, "fig_gis_B_smi_core.png"), dpi=300)
fig_B_core.savefig(os.path.join(out_dir, "fig_gis_B_smi_core.svg"), dpi=300)
plt.close(fig_B_core)

print("Done generating GaoDe GIS maps for B!")
