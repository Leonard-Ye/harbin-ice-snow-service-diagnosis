# 智能多源数据自动化与分析平台 · 架构说明

## 1. 架构演进路线

```text
单脚本 research script           模块化 OOP                 Web 服务化
analysis/30_*.py            →    src/{cleaning,pipeline,  →   src/api/ (FastAPI)
                                  engines,detectors,storage}
                                         ↓
                                  Streamlit Dashboard（API 优先 + 本地降级）
                                         ↓
                                  Docker 多阶段镜像 + Compose 编排 + GitHub CI
```

核心叙事不是“把 CSV 包一层接口”，而是把
`原始多源数据 → 清洗 → 锚点对齐 → 空间聚合 → 异常审计 → 指标计算 → 报表输出`
抽取为**可复现、可追溯、可容器化交付**的自动化 Pipeline。

## 2. 分层结构

| 层 | 组件 | 说明 |
|---|---|---|
| 表现层 | `dashboard/app.py` | Streamlit 5 页签；设置 `BACKEND_URL` 走 API，未设置自动本地引擎 |
| API 层 | `src/api/` | FastAPI + Pydantic V2 + OpenAPI；计算型路由使用同步 `def`（线程池），仅 AI 流式等 I/O 场景使用 async |
| 业务层 | `src/cleaning/`、`src/pipeline/`、`src/engines/`、`src/detectors/` | 清洗、锚点对齐、BallTree 缓冲聚合、需求/痛点/餐饮压力、五指标、质量审计 |
| 服务层 | `src/services/table_audit.py` | 通用单表质量体检，API 与 Streamlit 复用同一实现 |
| 存储层 | `src/storage/run_store.py` | SQLite + WAL；pipeline_run / artifact / metric_snapshot / anomaly_event |
| 部署层 | `docker/Dockerfile`、`docker-compose.yml` | 一个基础镜像两个 target（backend/frontend）；named volume 存运行数据 |

## 3. 数据流

```text
xhs / dianping / amap / ctrip
        │  DataCleaner（文本规整）
        ▼
AnchorAligner（白名单 + 别名 + 剔除规则）
        │
        ├── excluded_terms_v22_04R2.csv
        └── anchor_master_v22_04R2.csv
                │
                ▼
BufferAggregator（BallTree haversine，1/3/5km）
        │
        ▼
RiskCalculator（XHS 需求痛点 + 大众点评压力）
        │
        ▼
V30 底表（scale_sensitivity / base_3km）
        ├── AnomalyDetector → data_quality_audit_v22_04R2.csv
        └── MetricsEngine → anchor_index_v22_04R2.csv
                │
                ▼
RunStore（run_id / 输入输出 SHA256 / 指标快照 / 异常事件）
```

等权模式与 `analysis/30_multi_source_fusion_v22_04R2.py` 基线逐值一致；
全量数值回归脚本：`scripts/verify_v30_regression.py`（误差 < 1e-9）。

## 4. REST API

Base URL：`http://localhost:8000`；交互文档：`/docs`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 数据文件 / SQLite / 原始数据可用性探针 |
| GET | `/api/v1/meta/anchors` | 20 锚点基础信息 |
| GET | `/api/v1/anchors` | 锚点指标列表（排序/限制） |
| GET | `/api/v1/anchors/{name}` | 单锚点指标 + 痛点 + 策略 |
| GET | `/api/v1/dataset/full` | Dashboard 完整合并表 |
| POST | `/api/v1/metrics/calculate` | 动态计算（等权/熵权、1/3/5km） |
| GET | `/api/v1/metrics/trend` | 多尺度供给趋势 |
| GET | `/api/v1/quality/audit` | IQR/Z-score 审计 |
| POST | `/api/v1/pipeline/run` | 提交 Pipeline Job（202 + 轮询） |
| GET | `/api/v1/pipeline/runs` | 运行历史 |
| GET | `/api/v1/pipeline/runs/{id}` | 单次运行状态与产物 |
| POST | `/api/v1/ingest` | 通用表格质量体检（CSV/XLSX） |
| GET | `/api/v1/reports/{excel\|pdf\|html}` | 报表下载 |
| POST | `/api/v1/ai/diagnose` | AI 诊断（P5 预留，当前 501） |

错误契约统一为 `{"code", "message", "detail"}`。
原始数据缺失时 Pipeline 返回 `503 / RAW_DATA_UNAVAILABLE`，不抛裸文件异常。

## 5. 关键设计决策

1. **Parity first**：DataCleaner/AnchorAligner/BufferAggregator/RiskCalculator 均从原脚本抽取，
   默认 parity 口径，增强清洗需显式开启。
2. **同步 `def` 跑计算**：Pandas/BallTree/SQLite 是阻塞型工作，交给 FastAPI 线程池；
   避免 `async def` 阻塞事件循环。
3. **单飞 Job 队列**：进程内单 Worker 顺序执行 Pipeline，防止并发写同一批 V30 产物；
   不引入 Celery/Redis。
4. **SQLite 而非 Postgres**：当前为 20 锚点聚合数据，SQLite 足够；线程内独立连接 + WAL
   保证线程池安全，未来可替换 Repository 实现。
5. **API 优先但默认本地**：Streamlit 仅在显式 `BACKEND_URL` 时探测 API；
   Streamlit Cloud 无后端时保持原体验。
6. **镜像不含原始数据**：Dockerfile 只复制 V30 聚合结果；全量 Pipeline 需在本地
   具备原始数据的机器运行。
7. **容器 CJK 字体**：Noto CJK 用于 Matplotlib 渲染，WQY ZenHei 用于 ReportLab PDF，
   避免容器内中文方框。

## 6. 测试策略

| 层级 | 文件 | 说明 |
|---|---|---|
| 单元 | `tests/test_data_cleaner.py` | 清洗口径 |
| 单元 | `tests/test_run_store.py` | SQLite 持久化 |
| 集成 | `tests/test_pipeline.py` | 合成四源样本全链路冒烟（无需原始数据） |
| 回归 | `tests/test_metrics_engine.py` | 等权输出与 V30 基线 < 1e-9 |
| API | `tests/test_api_endpoints.py` | FastAPI TestClient 14 个端点 |
| UI | `tests/test_dashboard_app.py` | Streamlit AppTest + 静态契约 |
| 私有 | `scripts/verify_v30_regression.py` | 本地全量原始数据逐文件比对 |

当前 70 个 collected tests；CI 为 GitHub Actions（Python 3.11 + pytest + 双镜像构建）。

## 7. 范围边界（面试口径）

- 本平台是**离线历史快照的可复现自动化分析平台**，不是实时监控/流式系统；
- 通用 `/ingest` 只做数据质量体检，不计算文旅领域指标；
- AI 诊断接口为预留契约，P5 实现前不写入能力声明；
- 数据规模口径：8 万+ 条原始记录，融合为 20 个核心锚点。
