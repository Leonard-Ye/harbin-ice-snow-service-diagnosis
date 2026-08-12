# 基于多源异构数据的哈尔滨冰雪经济服务设施优化研究

大一年度项目结题作品 · 多源异构数据融合 · 空间供需错配诊断

## 一句话简介

基于 4 类异构数据源（**高德 POI / 携程住宿 / 大众点评餐饮评论 / 小红书舆情**，累计 8 万+ 条记录），通过 **POI 锚点对齐**统一多源空间参照系，自研 5 项综合指标（**DHI / SSI / ERI / ERI_plus / SMI**），对哈尔滨冰雪旅游 **20 个核心文旅锚点**进行供需错配空间诊断，输出分区分类的服务设施优化策略。

## 数据来源

| 数据源 | 规模 | 功能定位 | 空间形态 |
|---|---|---|---|
| 高德 POI | 5.8 万+ 设施点位 | 客观服务供给底座（餐饮/交通/公共/住宿等） | 经纬度点位 |
| 携程住宿 | 5,871 条住宿点位 | 游客可见的住宿供给 | 经纬度+档次 |
| 大众点评 | 7,000 条评论（6,307 条入样） | 餐饮消费价格/排队压力增强验证 | 商圈文本 |
| 小红书 | 3,261 笔记 + 11,793 评论 → 13,109 条结构化文本 → 1,208 条打卡笔记 | 需求热度 + 体验痛点 | 地点词文本 |

## 方法路线

```
单源画像（四类数据分别刻画供给/住宿/餐饮/舆情）
   → POI 锚点对齐（地点词 → 高德地理编码 → 人工白名单复核 → 核心锚点归并）
   → 多尺度缓冲圈统计（1km / 3km / 5km，主分析 3km）
   → 指数诊断（DHI / SSI / ERI / ERI_plus / SMI）
   → 分区分类优化策略（设施不足型 / 高峰承载型 / 餐饮压力区 / 外围节点）
```

## 目录结构

```
├── analysis/        # 多源融合分析核心脚本（融合计算 / 图表 / GIS 制图）
├── dashboard/       # Streamlit 交互看板（app + 数据层 + 主题 + PDF 报告）
├── outputs/         # 核心诊断图（SMI 排名 / 供需象限 / GIS 空间分布等）
├── docs/            # 项目报告 / 简历描述 / 审查文档
├── src/             # 工程化模块（MetricsEngine 指标引擎 / AnomalyDetector 异常检测）
├── tests/           # pytest 单元测试（44 用例）
├── .streamlit/      # Streamlit 原生主题配置
├── README.md
└── requirements*.txt
```

## 快速开始（核心可复现链）

```powershell
pip install -r requirements.txt
cd analysis
python 30_multi_source_fusion_v22_04R2.py   # 融合计算 → V30_Multi_Source_Fusion_R2/*.csv
python 31_v22_05_chart_generator.py         # 生成 8 张核心诊断图 → ../outputs/
```

运行单元测试：

```powershell
pip install -r requirements-dev.txt
python -m pytest tests/
```

> **数据合规说明**：仓库**不包含**平台原始评论、笔记与 POI 原始抓取文件（版权与隐私原因）。
> 运行 `30` 需要以下本地文件（未入库，可向作者索取或按结构重建）：
> - `00_原始基座数据/携程经纬度.csv`
> - `analysis/V25_Full_Mapping/*.csv`（多源→锚点全量映射）
> - `analysis/V27_Amap_Expansion/amap_poi_master_unlimited.csv`（高德 POI 扩展抓取）
>
> `V30_Multi_Source_Fusion_R2/` 下的**聚合结果 CSV 已入库**，可直接用于 `31` 图表生成与下游展示，无需原始数据。

## 工程化模块（src/）

将科研脚本中的核心逻辑重构为可配置、可测试的 OOP 模块：

| 模块 | 职责 | 关键能力 |
|---|---|---|
| `src/engines/metrics_engine.py` | `MetricsEngine` 供需诊断指标引擎 | 五指标计算（log1p+Z-score）；**权重方案可切换**：等权（equal，与 30 脚本基线逐值一致）或**熵权法**（entropy，按 20 锚点样本离散度客观赋权）；缓冲半径/指标权重/SMI 合成系数均可配置 |
| `src/detectors/anomaly_detector.py` | `AnomalyDetector` 数据质量与异常检测 | IQR / Z-score 离群检测（右偏列支持 log1p 变换避免漏检）、经纬度极值校验、一键 `quality_report()` 数据质量审计表 |

`dashboard_data.py` 内部改调 `MetricsEngine`，对外列结构不变（App 层零破坏）。审计结果：`data_quality_audit_v22_04R2.csv`（12 列审计，7 列检出离群——伏尔加庄园在六类供给上均为离群低值，果戈里大街排队率离群高值）。

## 交互式 Dashboard

基于 V30 聚合数据的 Streamlit 单页应用（4 页签：总览地图 / 指标筛选 / 单锚点诊断 / 数据质量），支持**权重方案切换（等权/熵权）**与**一键导出 Excel / HTML / PDF 诊断报告**，数据不含原始评论，可直接公开部署：

```powershell
pip install -r requirements.txt
streamlit run dashboard/app.py
```

详见 `dashboard/README.md`（含 Streamlit Cloud 免费部署步骤）。

## 可选：GIS 制图

`32_v22_06_spatial_maps.py` / `36` / `41` / `42` 生成报告中的 GIS 空间分布图（高德瓦片底图 + 锚点叠加）。

```powershell
pip install -r requirements-gis.txt   # geopandas / contextily / pyproj / Pillow
```

这些脚本需要**联网获取地图瓦片**，且部分依赖本地未入库的 POI 分类 CSV（`amap_餐饮服务.csv` 等，位于 `01_早期单源分析_归档/`）。

## 指标定义

所有指标均针对 **20 个核心锚点**做样本内相对比较（非绝对水平）。指标内部权重支持两种方案（Dashboard 侧边栏可切换）：

- **等权（equal）**：与结题报告口径逐值一致，用于数值回归验证。
- **熵权法（entropy）**：min-max 归一化 → 信息熵 → 差异系数 → 权重；离散度大（信息量大）的维度权重更高，常数列权重为 0。

| 指标 | 含义 | 计算要点 |
|---|---|---|
| DHI | 需求热度 | 小红书提及频次 → log1p → Z-score |
| SSI | 服务供给 | 锚点周边 3km 六类设施数量（住宿/餐饮/交通/公共/购物/医疗）→ log1p → Z-score → 按权重合成 |
| ERI | 体验风险 | 负面情绪占比 + 交通/排队/防寒/价格四类**痛点触发率**（非原始频次，避免热度放大风险）→ Z-score → 按权重合成 |
| ERI_plus | 餐饮压力增强 | ERI + 大众点评价格/排队/服务负向压力，仅作核心餐饮锚点验证，不参与 SMI 主排名 |
| SMI | 服务错配 | 需求与风险为正项、供给为缓解项（系数可配置，默认 z(DHI)+z(ERI)−z(SSI)） |

## 核心产出

- **指标与诊断结果**：`analysis/V30_Multi_Source_Fusion_R2/`（含 `data_quality_audit_v22_04R2.csv` 数据质量审计）
- **工程化模块与测试**：`src/`（MetricsEngine / AnomalyDetector）、`tests/`（15 个 pytest 用例）
- **核心诊断图**：`outputs/`（SMI 排名、供需象限、痛点热力图、GIS 分布图、多尺度敏感性）
- **方法审计**：`analysis/V22_method_audit_report.md`（数据分级 A/B/F、双层使用架构、因果规避声明）
- **结题报告**：`前中后期文档汇总/0624基于多元大数据的哈尔滨冰雪经济服务设施优化策略研究.docx`（docx 未入库）

## 关联工程

- `xiaohongshu_scraper/`：小红书数据采集工程（独立 CLI + pytest 测试套件，含断点续采、去重、质量看板）。

## 已知事项（诚实声明）

1. **SSI 口径**：代码（MetricsEngine）显式纳入六类设施（含购物、医疗）且权重可配置；结题报告正文表述为四类主类——报告文本待统一（指标结果未变）。
2. 用当前 seaborn 版本重跑 `31` 时，`supply_demand_quadrant.png` 布局与报告版本存在细微差异（库版本所致）。
3. 大众点评入样样本为"评分 ≥ 3.5 且经营 ≥ 3 年"子集，存在幸存者偏差，因此仅作为**压力验证层**而非全域供给主来源。
4. 20 个核心锚点由人工白名单复核产出（见 `30` 脚本 `WHITELIST_ANCHORS` / `ALIAS_MAP`），2 个高频打卡 POI 因坐标异常被剔除。
5. 数据采集时间口径：携程 2024-11 至 2025-02 运营数据；高德/大众点评/小红书采集时间未在报告正文统一交代。
